"""Tests for the GE_CANCEL guard goal `CancelOrdersGoal`: satisfaction, value, and
the one-GeCancelOrderAction-per-target relevant_actions emission (on-need item + TTL).
"""

from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.goals.cancel_orders import CANCEL_ORDERS_VALUE, CancelOrdersGoal
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.planner import GOAPPlanner
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


class TestAFullBagStopsTheCancelLivelock:
    """RUNS THE REAL PLANNER over the guard's own emission, which is the only
    thing that proves the room gate reaches the plan: `relevant_actions` still
    offers the cancel (the order IS a target), and it is `is_applicable` inside
    the search that must drop it.

    Reconstructs character HAL at 2026-09-10T11:04Z: bag 118/138, one aged SELL
    order whose escrowed stack does not fit in the 20 units of headroom. HEAD
    planned that cancel, the server refused it with HTTP 497 ("Character
    inventory is full"), the order stayed open, so it was a target again next
    cycle — `GeCancel(6aa2523fa4da349872694fc4)` ran 264 times. Lor took the
    same loop to `stuck_exit` and sat idle six hours.
    """

    _AGED = TTL_CYCLES + 1

    def _hal(self, order):
        return make_state(inventory={"shrimp": 100, "cheese": 18},
                          inventory_max=138, inventory_slots_max=100,
                          open_orders=(order,))

    def test_the_planner_drops_a_cancel_the_bag_cannot_receive(self):
        gd = _gd()
        order = _sell("6aa2523f", "shrimp", 40, 57, age=self._AGED)
        goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset())
        state = self._hal(order)

        # The guard genuinely fires and genuinely offers this cancel — so an
        # empty plan below is the room gate and nothing else.
        assert goal.is_satisfied(state) is False
        assert [repr(a) for a in goal.relevant_actions([], state, gd)] \
            == ["GeCancel(6aa2523f)"]
        assert state.inventory_free == 20

        assert GOAPPlanner().plan(state, goal, [], gd) == []

    def test_the_same_cancel_plans_once_the_stack_fits(self):
        """Vacuity guard AND the exit: the gate is a fit test on the LIVE bag,
        not a permanent veto — a deposit that frees room re-admits this cancel
        on the next cycle. A smaller order cancelled fine mid-burst live, which
        is what proved the id was not simply dead."""
        gd = _gd()
        order = _sell("6aa2523f", "shrimp", 40, 57, age=self._AGED)
        goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset())
        roomy = make_state(inventory={"shrimp": 100, "cheese": 18},
                           inventory_max=200, inventory_slots_max=100,
                           open_orders=(order,))

        assert [repr(a) for a in GOAPPlanner().plan(roomy, goal, [], gd)] \
            == ["GeCancel(6aa2523f)"]

    def test_a_gold_short_buy_cancel_survives_a_full_bag(self):
        """The escape the guard exists for must NOT be gated: a BUY cancel
        returns gold, so a bag with zero room cannot refuse it."""
        gd = _gd()
        order = _buy("b1", "shrimp", 40, 57, age=self._AGED)
        goal = CancelOrdersGoal(game_data=gd, need_gold=10_000, needed_items=frozenset())
        state = make_state(inventory={"shrimp": 138}, inventory_max=138,
                           inventory_slots_max=1, open_orders=(order,))

        assert state.inventory_free == 0
        assert [repr(a) for a in GOAPPlanner().plan(state, goal, [], gd)] \
            == ["GeCancel(b1)"]
