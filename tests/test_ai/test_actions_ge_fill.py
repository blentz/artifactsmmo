"""Tests for GeFillBuyOrderAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.ge_fill import GeFillBuyOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._ge_buy_orders = kwargs.get("ge_buy_orders", {})
    return gd


class TestGeFillBuyOrderAction:
    def test_repr(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        assert repr(a) == "GeFill(iron_ore×3@ord-1)"

    def test_not_applicable_without_ge_location(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=None)
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 10)})
        state = make_state(inventory={"iron_ore": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_inventory(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=5,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 10)})
        state = make_state(inventory={"iron_ore": 2})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_order_gone(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={})  # order no longer stands
        state = make_state(inventory={"iron_ore": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_order_id_changed(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-2", 9, 10)})
        state = make_state(inventory={"iron_ore": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_price_changed(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 7, 10)})
        state = make_state(inventory={"iron_ore": 3})
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_order_quantity_too_small(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 2)})
        state = make_state(inventory={"iron_ore": 3})
        assert a.is_applicable(state, gd) is False

    def test_applicable_when_order_stands_and_has_items(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 10)})
        state = make_state(inventory={"iron_ore": 3})
        assert a.is_applicable(state, gd) is True

    def test_apply_increments_gold_and_decrements_inventory(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=3,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 10)})
        state = make_state(x=0, y=0, gold=50, inventory={"iron_ore": 5})
        new_state = a.apply(state, gd)
        assert new_state.gold == 77   # 50 + 3 * 9
        assert new_state.inventory["iron_ore"] == 2
        assert (new_state.x, new_state.y) == (5, 1)

    def test_apply_removes_item_when_quantity_drops_to_zero(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=5,
                                 ge_location=(5, 1))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 10)})
        state = make_state(inventory={"iron_ore": 5})
        new_state = a.apply(state, gd)
        assert "iron_ore" not in new_state.inventory

    def test_cost_includes_distance(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=1,
                                 ge_location=(4, 0))
        gd = make_gd(ge_buy_orders={"iron_ore": ("ord-1", 9, 10)})
        state = make_state(x=0, y=0)
        # 1.0 + dist(4) = 5.0
        assert a.cost(state, gd) == pytest.approx(5.0)

    def test_execute_moves_then_calls_ge_fill_api(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=2,
                                 ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"iron_ore": 3})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_fill.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=5, y=1, inventory={"iron_ore": 3})
            with patch("artifactsmmo_cli.ai.actions.ge_fill.action_ge_fill",
                       return_value=make_api_result(char)) as mock_fill:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=5, y=1)
        mock_fill.assert_called_once()
        call_kwargs = mock_fill.call_args.kwargs
        assert call_kwargs["name"] == "testchar"
        assert call_kwargs["body"].id == "ord-1"
        assert call_kwargs["body"].quantity == 2

    def test_execute_without_move_when_already_at_ge(self):
        a = GeFillBuyOrderAction(order_id="ord-1", item_code="iron_ore", price=9, quantity=1,
                                 ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=5, y=1, inventory={"iron_ore": 3})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_fill.MoveAction") as MockMove:
            with patch("artifactsmmo_cli.ai.actions.ge_fill.action_ge_fill",
                       return_value=make_api_result(char)) as mock_fill:
                a.execute(state, client)
        MockMove.assert_not_called()
        mock_fill.assert_called_once()
