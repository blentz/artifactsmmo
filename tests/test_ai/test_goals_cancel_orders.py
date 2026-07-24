"""Tests for the GE_CANCEL guard goal `CancelOrdersGoal`: satisfaction, value, and
the one-GeCancelOrderAction-per-target relevant_actions emission (on-need item + TTL).
"""

from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.goals.cancel_orders import CANCEL_ORDERS_VALUE, CancelOrdersGoal
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state


def _gd(ge_loc=(7, 7)) -> GameData:
    gd = GameData()
    gd._grand_exchange_location = ge_loc
    return gd


def _sell(id_, code, qty, price, age=0):
    return OpenOrder(id_, code, qty, price, OrderSide.SELL, age)


def _buy(id_, code, qty, price, age=0):
    return OpenOrder(id_, code, qty, price, OrderSide.BUY, age)


def test_satisfied_when_no_targets():
    gd = _gd()
    goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset())
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    assert goal.is_satisfied(state) is True
    assert goal.value(state, gd) == 0.0
    assert goal.relevant_actions([], state, gd) == []


def test_unsatisfied_and_valued_on_item_need():
    gd = _gd()
    goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                            needed_items=frozenset({"iron"}))
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    assert goal.is_satisfied(state) is False
    assert goal.value(state, gd) == CANCEL_ORDERS_VALUE


def test_emits_one_cancel_action_per_target():
    gd = _gd(ge_loc=(4, 2))
    goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset())
    state = make_state(
        open_orders=(
            _sell("s_old", "iron", 3, 19, age=TTL_CYCLES + 1),
            _buy("b_old", "copper", 3, 9, age=TTL_CYCLES + 2),
            _sell("s_fresh", "gold", 1, 5, age=0),
        ),
    )
    actions = goal.relevant_actions([], state, gd)
    assert all(isinstance(a, GeCancelOrderAction) for a in actions)
    assert [a.order_id for a in actions] == ["s_old", "b_old"]
    assert all(a.ge_location == (4, 2) for a in actions)


def test_no_actions_without_ge_location():
    gd = _gd(ge_loc=None)
    goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                            needed_items=frozenset({"iron"}))
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    assert goal.relevant_actions([], state, gd) == []


def test_desired_state_and_repr():
    gd = _gd()
    goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset())
    assert goal.desired_state(make_state(), gd) == {"ge_orders_cancelled": True}
    assert repr(goal) == "CancelOrders"
