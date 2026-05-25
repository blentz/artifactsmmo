from dataclasses import dataclass

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import AcceptTaskAction, TaskCancelAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal  # noqa: F401 (used in repr checks)
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import (
    LEVEL_LOOKAHEAD,
    StrategyArbiter,
    _precedes,
    map_guard,
    map_means,
    objective_step_goal,
)
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   resistance={"earth": 5}, crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6}, "ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _ctx(**kw):
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


# ---------------------------------------------------------------------------
# map_guard unit tests
# ---------------------------------------------------------------------------

def test_map_guard_hp_critical():
    assert isinstance(map_guard(GuardKind.HP_CRITICAL, GameData(), _ctx()), RestoreHPGoal)


def test_map_guard_discard_critical():
    g = map_guard(GuardKind.DISCARD_CRITICAL, GameData(), _ctx())
    assert isinstance(g, DiscardOverstockGoal)


def test_map_guard_discard_high():
    g = map_guard(GuardKind.DISCARD_HIGH, GameData(), _ctx())
    assert isinstance(g, DiscardOverstockGoal)


def test_map_guard_bank_unlock():
    ctx = _ctx(bank_accessible=False, bank_unlock_monster="chicken", initial_xp=100)
    g = map_guard(GuardKind.BANK_UNLOCK, GameData(), ctx)
    assert isinstance(g, UnlockBankGoal)


def test_map_guard_reach_unlock_level():
    ctx = _ctx(bank_required_level=5)
    g = map_guard(GuardKind.REACH_UNLOCK_LEVEL, GameData(), ctx)
    assert isinstance(g, ReachUnlockLevelGoal)


def test_map_guard_deposit_full():
    g = map_guard(GuardKind.DEPOSIT_FULL, GameData(), _ctx())
    assert isinstance(g, DepositInventoryGoal)


def test_map_guard_unknown_raises():
    with pytest.raises(ValueError):
        map_guard("bogus", GameData(), _ctx())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# map_means unit tests
# ---------------------------------------------------------------------------

def test_map_means_claim_pending():
    assert isinstance(map_means(MeansKind.CLAIM_PENDING, GameData(), _ctx(), make_state()), ClaimPendingGoal)


def test_map_means_complete_task():
    assert isinstance(map_means(MeansKind.COMPLETE_TASK, GameData(), _ctx(), make_state()), CompleteTaskGoal)


def test_map_means_sell_pressured():
    assert isinstance(map_means(MeansKind.SELL_PRESSURED, GameData(), _ctx(), make_state()), SellInventoryGoal)


def test_map_means_sell_idle():
    assert isinstance(map_means(MeansKind.SELL_IDLE, GameData(), _ctx(), make_state()), SellInventoryGoal)


def test_map_means_low_yield_cancel():
    assert isinstance(map_means(MeansKind.LOW_YIELD_CANCEL, GameData(), _ctx(), make_state()), LowYieldCancelGoal)


def test_map_means_task_cancel():
    assert isinstance(map_means(MeansKind.TASK_CANCEL, GameData(), _ctx(), make_state()), TaskCancelGoal)


def test_map_means_accept_task():
    assert isinstance(map_means(MeansKind.ACCEPT_TASK, GameData(), _ctx(), make_state()), AcceptTaskGoal)


def test_map_means_task_exchange():
    g = map_means(MeansKind.TASK_EXCHANGE, GameData(), _ctx(task_exchange_min_coins=3), make_state())
    assert isinstance(g, TaskExchangeGoal)


def test_map_means_bank_expand():
    assert isinstance(map_means(MeansKind.BANK_EXPAND, GameData(), _ctx(), make_state()), ExpandBankGoal)


def test_map_means_unknown_raises():
    with pytest.raises(ValueError):
        map_means("bogus", GameData(), _ctx(), make_state())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# objective_step_goal unit tests
# ---------------------------------------------------------------------------

def test_objective_step_obtain_gear():
    gd = _gd()
    step = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, make_state(), gd, _ctx())
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("wooden_shield", "shield_slot")


