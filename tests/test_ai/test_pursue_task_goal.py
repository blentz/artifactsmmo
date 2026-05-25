"""Tests for PursueTaskGoal — the items-task PURSUE actuator."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.pursue_task import PRIORITY_WHEN_FIRING, PursueTaskGoal
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

    def test_max_depth(self):
        assert PursueTaskGoal("copper_bar", 0).max_depth == 100

    def test_relevant_actions_keep_produce_and_trade_drop_combat(self):
        g = PursueTaskGoal("copper_bar", 0)
        actions = [
            GatherAction(resource_code="copper_ore", locations=frozenset({(0, 0)})),
            CraftAction(code="copper_bar", workshop_location=(0, 0)),
            TaskTradeAction(code="copper_bar", quantity=1, taskmaster_location=(1, 2)),
            RestAction(),
            FightAction(monster_code="chicken", locations=frozenset({(0, 0)})),
        ]
        kept = g.relevant_actions(actions, _items_task(), GameData())
        kept_types = {type(a).__name__ for a in kept}
        assert "GatherAction" in kept_types
        assert "CraftAction" in kept_types
        assert "TaskTradeAction" in kept_types
        assert "RestAction" in kept_types
        assert "FightAction" not in kept_types
