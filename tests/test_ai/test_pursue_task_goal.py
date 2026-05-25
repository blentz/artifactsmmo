"""Tests for PursueTaskGoal — the items-task PURSUE actuator."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.pursue_task import PRIORITY_WHEN_FIRING, PursueTaskGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _items_task(progress=0, total=20):
    return make_state(task_code="copper_bar", task_type="items",
                      task_progress=progress, task_total=total)


class TestPursueTaskGoal:
    def test_repr(self):
        assert repr(PursueTaskGoal("copper_bar", 0)) == "PursueTask(copper_bar)"

    def test_value_fires_when_unsatisfied(self):
        g = PursueTaskGoal("copper_bar", 0)
        assert g.value(_items_task(progress=0), GameData()) == PRIORITY_WHEN_FIRING

    def test_value_zero_when_satisfied(self):
        g = PursueTaskGoal("copper_bar", 0)
        assert g.value(_items_task(progress=20), GameData()) == 0.0

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

    def test_is_satisfied_unaffected_by_batch(self):
        g = PursueTaskGoal("copper_bar", 5, batch=9)
        assert not g.is_satisfied(_items_task(progress=5))   # stalled
        assert g.is_satisfied(_items_task(progress=6))        # any advance trips it

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