def test_objective_step_obtain_material():
    gd = _gd()
    step = ObtainItem("ash_plank", 6)
    g = objective_step_goal(step, make_state(), gd, _ctx())
    assert isinstance(g, GatherMaterialsGoal)
    assert g._needed == {"ash_plank": 6}


def test_objective_step_reach_skill_level():
    step = ReachSkillLevel("mining", 10)
    # make_state() has mining level 3; target should be bounded to 3+LEVEL_LOOKAHEAD=6
    state = make_state(skills={"mining": 3}, skill_xp={"mining": 42})
    g = objective_step_goal(step, state, _gd(), _ctx())
    assert isinstance(g, LevelSkillGoal)
    assert g._skill_name == "mining"
    assert g._target_level == 6, f"expected target_level==6 (current+LEVEL_LOOKAHEAD), got {g._target_level}"
    assert g._initial_skill_xp == 42, f"expected initial_skill_xp==42, got {g._initial_skill_xp}"


def test_objective_step_reach_skill_level_bounds_to_current_plus_lookahead():
    """objective_step_goal must bound ReachSkillLevel target to current+LEVEL_LOOKAHEAD."""
    step = ReachSkillLevel("alchemy", 50)
    state = make_state(skills={"alchemy": 1}, skill_xp={"alchemy": 99})
    g = objective_step_goal(step, state, _gd(), _ctx())
    assert isinstance(g, LevelSkillGoal)
    assert g._target_level == 4, f"expected 4 (1+3), got {g._target_level}"
    assert g._initial_skill_xp == 99


def test_objective_step_reach_char_level_with_monster():
    step = ReachCharLevel(10)
    g = objective_step_goal(step, make_state(xp=50), _gd(), _ctx(combat_monster="chicken"))
    assert isinstance(g, GrindCharacterXPGoal)
    assert g._target_monster == "chicken" and g._initial_xp == 50


def test_objective_step_reach_char_level_no_monster():
    step = ReachCharLevel(10)
    g = objective_step_goal(step, make_state(), _gd(), _ctx(combat_monster=None))
    assert g is None


def test_objective_step_none_step():
    g = objective_step_goal(None, make_state(), _gd(), _ctx())
    assert g is None


# ---------------------------------------------------------------------------
# Helper stub for StrategyDecision (only chosen_step is used by StrategyArbiter)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FakeDecision:
    chosen_step: ObtainItem | ReachCharLevel | ReachSkillLevel | None


def _make_planner_gd() -> GameData:
    """Minimal GameData that lets the planner resolve Accept/Fight/Rest actions."""
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    return gd


# ---------------------------------------------------------------------------
# StrategyArbiter integration tests
# ---------------------------------------------------------------------------

def test_select_guard_preempts_means():
    """HP-critical guard fires: even if AcceptTask means is queued, RestoreHP wins."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # state: no task (AcceptTask fires), but HP is critical
    state = make_state(hp=10, max_hp=150, task_code=None, task_total=0)
    actions = [
        RestAction(),
        AcceptTaskAction(taskmaster_location=(2, 1)),
    ]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, RestoreHPGoal), f"expected RestoreHPGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_returns_objective_step_when_calm():
    """No guards, no collect-reward means; chosen_step→GrindCharacterXP plans."""
    planner = GOAPPlanner()
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    # Level 1 char with HP full, no task (so AcceptTask would fire as discretionary,
    # but chosen_step goal (GrindCharacterXP) appears before discretionary).
    # Use xp=0 and initial_xp=0 to make GrindXP not satisfied.
    state = make_state(level=1, hp=150, max_hp=150, xp=0, max_xp=500, task_code=None, task_total=0)
    actions = [FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, GrindCharacterXPGoal), f"expected GrindCharacterXPGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_falls_through_unplannable_to_next():
    """No guard fires; chosen_step can't plan (no FightAction); AcceptTask CAN → returns AcceptTask."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # Calm state: HP full, no bag pressure, no task (so AcceptTask fires as discretionary)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    # Provide AcceptTaskAction but NO FightAction → ReachCharLevel (GrindCharacterXP) cannot plan,
    # AcceptTaskGoal CAN plan via AcceptTaskAction.
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    # chosen_step is ReachCharLevel → maps to GrindCharacterXPGoal which needs FightAction
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, AcceptTaskGoal), f"expected AcceptTaskGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_returns_none_when_nothing_plans():
    """No plannable goal → (None, [], goals_tried)."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state = make_state(hp=150, max_hp=150, task_code="chicken", task_type="monster",
                       task_progress=0, task_total=5)
    actions: list = []  # no actions at all
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert goal is None
    assert plan == []


def test_select_skips_suppressed_means():
    """A means whose repr is in `suppressed` is skipped, falling through."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    # Without suppression AcceptTask would be selected; suppress it.
    goal, plan, tried = arbiter.select(
        decision, state, gd, actions, ctx, suppressed={"AcceptTask"})
    assert goal is None or repr(goal) != "AcceptTask"
    assert not any(gt["goal"] == "AcceptTask" for gt in tried)


