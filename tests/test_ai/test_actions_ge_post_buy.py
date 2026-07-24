from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd() -> GameData:
    return GameData()


class TestApplyEscrowsGold:
    def test_apply_removes_gold_and_appends_open_buy_order(self):
        # gold high enough to clear the _MIN_SAFETY_FLOOR (100) after the escrow
        # (bare GameData() has no reserved targets, so the floor is exactly 100).
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=9, ge_location=(5, 1))
        state = make_state(x=0, y=0, gold=1000, inventory={})
        new_state = a.apply(state, make_gd())
        assert new_state.gold == 973  # 1000 - 3*9
        assert "iron_ore" not in new_state.inventory  # item arrives only on fill
        assert len(new_state.open_orders) == 1
        o = new_state.open_orders[0]
        assert (o.code, o.qty, o.price, o.side) == ("iron_ore", 3, 9, OrderSide.BUY)

    def test_apply_raises_when_gold_insufficient(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=90, ge_location=(5, 1))
        state = make_state(gold=10)
        with pytest.raises(AssertionError):
            a.apply(state, make_gd())


class TestIsApplicable:
    def test_false_when_no_ge_location(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=1, price=9, ge_location=None)
        state = make_state(gold=100)
        assert a.is_applicable(state, make_gd()) is False

    def test_false_when_gold_below_reserve_floor(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=90, ge_location=(5, 1))
        state = make_state(gold=10)
        assert a.is_applicable(state, make_gd()) is False

    def test_true_when_gold_sufficient(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=9, ge_location=(5, 1))
        state = make_state(gold=1000)
        assert a.is_applicable(state, make_gd()) is True


class TestExecute:
    def test_execute_moves_then_posts_buy_order(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=2, price=9, ge_location=(5, 1))
        char = make_char_schema()
        existing_order = OpenOrder(
            id="existing:1", code="copper_ore", qty=5, price=3, side=OrderSide.SELL, age=1,
        )
        state = make_state(x=0, y=0, gold=100, open_orders=(existing_order,))
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_post_buy.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(
                x=5, y=1, gold=100, open_orders=(existing_order,))
            with patch("artifactsmmo_cli.ai.actions.ge_post_buy.action_ge_create_buy_order",
                       return_value=make_api_result(char)) as mock_post:
                new_state = a.execute(state, client)
        body = mock_post.call_args.kwargs["body"]
        assert (body.code, body.quantity, body.price) == ("iron_ore", 2, 9)
        # Passthrough: the returned WorldState still carries the pre-existing
        # open order (open_orders=state.open_orders passthrough, not dropped).
        assert new_state.open_orders == (existing_order,)

    def test_execute_skips_move_when_already_at_ge(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=1, price=5, ge_location=(5, 1))
        char = make_char_schema(x=5, y=1)
        state = make_state(x=5, y=1, gold=100)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_post_buy.MoveAction") as MockMove:
            with patch("artifactsmmo_cli.ai.actions.ge_post_buy.action_ge_create_buy_order",
                       return_value=make_api_result(char)):
                a.execute(state, client)
        MockMove.assert_not_called()


class TestCost:
    def test_cost_scales_with_distance_and_price(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=9, ge_location=(5, 1))
        state = make_state(x=0, y=0, gold=100)
        assert a.cost(state, make_gd()) == pytest.approx(2.0 + 6 + 27 / 10.0)


class TestRepr:
    def test_repr(self):
        a = GePostBuyOrderAction(item_code="iron_ore", quantity=3, price=9, ge_location=(5, 1))
        assert repr(a) == "GePostBuy(iron_ore×3@9)"
