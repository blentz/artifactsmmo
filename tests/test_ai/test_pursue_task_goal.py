"""Tests for PursueTaskGoal — the items-task PURSUE actuator."""

import os
import tempfile

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.pursue_task import (
    PRIORITY_FLOOR,
    PursueTaskGoal,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _items_task(progress=0, total=20):
    return make_state(task_code="copper_bar", task_type="items",
                      task_progress=progress, task_total=total)


class TestPursueTaskGoal:
    def test_repr(self):
        assert repr(PursueTaskGoal("copper_bar", 0)) == "PursueTask(copper_bar)"

    def test_serialize(self):
        g = PursueTaskGoal("copper_bar", initial_progress=3, batch=5)
        d = g.serialize()
        assert d == {"type": "PursueTaskGoal", "task_code": "copper_bar",
                     "initial_progress": 3, "batch": 5}

    def test_value_fires_when_unsatisfied(self):
        g = PursueTaskGoal("copper_bar", 0)
        assert g.value(_items_task(progress=0), GameData()) == PRIORITY_FLOOR

    def test_value_zero_when_satisfied(self):
        g = PursueTaskGoal("copper_bar", 0)
        assert g.value(_items_task(progress=20), GameData()) == 0.0

    def test_value_with_history_clamps_to_band(self):
        """An unsatisfied goal evaluated WITH a (cold) learning store routes
        the scalar-yield bonus through the band clamp; a cold goal yields the
        PRIORITY_FLOOR (line 62-64), staying inside the discretionary band."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        try:
            store = LearningStore(db_path=path, character="testchar")
            store.start_session()
            g = PursueTaskGoal("copper_bar", 0)
            value = g.value(_items_task(progress=0), GameData(), history=store)
            # Cold store -> no yield samples -> clamp returns the floor exactly.
            assert value == float(PRIORITY_FLOOR)
            store.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_desired_state_is_one_more_unit(self):
        g = PursueTaskGoal("copper_bar", 5)
        assert g.desired_state(_items_task(progress=5), GameData()) == {"task_progress": 6}

    def test_satisfied_when_full(self):
        assert PursueTaskGoal("copper_bar", 0).is_satisfied(_items_task(progress=20))

    def test_satisfied_when_task_gone(self):
        assert PursueTaskGoal("copper_bar", 0).is_satisfied(make_state(task_code=None, task_total=0))

    def test_satisfied_when_progress_advanced(self):
        assert PursueTaskGoal("copper_bar", 5).is_satisfied(_items_task(progress=6))

    def test_not_satisfied_while_stalled(self):
        assert not PursueTaskGoal("copper_bar", 5).is_satisfied(_items_task(progress=5))

    def test_batch_defaults_to_one(self):
        g = PursueTaskGoal("copper_bar", 5)
        assert g.desired_state(_items_task(progress=5), GameData()) == {"task_progress": 6}

    def test_desired_state_reflects_batch(self):
        g = PursueTaskGoal("copper_bar", 5, batch=9)
        assert g.desired_state(_items_task(progress=5), GameData()) == {"task_progress": 14}

    def test_is_satisfied_requires_full_batch(self):
        g = PursueTaskGoal("copper_bar", 5, batch=9)
        assert not g.is_satisfied(_items_task(progress=5))   # stalled
        assert not g.is_satisfied(_items_task(progress=6))   # partial advance not enough
        assert g.is_satisfied(_items_task(progress=14))      # exactly batch units delivered

    def test_max_depth(self):
        assert PursueTaskGoal("copper_bar", 0).max_depth == 100

    def _closure_gd(self):
        # copper_bar is crafted from copper_ore; copper_ore drops from copper_rocks.
        gd = GameData()
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 6}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        return gd

    def test_relevant_actions_keep_produce_and_trade_drop_combat(self):
        g = PursueTaskGoal("copper_bar", 0)
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset({(0, 0)})),
            CraftAction(code="copper_bar", workshop_location=(0, 0)),
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(1, 2)),
            RestAction(),
            FightAction(monster_code="chicken", locations=frozenset({(0, 0)})),
        ]
        kept = g.relevant_actions(actions, _items_task(), self._closure_gd())
        kept_types = {type(a).__name__ for a in kept}
        assert "GatherAction" in kept_types
        assert "CraftAction" in kept_types
        assert "TaskTradeAction" in kept_types
        assert "RestAction" in kept_types       # recovery is supporting
        assert "FightAction" not in kept_types

    def test_relevant_actions_scopes_to_recipe_closure(self):
        """Regression: unbounded gather/craft made the planner explode to a
        timeout (no_plan). Only the task item's recipe closure + its TaskTrade
        survive; unrelated gathers/crafts and a wrong-code TaskTrade are dropped."""
        g = PursueTaskGoal("copper_bar", 0)
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset({(0, 0)})),  # in-closure
            GatherAction(resource_code="iron_rocks", locations=frozenset({(0, 0)})),    # unrelated
            CraftAction(code="copper_bar", workshop_location=(0, 0)),                   # in-closure
            CraftAction(code="cooked_gudgeon", workshop_location=(0, 0)),               # unrelated
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(1, 2)), # task item
            TaskTradeAction(code="iron_bar", quantity=1, taskmaster_location=(1, 2)),   # wrong item
        ]
        kept = g.relevant_actions(actions, _items_task(), self._closure_gd())
        gathered = {a.resource_code for a in kept if isinstance(a, GatherAction)}
        crafted = {a.code for a in kept if isinstance(a, CraftAction)}
        traded = {a.code for a in kept if isinstance(a, TaskTradeAction)}
        assert gathered == {"copper_rocks"}
        assert crafted == {"copper_bar"}
        assert traded == {"copper_bar"}

    def _two_level_gd(self):
        """ashwood_staff <- ash_plank (intermediate) <- ash_wood (drop of ash_tree)."""
        gd = GameData()
        gd._crafting_recipes = {
            "ashwood_staff": {"ash_plank": 1},
            "ash_plank": {"ash_wood": 2},
        }
        gd._resource_drops = {"ash_tree": "ash_wood"}
        return gd

    def test_relevant_actions_sizes_intermediate_craft_to_batch(self):
        """Intermediate crafts (not the task item itself) are sized by
        size_intermediate_craft to inventory-bounded closure demand, not
        left at quantity=1.  Regression guard for Task-4 (intermediate-craft
        batching).

        Setup: ashwood_staff <- ash_plank <- ash_wood; batch=3; empty inventory.
        Expected ash_plank quantity:
          demand = 3  (closure_demand("ashwood_staff", 3) → ash_plank: 3)
          mats_per_unit = 2  (2 ash_wood per ash_plank)
          fit = (inventory_free=20 + held_recipe=0 − 3) // 2 = 8
          result = max(1, min(3, 8, 10)) = 3
        """
        gd = self._two_level_gd()
        batch = 3
        state = make_state(
            task_code="ashwood_staff", task_type="items",
            task_progress=0, task_total=20,
            inventory={}, inventory_max=20,
        )
        g = PursueTaskGoal("ashwood_staff", 0, batch=batch)
        actions = [
            GatherAction(resource_code="ash_tree", locations=frozenset({(0, 0)})),
            CraftAction(code="ash_plank", quantity=1, workshop_location=(0, 0)),
            CraftAction(code="ashwood_staff", quantity=batch, workshop_location=(0, 0)),
            TaskTradeAction(code="ashwood_staff", quantity=batch, taskmaster_location=(1, 2)),
        ]
        kept = g.relevant_actions(actions, state, gd)
        intermediate = next(
            a for a in kept if isinstance(a, CraftAction) and a.code == "ash_plank"
        )
        assert intermediate.quantity == 3

    def test_relevant_actions_includes_withdraw_for_recipe_chain(self):
        """If recipe materials are already in the bank, the planner must be
        able to Withdraw them instead of regathering. Pre-fix, PursueTask's
        relevant_actions silently dropped every WithdrawItemAction so the
        bot ignored its bank entirely — Robby (trace 2026-06-05) had
        cycles of repeated Gather(ash_tree) while the same ash_wood sat
        banked. Withdraw of the task item itself (copper_bar already
        crafted and banked) is also kept."""
        g = PursueTaskGoal("copper_bar", 0)
        gd = self._closure_gd()
        actions = [
            # In-closure raw material (leaf input).
            WithdrawItemAction(code="copper_ore", quantity=1, bank_location=(4, 0)),
            # The task item itself, previously banked.
            WithdrawItemAction(code="copper_bar", quantity=1, bank_location=(4, 0)),
            # Out-of-closure item — must be dropped.
            WithdrawItemAction(code="iron_ore", quantity=1, bank_location=(4, 0)),
        ]
        kept = g.relevant_actions(actions, _items_task(), gd)
        withdraw_codes = {a.code for a in kept if isinstance(a, WithdrawItemAction)}
        assert "copper_ore" in withdraw_codes, (
            "leaf-input withdraw should be allowed so banked mats can be pulled"
        )
        assert "copper_bar" in withdraw_codes, (
            "task-item withdraw should be allowed (banked crafted unit ready for TaskTrade)"
        )
        assert "iron_ore" not in withdraw_codes, (
            "unrelated withdraw must stay filtered to bound planner branching"
        )


class TestPursueTaskPlans:
    """Regression for the production no_plan: with the action scope bounded to
    copper_bar's recipe closure, the planner finds gather->craft->trade instead
    of exploding across every gather/craft in the game and timing out."""

    def _gd(self):
        gd = GameData()
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="weaponcrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 1}}
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        # copper_rocks has no skill gate -> gather applicable with free slots.
        return gd

    def test_planner_finds_plan_amid_unrelated_actions(self):
        gd = self._gd()
        state = make_state(
            task_code="copper_bar", task_type="items", task_progress=0, task_total=20,
            skills={"weaponcrafting": 1}, inventory={}, inventory_max=100,
            x=0, y=0,
        )
        actions = [
            # In-closure path for copper_bar:
            GatherAction(resource_code="copper_rocks", locations=frozenset({(1, 0)})),
            CraftAction(code="copper_bar", workshop_location=(2, 0)),
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(3, 0)),
            # Unrelated noise the old unscoped filter would have branched across:
            GatherAction(resource_code="iron_rocks", locations=frozenset({(5, 5)})),
            GatherAction(resource_code="ash_tree", locations=frozenset({(6, 6)})),
            FightAction(monster_code="chicken", locations=frozenset({(7, 7)})),
            RestAction(),
        ]
        goal = PursueTaskGoal("copper_bar", 0)
        plan = GOAPPlanner().plan(state, goal, actions, gd, None)

        assert plan, "expected a non-empty plan (gather->craft->trade)"
        # The plan must end by delivering the item — that's what advances the task.
        assert isinstance(plan[-1], TaskTradeAction)
        assert plan[-1].code == "copper_bar"

    def test_batched_plan_delivers_many_in_one_trade(self):
        gd = GameData()
        gd._item_stats = {
            "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                    crafting_skill="weaponcrafting", crafting_level=1),
        }
        gd._crafting_recipes = {"copper_bar": {"copper_ore": 1}}   # 1 ore/unit keeps search small
        gd._resource_drops = {"copper_rocks": "copper_ore"}
        state = make_state(
            task_code="copper_bar", task_type="items", task_progress=0, task_total=20,
            skills={"weaponcrafting": 1}, inventory={}, inventory_max=100, x=0, y=0,
        )
        batch = 3
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset({(1, 0)})),
            CraftAction(code="copper_bar", quantity=batch, workshop_location=(2, 0)),
            TaskTradeAction(code="copper_bar", quantity=batch, taskmaster_location=(3, 0)),
            CraftAction(code="copper_bar", quantity=1, workshop_location=(2, 0)),
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(3, 0)),
            GatherAction(resource_code="iron_rocks", locations=frozenset({(9, 9)})),
        ]
        goal = PursueTaskGoal("copper_bar", 0, batch=batch)
        plan = GOAPPlanner().plan(state, goal, actions, gd, None)

        assert plan, "expected a non-empty plan"
        traded = sum(a.quantity for a in plan if isinstance(a, TaskTradeAction))
        assert traded >= batch, "the plan must deliver the whole batch"
        assert any(isinstance(a, TaskTradeAction) and a.quantity == batch for a in plan)