def test_select_never_suppresses_task_cancel(tmp_path):
    """TaskCancel is the escape hatch and must never be filtered by suppression."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # A monsters task far above the character's level → task_decision PIVOTs, so
    # TASK_CANCEL fires (requires a non-None history). No FightAction is given so
    # nothing else plans, forcing the walk to reach the (suppressed) TaskCancel.
    gd._monster_level["dragon"] = 50
    store = LearningStore(db_path=str(tmp_path / "tc.db"), character="hero")
    try:
        state = make_state(level=5, hp=150, max_hp=150, task_code="dragon",
                           task_type="monsters", task_progress=0, task_total=5)
        actions = [TaskCancelAction(taskmaster_location=(2, 1))]
        ctx = _ctx()
        arbiter = StrategyArbiter(planner, history=store)
        decision = _FakeDecision(chosen_step=None)
        _goal, _plan, tried = arbiter.select(
            decision, state, gd, actions, ctx, suppressed={"TaskCancel"})
        assert any(gt["goal"] == "TaskCancel" for gt in tried), (
            "TaskCancel must not be skipped even when suppressed"
        )
    finally:
        store.close()


def test_select_sticky_keeps_committed_means():
    """If a means committed on cycle 1 still fires and plans, cycle 2 returns same repr."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # No task: AcceptTask fires (discretionary)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    goal1, plan1, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal), f"cycle 1: expected AcceptTask, got {goal1!r}"

    # Cycle 2: state unchanged, AcceptTask still fires and plans
    goal2, plan2, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert repr(goal2) == repr(goal1), f"cycle 2: expected sticky {goal1!r}, got {goal2!r}"


def test_select_no_double_count_when_committed_becomes_unplannable():
    """Fix 1: committed means unplannable on cycle 2 must not appear twice in goals_tried."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # No task: AcceptTask fires as discretionary; AcceptTaskAction enables it to plan.
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions_with_accept = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    # Cycle 1: AcceptTask commits
    goal1, plan1, _ = arbiter.select(decision, state, gd, actions_with_accept, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: remove AcceptTaskAction so the committed goal can't plan;
    # provide no other plannable action either → expect (None, [])
    goal2, plan2, tried2 = arbiter.select(decision, state, gd, [], ctx)
    assert goal2 is None

    # AcceptTask repr must appear at most once in goals_tried (not double-counted)
    accept_reprs = [e["goal"] for e in tried2 if e["goal"] == repr(AcceptTaskGoal())]
    assert len(accept_reprs) <= 1, f"double-counted: {tried2}"


def test_select_guard_clears_committed_repr():
    """Fix 2: when a guard fires and plans, _committed_repr is cleared (not left stale)."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state_calm = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [
        AcceptTaskAction(taskmaster_location=(2, 1)),
        RestAction(),
    ]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    # Cycle 1: calm state — AcceptTask commits
    goal1, _, _ = arbiter.select(decision, state_calm, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: HP now critical — RestoreHP guard fires and plans
    state_low_hp = make_state(hp=10, max_hp=150, task_code=None, task_total=0)
    goal2, plan2, _ = arbiter.select(decision, state_low_hp, gd, actions, ctx)
    assert isinstance(goal2, RestoreHPGoal), f"expected RestoreHPGoal, got {goal2!r}"
    assert len(plan2) >= 1
    # commitment must be cleared after a guard return
    assert arbiter._committed_repr is None


# ---------------------------------------------------------------------------
# Part B: targeted coverage tests
# ---------------------------------------------------------------------------

def test_objective_step_goal_none_for_no_step():
    """objective_step_goal(None, ...) returns None (line 90) and an unrecognized
    step type also falls through to the final return None (line 106)."""
    # None step → early return None
    assert objective_step_goal(None, make_state(), _gd(), _ctx()) is None

    # Unrecognized step type (not ObtainItem / ReachSkillLevel / ReachCharLevel)
    class _UnknownStep:
        pass

    assert objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx()) is None  # type: ignore[arg-type]


