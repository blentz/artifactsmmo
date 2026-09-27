"""The pure quantity walk behind `ObtainModel.feasible`, mirrored by
`formal/Formal/ObtainModelSupply.lean::can`.

"Can I get `qty` units of X from here?" Yes when that many are on hand, or
when some ready route can deliver `qty` (its capacity allows it) and every
input can be had in the amount its applications consume. A route used `runs`
times, `runs = ceil(qty / yield_per)`, consumes `runs * per_application` of
each input. An item already being asked about further up the same path is
not obtainable through itself: cycles resolve to no.

Kept apart from the model so the differential harness can drive it with
arbitrary graphs. Kernel-checked properties of the Lean mirror: soundness
(every yes has a finite supply tree), monotonicity in holdings, antitonicity in
quantity (fewer is never harder), and a fuel bound that makes the mirror's
recursion reach the same answer as this unbounded one.

Deliberately conservative: stock and production are not mixed (holding 3 of 5
does not make the other 2 cheaper to produce), and two inputs that draw on the
same stock each see all of it. The planner does the exact accounting; this
answers whether an attempt can succeed at all, not what it costs.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Supply:
    """One ready route as the walk sees it: `yield_per` units per application,
    at most `capacity` units in total, consuming `inputs` (item, amount) per
    application."""

    yield_per: int
    capacity: int
    inputs: tuple[tuple[str, int], ...]


def can_supply(item: str, qty: int, on_hand: Mapping[str, int],
               supplies: Mapping[str, Sequence[Supply]]) -> bool:
    """Whether `qty` units of `item` can be had (see the module docstring).

    Each (item, qty) answer is memoised with the items its walk visited and,
    among them, the ones it found already on the path (a cut). The walk reads
    the path only at visited items, so a later ask under a path that holds
    exactly those cuts and no other visited item would run identically, and
    reuses the answer. Without the memo a node reached by many parents is
    re-walked per parent, and the cost grows exponentially with recipe fan-out
    (the `acquisition_cost_core` blow-up)."""
    memo: dict[tuple[str, int], _Walk] = {}
    return _can(item, qty, frozenset(), on_hand, supplies, memo)[0]


_Walk = tuple[bool, frozenset[str], frozenset[str]]
"""(answer, items visited, visited items found on the path)."""


def _can(item: str, qty: int, path: frozenset[str], on_hand: Mapping[str, int],
         supplies: Mapping[str, Sequence[Supply]], memo: dict[tuple[str, int], _Walk]) -> _Walk:
    """The walk for `qty` of `item` under `path`."""
    if on_hand.get(item, 0) >= qty:
        return True, frozenset({item}), frozenset()
    if item in path:
        return False, frozenset({item}), frozenset({item})
    cached = memo.get((item, qty))
    if cached is not None and cached[2] <= path and not ((cached[1] - cached[2]) & path):
        return cached
    inner = path | {item}
    visited = {item}
    cuts: set[str] = set()
    answer = False
    for supply in supplies.get(item, ()):
        if supply.capacity < qty:
            continue
        runs = -(-qty // supply.yield_per)
        ok = True
        for material, per_application in supply.inputs:
            found, seen, hit = _can(material, runs * per_application, inner, on_hand, supplies, memo)
            visited |= seen
            cuts |= hit - {item}
            if not found:
                ok = False
                break
        if ok:
            answer = True
            break
    result = (answer, frozenset(visited), frozenset(cuts))
    memo[(item, qty)] = result
    return result
