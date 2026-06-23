"""Tests for the craft-plan generator (Task 4 of next-craft-action generator).

Covers:
- copper_ring-style all-gatherable closure → generator returns GatherAction or CraftAction
- monster-drop leaf → returns None (A* fallback)
- unmet skill gate → returns None (A* fallback)
- non-GatherMaterialsGoal → returns None
- all-satisfied (owned>=qty) → returns None
- Integration through StrategyArbiter._plans: generator path records nodes==0;
  monster-drop goal still routes to A* (planner invoked).
"""

import pytest

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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

        assert result is not None, "Expected a gather action, not None (A* fallback)"
        assert len(result) == 1
        assert isinstance(result[0], GatherAction)
        assert result[0].resource_code == "copper_rocks"

    def test_returns_craft_bar_when_ore_present(self):
        """10 copper_ore owned → next step is craft copper_bar."""
        gd = _gd_copper_ring()
        state = make_state(inventory={"copper_ore": 10}, bank_items={},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], CraftAction)
        assert result[0].code == "copper_bar"

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
            def plan(self, *args, **kwargs):
                self.__class__.calls += 1
                return []

        spy = _SpyPlanner()
        arbiter = StrategyArbiter(spy, history=None)
        plan = arbiter._plans(goal, state, gd, actions)

        assert plan, "Expected a non-empty generated plan"
        assert _SpyPlanner.calls == 0, "Planner must NOT be invoked for copper_ring goal"
        assert arbiter.goals_tried[-1]["nodes"] == 0
        assert len(plan) == 1
        assert isinstance(plan[0], GatherAction)

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
            def plan(self, *args, **kwargs):
                self.__class__.calls += 1
                return []

        spy = _SpyPlanner()
        arbiter = StrategyArbiter(spy, history=None)
        arbiter._plans(goal, state, gd, actions)

        assert _SpyPlanner.calls == 1, "Planner must be invoked for monster-drop goal"

    def test_bank_items_count_toward_owned(self):
        """Bar in bank (not inventory) still satisfies the bar need → craft ring."""
        gd = _gd_copper_ring()
        state = make_state(inventory={}, bank_items={"copper_bar": 1},
                           skills={"mining": 5, "jewelrycrafting": 5})
        goal = GatherMaterialsGoal("copper_ring", {"copper_ring": 1})
        actions = _copper_ring_actions()

        result = generate_next_craft_action(goal, state, gd, actions)

        # Bar is in bank → owned["copper_bar"]=1, so next step is craft ring.
        assert result is not None
        assert isinstance(result[0], CraftAction)
        assert result[0].code == "copper_ring"
