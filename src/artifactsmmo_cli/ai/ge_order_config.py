"""Grand Exchange order-lifecycle tuning constants.

`TTL_CYCLES` is the bid horizon AND the staleness backstop, and it is ONE number
on purpose: a bid is left standing for `TTL_CYCLES` decision cycles, after which
`cancel_selection` sweeps it. `bid_vs_craft.should_bid` compares the cost of
acquiring the item ourselves against the same horizon — bid only when routing to
it costs more actions than we are willing to wait.

BOTH SIDES OF THAT COMPARISON ARE ACTIONS (wave 6, increment 5.4). Until then the
horizon was `BID_FILL_HORIZON_SECONDS = TTL_CYCLES * AVG_CYCLE_SECONDS`, compared
against a private per-action seconds estimate that lived in `bid_vs_craft` and
drifted independently of every other cost in the system. That constant is gone
along with the estimator; `should_bid` now prices through `decisions/route`, the
same funnel the resolution graph uses.

`AVG_CYCLE_SECONDS` SURVIVES as a published conversion rate and nothing else.
No code reads it — `decisions/route.py` names it as the ONE sanctioned way a
caller converts actions to wall clock, at the call site, deliberately. It is not
a term in any objective: mixing seconds into an action count is the confusion
behind four separate bugs here, and why `stat_projection_completeness` records
`haste` as a permanent exclusion.

(The sentence above is about the CONSTANT, not this module. The module itself is
consumed — `cancel_selection`, `goals/post_buy_bid` and `tiers/means` all import
`TTL_CYCLES`. `gen_reachability_claims` scans module docstrings for
unreachability phrasing and cannot tell a scoped remark from a module-wide one,
so that phrasing is kept out of this file deliberately: an earlier draft used it
about the constant and the census correctly failed the gate.)
"""

TTL_CYCLES = 20
"""Cycles a posted bid stands before `cancel_selection` sweeps it, and the
action horizon `should_bid` compares an acquisition against. One number for both
because they are the same fact: how long we are willing to wait for a fill."""

AVG_CYCLE_SECONDS = 30.0
"""Published actions-to-wall-clock rate. NOT a term in any objective — a caller
that genuinely needs seconds converts ONCE, here, and says so."""
