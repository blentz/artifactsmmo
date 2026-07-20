"""How far to grind toward a vendor's item-currency price in one goal.

Replaces the bare `held + 1` "grind-one-replan" idiom. That idiom exists for a
real reason: a one-shot plan for a 230-coin price is ~120 fights deep and dies on
`max_depth` (sandwhisper_bag probe 2026-07-06 @L50: 28K nodes, plan_len=0). So the
target MUST stay shallow -- asking for the full price is not an option.

But `held + 1` re-arms on every single acquisition, and `needed` is part of a
GatherMaterialsGoal's identity (`goals/gathering.py`), so the goal's repr churned
every time a unit landed, resetting sticky-commit keying each cycle.

The milestone ladder keeps both properties. The target is an ABSOLUTE multiple of
`CURRENCY_GRIND_BATCH`, so it does not move while the character works through a
batch, and it is never more than one batch beyond `held`, so plan depth is bounded
by the batch rather than by the price.

Live case: `event_ticket` drops at 0.5% per gather (changelog 8.2.0, 07/19/26), so
a 100-ticket vendor price is roughly 20,000 gather actions. Whether such a target
is worth pursuing AT ALL is a separate question -- raids yield tickets at a
guaranteed 1 per 20,000 damage (see docs/PLAN_events_raids_epic.md).
"""

from artifactsmmo_cli.ai.thresholds import CURRENCY_GRIND_BATCH


def currency_grind_target_pure(held: int, price: int) -> int:
    """Total units of the currency this goal should ask for.

    Returns the next batch milestone strictly above `held`, clamped to `price`.
    Zero when there is nothing to grind toward (`price <= 0`).

    Always strictly greater than `held` while `held < price`, so the goal can
    never be trivially satisfied and spin.
    """
    if price <= 0:
        return 0
    if held >= price:
        return price
    # Next multiple of the batch strictly above `held`: ceil((held + 1) / batch).
    batches = -(-(held + 1) // CURRENCY_GRIND_BATCH)
    return min(price, batches * CURRENCY_GRIND_BATCH)
