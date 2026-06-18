"""Pure ceil-division of raw gather UNITS into gather ACTIONS by drop yield.

`min_gathers` counts raw UNITS needed (one unit = one drop), implicitly assuming
each gather mints exactly one. The game's resource drop tables expose a per-gather
`max_quantity` > 1 for some resources, so the true minimum number of gather
ACTIONS to obtain `units` is `ceil(units / max_yield)` (best case: every gather
rolls the maximum drop). This is a TIGHTER — and still SOUND — lower bound than
`units` itself (`ceil(units / max_yield) <= units` for `max_yield >= 1`), so the
depth-unreachability gate (`gathers > max_depth ⇒ skip`) stops OVER-counting
multi-yield resources and no longer marks a reachable gear chain unplannable.

Mirrored by `Formal.StepDispatch.ceilGathers` and exercised through the
`gather_step_target` differential harness.
"""


def ceil_gathers(units: int, max_yield: int) -> int:
    """`ceil(units / max_yield)` for `units >= 0` and `max_yield >= 1`.

    `max_yield` is the resource drop table's `max_quantity` (>= 1 by
    construction — see `GameData.max_gather_yield`); callers source it from game
    data, never default it past the API. With `max_yield == 1` this is the
    identity on `units`, so single-yield resources keep their exact gather count.
    """
    return (units + max_yield - 1) // max_yield
