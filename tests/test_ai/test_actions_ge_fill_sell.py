"""Tests for GeFillSellOrderAction (BUY by filling a standing GE sell order)."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._ge_sell_orders = kwargs.get("ge_sell_orders", {})
    return gd


def _afford():
    """Gold high enough to clear the reserve after the buy."""
    return GOLD_RESERVE + 1000


class TestGeFillSellOrderAction:
    def test_repr(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        assert repr(a) == "GeBuy(iron_ore×3@ord-1)"

    def test_not_applicable_without_ge_location(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=None)
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 10)})
        state = make_state(gold=_afford(), inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_free_slots(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=5,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 10)})
        state = make_state(gold=_afford(), inventory={"x": 18}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_buy_would_breach_reserve(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=100, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 100, 10)})
        # gold - 300 < GOLD_RESERVE → not applicable
        state = make_state(gold=GOLD_RESERVE + 200, inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_order_gone(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={})  # order no longer stands
        state = make_state(gold=_afford(), inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_order_id_changed(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-2", 2, 10)})
        state = make_state(gold=_afford(), inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_price_changed(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 4, 10)})
        state = make_state(gold=_afford(), inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_order_quantity_too_small(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 2)})
        state = make_state(gold=_afford(), inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is False

    def test_applicable_when_order_stands_affordable_and_slots(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 10)})
        state = make_state(gold=_afford(), inventory={}, inventory_max=20)
        assert a.is_applicable(state, gd) is True

    def test_apply_decrements_gold_and_mints_inventory(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=3,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 10)})
        state = make_state(x=0, y=0, gold=1000, inventory={"iron_ore": 5}, inventory_max=20)
        new_state = a.apply(state, gd)
        assert new_state.gold == 994   # 1000 - 3 * 2
        assert new_state.inventory["iron_ore"] == 8
        assert (new_state.x, new_state.y) == (5, 1)

    def test_apply_mints_new_item_entry(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=4,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 10)})
        state = make_state(gold=1000, inventory={}, inventory_max=20)
        new_state = a.apply(state, gd)
        assert new_state.inventory["iron_ore"] == 4

    def test_apply_asserts_slot_precondition(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=5,
                                  ge_location=(5, 1))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 2, 10)})
        state = make_state(gold=1000, inventory={"x": 18}, inventory_max=20)
        with pytest.raises(AssertionError):
            a.apply(state, gd)

    def test_cost_includes_distance_and_gold(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=10, quantity=2,
                                  ge_location=(4, 0))
        gd = make_gd(ge_sell_orders={"iron_ore": ("ord-1", 10, 10)})
        state = make_state(x=0, y=0)
        # 2.0 + dist(4) + 10*2/10 = 8.0
        assert a.cost(state, gd) == pytest.approx(8.0)

    def test_execute_moves_then_calls_ge_buy_api(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=2,
                                  ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, gold=1000, inventory={}, inventory_max=20)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_fill_sell.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=5, y=1, gold=1000,
                                                            inventory={}, inventory_max=20)
            with patch("artifactsmmo_cli.ai.actions.ge_fill_sell.action_ge_buy",
                       return_value=make_api_result(char)) as mock_buy:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=5, y=1)
        mock_buy.assert_called_once()
        call_kwargs = mock_buy.call_args.kwargs
        assert call_kwargs["name"] == "testchar"
        assert call_kwargs["body"].id == "ord-1"
        assert call_kwargs["body"].quantity == 2

    def test_execute_without_move_when_already_at_ge(self):
        a = GeFillSellOrderAction(order_id="ord-1", item_code="iron_ore", price=2, quantity=1,
                                  ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=5, y=1, gold=1000, inventory={}, inventory_max=20)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_fill_sell.MoveAction") as MockMove:
            with patch("artifactsmmo_cli.ai.actions.ge_fill_sell.action_ge_buy",
                       return_value=make_api_result(char)) as mock_buy:
                a.execute(state, client)
        MockMove.assert_not_called()
        mock_buy.assert_called_once()
