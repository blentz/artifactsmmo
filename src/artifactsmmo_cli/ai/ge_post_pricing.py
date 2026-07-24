"""Pure price-setting for POSTED Grand Exchange orders — the speculative half
deliberately left out of liquidation_venue / buy_source_venue, made safe by two
guards: (1) FAIL CLOSED with no live anchor (best-order is None -> None -> no post),
so an empty book never yields a speculative price; (2) FLOOR/CEILING BOUND against
the realizable alternative, so a posted price can never be worse than dumping to /
buying from the NPC. Undercut/overbid by ONE tick to sit in front of the queue.

These are the differential target proved in formal/Formal/GePostPricing.lean.
"""


def sell_post_price(best_sell: int | None, npc_sellback: int, margin: int) -> int | None:
    """Price to post a SELL order at: one tick below the best standing sell order,
    but never below the NPC sell-back floor plus margin. None (no post) when there
    is no standing sell order to anchor on."""
    if best_sell is None:
        return None
    return max(best_sell - 1, npc_sellback + margin)


def buy_post_price(best_buy: int | None, alt_cost: int, margin: int) -> int | None:
    """Price to post a BUY order at: one tick above the best standing buy order, but
    never above the realizable alternative cost (NPC buy / fillable sell order) minus
    margin. None (no post) when there is no standing buy order to anchor on."""
    if best_buy is None:
        return None
    return min(best_buy + 1, alt_cost - margin)
