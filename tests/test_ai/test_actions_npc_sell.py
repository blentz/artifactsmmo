"""Tests for NpcSellAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._npc_locations = kwargs.get("npc_locations", {})
    gd._npc_sell_prices = kwargs.get("npc_sell_prices", {})
    return gd


class TestNpcSellAction:
    def test_repr(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=3, npc_location=(2, 1))
        assert repr(a) == "NpcSell(cooked_chicken×3@cook)"

    def test_not_applicable_without_npc_location(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=None)
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_npc_does_not_buy_item(self):
        a = NpcSellAction(npc_code="cook", item_code="unknown", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"unknown": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_inventory(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 2})
        assert a.is_applicable(state, gd) is False

    def test_applicable_when_has_items_and_npc_buys(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=2, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 5})
        assert a.is_applicable(state, gd) is True

    def test_apply_increments_gold_and_decrements_inventory(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=3, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(x=0, y=0, gold=50, inventory={"cooked_chicken": 5})
        new_state = a.apply(state, gd)
        assert new_state.gold == 65   # 50 + 3 * 5
        assert new_state.inventory["cooked_chicken"] == 2
        assert (new_state.x, new_state.y) == (2, 1)

    def test_apply_removes_item_when_quantity_drops_to_zero(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(inventory={"cooked_chicken": 5})
        new_state = a.apply(state, gd)
        assert "cooked_chicken" not in new_state.inventory

    def test_cost_includes_distance(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(4, 0))
        gd = make_gd(npc_sell_prices={"cook": {"cooked_chicken": 5}})
        state = make_state(x=0, y=0)
        # 1.5 + dist(4) = 5.5
        assert a.cost(state, gd) == pytest.approx(5.5)

    def test_execute_moves_then_calls_npc_sell_api(self):
        a = NpcSellAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"cooked_chicken": 3})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.npc_sell.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=2, y=1, inventory={"cooked_chicken": 3})
            with patch("artifactsmmo_cli.ai.actions.npc_sell.action_npc_sell",
                       return_value=make_api_result(char)) as mock_sell:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=2, y=1)
        mock_sell.assert_called_once()
        # Verify the body has the right code+quantity
        call_kwargs = mock_sell.call_args.kwargs
        assert call_kwargs["name"] == "testchar"
        assert call_kwargs["body"].code == "cooked_chicken"
        assert call_kwargs["body"].quantity == 1
