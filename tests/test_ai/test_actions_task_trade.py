"""Tests for TaskTradeAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._taskmaster_location = kwargs.get("taskmaster_location", (1, 2))
    return gd


class TestTaskTradeAction:
    def test_repr(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        assert repr(a) == "TaskTrade(iron_ore×5)"

    def test_not_applicable_without_items_task(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="iron_ore", task_type="monsters", inventory={"iron_ore": 10})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_task_code_does_not_match(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="copper_ore", task_type="items", inventory={"iron_ore": 10})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_inventory(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="iron_ore", task_type="items", inventory={"iron_ore": 2})
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_matching_items_task_and_inventory(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(task_code="iron_ore", task_type="items", inventory={"iron_ore": 10})
        assert a.is_applicable(state, gd) is True

    def test_apply_decrements_inventory_and_advances_task(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(
            x=0, y=0, task_code="iron_ore", task_type="items",
            task_progress=0, task_total=20, inventory={"iron_ore": 10},
        )
        new_state = a.apply(state, gd)
        assert new_state.task_progress == 5
        assert new_state.inventory["iron_ore"] == 5
        assert (new_state.x, new_state.y) == (1, 2)

    def test_cost_includes_distance(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        gd = make_gd()
        state = make_state(x=0, y=0)
        # 2 + dist(3) = 5
        assert a.cost(state, gd) == pytest.approx(5.0)

    def test_execute_moves_and_calls_api(self):
        a = TaskTradeAction(code="iron_ore", quantity=5, taskmaster_location=(1, 2))
        char = make_char_schema()
        state = make_state(x=0, y=0, task_code="iron_ore", task_type="items",
                           inventory={"iron_ore": 10})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.task_trade.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(
                x=1, y=2, task_code="iron_ore", task_type="items", inventory={"iron_ore": 10},
            )
            with patch("artifactsmmo_cli.ai.actions.task_trade.action_task_trade",
                       return_value=make_api_result(char)) as mock_tt:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=1, y=2)
        mock_tt.assert_called_once()
        body = mock_tt.call_args.kwargs["body"]
        assert body.code == "iron_ore"
        assert body.quantity == 5