def test_precedes_false_when_target_absent():
    """_precedes returns False when b_repr is not present in the candidates list."""
    goal_a = AcceptTaskGoal()
    candidates: list[tuple[Goal, bool]] = [(goal_a, True)]
    # "NotPresent" is not in the list → b_idx is None → return False
    assert _precedes(candidates, repr(goal_a), "NotPresent") is False
    # a_repr also absent → a_idx is None → return False
    assert _precedes(candidates, "AlsoAbsent", "NotPresent") is False


def test_select_skips_satisfied_step_goal_continues_to_next():
    """A candidate step_goal that is_satisfied(state) is skipped; a later
    plannable discretionary goal (AcceptTask) is returned instead."""
    planner = GOAPPlanner()
    gd = _gd()
    # Give GameData the monster/bank locations AcceptTask needs
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)

    # State already has ash_plank: 6 in inventory so GatherMaterialsGoal is satisfied
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0,
                       inventory={"ash_plank": 6})
    # chosen_step → GatherMaterialsGoal(needed={"ash_plank": 6}) which is_satisfied → skipped
    # AcceptTaskAction is available so AcceptTask discretionary goal will plan
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)

    # Use ObtainItem("ash_plank", 6) as chosen_step; state already satisfies it
    decision = _FakeDecision(chosen_step=ObtainItem("ash_plank", 6))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)

    # The satisfied GatherMaterialsGoal must have been skipped (not attempted)
    attempted_reprs = [e["goal"] for e in goals_tried]
    gather_repr = repr(GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 6}))
    assert gather_repr not in attempted_reprs, (
        f"satisfied goal should be skipped, but appeared in goals_tried: {attempted_reprs}"
    )
    assert isinstance(goal, AcceptTaskGoal), f"expected AcceptTaskGoal, got {goal!r}"
    assert len(plan) >= 1


# ---------------------------------------------------------------------------
# LEVEL_LOOKAHEAD tests
# ---------------------------------------------------------------------------

class TestLevelLookahead:
    def test_constant_is_three(self):
        assert LEVEL_LOOKAHEAD == 3

    def test_skill_step_targets_current_plus_lookahead(self):
        state = make_state(skills={"weaponcrafting": 1})
        goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 50), state, GameData(), _ctx())
        assert repr(goal) == "LevelSkill(weaponcrafting->4)"   # min(50, 1+3)

    def test_skill_step_caps_at_step_level(self):
        state = make_state(skills={"weaponcrafting": 48})
        goal = objective_step_goal(ReachSkillLevel("weaponcrafting", 50), state, GameData(), _ctx())
        assert repr(goal) == "LevelSkill(weaponcrafting->50)"   # min(50, 48+3)


# ---------------------------------------------------------------------------
# PURSUE_TASK mapping tests
# ---------------------------------------------------------------------------

