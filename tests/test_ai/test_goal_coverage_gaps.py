"""Behavior tests closing coverage gaps in small goal modules.

Each test asserts the goal's observable contract (value / is_satisfied /
desired_state / relevant_actions), never just line execution.
"""

from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai.fixtures import make_state

# --- DiscardOverstockGoal -------------------------------------------------

class TestDiscardOverstockGaps:
    def _gd(self) -> GameData:
        gd = GameData()
        gd._item_stats = {"sap": ItemStats(code="sap", level=1, type_="resource")}
        gd._crafting_recipes = {"potion": {"sap": 1}}
        return gd

    def test_desired_state_flags_overstock_cleared(self):
        goal = DiscardOverstockGoal(game_data=self._gd())
        state = make_state(inventory={"sap": 50})
        assert goal.desired_state(state, self._gd()) == {
            "inventory_overstock_cleared": True
        }

    def test_max_depth_high_enough_for_many_items(self):
        """One Delete/Sell per overstocked item — depth must exceed the
        default 15 or large overstock yields plan_len=0."""
        assert DiscardOverstockGoal(game_data=self._gd()).max_depth == 64

    def test_relevant_actions_empty_when_no_overstock(self):
        goal = DiscardOverstockGoal(game_data=self._gd())
        state = make_state(inventory={"sap": 2})
        assert goal.relevant_actions([], state, self._gd()) == []

    def test_repr(self):
        assert repr(DiscardOverstockGoal(game_data=self._gd())) == "DiscardOverstock"


# --- ExpandBankGoal -------------------------------------------------------

