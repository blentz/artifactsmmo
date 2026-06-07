"""Immediate-fill BUY source venue decision — the DUAL of liquidation_venue. To
buy ONE needed unit, choose the venue with strictly LOWER REALIZABLE cost: NPC
buy (always realizable) vs filling an EXISTING Grand Exchange SELL order (realizable
ONLY if such an order stands). We NEVER post a new GE buy order — a posted order may
never fill, so its "price" is speculative, not realizable; that speculative half is
deliberately out of scope.

This is the exact mirror of liquidation_venue: liquidating SELLS and picks the
HIGHER proceeds (max), so it fills a standing BUY order; sourcing BUYS and picks the
LOWER cost (min), so it fills a standing SELL order. The `ge_price: int | None`
Option is the ANTI-SURROGATE guard: `None` encodes "no fillable standing sell
order", and GE is chosen only when a real order exists AND is strictly cheaper. The
pure `choose_buy_venue` / `realized_cost` are the differential target proved in
formal/Formal/BuySourceVenue.lean over `Int` with `Option Int`.
"""

from enum import Enum


class BuyVenue(Enum):
    NPC = "npc"
    GE = "ge"


def choose_buy_venue(npc_price: int, ge_price: int | None) -> BuyVenue:
    """GE iff a fillable standing sell order exists (`ge_price is not None`) AND it
    costs STRICTLY LESS than the NPC buy price; otherwise NPC. NPC is always
    realizable, so it is the safe default."""
    if ge_price is not None and ge_price < npc_price:
        return BuyVenue.GE
    return BuyVenue.NPC


def realized_cost(npc_price: int, ge_price: int | None, venue: BuyVenue) -> int:
    """The gold actually spent at `venue`: the standing GE sell order's price when GE
    is chosen (and an order exists), else the NPC buy price. Couples the decision to
    real gold so the choice cannot 'win' on a phantom price."""
    if venue is BuyVenue.GE and ge_price is not None:
        return ge_price
    return npc_price