class TestPursueTaskMapping:
    def test_feasible_items_task_maps_to_pursue_task(self):
        # no crafting recipe known -> task_requirement returns None -> feasible
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        goal = map_means(MeansKind.PURSUE_TASK, GameData(), _ctx(), state)
        assert repr(goal) == "PursueTask(copper_bar)"

    def test_skill_gated_items_task_maps_to_level_skill(self):
        gd = GameData()
        gd._item_stats["copper_bar"] = ItemStats(
            code="copper_bar", type_="resource", level=1,
            crafting_skill="weaponcrafting", crafting_level=3,
        )
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0, skills={"weaponcrafting": 1})
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        assert repr(goal) == "LevelSkill(weaponcrafting->3)"   # min(gate=3, 1+LEVEL_LOOKAHEAD=4) -> 3

    def test_pursue_task_goal_carries_batch(self):
        gd = GameData()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=2, inventory={}, inventory_max=100)
        goal = map_means(MeansKind.PURSUE_TASK, gd, _ctx(), state)
        expected = 2 + task_batch_size(state, gd)
        assert goal.desired_state(state, gd) == {"task_progress": expected}
        assert task_batch_size(state, gd) > 1   # this state genuinely batches


# ---------------------------------------------------------------------------
# Items-task grind stand-down tests
# ---------------------------------------------------------------------------

class TestItemsTaskStandDown:
    def test_char_step_stands_down_for_items_task(self):
        state = make_state(task_code="copper_bar", task_type="items",
                           task_total=20, task_progress=0)
        assert objective_step_goal(ReachCharLevel(50), state, GameData(),
                                   _ctx(combat_monster="chicken")) is None

    def test_char_step_grinds_for_monster_task(self):
        state = make_state(task_code="chicken", task_type="monsters",
                           task_total=20, task_progress=0)
        goal = objective_step_goal(ReachCharLevel(50), state, GameData(),
                                   _ctx(combat_monster="chicken"))
        assert goal is not None and repr(goal).startswith("GrindCharacterXP")

    def test_char_step_grinds_with_no_task(self):
        goal = objective_step_goal(ReachCharLevel(50), make_state(), GameData(),
                                   _ctx(combat_monster="chicken"))
        assert goal is not None and repr(goal).startswith("GrindCharacterXP")


# ---------------------------------------------------------------------------
# End-to-end arbiter test: items task selects PursueTask, not GrindCharacterXP
# ---------------------------------------------------------------------------

class TestPursueTaskEndToEnd:
    """Reconstruct the production stall: copper_bar 0/20 items task, feasible
    (no skill gap), ReachCharLevel(50) as chosen_step → arbiter must return
    PursueTask(copper_bar), NOT GrindCharacterXP."""

    def test_items_task_selects_pursue_not_grind(self, monkeypatch, tmp_path):
        import artifactsmmo_cli.ai.tiers.means as means_module

        # Patch task_decision in means so PURSUE_TASK fires without needing a
        # populated LearningStore.
        monkeypatch.setattr(means_module, "task_decision", lambda *_: means_module.PURSUE)

        planner = GOAPPlanner()
        gd = _make_planner_gd()
        # No crafting recipe for copper_bar → task_requirement returns None → feasible
        # State: items task active, one copper_bar already in inventory (so
        # TaskTradeAction is immediately applicable). task_total=1 ensures
        # task_batch_size returns 1, so PursueTaskGoal(batch=1) is satisfied
        # after trading the single bar.
        state = make_state(
            level=5, hp=150, max_hp=150, xp=0, max_xp=500,
            task_code="copper_bar", task_type="items",
            task_progress=0, task_total=1,
            skills={"weaponcrafting": 5},
            inventory={"copper_bar": 1},
        )
        # TaskTradeAction lets PursueTaskGoal plan in one step.
        actions = [TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(2, 1))]
        ctx = _ctx(combat_monster="chicken")

        # Use a real (empty) LearningStore so history is not None (required for
        # PURSUE_TASK._fires), but task_decision is patched so it always PURSUEs.
        store = LearningStore(db_path=str(tmp_path / "e2e.db"), character="testchar")
        try:
            arbiter = StrategyArbiter(planner, history=store)
            decision = _FakeDecision(chosen_step=ReachCharLevel(50))
            goal, plan, _ = arbiter.select(decision, state, gd, actions, ctx)
        finally:
            store.close()

        assert repr(goal) == "PursueTask(copper_bar)", (
            f"expected PursueTask(copper_bar), got {goal!r}"
        )
        assert len(plan) >= 1
