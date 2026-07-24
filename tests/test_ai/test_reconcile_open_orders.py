"""Tests for reconcile_open_orders: API-truth fill detection + per-cycle aging."""

from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.reconcile_open_orders import reconcile_open_orders


def _o(id, code, qty, price, side, age=0):
    return OpenOrder(id=id, code=code, qty=qty, price=price, side=side, age=age)


def test_disappeared_order_is_a_fill():
    prev = (_o("o1", "iron_ore", 3, 19, OrderSide.SELL),)
    api_open = ()
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders == ()
    assert res.filled == (_o("o1", "iron_ore", 3, 19, OrderSide.SELL),)


def test_reduced_quantity_is_a_partial_fill():
    prev = (_o("o1", "iron_ore", 5, 19, OrderSide.SELL),)
    api_open = (_o("o1", "iron_ore", 2, 19, OrderSide.SELL),)
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders[0].qty == 2
    assert res.filled[0].qty == 3        # 5 -> 2 = 3 filled


def test_still_open_order_ages_by_one():
    prev = (_o("o1", "iron_ore", 5, 19, OrderSide.SELL, age=2),)
    api_open = (_o("o1", "iron_ore", 5, 19, OrderSide.SELL, age=0),)
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders[0].age == 3   # aged, not reset
    assert res.filled == ()


def test_unknown_api_order_passes_through_unaged():
    """An order the API reports that wasn't in `prev` (e.g. restored session,
    or posted out-of-band) is tracked going forward without inventing an age."""
    prev = ()
    unknown = _o("o9", "copper_ore", 4, 12, OrderSide.BUY, age=0)
    api_open = (unknown,)
    res = reconcile_open_orders(prev, api_open)
    assert res.open_orders == (unknown,)
    assert res.filled == ()
