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

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.combat import is_winnable
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
        plan = arbiter._plans(goal, state, gd, actions)

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
        arbiter._plans(goal, state, gd, actions)

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

        result = generate_next_craft_action(goal, state, gd, _drop_leaf_actions())

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

        result = generate_next_craft_action(goal, state, gd, actions)

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

        result = generate_next_craft_action(goal, state, gd, _drop_leaf_actions())

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

        result = generate_next_craft_action(goal, state, gd, actions)

        assert result is not None
        assert [type(a).__name__ for a in result] == \
            ["WithdrawItemAction", "CraftAction"], result
        assert result[0].code == "feather" and result[0].quantity == 8
        assert result[-1].code == "feather_coat"
