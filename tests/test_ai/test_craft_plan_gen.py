"""Tests for the craft-plan generator (Task 4 of next-craft-action generator).

Covers:
- copper_ring-style all-gatherable closure → generator returns GatherAction or CraftAction
- monster-drop leaf → returns None (A* fallback)
- unmet skill gate → returns None (A* fallback)
- non-GatherMaterialsGoal → returns None
- all-satisfied (owned>=qty) → returns None
- Integration through StrategyArbiter._plans: generator path records nodes==0;
  monster-drop goal still routes to A* (planner invoked).
- Intermediate CraftAction is batched to inventory-bounded closure demand (> 1).
"""

import dataclasses

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.craft_plan_gen import _map_next_action
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.next_craft_core import NextAction
from artifactsmmo_cli.ai.obtain_sources import Source, SourceKind
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**kw: object) -> SelectionContext:
    base: dict[str, object] = dict(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
    )
    base.update(kw)
    return SelectionContext(**base)

def _gd_copper_ring() -> GameData:
    """copper_ring → copper_bar (1 bar each) → copper_ore (10 ore per bar).

    Closure: copper_ring (craftable, jewel lv1), copper_bar (craftable, mining lv1),
    copper_ore (raw; produced by copper_rocks resource).
    """
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "copper_ring": ItemStats(
            code="copper_ring", level=1, type_="ring",
            crafting_skill="jewelrycrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_ring": {"copper_bar": 1},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._workshop_locations = {"mining": (1, 5), "jewelrycrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


def _copper_ring_actions() -> list:
    """Minimal action list for the copper_ring goal."""
    return [
        GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
        CraftAction(code="copper_bar", workshop_location=(1, 5)),
        CraftAction(code="copper_ring", workshop_location=(3, 1)),
    ]


def _gd_monster_drop() -> GameData:
    """feather_coat → feather (monster-drop only, NOT a resource drop)."""
    gd = GameData()
    gd._item_stats = {
        "feather": ItemStats(code="feather", level=1, type_="resource"),
        "feather_coat": ItemStats(
            code="feather_coat", level=5, type_="body_armor",
            crafting_skill="gearcrafting", crafting_level=5,
        ),
    }
    gd._crafting_recipes = {
        "feather_coat": {"feather": 8},
    }
    # feather is NOT in resource_drops — it is a monster drop.
    gd._resource_drops = {}
    gd._workshop_locations = {"gearcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


# ---------------------------------------------------------------------------
# Unit tests for generate_next_craft_action
# ---------------------------------------------------------------------------

class TestCopperRingGatherPhase:
    """0 owned copper_ore → first action must gather copper_ore."""

    def test_returns_gather_action_when_ore_missing(self):
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None, "Expected a plan, not None (A* fallback)"
        assert isinstance(result[0], GatherAction)
        assert result[0].resource_code == "copper_rocks"
        assert isinstance(result[-1], CraftAction) and result[-1].code == "copper_ring"

    def test_returns_craft_bar_when_ore_present(self):
        """10 copper_ore owned → next step is craft copper_bar."""
        gd = _gd_copper_ring()
        state = make_state(inventory={"copper_ore": 10}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert isinstance(result[0], CraftAction)
        assert result[0].code == "copper_bar"
        assert isinstance(result[-1], CraftAction) and result[-1].code == "copper_ring"

    def test_returns_craft_ring_when_bar_present(self):
        """1 copper_bar owned → final step is craft copper_ring."""
        gd = _gd_copper_ring()
        state = make_state(inventory={"copper_bar": 1}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], CraftAction)
        assert result[0].code == "copper_ring"


class TestFullSlotsDefersToAStar:
    """Live Robby 497 livelock (2026-07-09): 20/20 slots full with quantity
    headroom. The directed generator emits a deterministic gather leg but does
    NOT model inventory-room preconditions, so it would surface a plan whose
    plan[0] gather is NOT applicable (a NEW-stack gather blocked by the full
    slot cap — the Task-4 slot gate). The generator must detect the
    inapplicable first leg and return None so A* sequences the slot-freeing
    relief (DepositAll/Recycle/Sell) before the gather."""

    @staticmethod
    def _full_bag_inventory(n_stacks: int) -> dict[str, int]:
        """`n_stacks` distinct junk stacks (none in the copper_ring closure)."""
        return {f"junk_{i}": 1 for i in range(n_stacks)}

    def test_full_slots_new_stack_gather_returns_none(self):
        """slots_free == 0 (distinct stacks == slot cap) with plenty of quantity
        headroom → the copper_ore gather is a NEW stack blocked by the slot cap,
        so its is_applicable is False → generator returns None (A* fallback)."""
        gd = _gd_copper_ring()
        state = make_state(
            inventory=self._full_bag_inventory(5),
            inventory_slots_max=5,   # 5 distinct stacks → slots_free == 0
            inventory_max=100,       # ample quantity headroom (not the blocker)
            bank_items={},
            skills={"mining": 5, "jewelrycrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        # Sanity: the slot cap really is what blocks the leg (quantity fits).
        assert state.inventory_slots_free == 0
        assert state.inventory_max - state.inventory_used >= 3
        gather = actions[0]
        assert isinstance(gather, GatherAction)
        assert gather.is_applicable(state, gd) is False

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, (
            "a full-slot state whose first leg (new-stack gather) is not "
            "applicable must defer to A* for slot-freeing relief"
        )

    def test_room_for_new_stack_returns_gather_leg(self):
        """Control: one free slot → the copper_ore gather IS applicable, so the
        generator fires and returns the gather leg (non-None)."""
        gd = _gd_copper_ring()
        state = make_state(
            inventory=self._full_bag_inventory(5),
            inventory_slots_max=6,   # one free slot for the new copper_ore stack
            inventory_max=100,
            bank_items={},
            skills={"mining": 5, "jewelrycrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        assert state.inventory_slots_free == 1

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None, "room for the new stack → generator must fire"
        assert isinstance(result[0], GatherAction)
        assert result[0].resource_code == "copper_rocks"
        assert result[0].is_applicable(state, gd) is True


class TestWithdrawsBankedIntermediate:
    """Banked craftable intermediate → emit a WithdrawItemAction (no A* bank-gate)."""

    def test_returns_withdraw_when_bar_banked(self):
        """copper_bar in the bank, short inventory → withdraw it, not gather/craft."""
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={"copper_bar": 5},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = [
            *_copper_ring_actions(),
            WithdrawItemAction(code="copper_bar", quantity=1, bank_location=(4, 0)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert isinstance(result[0], WithdrawItemAction)
        assert result[0].code == "copper_bar"
        assert isinstance(result[-1], CraftAction) and result[-1].code == "copper_ring"

    def test_none_when_withdraw_action_absent(self):
        """Banked bar but no WithdrawItemAction in the list → fall back to A*."""
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={"copper_bar": 5},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()  # no WithdrawItemAction surfaced

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None


class TestWithdrawClampedToBankStock:
    """Regression (live 2026-06-24 Robby): the bank held FEWER of an intermediate
    than the recipe needs (ash_plank: bank 4, wooden_shield wants 6). The proved
    core clamps the withdraw to bank stock and gathers the rest, but the action
    mapping returned a pre-built FULL-quantity WithdrawItemAction → withdrawing
    more than the bank holds → HTTP 478, and the plan never reached the gather
    step (Withdraw(ash_plank×7)→478 loop). The mapped withdraw must carry the
    core's clamped quantity."""

    def test_withdraw_quantity_clamped_to_bank_stock(self):
        gd = _gd_copper_ring()
        gd._crafting_recipes["copper_ring"] = {"copper_bar": 3}  # need 3 bars
        state = make_state(inventory={}, bank_items={"copper_bar": 2},  # bank has only 2
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = [
            *_copper_ring_actions(),
            # Full-requirement withdraw listed FIRST — the by-code-only mapping
            # would pick this (quantity 3) over the bank-available 2.
            WithdrawItemAction(code="copper_bar", quantity=3, bank_location=(4, 0)),
            WithdrawItemAction(code="copper_bar", quantity=1, bank_location=(4, 0)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        first = result[0]
        assert isinstance(first, WithdrawItemAction) and first.code == "copper_bar"
        assert first.quantity == 2, (
            f"withdraw qty must clamp to bank stock (2), got {first.quantity}"
        )
        assert first.bank_location == (4, 0)
        # The plan must still gather the deficit the bank cannot cover.
        assert any(isinstance(a, GatherAction) for a in result), (
            "plan must gather the deficit the bank can't cover"
        )


class TestSatisfiedGoalReturnsNone:
    """Goal already satisfied (owned >= qty) → None."""

    def test_none_when_already_owned(self):
        gd = _gd_copper_ring()
        state = make_state(inventory={"copper_ring": 1}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None


class TestMonsterDropLeafFallsBack:
    """Closure containing a monster-drop leaf → None (A* fallback)."""

    def test_monster_drop_returns_none(self):
        gd = _gd_monster_drop()
        state = make_state(inventory={}, bank_items={},
                           skills={"gearcrafting": 5})
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        # No GatherAction for feather (there is no resource node for it).
        actions = [CraftAction(code="feather_coat", workshop_location=(3, 1))]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, "Monster-drop leaf must fall back to A*"


class TestUnmetSkillGateFallsBack:
    """Closure has a craftable whose skill gate the character hasn't met → None."""

    def test_skill_gate_not_met_returns_none(self):
        gd = _gd_copper_ring()
        # Character has mining=0 (<1 required for copper_bar).
        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 0, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, "Unmet skill gate must fall back to A*"

    def test_skill_gate_not_met_emits_applicable_levelskill(self):
        """Unmet skill gate WITH an applicable LevelSkill in the pool → the
        generator emits the grind leg (one-leg-per-cycle), NOT a fall-back to A*.
        Mirror of `test_skill_gate_not_met_returns_none`: same under-skill state,
        but the caller surfaced a LevelSkill whose grind rung is reachable (a
        mining resource gatherable now grants mining xp), so `_finish([lvl])`
        fires."""
        gd = _gd_copper_ring()
        # Wire copper_rocks as a mining resource gatherable at level 0, so
        # best_gather_resource_drop makes LevelSkill("mining", 1) applicable.
        gd._resource_skill = {"copper_rocks": ("mining", 0)}
        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 0, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        lvl = LevelSkill(skill="mining", target_level=1)
        assert lvl.is_applicable(state, gd)
        actions = [*_copper_ring_actions(), lvl]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result == [lvl], "Unmet gate + applicable grind must emit the LevelSkill leg"

    def test_skill_gate_met_does_not_fall_back(self):
        """Exact skill level equal to required → gate is met, generator fires."""
        gd = _gd_copper_ring()
        # Character has exactly the required skill level (mining=1, jewel=1).
        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 1, "jewelrycrafting": 1})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None, "Exactly-met skill gate should not fall back to A*"


class TestMissingItemStatsOrWorkshopFallsBack:
    """Craftable with no ItemStats or no workshop → None (A* fallback)."""

    def test_no_item_stats_for_craftable_returns_none(self):
        """Recipe exists but ItemStats is absent → unknown requirements → fall back."""
        gd = GameData()
        gd._item_stats = {}  # No stats for copper_ring.
        gd._crafting_recipes = {"copper_ring": {"copper_ore": 6}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._workshop_locations = {"jewelrycrafting": (3, 1)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        fill_monster_stat_defaults(gd)

        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_ring", workshop_location=(3, 1)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, "Missing ItemStats must fall back to A*"

    def test_no_workshop_for_craft_skill_returns_none(self):
        """Recipe and stats exist but no workshop for the craft skill → fall back."""
        gd = _gd_copper_ring()
        # Remove the workshop for jewelrycrafting (the ring's craft skill).
        gd._workshop_locations = {"mining": (1, 5)}  # jewelrycrafting missing.

        state = make_state(inventory={"copper_bar": 1}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, "Missing workshop must fall back to A*"


class TestNonGatherMaterialsGoalReturnsNone:
    """Any non-GatherMaterialsGoal → None immediately."""

    def test_wait_goal_returns_none(self):
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={})
        result = generate_next_craft_action(WaitGoal(), state, gd, [])
        assert result is None

    def test_plain_object_returns_none(self):
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={})
        result = generate_next_craft_action(object(), state, gd, [])
        assert result is None


class TestSharedIntermediateClosure:
    """Shared intermediate (used by two recipes) exercises the seen-guard in _closure_items."""

    def test_shared_ore_both_rings(self):
        """copper_ore is a leaf for both copper_ring AND copper_amulet.

        Exercises the ``if item in seen: continue`` branch in _closure_items.
        """
        gd = GameData()
        gd._item_stats = {
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
            "copper_bar": ItemStats(
                code="copper_bar", level=1, type_="resource",
                crafting_skill="mining", crafting_level=1,
            ),
            "copper_ring": ItemStats(
                code="copper_ring", level=1, type_="ring",
                crafting_skill="jewelrycrafting", crafting_level=1,
            ),
            "copper_amulet": ItemStats(
                code="copper_amulet", level=1, type_="amulet",
                crafting_skill="jewelrycrafting", crafting_level=1,
            ),
        }
        gd._crafting_recipes = {
            "copper_bar": {"copper_ore": 10},
            "copper_ring": {"copper_bar": 1},
            "copper_amulet": {"copper_bar": 2},  # copper_ore reachable via TWO paths
        }
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        gd._workshop_locations = {"mining": (1, 5), "jewelrycrafting": (3, 1)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        fill_monster_stat_defaults(gd)

        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        # Goal needs BOTH rings; copper_ore is a shared leaf.
        goal = GatherMaterialsGoal(
            "copper_ring",
            {"copper_ring": 1, "copper_amulet": 1},
        )
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_ring", workshop_location=(3, 1)),
            CraftAction(code="copper_amulet", workshop_location=(3, 1)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        # Should generate a gather action (ore needed), not fall back to A*.
        assert result is not None
        assert isinstance(result[0], GatherAction)
        assert result[0].resource_code == "copper_rocks"


class TestNoMatchingActionFallsBack:
    """Generator found a next action (item,kind) but it is absent from relevant_actions → None."""

    def test_no_gather_action_for_raw_leaf_returns_none(self):
        """Closure is all-gatherable but no GatherAction was passed → None."""
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        # Pass only CraftActions — no GatherAction for copper_ore.
        actions = [
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_ring", workshop_location=(3, 1)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None

    def test_no_craft_action_for_craftable_returns_none(self):
        """Inputs on hand but no CraftAction for the item → None."""
        gd = _gd_copper_ring()
        # Ore present → next step is craft bar, but bar craft action is missing.
        state = make_state(inventory={"copper_ore": 10}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            # CraftAction for copper_bar intentionally omitted.
            CraftAction(code="copper_ring", workshop_location=(3, 1)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None


# ---------------------------------------------------------------------------
# Integration tests through StrategyArbiter._plans
# ---------------------------------------------------------------------------

class TestStrategyArbiterIntegration:
    """_plans should use the generator for copper_ring (nodes==0) and fall back
    to A* for monster-drop goals (planner invoked)."""

    def test_copper_ring_goal_bypasses_planner(self):
        """A copper_ring GatherMaterials goal in _plans records nodes=0 (no A*)."""
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        class _SpyPlanner:
            calls = 0
            class last_stats:
                nodes_explored = 0
                max_depth_reached = 0
                timed_out = False
                node_capped = False
            def plan(self, *args, **kwargs):
                self.__class__.calls += 1
                return []

        spy = _SpyPlanner()
        arbiter = StrategyArbiter(spy, history=None)
        plan = arbiter._plans(goal, state, gd, actions, _ctx())

        assert plan, "Expected a non-empty generated plan"
        assert _SpyPlanner.calls == 0, "Planner must NOT be invoked for copper_ring goal"
        assert arbiter.goals_tried[-1]["nodes"] == 0
        # Full deterministic plan: first step gathers ore, last step crafts the ring.
        assert isinstance(plan[0], GatherAction)
        assert isinstance(plan[-1], CraftAction) and plan[-1].code == "copper_ring"

    def test_monster_drop_goal_invokes_planner(self):
        """A feather_coat goal (monster-drop leaf) must invoke the planner (A*)."""
        gd = _gd_monster_drop()
        state = make_state(inventory={}, bank_items={},
                           skills={"gearcrafting": 5})
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        actions = [CraftAction(code="feather_coat", workshop_location=(3, 1))]

        class _SpyPlanner:
            calls = 0
            class last_stats:
                nodes_explored = 5
                max_depth_reached = 2
                timed_out = False
                node_capped = False
            def plan(self, *args, **kwargs):
                self.__class__.calls += 1
                return []

        spy = _SpyPlanner()
        arbiter = StrategyArbiter(spy, history=None)
        arbiter._plans(goal, state, gd, actions, _ctx())

        assert _SpyPlanner.calls == 1, "Planner must be invoked for monster-drop goal"

    def test_banked_target_still_generates(self) -> None:
        """Banked TARGET (finished output) → generator fires, does NOT fall back.

        Issue #1 regression guard: the old blanket gate fired when copper_ring was
        in the bank, even though copper_ring is the OUTPUT (not an input needing
        withdraw).  The precise gate skips top-level needed keys.

        Setup: needed={copper_ring:2}, bank has copper_ring:1 (one already banked),
        inventory has no ore → generator should emit GatherAction(copper_rocks) to
        make the remaining ring from scratch.
        """
        gd = _gd_copper_ring()
        state = make_state(
            inventory={},
            bank_items={"copper_ring": 1},  # banked TARGET, not an input
            skills={"mining": 5, "jewelrycrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 2})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None, (
            "Banked target (output) must NOT cause A* fallback — "
            "generator should make the remaining quantity from scratch"
        )
        # Full plan re-makes the remaining ring: gather ore first, craft ring last.
        assert isinstance(result[0], GatherAction)
        assert result[0].resource_code == "copper_rocks"
        assert isinstance(result[-1], CraftAction) and result[-1].code == "copper_ring"

    def test_surplus_banked_input_inventory_covers_generates(self) -> None:
        """Surplus banked input but inventory already covers requirement → generates.

        Issue #2 regression guard: the old blanket gate fired when copper_bar was
        in the bank, even when inventory held enough bars to craft the ring without
        any withdraw.

        Setup: inventory={copper_bar:1} (covers 1-ring requirement), bank has an
        extra copper_bar:1 (surplus) → generator emits CraftAction(copper_ring).
        """
        gd = _gd_copper_ring()
        state = make_state(
            inventory={"copper_bar": 1},   # covers the requirement (1 bar per ring)
            bank_items={"copper_bar": 1},  # surplus — no withdraw needed
            skills={"mining": 5, "jewelrycrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None, (
            "Surplus banked input (inventory covers requirement) must NOT cause "
            "A* fallback — no withdraw is needed"
        )
        assert len(result) == 1
        assert isinstance(result[0], CraftAction)
        assert result[0].code == "copper_ring"

    def test_banked_needed_input_inventory_short_falls_back(self) -> None:
        """Banked INPUT genuinely needed (inventory short) → A* fallback.

        Crash-avoidance + correct deferral: copper_bar is an INPUT that must be
        withdrawn before CraftAction can use it.  With 0 bars in inventory and
        the recipe requiring 1 bar per ring, the generator cannot emit a craft
        without a prior withdraw step.  Returning None lets A* emit Withdraw→Craft.
        """
        gd = _gd_copper_ring()
        state = make_state(
            inventory={},              # 0 bars in inventory
            bank_items={"copper_bar": 6},  # bars banked and genuinely needed
            skills={"mining": 5, "jewelrycrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, (
            "Generator must return None (A* fallback) when a banked INPUT is "
            "genuinely needed — A* will emit Withdraw→Craft correctly"
        )

    def test_inventory_material_does_not_fall_back(self) -> None:
        """Bar in INVENTORY (not bank) → generator fires and emits CraftAction.

        Confirms that the bank-fallback guard does not affect the normal
        from-scratch gather→craft case where materials land in inventory.
        """
        gd = _gd_copper_ring()
        state = make_state(inventory={"copper_bar": 1}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        # Bar is in inventory → generator can directly emit CraftAction(copper_ring).
        assert result is not None, "Inventory-held bar must not trigger A* fallback"
        assert isinstance(result[0], CraftAction)
        assert result[0].code == "copper_ring"


# ---------------------------------------------------------------------------
# Intermediate-craft batch sizing in generate_next_craft_action
# ---------------------------------------------------------------------------

def _gd_copper_dagger() -> GameData:
    """copper_dagger → copper_bar:6 (per dagger) → copper_ore:10 (per bar).

    Closure: copper_dagger (craftable, weaponcrafting lv1),
             copper_bar (craftable, mining lv1),
             copper_ore (raw; produced by copper_rocks resource).
    """
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_dagger": {"copper_bar": 6},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._workshop_locations = {"mining": (1, 5), "weaponcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


class TestIntermediateCraftSizedInGenerator:
    """generate_next_craft_action batches intermediate CraftActions to inventory-bounded demand."""

    def test_intermediate_craft_quantity_gt_one_when_multiple_needed(self):
        """copper_dagger needs 6 copper_bars; 60 ore in inventory → plan[0] = CraftAction(copper_bar, qty=6)."""
        gd = _gd_copper_dagger()
        state = make_state(
            inventory={"copper_ore": 60},
            inventory_max=100,
            bank_items={},
            skills={"mining": 5, "weaponcrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_dagger", workshop_location=(3, 1)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None, "expected a plan, not None (A* fallback)"
        assert isinstance(result[0], CraftAction) and result[0].code == "copper_bar", (
            f"expected CraftAction(copper_bar) as first step, got {result[0]}"
        )
        assert result[0].quantity > 1, (
            f"intermediate craft should be batched to demand, "
            f"got quantity={result[0].quantity}"
        )


# ---------------------------------------------------------------------------
# GAP-8: monster-drop leaves get a Fight leg (2026-07-08 live water_bow stall)
# ---------------------------------------------------------------------------

def _gd_drop_leaf(char_beats_chicken: bool = True) -> GameData:
    """feather_coat → feather (monster drop; chicken drops it 1-in-8).

    Same closure shape as _gd_monster_drop but WITH a dropper on file, so
    the goal's relevant_actions can emit the GAP-6-proven dropper Fight.
    `char_beats_chicken=False` makes the chicken unbeatable (hp/attack far
    above the test state's stats) so is_winnable gates the fight out."""
    gd = GameData()
    gd._item_stats = {
        "feather": ItemStats(code="feather", level=1, type_="resource"),
        "feather_coat": ItemStats(
            code="feather_coat", level=5, type_="body_armor",
            crafting_skill="gearcrafting", crafting_level=5,
        ),
    }
    gd._crafting_recipes = {
        "feather_coat": {"feather": 8},
    }
    gd._resource_drops = {}
    gd._workshop_locations = {"gearcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 60 if char_beats_chicken else 99999}
    gd._monster_attack = {"chicken": {"air": 4 if char_beats_chicken else 9999}}
    gd._monster_drops = {"chicken": [("feather", 8, 1, 1)]}
    fill_monster_stat_defaults(gd)
    return gd


def _gd_drop_leaf_suicide_guard() -> GameData:
    """Same recipe/dropper shape as `_gd_drop_leaf`, but the chicken sits 3
    levels above the fighter's level (5+3=8): weak hp/attack keeps it
    stat-winnable (predict_win/is_winnable both True, so
    GatherMaterialsGoal.relevant_actions still emits its Fight), but
    FightAction.is_applicable's level+2 suicide guard (monster_level <=
    char_level + 2) rejects it. `is_winnable` is a stat-only PREDICTION
    blind to that structural gate — reproduces the admit/emit asymmetry
    finding (scratchpad probe arm 1: chicken L8 vs char L5)."""
    gd = _gd_drop_leaf()
    gd._monster_level = {"chicken": 8}
    return gd


def _gd_drop_leaf_suboptimal_loadout() -> GameData:
    """Same recipe/dropper shape as `_gd_drop_leaf`, plus two weapons: a weak
    one (equipped) and a strictly stronger one (owned, unequipped). Chicken's
    resistance is all-zero (fill_monster_stat_defaults), so `pick_loadout`
    unambiguously prefers the higher flat attack `strong_bow` over the
    equipped `weak_stick` — the "dropper is structurally fine, only its
    loadout needs a swap" shape Task 5b Part 2/3 fixes (mirrors
    test_fight_loadout_precondition.py's water_bow/copper_pickaxe fixture)."""
    gd = _gd_drop_leaf()
    gd._item_stats["weak_stick"] = ItemStats(
        code="weak_stick", level=1, type_="weapon", attack={"earth": 2})
    gd._item_stats["strong_bow"] = ItemStats(
        code="strong_bow", level=1, type_="weapon", attack={"air": 10})
    return gd


_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _fighter_state(**overrides):
    """A state whose combat stats beat the harmless chicken (mirrors the
    winnability fixture in test_no_combat_deadlock)."""
    base = dict(
        inventory={}, bank_items={}, skills={"gearcrafting": 5},
        hp=165, max_hp=165, attack={"air": 5}, dmg=18,
    )
    base.update(overrides)
    return make_state(**base)


def _drop_leaf_actions() -> list:
    return [
        CraftAction(code="feather_coat", workshop_location=(3, 1)),
        FightAction(monster_code="chicken", locations=frozenset([(0, 1)])),
    ]


_FEATHER_DROP_SOURCES = {"feather": [Source(SourceKind.DROP, "chicken", 1, 10**9)]}
"""DROP is a SourceKind now: the goal's own `relevant_actions` narrowing
still owns WHICH Fight is admitted (winnable / grey-farm / structurally-
applicable), so this map need only ADMIT the closure — chicken is the only
dropper in every `_gd_drop_leaf*` fixture below."""


class TestDropLeafFightLeg:
    """GAP-8: a monster-drop leaf with a winnable dropper generates a Fight
    leg instead of falling back to the A* flood (live Robby water_bow stall:
    38K nodes/timeout/plan_len 0, 65 cycles of red_slime grinding)."""

    def test_winnable_dropper_returns_fight_leg(self):
        """Empty holdings → the first (and only, one-leg-per-cycle) action
        is the dropper Fight; xp-positive at L5 → the PLAIN fight, not the
        drop_farm variant."""
        gd = _gd_drop_leaf()
        state = _fighter_state()
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})

        result = generate_next_craft_action(goal, state, gd, _drop_leaf_actions(),
                                           _FEATHER_DROP_SOURCES)

        assert result is not None, "winnable dropper must not fall back to A*"
        assert len(result) == 1, result
        assert isinstance(result[0], FightAction)
        assert result[0].monster_code == "chicken"
        assert result[0].drop_farm is False

    def test_fight_leg_truncates_plan(self):
        """A recipe whose FIRST short input is gatherable and whose second
        is a monster drop: the generated plan keeps the deterministic
        gather leg and TRUNCATES at the Fight — a kill's yield is
        stochastic, so the steps after it (the craft) are the next cycle's
        replan, never simulated optimism."""
        gd = _gd_drop_leaf()
        gd._item_stats["ash_wood"] = ItemStats(
            code="ash_wood", level=1, type_="resource")
        gd._crafting_recipes = {
            "feather_coat": {"ash_wood": 2, "feather": 1},
        }
        gd._resource_drops = {"ash_tree": "ash_wood"}
        state = _fighter_state(skills={"gearcrafting": 5, "woodcutting": 1})
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        actions = [
            GatherAction(resource_code="ash_tree", locations=frozenset([(0, 2)])),
            *_drop_leaf_actions(),
        ]

        result = generate_next_craft_action(goal, state, gd, actions,
                                           _FEATHER_DROP_SOURCES)

        assert result is not None
        assert [type(a).__name__ for a in result] == \
            ["GatherAction", "FightAction"], result
        assert not any(isinstance(a, CraftAction) for a in result), (
            "no step may be planned past the stochastic Fight leg", result)

    def test_grey_dropper_reuses_drop_farm_variant(self):
        """At L11 the L1 chicken is GREY (xp_per_kill 0, diff >= 10). The
        goal's relevant_actions routes it through grey_farm_allowed (the
        consuming recipe feather_coat has no higher same-family tier →
        allowed) and emits the drop_farm variant — the generator must reuse
        exactly that emitted fight, drop_farm flag intact."""
        gd = _gd_drop_leaf()
        state = _fighter_state(level=11)
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})

        result = generate_next_craft_action(goal, state, gd, _drop_leaf_actions(),
                                           _FEATHER_DROP_SOURCES)

        assert result is not None, "grey-farm-allowed dropper must generate"
        assert isinstance(result[0], FightAction)
        assert result[0].drop_farm is True

    def test_unwinnable_dropper_returns_none(self):
        """A dropper exists but is_winnable rejects it → relevant_actions
        emits no Fight → the generator falls back to A* honestly (the
        goal's is_plannable owns the pruning)."""
        gd = _gd_drop_leaf(char_beats_chicken=False)
        state = _fighter_state()
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})

        result = generate_next_craft_action(goal, state, gd, _drop_leaf_actions())

        assert result is None, "unwinnable dropper must fall back to A*"

    def test_suicide_guard_dropper_returns_none(self):
        """Admit/emit asymmetry finding: a dropper 3 levels above the
        character is stat-winnable (is_winnable True, so
        relevant_actions emits its Fight) but FightAction.is_applicable's
        level+2 suicide guard rejects it — A* would never plan it, so the
        generator must not emit it either. Pre-fix this returned
        ``[Fight(chicken)]`` even though ``Fight.is_applicable`` was False
        (confirmed via direct probe), which player.py would then execute
        with no separate applicability check."""
        gd = _gd_drop_leaf_suicide_guard()
        state = _fighter_state()
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        actions = _drop_leaf_actions()

        # Sanity: the dropper really is admitted by is_winnable/xp but
        # rejected by is_applicable — otherwise this test would not be
        # exercising the asymmetry at all.
        fight = actions[1]
        assert isinstance(fight, FightAction)
        assert is_winnable(state, gd, "chicken") is True
        assert gd.xp_per_kill("chicken", state.level) > 0
        assert fight.is_applicable(state, gd) is False

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is None, (
            "a stat-winnable dropper that violates the level+2 suicide "
            "guard must fall back to A*, not be emitted as a Fight leg"
        )

    def test_banked_drop_leaf_withdraws_not_fights(self):
        """The live l13 shape in miniature: the drop deficit is covered by
        the BANK, so the core's withdraw arm serves it and no Fight leg is
        needed — the plan is the full deterministic Withdraw → Craft chain,
        untruncated."""
        gd = _gd_drop_leaf()
        state = _fighter_state(bank_items={"feather": 8})
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        actions = [
            *_drop_leaf_actions(),
            WithdrawItemAction(code="feather", quantity=8,
                               bank_location=(4, 0)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions,
                                           _FEATHER_DROP_SOURCES)

        assert result is not None
        assert [type(a).__name__ for a in result] == \
            ["WithdrawItemAction", "CraftAction"], result
        assert result[0].code == "feather" and result[0].quantity == 8
        assert result[-1].code == "feather_coat"


class TestDropLeafSuboptimalLoadoutRearm:
    """Task 5b: `_dropper_fight` (Part 2) admits a structurally-fine dropper
    even when its equipped loadout is suboptimal — the loadout mismatch is a
    SEQUENCING precondition, not infeasibility. `_with_rearm` (Part 3) then
    fronts `OptimizeLoadout(<monster>)` so the fast path never executes a
    suboptimal Fight as plan[0] (mirrors the pre-existing Gather-first
    re-arm). Regression coverage for the L13 water_bow flood (31148 A*
    nodes) this task fixes."""

    def test_suboptimal_loadout_dropper_generates_rearm_then_fight(self):
        """weak_stick equipped, strong_bow owned unequipped: the generator
        must still admit the chicken dropper (not fall back to A*) and the
        generated plan must open with OptimizeLoadout(chicken), Fight(chicken)
        strictly after it — never a bare suboptimal Fight as plan[0]."""
        gd = _gd_drop_leaf_suboptimal_loadout()
        eq = dict(_ALL_SLOTS)
        eq["weapon_slot"] = "weak_stick"
        state = _fighter_state(equipment=eq, inventory={"strong_bow": 1})
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        actions = _drop_leaf_actions()

        # Sanity: the exact admit/emit shape this task fixes — structurally
        # fine, but is_applicable's loadout gate rejects it.
        fight = actions[1]
        assert isinstance(fight, FightAction)
        assert fight._structurally_applicable(state, gd) is True
        assert fight.is_applicable(state, gd) is False

        result = generate_next_craft_action(goal, state, gd, actions,
                                           _FEATHER_DROP_SOURCES)

        assert result is not None, (
            "a structurally-fine dropper with only a loadout mismatch must "
            "not fall back to A*"
        )
        assert [type(a).__name__ for a in result] == \
            ["OptimizeLoadoutAction", "FightAction"], result
        rearm, fought = result
        assert isinstance(rearm, OptimizeLoadoutAction)
        assert rearm.target_monster_code == "chicken"
        assert fought.monster_code == "chicken"
        # The fronted rearm must itself be applicable NOW — the generator's
        # own post-hoc plan[0].is_applicable check (generate_next_craft_action)
        # would otherwise silently discard this plan and fall back to A*.
        assert rearm.is_applicable(state, gd) is True

    def test_optimal_loadout_dropper_generates_fight_only(self):
        """strong_bow already equipped -> no rearm is fronted; matches the
        pre-existing test_winnable_dropper_returns_fight_leg shape."""
        gd = _gd_drop_leaf_suboptimal_loadout()
        eq = dict(_ALL_SLOTS)
        eq["weapon_slot"] = "strong_bow"
        state = _fighter_state(equipment=eq, inventory={})
        goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
        actions = _drop_leaf_actions()

        fight = actions[1]
        assert isinstance(fight, FightAction)
        assert fight.is_applicable(state, gd) is True

        result = generate_next_craft_action(goal, state, gd, actions,
                                           _FEATHER_DROP_SOURCES)

        assert result is not None
        assert [type(a).__name__ for a in result] == ["FightAction"], result
        assert result[0].monster_code == "chicken"


# ---------------------------------------------------------------------------
# THE RECYCLE ROUTE (recycle-as-acquisition epic, Task 8).
#
# The generator fires on exactly the deterministic gather-craft closure the epic
# targets, so a generator with no Recycle leg silently OUT-RAN the A* that knew
# about the route: it chopped ash_wood while the bag held bows whose recipe IS
# ash_plank. Found by the recycle-source census (audit/recycle_source_
# completeness.py), which drives the real StrategyArbiter.select seam.
#
# The RecycleActions handed in here stand for the LICENSED pool: production
# filters it at `StrategyArbiter.select` (license_destructive_actions), so a
# protected source simply HAS no RecycleAction — which is why the "unlicensed"
# test below passes no Recycle at all rather than expecting the generator to
# re-derive a protection rule it must never own.
# ---------------------------------------------------------------------------

def _gd_recyclable() -> GameData:
    """copper_bar ← 10 copper_ore, and a copper_dagger (weapon) whose recipe is
    6 copper_bar — so ONE unit recycle recovers max(1, 6 // 2) = 3 bars."""
    gd = _gd_copper_ring()
    gd._item_stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=1)
    gd._item_stats["iron_dagger"] = ItemStats(
        code="iron_dagger", level=10, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=10)
    gd._crafting_recipes["copper_dagger"] = {"copper_bar": 6}
    gd._crafting_recipes["iron_dagger"] = {"copper_bar": 6}
    gd._workshop_locations["weaponcrafting"] = (2, 2)
    return gd


def _bar_actions(*extra) -> list:
    return [
        GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
        CraftAction(code="copper_bar", workshop_location=(1, 5)),
        WithdrawItemAction(code="copper_bar", quantity=10, bank_location=(4, 0),
                           accessible=True),
        WithdrawItemAction(code="copper_dagger", quantity=1, bank_location=(4, 0),
                           accessible=True),
        *extra,
    ]


class TestRecycleAsASource:
    def test_bag_surplus_is_recycled_instead_of_gathered(self):
        """3 copper_bar needed, a spare copper_dagger in the bag: ONE recycle
        recovers exactly 3 bars, so the plan must dismantle it rather than mine
        30 copper_ore. `sources` stands in for what `obtain_source_map` would
        derive from the licensed RecycleAction pool."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 1}, bank_items={},
                           skills={"mining": 5, "weaponcrafting": 5})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})
        actions = _bar_actions(RecycleAction(code="copper_dagger", quantity=1,
                                             workshop_location=(2, 2)))
        sources = {"copper_bar": [Source(SourceKind.RECYCLE, "copper_dagger", 3, 3)]}

        result = generate_next_craft_action(goal, state, gd, actions, sources)

        assert result is not None
        assert [type(a).__name__ for a in result] == ["RecycleAction"], result
        assert result[0].code == "copper_dagger"

    def test_an_unlicensed_source_is_never_recycled(self):
        """The keep authority protects the last copper_dagger, so production's
        licence leaves NO RecycleAction in the pool. The generator must gather —
        it may only ever take a recycle the authority already handed it."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 1}, bank_items={},
                           skills={"mining": 5, "weaponcrafting": 5})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})

        result = generate_next_craft_action(goal, state, gd, _bar_actions())

        assert result is not None
        assert isinstance(result[0], GatherAction)

    def test_a_bank_only_source_falls_back_to_gathering(self):
        """The surplus lives ONLY in the bank (where DEPOSIT_FULL puts it).

        Staging a bank-held recycle SOURCE (Withdraw the source, then recycle
        it) is a capability the pre-Task-4 `_recycle_prefix`/`_staging_withdraw`
        bolt-on had that the shared model
        (`next_craft_core`/`craft_plan_driver_core`, Tasks 1-3) does not
        reproduce: `_step_for`'s RECYCLE arm reads only the CURRENT BAG stock
        of the source item (`owned.get(src.code, 0)`), never the bank, and the
        descent never recurses into "obtain more of the recycle source" the
        way it recurses into a craft recipe's own inputs. With 0 bag copies of
        copper_dagger the RECYCLE source yields nothing right now, so the
        descent correctly falls through to CRAFT -> gather/craft -- a
        CORRECT, if less economical, plan. (A* -- which this generator
        preempts -- still has its own Withdraw+Recycle actions in its pool and
        can find the staged route if this fast path declines; that residual
        gap is a known narrowing, not a safety issue.)"""
        gd = _gd_recyclable()
        state = make_state(inventory={}, bank_items={"copper_dagger": 2},
                           skills={"mining": 5, "weaponcrafting": 5})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})
        actions = _bar_actions(RecycleAction(code="copper_dagger", quantity=1,
                                             workshop_location=(2, 2)))
        sources = {"copper_bar": [Source(SourceKind.RECYCLE, "copper_dagger", 3, 6)]}

        result = generate_next_craft_action(goal, state, gd, actions, sources)

        assert result is not None
        assert not any(isinstance(a, RecycleAction) for a in result), result
        assert isinstance(result[0], GatherAction), result

    def test_the_bag_floor_defers_to_a_star_rather_than_eat_the_working_copy(self):
        """One copy in the bag is the WORKING one (bag_floor=1) and two sit in
        the bank. The descent's RECYCLE arm reads only raw bag QUANTITY
        (`owned.get(src.code, 0)`), blind to `bag_floor` -- it proposes
        recycling the one bag copy. But that proposal IS the whole plan
        (one recycle fully covers the 3-bar demand), so the SAFETY NET (the
        first-leg `is_applicable` gate every generated plan is gated on) is
        asked of the CONCRETE `RecycleAction(bag_floor=1)` and correctly
        refuses it (the bag copy can't drop below its floor) -- the whole
        plan is discarded and the generator defers to A*, which sequences
        Withdraw(bank copy) -> Recycle instead of ever touching the working
        tool. Safety holds; the fast path merely declines here (a known
        narrowing -- see `test_a_bank_only_source_falls_back_to_gathering`)."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 1},
                           bank_items={"copper_dagger": 2},
                           skills={"mining": 5, "weaponcrafting": 5})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})
        actions = _bar_actions(RecycleAction(code="copper_dagger", quantity=1,
                                             workshop_location=(2, 2),
                                             bag_floor=1))
        sources = {"copper_bar": [Source(SourceKind.RECYCLE, "copper_dagger", 3, 9)]}

        result = generate_next_craft_action(goal, state, gd, actions, sources)

        assert result is None, (
            "the bag-floor-protected copy must never be recycled; the "
            "generator must defer to A* rather than propose it"
        )

    def test_the_owned_floor_protects_the_first_leg_the_runtime_net_protects_the_rest(self):
        """PARTIAL PROTECTION (whole-branch review, CRITICAL 1) -- re-verified
        under the shared model, where it holds for a DIFFERENT reason.

        Two copper_daggers in the bag with `destroyable == 1` (the licence
        stamps `owned_floor=1`): 6 bars are needed and each dagger recovers 3.
        `next_craft_core._step_for`'s RECYCLE arm bounds a SINGLE step by the
        CURRENT bag quantity (`owned.get(src.code, 0) * yield_per`), which is
        blind to `owned_floor` -- across the two internal descent steps this
        single `craft_plan_full` call takes, it proposes recycling BOTH
        copies (a residual gap in the already-landed shared model: `capacity`
        is a one-shot snapshot, not decremented across steps within one call;
        confirmed empirically, out of Task 4's scope to fix). Only ONE of
        those two proposed legs is ever the returned plan's FIRST element,
        and the safety net is anchored there: `is_applicable` on the
        CONCRETE RecycleAction is checked before this plan is even returned
        (still True -- one recycle from 2 owned copies never violates
        owned_floor=1), and -- if this simulated plan's second Recycle were
        ever reached -- the SAME per-cycle `is_applicable` re-validation
        (`should_replan`, `player.py`) would refuse it against the REAL
        post-first-recycle state (1 owned copy, owned_floor=1 => refused),
        forcing a replan instead of ever destroying the licence-protected
        second copy. The licence is enforced at EXECUTION, never at
        generation."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 2}, bank_items={},
                           skills={"mining": 5, "weaponcrafting": 5},
                           inventory_max=200, inventory_slots_max=30)
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 6})
        actions = _bar_actions(RecycleAction(code="copper_dagger", quantity=1,
                                             workshop_location=(2, 2),
                                             owned_floor=1))
        sources = {"copper_bar": [Source(SourceKind.RECYCLE, "copper_dagger", 3, 3)]}

        result = generate_next_craft_action(goal, state, gd, actions, sources)

        assert result is not None
        assert isinstance(result[0], RecycleAction)
        assert result[0].is_applicable(state, gd) is True, (
            "the FIRST leg is the one safety guarantee this generator itself "
            "owns -- it must never violate owned_floor"
        )
        # The simulated remainder MAY over-propose (the residual gap above);
        # the runtime per-cycle re-check -- not this generator -- is what
        # stops a second illegal recycle from ever executing.
        second_recycle = next(
            (a for a in result[1:] if isinstance(a, RecycleAction)), None)
        if second_recycle is not None:
            assert second_recycle.is_applicable(
                dataclasses.replace(state, inventory={"copper_dagger": 1}), gd
            ) is False, "a second recycle must be refused once only 1 copy remains"

    def test_the_goals_own_target_is_never_recycled_for_its_own_parts(self):
        """STRUCTURAL exclusion (whole-branch review, MINOR 4). The goal needs 5
        copper_rings and holds 2 spares; `Recycle(copper_ring)` recovers
        copper_bar — a genuine deficit — so `_best_recycle` would pick it and plan
        `Recycle(copper_ring) -> Craft(copper_ring)`: destroy a ring to get back
        HALF of its own inputs. Only the keep reasons driving `destroyable` to 0
        prevented it, which is incidental. The source must not be in the goal's
        closure, full stop."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_ring": 2}, bank_items={},
                           skills={"mining": 5, "weaponcrafting": 5,
                                   "jewelrycrafting": 5},
                           inventory_max=200, inventory_slots_max=30)
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 5})
        actions = [
            GatherAction(resource_code="copper_rocks",
                         locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_ring", workshop_location=(3, 1)),
            RecycleAction(code="copper_ring", quantity=1,
                          workshop_location=(3, 1)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert not any(isinstance(a, RecycleAction) for a in result), result
        assert isinstance(result[0], GatherAction), result

    def test_a_partial_recovery_comes_out_as_ONE_mixed_plan(self):
        """6 bars needed, one dagger recovers 3: the plan recycles for what it
        can and GATHERS the rest — the mixed plan A* cannot find within budget."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 1}, bank_items={},
                           skills={"mining": 5, "weaponcrafting": 5},
                           inventory_max=200, inventory_slots_max=30)
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 6})
        actions = _bar_actions(RecycleAction(code="copper_dagger", quantity=1,
                                             workshop_location=(2, 2)))
        sources = {"copper_bar": [Source(SourceKind.RECYCLE, "copper_dagger", 3, 3)]}

        result = generate_next_craft_action(goal, state, gd, actions, sources)

        assert result is not None
        kinds = [type(a).__name__ for a in result]
        assert kinds[0] == "RecycleAction"
        assert "GatherAction" in kinds and "CraftAction" in kinds, result

    def test_nothing_is_recycled_when_the_material_is_already_owned(self):
        """The demand is covered by OWNED stock (bag+bank), so the character is
        short of nothing: destroying an item to duplicate what it already owns
        would be pure loss. The prefix stops before it starts."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 1},
                           bank_items={"copper_bar": 10},
                           skills={"mining": 5, "weaponcrafting": 5})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})
        actions = _bar_actions(RecycleAction(code="copper_dagger", quantity=1,
                                             workshop_location=(2, 2)))

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert not any(isinstance(a, RecycleAction) for a in result), result

    def test_the_generator_takes_the_first_source_the_model_offers(self):
        """Two sources could each serve the 3-bar deficit; the generator
        itself applies NO ranking of its own — it takes the FIRST applicable
        source in `sources`' priority order (next_craft_core._next), exactly
        the order `obtain_source_map` built it in. Semantic ranking of WHICH
        source is cheapest to sacrifice (yield, level, waste — never a name
        sort, per feedback_no_alphabetical_tiebreak) is `obtain_sources`'
        responsibility (Tasks 1-3), not this generator's; this test pins
        only the generator's own contract: first-in-list wins."""
        gd = _gd_recyclable()
        state = make_state(inventory={"iron_dagger": 1, "copper_dagger": 1},
                           bank_items={},
                           skills={"mining": 5, "weaponcrafting": 15})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})
        actions = _bar_actions(
            RecycleAction(code="iron_dagger", quantity=1,
                          workshop_location=(2, 2)),
            RecycleAction(code="copper_dagger", quantity=1,
                          workshop_location=(2, 2)))
        sources = {"copper_bar": [
            Source(SourceKind.RECYCLE, "copper_dagger", 3, 3),
            Source(SourceKind.RECYCLE, "iron_dagger", 3, 3),
        ]}

        result = generate_next_craft_action(goal, state, gd, actions, sources)

        assert result is not None
        assert result[0].code == "copper_dagger", result

    def test_a_bank_source_with_no_withdraw_leg_falls_back_to_gathering(self):
        """No Withdraw for the source in the menu → the recycle has no first leg,
        so the prefix stops and the recipe descent answers alone."""
        gd = _gd_recyclable()
        state = make_state(inventory={}, bank_items={"copper_dagger": 2},
                           skills={"mining": 5, "weaponcrafting": 5})
        goal = GatherMaterialsGoal("copper_bar", {"copper_bar": 3})
        actions = [
            GatherAction(resource_code="copper_rocks",
                         locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            RecycleAction(code="copper_dagger", quantity=1,
                          workshop_location=(2, 2)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert isinstance(result[0], GatherAction)

    def test_a_source_that_serves_no_deficit_is_left_alone(self):
        """The dagger's only output (copper_bar) is already covered by the bank,
        so recycling it would buy the plan nothing. The menu still OFFERS it (its
        recipe intersects the closure) — the prefix declines."""
        gd = _gd_recyclable()
        state = make_state(inventory={"copper_dagger": 1},
                           bank_items={"copper_bar": 10},
                           skills={"mining": 5, "weaponcrafting": 5,
                                   "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = [
            GatherAction(resource_code="copper_rocks",
                         locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_ring", workshop_location=(3, 1)),
            WithdrawItemAction(code="copper_bar", quantity=1,
                               bank_location=(4, 0), accessible=True),
            RecycleAction(code="copper_dagger", quantity=1,
                          workshop_location=(2, 2)),
        ]

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert not any(isinstance(a, RecycleAction) for a in result), result
        assert [type(a).__name__ for a in result] == [
            "WithdrawItemAction", "CraftAction"], result


# ---------------------------------------------------------------------------
# THE ACTIVATION (Task 4): the generator reads THE ONE OBTAIN MODEL via a
# `sources` map instead of the four hand-bolted routes (_recycle_prefix,
# drop_fights, the LevelSkill early-return, the NPC-buy decline). These two
# tests are the ones that started the whole epic.
# ---------------------------------------------------------------------------

def _gd_fire_staff() -> GameData:
    """fire_staff (weaponcrafting lv1) needs 5 ash_plank. ash_plank is a raw
    gatherable (ash_tree). fishing_net (a bag, weaponcrafting lv1) is made
    from 6 ash_plank each -- so ONE unit recycle recovers max(1, 6 // 2) = 3
    planks. The bag holds 7 spare fishing_nets."""
    gd = GameData()
    gd._item_stats = {
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        "fire_staff": ItemStats(
            code="fire_staff", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1),
        "fishing_net": ItemStats(
            code="fishing_net", level=1, type_="bag",
            crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "fire_staff": {"ash_plank": 5},
        "fishing_net": {"ash_plank": 6},
    }
    gd._resource_drops = {"ash_tree": "ash_plank"}
    gd._workshop_locations = {"weaponcrafting": (2, 2)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    fill_monster_stat_defaults(gd)
    return gd


class TestTheActivationRecycleBug:
    """THE BUG that started the whole epic: the generator planned
    Gather(ash_tree) -- 50 gathers of WOODCUTTING xp -- because its recipe
    descent could not express a recycle, even while the bag held 7
    fishing_nets whose recipe IS ash_plank. It must now emit a Recycle leg
    from the SHARED model, with no `_recycle_prefix` in existence."""

    def test_generator_recycles_instead_of_chopping(self):
        gd = _gd_fire_staff()
        state = make_state(inventory={"fishing_net": 7}, bank_items={},
                           skills={"weaponcrafting": 5})
        goal = GatherMaterialsGoal("fire_staff", {"fire_staff": 1})
        pool = [
            GatherAction(resource_code="ash_tree", locations=frozenset([(0, 1)])),
            CraftAction(code="fire_staff", workshop_location=(2, 2)),
            RecycleAction(code="fishing_net", quantity=1, workshop_location=(2, 2)),
        ]
        sources = {"ash_plank": [Source(SourceKind.RECYCLE, "fishing_net", 3, 21)]}

        plan = generate_next_craft_action(goal, state, gd, pool, sources)

        assert plan is not None
        assert any(isinstance(a, RecycleAction) for a in plan), plan
        assert not any(
            isinstance(a, GatherAction) and a.resource_code == "ash_tree"
            for a in plan
        ), plan


def _gd_widget_buy() -> GameData:
    """widget (gearcrafting lv1) needs 3 widget_part -- a raw leaf with no
    recipe and no resource drop, sold ONLY by a permanent, reachable NPC."""
    gd = GameData()
    gd._item_stats = {
        "widget_part": ItemStats(code="widget_part", level=1, type_="resource"),
        "widget": ItemStats(
            code="widget", level=1, type_="ring",
            crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"widget": {"widget_part": 3}}
    gd._resource_drops = {}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._npc_stock = {"merchant": {"widget_part": 5}}
    gd._npc_locations = {"merchant": (3, 3)}
    fill_monster_stat_defaults(gd)
    return gd


class TestTheActivationNpcBuy:
    """A permanent-vendor leaf used to force a hand-rolled `return None`
    decline (NPC-buy wasn't modeled at all). BUY is a SourceKind now."""

    def test_npc_buy_no_longer_declines_to_a_star(self):
        gd = _gd_widget_buy()
        state = make_state(inventory={}, bank_items={},
                           skills={"gearcrafting": 5})
        goal = GatherMaterialsGoal("widget", {"widget": 1})
        pool = [
            CraftAction(code="widget", workshop_location=(2, 2)),
            NpcBuyAction(npc_code="merchant", item_code="widget_part",
                        quantity=1, npc_location=(3, 3)),
        ]
        sources = {"widget_part": [Source(SourceKind.BUY, "merchant", 1, 10**9)]}

        plan = generate_next_craft_action(goal, state, gd, pool, sources)

        assert plan is not None
        assert any(isinstance(a, NpcBuyAction) for a in plan), plan


class TestMapNextActionMissingConcreteAction:
    """`_map_next_action`'s per-kind "the model named a source but the licensed
    pool has no concrete action to serve it" → None branches. These are the
    admit/emit divergence the parity census targets: the source map may name a
    RECYCLE/BUY/DROP route the goal's own `relevant_actions` (licence-filtered)
    did not surface an action for, and the generator must decline (→ A*), never
    fabricate a leg. Exercised directly since through the full generator the
    same map drives both the step and the mapping, so they never disagree."""

    def test_recycle_step_with_no_matching_source_returns_none(self):
        """A recycle NextAction whose `code` names no RECYCLE Source in the map
        → the yield_per lookup fails → None (line: `match is None`)."""
        gd = _gd_recyclable()
        na = NextAction("copper_bar", "recycle", 3, "copper_dagger")
        assert _map_next_action(na, [], gd, {}) is None

    def test_recycle_step_source_present_but_no_action_returns_none(self):
        """The RECYCLE Source exists (yield_per resolves) but the licensed pool
        has no matching RecycleAction → None (the licence stripped it)."""
        gd = _gd_recyclable()
        na = NextAction("copper_bar", "recycle", 3, "copper_dagger")
        sources = {"copper_bar": [Source(SourceKind.RECYCLE, "copper_dagger", 3, 9)]}
        # relevant pool has NO RecycleAction(copper_dagger).
        assert _map_next_action(na, [], gd, sources) is None

    def test_buy_step_with_no_matching_action_returns_none(self):
        """A buy NextAction with no matching NpcBuyAction in the pool → None."""
        gd = _gd_copper_ring()
        na = NextAction("widget_part", "buy", 1, "merchant")
        assert _map_next_action(na, [], gd, {}) is None

    def test_drop_step_with_no_matching_fight_returns_none(self):
        """A drop NextAction whose dropper has no FightAction in the pool → None."""
        gd = _gd_drop_leaf()  # chicken drops feather
        na = NextAction("feather", "drop", 1, "chicken")
        assert _map_next_action(na, [], gd, {}) is None
