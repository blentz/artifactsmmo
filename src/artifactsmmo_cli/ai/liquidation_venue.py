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

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


class Venue(Enum):
    NPC = "npc"
    GE = "ge"           # fill a standing buy order (immediate)
    GE_POST = "ge_post"  # post our own sell order (deferred)


def choose_venue3(npc_pay: int, ge_fill_proceeds: int | None, post_price: int | None) -> Venue:
    """Three-way sell venue. FILL an existing buy order when it pays at least our
    post price (immediate beats deferred at equal terms). Else POST our own sell
    order when its price beats the NPC floor. Else NPC. `post_price is None` is the
    fail-closed anchor guard (no book to anchor on)."""
    if ge_fill_proceeds is not None and post_price is not None and ge_fill_proceeds >= post_price:
        return Venue.GE
    if ge_fill_proceeds is not None and post_price is None and ge_fill_proceeds > npc_pay:
        return Venue.GE
    if post_price is not None and post_price > npc_pay:
        return Venue.GE_POST
    # Provably unreachable totality-mirror of Lean's innermost `if f > npcPay`
    # in the some/some arm: reaching here needs post_price present with
    # post_price <= npc_pay and ge_fill_proceeds < post_price, yet
    # ge_fill_proceeds > npc_pay -- i.e. npc_pay < ge_fill_proceeds < post_price
    # <= npc_pay.
    if ge_fill_proceeds is not None and ge_fill_proceeds > npc_pay:  # pragma: no cover
        return Venue.GE
    return Venue.NPC


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


def liquidation_venue(item: str, qty: int, state: WorldState, game_data: GameData) -> Venue:
    """Impure adapter (like `craft_vs_buy.acquisition_method`): assemble the venue
    inputs from GameData and delegate to the proved `choose_venue`.

    `npc_pay` is the MAX price any NPC pays to buy `qty` of `item` (per unit; 0 when
    none buys it — NPC sell-back is per-unit and always realizable). `ge_proceeds`
    is the price of the highest standing GE buy order IF it can absorb the whole
    `qty` in one fill (quantity >= qty), else None — the anti-surrogate guard, so a
    partially-fillable order never masquerades as a single-fill venue for `qty`.
    State is accepted for signature symmetry with the other adapters; the decision
    needs only API-sourced prices."""
    buyers = game_data.npcs_buying_item(item)
    npc_pay = max((price for _npc, price in buyers), default=0)
    order = game_data.ge_best_buy_order(item)
    ge_proceeds: int | None = None
    if order is not None:
        _order_id, price, order_qty = order
        if order_qty >= qty:
            ge_proceeds = price
    return choose_venue(npc_pay, ge_proceeds)
