"""Grand Exchange order-lifecycle tuning constants.

`BID_FILL_HORIZON_SECONDS` is the wall-clock window we are willing to wait for a
posted GE buy order to fill before self-crafting would have been the faster
acquisition. It is `TTL_CYCLES * AVG_CYCLE_SECONDS`: a bid is left standing for
`TTL_CYCLES` decision cycles (the TTL-cancel horizon), and a cycle averages
`AVG_CYCLE_SECONDS` of wall time. `bid_vs_craft.should_bid` compares this horizon
against the pure craft-time estimate — bid only when self-crafting is strictly
slower than the fill horizon.
"""

TTL_CYCLES = 20
AVG_CYCLE_SECONDS = 30.0
BID_FILL_HORIZON_SECONDS = TTL_CYCLES * AVG_CYCLE_SECONDS
