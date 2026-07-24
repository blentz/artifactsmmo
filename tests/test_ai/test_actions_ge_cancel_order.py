from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


class TestApplyReversesEscrow:
    def test_cancel_sell_returns_item(self):
        order = OpenOrder(id="o1", code="iron_ore", qty=3, price=19, side=OrderSide.SELL, age=2)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(gold=50, inventory={}, open_orders=(order,))
        new_state = a.apply(state, GameData())
        assert new_state.inventory["iron_ore"] == 3
        assert new_state.gold == 50
        assert new_state.open_orders == ()

    def test_cancel_buy_returns_gold(self):
        order = OpenOrder(id="o2", code="iron_ore", qty=3, price=9, side=OrderSide.BUY, age=2)
        a = GeCancelOrderAction(order_id="o2", ge_location=(5, 1))
        state = make_state(gold=50, inventory={}, open_orders=(order,))
        new_state = a.apply(state, GameData())
        assert new_state.gold == 77                          # 50 + 3*9
        assert new_state.open_orders == ()

    def test_not_applicable_when_order_absent(self):
        a = GeCancelOrderAction(order_id="missing", ge_location=(5, 1))
        assert a.is_applicable(make_state(open_orders=()), GameData()) is False

    def test_not_applicable_when_no_ge_location(self):
        order = OpenOrder(id="o1", code="iron_ore", qty=3, price=19, side=OrderSide.SELL, age=2)
        a = GeCancelOrderAction(order_id="o1", ge_location=None)
        assert a.is_applicable(make_state(open_orders=(order,)), GameData()) is False

    def test_apply_raises_when_order_absent(self):
        a = GeCancelOrderAction(order_id="missing", ge_location=(5, 1))
        state = make_state(open_orders=())
        try:
            a.apply(state, GameData())
        except AssertionError:
            pass
        else:
            raise AssertionError("expected AssertionError")


class TestCostAndRepr:
    def test_cost_includes_travel_distance(self):
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(x=0, y=0)
        assert a.cost(state, GameData()) == 1.0 + 6

    def test_repr(self):
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        assert repr(a) == "GeCancel(o1)"


class TestExecute:
    def test_execute_calls_cancel_api(self):
        order = OpenOrder(id="o1", code="iron_ore", qty=1, price=19, side=OrderSide.SELL, age=1)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(x=5, y=1, open_orders=(order,))
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                   return_value=make_api_result(make_char_schema())) as mock_cancel:
            a.execute(state, client)
        assert mock_cancel.call_args.kwargs["body"].id == "o1"

    def test_execute_returns_state_with_remaining_orders_only(self):
        cancelled = OpenOrder(id="o1", code="iron_ore", qty=1, price=19, side=OrderSide.SELL, age=1)
        kept = OpenOrder(id="o2", code="copper_ore", qty=2, price=7, side=OrderSide.BUY, age=0)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(x=5, y=1, open_orders=(cancelled, kept))
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                   return_value=make_api_result(make_char_schema())):
            new_state = a.execute(state, client)
        assert kept in new_state.open_orders
        assert cancelled not in new_state.open_orders
        assert len(new_state.open_orders) == 1

    def test_execute_moves_first_when_not_at_ge_location(self):
        order = OpenOrder(id="o1", code="iron_ore", qty=1, price=19, side=OrderSide.SELL, age=1)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(x=0, y=0, open_orders=(order,))
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                   return_value=make_api_result(make_char_schema(x=5, y=1))):
            with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
                mock_move.return_value = make_api_result(make_char_schema(x=5, y=1))
                a.execute(state, client)
        mock_move.assert_called_once()
