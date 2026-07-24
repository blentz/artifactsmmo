from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.ge_post_sell import GePostSellOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OrderSide
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._ge_sell_orders = kwargs.get("ge_sell_orders", {})
    return gd


class TestApplyEscrowsItem:
    def test_apply_removes_item_and_appends_open_sell_order(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=3, price=19, ge_location=(5, 1))
        gd = make_gd()
        state = make_state(x=0, y=0, gold=50, inventory={"iron_ore": 5})
        new_state = a.apply(state, gd)
        assert new_state.inventory["iron_ore"] == 2          # item escrowed out of the bag
        assert new_state.gold == 50                          # gold arrives only on fill
        assert len(new_state.open_orders) == 1
        o = new_state.open_orders[0]
        assert (o.code, o.qty, o.price, o.side) == ("iron_ore", 3, 19, OrderSide.SELL)
        assert (new_state.x, new_state.y) == (5, 1)

    def test_apply_raises_when_inventory_insufficient(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=9, price=19, ge_location=(5, 1))
        state = make_state(inventory={"iron_ore": 2})
        with pytest.raises(AssertionError):
            a.apply(state, make_gd())

    def test_apply_removes_item_key_entirely_when_fully_sold(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=5, price=19, ge_location=(5, 1))
        state = make_state(inventory={"iron_ore": 5})
        new_state = a.apply(state, make_gd())
        assert "iron_ore" not in new_state.inventory


class TestCost:
    def test_cost_is_base_plus_manhattan_distance(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=1, price=19, ge_location=(3, 4))
        state = make_state(x=0, y=0)
        assert a.cost(state, make_gd()) == pytest.approx(2.0 + 3 + 4)


class TestRepr:
    def test_repr_shows_item_quantity_and_price(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=3, price=19, ge_location=(5, 1))
        assert repr(a) == "GePostSell(iron_ore×3@19)"


class TestApplicable:
    def test_not_applicable_without_ge_location(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=1, price=19, ge_location=None)
        assert a.is_applicable(make_state(inventory={"iron_ore": 1}), make_gd()) is False

    def test_not_applicable_without_item(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=1, price=19, ge_location=(5, 1))
        assert a.is_applicable(make_state(inventory={}), make_gd()) is False


class TestExecute:
    def test_execute_moves_then_posts_sell_order(self):
        a = GePostSellOrderAction(item_code="iron_ore", quantity=2, price=19, ge_location=(5, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"iron_ore": 3})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_post_sell.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(x=5, y=1, inventory={"iron_ore": 3})
            with patch("artifactsmmo_cli.ai.actions.ge_post_sell.action_ge_create_sell_order",
                       return_value=make_api_result(char)) as mock_post:
                a.execute(state, client)
        mock_post.assert_called_once()
        body = mock_post.call_args.kwargs["body"]
        assert (body.code, body.quantity, body.price) == ("iron_ore", 2, 19)
