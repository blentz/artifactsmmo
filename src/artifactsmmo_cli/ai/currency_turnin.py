"""When the fleet's dual-role stock is enough to buy the thing it pays for.

Pure over plain mappings so the whole decision is testable without a
coordination DB, five characters, or a live account.

THE THRESHOLD IS THE VENDOR'S PRICE, NOT A TUNED CONSTANT. `lich_race_trophy`
costs exactly 10 `lich_race_medal`; asking for a margin on top would be a
number nobody could derive from the game."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnIn:
    """A resolved turn-in: what to buy, where, in what currency, by whom."""

    item_code: str
    npc_code: str
    price: int
    currency: str
    buyer: str
    fleet_total: int


def fleet_total_pure(own: Mapping[str, int], siblings: Mapping[str, int],
                     bank: Mapping[str, int], code: str) -> int:
    """Units of `code` the whole account can reach: this character's worn and
    carried units, every live sibling's, and the shared bank.

    The bank is added exactly once because only one of the three arguments is
    allowed to carry it — see `HoldingLedger`, which never publishes it."""
    return own.get(code, 0) + siblings.get(code, 0) + bank.get(code, 0)


def turn_in_ready_pure(fleet_total: int, price: int) -> bool:
    """True when the fleet can pay the vendor's price outright."""
    if price <= 0:
        return False
    return fleet_total >= price


def recall_shortfall_pure(price: int, buyer_held: int, bank: int) -> int:
    """Units the buyer must ask siblings to surrender, never negative.

    The buyer's own worn/carried units and the bank are reachable without any
    coordination, so only the remainder is a recall."""
    return max(0, price - buyer_held - bank)
