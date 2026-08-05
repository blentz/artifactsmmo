# shed_urgency

"""The hoist thresholds for the shed rungs — when a pile stops being working
slack and starts being worth a cycle of the objective step's time.

WHY THIS MODULE EXISTS. The BAG-side ladder was written for RECYCLE_SURPLUS on
2026-07-05 and lived in `ai/recycle_surplus.py` under the name
`recycle_urgency_pure`, because recycle was the only rung the arbiter hoisted.
On 2026-08-05 the hoist was extended to SELL_IDLE and DRAIN_BANK_JUNK (part 2 of
the disposal-unification epic — the three rungs that fire and are never
selected), so the question has three askers and belongs to none of them.

TWO RULES, BECAUSE THERE ARE TWO POPULATIONS AND TWO COSTS. This is the whole
content of the module and neither rule is a matter of taste:

  * BAG-side (`shed_urgency`): the copies are already in hand and the episode is
    ONE action — a recycle at the workshop, or a sale at the merchant. The only
    question is whether the pile is past normal working slack, and the answer
    that has been live since 2026-07-05 is "more than five spares".

  * BANK-side (`bank_shed_hoist_pure`): the episode is a ROUND TRIP — a withdraw
    at the bank, then a shed somewhere else — and it can carry at most one
    bag-load however deep the pile. That is the classic batching shape, so the
    trip pays for itself only at a FULL load. Below a bag-load the copies stay in
    the discretionary band, where they are shed opportunistically; at or above
    one, the pile can no longer be cleared by a single opportunistic episode and
    is on its way to the 703-deep hoards the live diagnosis found.

WHY THE BANK RULE IS NOT THE BAG RULE, measured. The bag rule at >5 copies is
correct for GEAR spares (six spare helmets is abnormal) and wrong for BANK bulk:
a bank routinely holds tens of a gathering material as ordinary stock. Applied
to the bank it hoisted on the `l20_dual_utility` scenario's 30 `nettle_leaf` and
preempted a winnable fight — a rung that outranks progression on ordinary stock
is the "unconditional hoist" failure this epic set out not to ship.

The bank rule is also SELF-LIMITING, which the bag rule is not: a per-code pile
can exceed one bag-load only until the next idle cycle, so the bank's junk per
code is bounded by roughly one bag-load instead of growing without limit.

This module answers only "is it urgent". WHICH copies are licensed is the keep
authority's answer (`ai/inventory_keep`), and WHETHER they are worth keeping at
all is `ai/keep_valuation`'s.
"""

URGENCY_STEP = 5
"""Surplus copies per +1x urgency: every 5 spares of the piling item add one
urgency multiple (a ~40-copy hoard is 8x more urgent than <5)."""

BANK_SHED_BAG_LOADS = 1
"""Bag-loads of licensed copies a BANK-side shed rung needs before it outranks
the objective step.

DERIVED FROM THE RATE BUDGET, not chosen. A bank-side shed episode costs a fixed
overhead — one `Withdraw` at the bank tile plus one shed action — and every one
of those is a request in the ACTION bucket, whose sustainable pace is
`utils/rate_budget.WindowBudget.sustainable_interval` (max over the API's
declared windows of `span / limit`, divided among `play --all` children). That
overhead is the same whether the trip carries one copy or a full bag, and the
carrying capacity is capped by the server's own inventory quantity limit (HTTP
497). Paying a fixed cost for a partial batch is exactly what batching exists to
avoid, so ONE full load is the smallest pile for which preempting the objective
step is a better use of the same two requests.

Live figures (R2D2, 120-quantity bag): of the seven deepest piles — sap 703,
raw_wolf_meat 509, raw_chicken 272, raw_beef 161, gudgeon 143, wolf_hair 124,
raw_porkchop 104 — six clear one bag-load and hoist, and `raw_porkchop` does not.
That is the intended cut, not a knife edge: the hoist takes the piles that cannot
be cleared opportunistically and leaves the one that can."""


def shed_urgency_pure(max_surplus: int) -> int:
    """Urgency multiplier for the largest BAG-side surplus pile:
    ``max(1, ceil(q/5))``.

    <=5 surplus is baseline (1x); each further 5 copies add 1x, so the pile a
    skill grind keeps feeding becomes progressively harder to ignore instead of
    growing unbounded in the starved discretionary tier."""
    return max(1, -(-max_surplus // URGENCY_STEP))


def shed_urgency(surplus: dict[str, int]) -> int:
    """Urgency of a BAG-side licensed-surplus map: driven by its LARGEST pile
    (the code a grind keeps feeding is by construction the one that piles up). An
    EMPTY map scores the 1x baseline, which is below every hoist threshold — "no
    work" can never hoist a rung."""
    return shed_urgency_pure(max(surplus.values(), default=0))


def bank_shed_hoist_pure(max_licensed: int, inventory_max: int) -> bool:
    """Whether a BANK-side pile of `max_licensed` copies of ONE code is worth the
    round trip: at least `BANK_SHED_BAG_LOADS` bag-loads.

    The measure is the LARGEST pile, not the total, because the withdraw is
    per-code: an episode carries one code's batch, so twenty 30-copy piles still
    move only 30 copies per trip and are exactly the partial batch this rule
    declines to pay for.

    `inventory_max == 0` is a bag that cannot receive a withdraw at all, so no
    pile is ever worth the trip — stated explicitly, because the comparison alone
    would read a zero-capacity bag as "every pile is a full load"."""
    if inventory_max <= 0:
        return False
    return max_licensed >= inventory_max * BANK_SHED_BAG_LOADS


def bank_shed_hoist(surplus: dict[str, int], inventory_max: int) -> bool:
    """`bank_shed_hoist_pure` over a licensed-surplus map. An EMPTY map has no
    largest pile and never hoists — "no work" can never hoist a rung."""
    return bank_shed_hoist_pure(max(surplus.values(), default=0), inventory_max)
