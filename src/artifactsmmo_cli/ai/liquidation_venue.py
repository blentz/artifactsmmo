"""Immediate-fill liquidation venue decision. To sell ONE surplus unit, choose the
venue with strictly higher REALIZABLE proceeds: NPC sell-back (always realizable)
vs filling an EXISTING Grand Exchange buy order (realizable ONLY if such an order
stands). We NEVER post a new GE order — a posted order may never fill, so its
"price" is speculative, not realizable; that speculative half is deliberately out
of scope.

The `ge_proceeds: int | None` Option is the ANTI-SURROGATE guard: `None` encodes
"no fillable standing buy order", and GE is chosen only when a real order exists
AND pays strictly more. The pure `choose_venue` / `realized_proceeds` are the
differential target proved in formal/Formal/LiquidationVenue.lean over `Int` with
`Option Int`.
"""

from enum import Enum


class Venue(Enum):
    NPC = "npc"
    GE = "ge"


def choose_venue(npc_pay: int, ge_proceeds: int | None) -> Venue:
    """GE iff a fillable standing buy order exists (`ge_proceeds is not None`) AND
    it pays STRICTLY more than the NPC sell-back; otherwise NPC. NPC is always
    realizable, so it is the safe default."""
    if ge_proceeds is not None and ge_proceeds > npc_pay:
        return Venue.GE
    return Venue.NPC


def realized_proceeds(npc_pay: int, ge_proceeds: int | None, venue: Venue) -> int:
    """The gold actually realized at `venue`: the standing GE order's price when
    GE is chosen (and an order exists), else the NPC sell-back price. Couples the
    decision to real gold so the choice cannot 'win' on a phantom price."""
    if venue is Venue.GE and ge_proceeds is not None:
        return ge_proceeds
    return npc_pay