class TestExpandBankGaps:
    def _gd(self, capacity=30, cost=1000) -> GameData:
        gd = GameData()
        gd._bank_capacity = capacity
        gd._next_expansion_cost = cost
        return gd

    def test_relevant_actions_is_expansion_only(self):
        """The buy action folds bank travel into its own cost/apply, so the
        expansion plan is single-step — no other action can contribute. With
        default all-actions relevance the h=0 planner had to exhaust every
        state cheaper than the gold-scaled buy cost (5 + dist + cost/100 —
        50+ once expansions cost thousands): live probe 2026-07-06 timed out
        the whole 10s cheap pass (1096 explored, 127K created, NO plan), so
        the bank could never expand once prices grew."""
        goal = ExpandBankGoal(bank_accessible=True, game_data=self._gd())
        state = make_state(gold=2000,
                           bank_items={f"i{i}": 1 for i in range(29)})
        buy = BuyBankExpansionAction(bank_location=(4, 1), accessible=True)
        others = [DepositAllAction(), OptimizeLoadoutAction(target_skill="mining")]
        relevant = goal.relevant_actions([*others, buy], state, self._gd())
        assert relevant == [buy]

    def test_value_zero_when_capacity_unknown(self):
        """value() reaches the capacity==0 guard: not satisfied (bank known
        and over the satisfied threshold) but game_data has no capacity."""
        gd = self._gd(capacity=0)
        # is_satisfied uses goal._game_data (capacity 30) -> not satisfied at 29;
        # value uses the passed game_data (capacity 0) -> guard returns 0.
        goal = ExpandBankGoal(bank_accessible=True, game_data=self._gd(capacity=30))
        state = make_state(gold=2000,
                           bank_items={f"i{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_fill_between_satisfied_and_trigger(self):
        """0.90 <= fill < 0.95 — not satisfied, but below the value trigger."""
        gd = self._gd(capacity=30, cost=1000)
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        # 28/30 = 0.933 -> not satisfied (>= 0.90) but fill < 0.95 -> value 0.
        state = make_state(gold=2000, bank_items={f"i{i}": 1 for i in range(28)})
        assert goal.is_satisfied(state) is False
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_insufficient_gold_at_trigger(self):
        """fill >= 0.95 and unsatisfied, but gold < expansion cost -> 0."""
        gd = self._gd(capacity=30, cost=5000)
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        state = make_state(gold=100, bank_items={f"i{i}": 1 for i in range(29)})
        assert goal.is_satisfied(state) is False
        assert goal.value(state, gd) == 0.0

    def test_desired_state_requests_one_more_slot(self):
        gd = self._gd(capacity=30)
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        assert goal.desired_state(make_state(), gd) == {"bank_capacity": 31}


# --- LevelSkillGoal -------------------------------------------------------

class TestLevelSkillGaps:
    def _gd(self) -> GameData:
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                       crafting_skill="weaponcrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
        return gd

    def test_desired_state_targets_skill_level(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        assert goal.desired_state(make_state(), self._gd()) == {
            "skills": {"weaponcrafting": 3}
        }

    def test_relevant_actions_keeps_deposit(self):
        goal = LevelSkillGoal("weaponcrafting", 3)
        deposit = DepositAllAction()
        relevant = goal.relevant_actions([deposit], make_state(), self._gd())
        assert deposit in relevant

    def test_has_craftable_skips_recipe_with_missing_or_wrong_skill_stats(self):
        """A recipe whose item has no ItemStats (or a different skill) is
        skipped; with no usable recipe at level, the goal does not fire."""
        gd = GameData()
        # recipe present but NO item_stats for it -> _has_craftable_in_skill
        # hits the `stats is None` continue and finds nothing craftable.
        gd._item_stats = {}
        gd._crafting_recipes = {"mystery_item": {"x": 1}}
        goal = LevelSkillGoal("weaponcrafting", 3)
        state = make_state(skills={"weaponcrafting": 1})
        assert goal.value(state, gd) == 0.0


# --- LowYieldCancelGoal ---------------------------------------------------

class TestLowYieldCancelGaps:
    def test_desired_state_clears_task(self):
        goal = LowYieldCancelGoal()
        assert goal.desired_state(make_state(), GameData()) == {
            "task_code": None, "task_total": 0
        }

    def test_repr(self):
        assert repr(LowYieldCancelGoal()) == "LowYieldCancel"


# --- ReachUnlockLevelGoal -------------------------------------------------

class TestReachUnlockLevelGaps:
    def test_value_zero_for_nonpositive_target(self):
        """target_level <= 0 is meaningless -> never fires."""
        goal = ReachUnlockLevelGoal(target_level=0)
        # not satisfied (level 5 >= 0 is True actually) -> use negative target
        goal_neg = ReachUnlockLevelGoal(target_level=-1)
        state = make_state(level=-5)  # below target so not satisfied
        assert goal_neg.value(state, GameData()) == 0.0
        # target 0: level >= 0 -> satisfied -> 0 as well
        assert goal.value(make_state(level=5), GameData()) == 0.0

    def test_desired_state_targets_level(self):
        goal = ReachUnlockLevelGoal(target_level=8)
        assert goal.desired_state(make_state(), GameData()) == {"level": 8}

    def test_relevant_actions_keeps_loadout_for_beatable_target(self):
        """An equip-tagged OptimizeLoadout targeting a beatable monster is
        kept; one targeting an over-level monster is dropped."""
        gd = GameData()
        gd._monster_level = {"chicken": 1, "lich": 30}
        goal = ReachUnlockLevelGoal(target_level=8)
        state = make_state(level=5)
        beatable = OptimizeLoadoutAction(target_monster_code="chicken")
        too_strong = OptimizeLoadoutAction(target_monster_code="lich")
        relevant = goal.relevant_actions([beatable, too_strong], state, gd)
        assert beatable in relevant
        assert too_strong not in relevant


# --- UnlockBankGoal -------------------------------------------------------

class TestUnlockBankGaps:
    def test_value_zero_when_target_unreachable(self):
        """A way-over-level target monster -> defer (value 0) instead of
        looping on unwinnable fights."""
        gd = GameData()
        gd._monster_level = {"lich": 30}
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100,
                              target_monster="lich")
        state = make_state(level=5, xp=100)  # xp not yet above initial
        assert goal.value(state, gd) == 0.0

    def test_value_fires_when_target_reachable(self):
        gd = GameData()
        gd._monster_level = {"yellow_slime": 4}
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100,
                              target_monster="yellow_slime")
        # level 5 >= 4 - 1 -> reachable; xp still at initial -> fires at 90.
        state = make_state(level=5, xp=100, inventory={}, inventory_max=20)
        assert goal.value(state, gd) == 90.0

    def test_unreachable_false_for_unknown_monster_level(self):
        """Unknown monster level (<=0) is NOT treated as unreachable — let
        the planner try."""
        gd = GameData()
        gd._monster_level = {}  # unknown target
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100,
                              target_monster="ghost")
        state = make_state(level=5, xp=100, inventory={}, inventory_max=20)
        assert goal.value(state, gd) == 90.0

    def test_unreachable_false_when_no_target_monster(self):
        gd = GameData()
        goal = UnlockBankGoal(bank_locked=True, initial_xp=100, target_monster=None)
        state = make_state(level=5, xp=100, inventory={}, inventory_max=20)
        assert goal.value(state, gd) == 90.0


# --- GatherMaterialsGoal --------------------------------------------------

class TestGatherMaterialsGaps:
    def test_value_uses_base_when_no_progress_history(self, tmp_path):
        """history present but no recorded cycles for this goal ->
        goal_avg_cycles_to_satisfy is None -> base value returned (no
        efficiency scaling)."""
        store = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
        gd = GameData()
        gd._crafting_recipes = {}
        goal = GatherMaterialsGoal("wooden_shield", {"ash_wood": 10})
        state = make_state(inventory={})  # nothing gathered -> not satisfied
        base = goal._compute_base_value(state, gd)
        assert base > 0.0
        # With an empty store, avg cycles is None -> value equals base exactly.
        assert goal.value(state, gd, store) == base
        store.close()
