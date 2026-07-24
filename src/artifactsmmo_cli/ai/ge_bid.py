"""Biddable GE buy-order candidates for the current objective step.

A single pure predicate shared by BOTH the `MeansKind.GE_BID` firing guard
(`tiers/means.py::_fires`) and the reactive goal (`goals/post_buy_bid.py`), so
the means never fires on a candidate its goal then refuses to bid (the
zero-length-plan trap the means module warns about).

A candidate is a material the current objective step is accumulating
(`ctx.step_profile`, the GOAL_MATERIALS demand bound per-cycle) that we do NOT
already hold, that is SLOW to self-craft (`should_bid` — self-crafting is slower
than the fill horizon), that has a live GE buy-anchor to overbid AND an NPC
alternative to ceiling-bound the post price, that we are not already acquiring
another way (no open order for it), and for which the three-way buy-venue choice
lands on posting our own order (`BuyVenue.GE_POST`) rather than filling a standing
sell order or buying from the NPC. The posted price is `buy_post_price`: one tick
over the anchor, ceiling-bounded by the NPC alternative minus margin.
"""

from artifactsmmo_cli.ai.bid_vs_craft import should_bid
from artifactsmmo_cli.ai.buy_source_venue import BuyVenue, choose_buy_venue3
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_post_pricing import buy_post_price
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

_BID_MARGIN = 1


def _owned(code: str, state: WorldState) -> int:
    """Total holdings of `code`: inventory + bank + equipped copies."""
    bank = state.bank_items or {}
    equipped = sum(1 for c in state.equipment.values() if c == code)
    return state.inventory.get(code, 0) + bank.get(code, 0) + equipped


def ge_bid_candidates(
    state: WorldState, game_data: GameData, ctx: SelectionContext,
    bid_fill_horizon_s: float,
) -> list[tuple[str, int, int]]:
    """Return `(item_code, qty, post_price)` for every objective-step material
    that should be acquired by posting a GE buy order this cycle.

    Empty when the map has no Grand Exchange (nowhere to post)."""
    if game_data.grand_exchange_location() is None:
        return []
    open_codes = {o.code for o in state.open_orders}
    out: list[tuple[str, int, int]] = []
    for item, wanted in ctx.step_profile.items():
        if item in open_codes:
            continue  # suppression: already acquiring via a standing order
        qty = wanted - _owned(item, state)
        if qty <= 0:
            continue  # already held
        if not should_bid(item, qty, bid_fill_horizon_s, game_data):
            continue  # fast to self-craft — no bid
        sellers = game_data.npcs_selling_item(item)
        if not sellers:
            continue  # no NPC alternative to ceiling-bound the post price
        npc_price = min(price for _npc, price in sellers)
        buy_anchor = game_data.ge_best_buy_order(item)
        best_buy = buy_anchor[1] if buy_anchor is not None else None
        post_price = buy_post_price(best_buy, alt_cost=npc_price, margin=_BID_MARGIN)
        if post_price is None:
            continue  # no live buy-anchor — fail closed, never post speculatively
        sell_order = game_data.ge_best_sell_order(item)
        fill_cost = sell_order[1] if sell_order is not None else None
        if choose_buy_venue3(npc_price, fill_cost, post_price) is BuyVenue.GE_POST:
            out.append((item, qty, post_price))
    return out
