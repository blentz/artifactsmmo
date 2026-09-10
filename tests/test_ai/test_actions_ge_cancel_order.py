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

    def test_execute_move_fold_preserves_other_open_orders(self):
        """Regression: when the character is NOT already at ge_location,
        GeCancelOrderAction.execute folds a MoveAction first. MoveAction.execute
        rebuilds WorldState via from_character_schema without threading
        open_orders through, so it used to default to () and wipe every
        tracked open order — not just the one being cancelled. With two open
        orders (o1 cancelled, o2 kept) and the character starting away from
        ge_location (forcing the move fold to run), the returned state must
        still carry o2 and must not carry o1.
        """
        cancelled = OpenOrder(id="o1", code="iron_ore", qty=1, price=19, side=OrderSide.SELL, age=1)
        kept = OpenOrder(id="o2", code="copper_ore", qty=2, price=7, side=OrderSide.BUY, age=0)
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(x=0, y=0, open_orders=(cancelled, kept))
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
                   return_value=make_api_result(make_char_schema(x=5, y=1))):
            with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
                mock_move.return_value = make_api_result(make_char_schema(x=5, y=1))
                new_state = a.execute(state, client)
        assert kept in new_state.open_orders
        assert cancelled not in new_state.open_orders
        assert len(new_state.open_orders) == 1


class TestSellCancelNeedsInventoryRoom:
    """Cancelling a SELL order MINTS the escrowed stack back into the bag, so it
    needs the same slot+quantity room every other stack-creating action checks
    (`WithdrawItemAction`, `NpcBuyAction`, `GeFillSellOrderAction`).

    Without the gate the action lies about its applicability: the planner picks
    it, the server refuses with HTTP 497 ("Character inventory is full"), the
    order stays open, so `cancel_targets` names it again next cycle and the
    guard re-picks the SAME id forever. `CancelOrdersGoal`'s fire-and-lose
    liveness argument assumes the cancel SUCCEEDS; a refused cancel is a
    livelock with no exit.

    Live 2026-09-09/10: 685 of 4465 cycles across all five characters were
    HTTP_497 cancels — `GeCancel(6aa2523fa4da349872694fc4)` alone 264 times with
    HAL pinned at 118/138 — and it is what took Lor to `stuck_exit`, idle for
    six hours. A SMALLER order cancelled fine mid-burst, which is what proves
    this is a room fit and not a permanently dead order id.
    """

    _ORDER = OpenOrder(id="o1", code="iron_ore", qty=10, price=19,
                       side=OrderSide.SELL, age=2)

    def test_not_applicable_when_returned_quantity_overflows_the_cap(self):
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        # 15 of 20 quantity used, the stack is already held (so slots are not
        # the binding term), and the cancel would mint 10 more.
        state = make_state(inventory={"iron_ore": 15}, inventory_max=20,
                           inventory_slots_max=20, open_orders=(self._ORDER,))
        assert state.inventory_free == 5
        assert a.is_applicable(state, GameData()) is False

    def test_not_applicable_when_a_new_stack_has_no_free_slot(self):
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        # Quantity headroom is ample; every SLOT is taken by another code, and
        # iron_ore is not held, so the returned stack has nowhere to land.
        state = make_state(inventory={f"junk_{i}": 1 for i in range(3)},
                           inventory_max=100, inventory_slots_max=3,
                           open_orders=(self._ORDER,))
        assert state.inventory_free == 97
        assert state.inventory_slots_free == 0
        assert a.is_applicable(state, GameData()) is False

    def test_applicable_when_the_returned_stack_fits(self):
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(inventory={"iron_ore": 5}, inventory_max=20,
                           inventory_slots_max=20, open_orders=(self._ORDER,))
        assert a.is_applicable(state, GameData()) is True

    def test_buy_cancel_is_unaffected_by_a_full_bag(self):
        """A BUY cancel returns GOLD, not items — a full bag cannot refuse it,
        and gating it would strand the gold-short escape the guard exists for."""
        buy = OpenOrder(id="o2", code="iron_ore", qty=10, price=9,
                        side=OrderSide.BUY, age=2)
        a = GeCancelOrderAction(order_id="o2", ge_location=(5, 1))
        state = make_state(inventory={"iron_ore": 20}, inventory_max=20,
                           inventory_slots_max=1, open_orders=(buy,))
        assert state.inventory_free == 0
        assert state.inventory_slots_free == 0
        assert a.is_applicable(state, GameData()) is True

    def test_apply_raises_when_the_returned_stack_does_not_fit(self):
        """Mirror of the precondition — the chain-safe defense that crashes
        loudly if a caller bypasses the gate (same shape as
        `WithdrawItemAction.apply`)."""
        a = GeCancelOrderAction(order_id="o1", ge_location=(5, 1))
        state = make_state(inventory={"iron_ore": 15}, inventory_max=20,
                           inventory_slots_max=20, open_orders=(self._ORDER,))
        try:
            a.apply(state, GameData())
        except AssertionError:
            pass
        else:
            raise AssertionError("expected AssertionError")
