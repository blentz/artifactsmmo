"""Posted Grand Exchange order state: a frozen record of one open (buy or sell)
order the character has posted, with the age (in cycles) used by the TTL cancel."""

from enum import Enum
from typing import NamedTuple


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OpenOrder(NamedTuple):
    id: str
    code: str
    qty: int
    price: int
    side: OrderSide
    age: int
