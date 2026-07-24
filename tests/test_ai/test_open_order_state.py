"""Tests for OpenOrder type and WorldState.open_orders escrow field."""

import pytest

from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state


def test_open_orders_defaults_empty():
    state = make_state()
    assert state.open_orders == ()


def test_open_orders_carries_order_records():
    order = OpenOrder(id="ord-1", code="iron_ore", qty=5, price=9, side=OrderSide.SELL, age=0)
    state = make_state(open_orders=(order,))
    assert state.open_orders[0].code == "iron_ore"
    assert state.open_orders[0].side is OrderSide.SELL


def test_open_order_is_frozen_namedtuple():
    order = OpenOrder(id="o", code="c", qty=1, price=1, side=OrderSide.BUY, age=0)
    with pytest.raises(AttributeError):
        order.qty = 2  # NamedTuple is immutable
