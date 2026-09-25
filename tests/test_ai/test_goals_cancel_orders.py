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
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset(),
                            state=state)
    assert goal.is_satisfied(state) is True
    assert goal.value(state, gd) == 0.0
    assert goal.relevant_actions([], state, gd) == []


def test_unsatisfied_and_valued_on_item_need():
    gd = _gd()
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                            needed_items=frozenset({"iron"}), state=state)
    assert goal.is_satisfied(state) is False
    assert goal.value(state, gd) == CANCEL_ORDERS_VALUE


def test_emits_one_cancel_action_per_target():
    gd = _gd(ge_loc=(4, 2))
    state = make_state(
        open_orders=(
            _sell("s_old", "iron", 3, 19, age=TTL_CYCLES + 1),
            _buy("b_old", "copper", 3, 9, age=TTL_CYCLES + 2),
            _sell("s_fresh", "gold", 1, 5, age=0),
        ),
    )
    goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset(),
                            state=state)
    actions = goal.relevant_actions([], state, gd)
    assert all(isinstance(a, GeCancelOrderAction) for a in actions)
    assert [a.order_id for a in actions] == ["s_old", "b_old"]
    assert all(a.ge_location == (4, 2) for a in actions)


def test_no_actions_without_ge_location():
    gd = _gd(ge_loc=None)
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                            needed_items=frozenset({"iron"}), state=state)
    assert goal.relevant_actions([], state, gd) == []


def test_desired_state_and_repr():
    gd = _gd()
    goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset(),
                            state=make_state())
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
        state = self._hal(order)
        goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset(),
                                state=state)

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
        roomy = make_state(inventory={"shrimp": 100, "cheese": 18},
                           inventory_max=200, inventory_slots_max=100,
                           open_orders=(order,))
        goal = CancelOrdersGoal(game_data=gd, need_gold=0, needed_items=frozenset(),
                                state=roomy)

        assert [repr(a) for a in GOAPPlanner().plan(roomy, goal, [], gd)] \
            == ["GeCancel(6aa2523f)"]

    def test_a_gold_short_buy_cancel_survives_a_full_bag(self):
        """The escape the guard exists for must NOT be gated: a BUY cancel
        returns gold, so a bag with zero room cannot refuse it."""
        gd = _gd()
        order = _buy("b1", "shrimp", 40, 57, age=self._AGED)
        state = make_state(inventory={"shrimp": 138}, inventory_max=138,
                           inventory_slots_max=1, open_orders=(order,))
        goal = CancelOrdersGoal(game_data=gd, need_gold=10_000, needed_items=frozenset(),
                                state=state)

        assert state.inventory_free == 0
        assert [repr(a) for a in GOAPPlanner().plan(state, goal, [], gd)] \
            == ["GeCancel(b1)"]


class TestOneCancelSatisfiesTheGuard:
    """The goal is "cancel one of the orders the guard fired on", not "cancel all
    of them".

    Live 2026-09-24: `/my/grandexchange/orders` is account-scoped, so every
    character held all 83 of the account's SELL orders, and `TTL_CYCLES` made
    every one a target. Requiring all 83 cancelled needs 83 steps against the
    planner's depth cap of 15, so the goal was unplannable on every cycle: an
    `h=0` A* enumerated subsets of commuting cancels until its time or node cap
    (~0.5-1 GB transient per cycle per character), the guard never selected, and
    no order was ever cancelled. One cancel per cycle is also what the
    fire-and-lose argument already assumed: the next cycle re-fires on the rest.
    """

    _AGED = TTL_CYCLES + 1

    def _many(self, n):
        return tuple(_sell(f"o{i}", "raw_chicken", 8, 2, age=self._AGED)
                     for i in range(n))

    def test_the_planner_cancels_one_order_of_many(self):
        gd = _gd()
        state = make_state(open_orders=self._many(83))
        goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                                needed_items=frozenset(), state=state)
        planner = GOAPPlanner()

        plan = planner.plan(state, goal, [], gd, max_nodes=5_000)

        assert [repr(a) for a in plan] == ["GeCancel(o0)"]
        assert planner.last_stats.timed_out is False
        assert planner.last_stats.nodes_explored <= 2

    def test_satisfied_once_a_fired_order_is_gone(self):
        gd = _gd()
        state = make_state(open_orders=self._many(3))
        goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                                needed_items=frozenset(), state=state)
        assert goal.is_satisfied(state) is False
        after = make_state(open_orders=self._many(3)[1:])
        assert goal.is_satisfied(after) is True

    def test_a_new_target_alone_does_not_satisfy(self):
        """Satisfaction is about the orders the guard fired on: an order that
        became a target later is still open, so it cannot stand in for a cancel."""
        gd = _gd()
        state = make_state(open_orders=self._many(2))
        goal = CancelOrdersGoal(game_data=gd, need_gold=0,
                                needed_items=frozenset(), state=state)
        later = make_state(open_orders=(*self._many(2),
                                        _sell("late", "iron", 1, 5, age=self._AGED)))
        assert goal.is_satisfied(later) is False
