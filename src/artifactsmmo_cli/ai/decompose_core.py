"""THE ONE WALK: feasibility and the next action in one computation, mirrored by
`formal/Formal/Decompose.lean` (Phase 2c-2 of
docs/PLAN_decision_architecture_redesign.md).

Two models used to answer "can I get N of X" (`supply_core`) and "what do I do
next" (`next_craft_core` over a separate recipe map and a lossy source
projection). They disagreed, and every disagreement read "the model says yes,
decomposition declines, the search times out". Here the next step is the first
leaf of the supply tree the feasibility walk finds, so they cannot disagree.
Kernel-checked properties of the Lean mirror: a feasible unmet goal always has a
step (complete); a step is only emitted when feasible (sound); an action is
emitted only for a ready route that can deliver the deficit, with every input
on hand (ordering); a gate-blocked route yields "open its first gate"; a route
runs `ceil(deficit / yield)` times; monotone in holdings and quantity; and the
fuel bound under which the Lean walk equals this unbounded one.

DEFICIT semantics, filled GREEDILY across routes: `qty` of `item` can be had when
the bag holds that many, or when the routes, in the order given, fill the deficit
`qty - bag[item]`: each usable route takes as much of what is left as its
capacity allows, provided every input can be had in the amount its runs consume.
A WITHDRAW route's capacity is the bank's stock, so banked stock mixes with
production (21 banked, 33 needed: withdraw 21, gather 12), and a licensed RECYCLE
covers what it can while a gather covers the rest. A CRAFT route's inputs are its
recipe. The adapter puts ready routes before gate-blocked ones. An item already
asked about further up the same path is not obtainable through itself.
"""

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Route[K: Hashable]:
    """One route to an item as the walk sees it. `tag` names the concrete
    action that serves it (opaque to the walk); `gates` are the openable gates
    that still block it (empty when it is ready)."""

    tag: Hashable
    yield_per: int
    capacity: int
    inputs: tuple[tuple[K, int], ...]
    gates: tuple[Hashable, ...] = ()


@dataclass(frozen=True)
class Act[K: Hashable]:
    """Run route `route` (its index in `item`'s list) `runs` times, delivering
    `amount` units."""

    item: K
    route: int
    amount: int
    runs: int


@dataclass(frozen=True)
class OpenGate[K: Hashable]:
    """Open `gate`, which blocks route `route` of `item`: a sub-task."""

    item: K
    route: int
    gate: Hashable


type Step[K: Hashable] = Act[K] | OpenGate[K]

type _Walk[K: Hashable] = tuple[bool, frozenset[K], frozenset[K]]
"""(answer, items visited, visited items found on the path)."""


def runs(deficit: int, yield_per: int) -> int:
    """Applications that deliver `deficit` units at `yield_per` each; a yield of
    0 in the data reads as 1."""
    return -(-deficit // max(1, yield_per))


class _Walker[K: Hashable]:
    """One question's walk: the graph plus the feasibility memo, shared by the
    feasibility answer and the step so both read the same verdicts."""

    def __init__(self, on_hand: Mapping[K, int], routes: Mapping[K, Sequence[Route[K]]]) -> None:
        self._on_hand = on_hand
        self._routes = routes
        self._memo: dict[tuple[K, int], _Walk[K]] = {}

    def can(self, item: K, qty: int, path: frozenset[K]) -> _Walk[K]:
        """The feasibility walk (`Decompose.can`). Each (item, qty) answer is
        memoised with the items its walk visited and, among them, the ones it
        found on the path (a cut); it is reused only under a path that holds
        exactly those cuts and no other visited item, where the walk would run
        identically (the `supply_core` memo, whose soundness argument carries
        over unchanged)."""
        have = self._on_hand.get(item, 0)
        if have >= qty:
            return True, frozenset({item}), frozenset()
        if item in path:
            return False, frozenset({item}), frozenset({item})
        cached = self._memo.get((item, qty))
        if cached is not None and cached[2] <= path and not ((cached[1] - cached[2]) & path):
            return cached
        answer, visited, cuts = self._fill(item, qty - have, path | {item})
        result = (answer, visited | {item}, cuts - {item})
        self._memo[(item, qty)] = result
        return result

    def _fill(self, item: K, deficit: int, inner: frozenset[K]) -> _Walk[K]:
        """`Decompose.fill`: `item`'s routes, in order, cover `deficit`; each
        contributing route takes `min(capacity, what is left)`."""
        visited: set[K] = set()
        cuts: set[K] = set()
        remaining = deficit
        for route in self._routes.get(item, ()):
            if remaining == 0:
                break
            take = min(route.capacity, remaining)
            if take <= 0:
                continue
            ok, seen, hit = self._usable(route, take, inner)
            visited |= seen
            cuts |= hit
            if ok:
                remaining -= take
        return remaining == 0, frozenset(visited), frozenset(cuts)

    def _usable(self, route: Route[K], deficit: int, inner: frozenset[K]) -> _Walk[K]:
        """`Decompose.usable`: every input can be had in the amount the runs for
        `deficit` consume (checked in order, stopping at the first that cannot,
        as `List.all` does). Callers pass an amount within the route's capacity
        (`take`), so the capacity conjunct of the Lean `usable` always holds."""
        n = runs(deficit, route.yield_per)
        visited: set[K] = set()
        cuts: set[K] = set()
        for material, per in route.inputs:
            found, seen, hit = self.can(material, n * per, inner)
            visited |= seen
            cuts |= hit
            if not found:
                return False, frozenset(visited), frozenset(cuts)
        return True, frozenset(visited), frozenset(cuts)

    def step(self, item: K, qty: int, path: frozenset[K]) -> Step[K] | None:
        """The first leaf of the supply the walk finds (`Decompose.step`): the
        first route that contributes to the fill, its gate, its first input the
        bag lacks, or the route itself."""
        have = self._on_hand.get(item, 0)
        if have >= qty or item in path:
            return None
        deficit = qty - have
        inner = path | {item}
        if not self._fill(item, deficit, inner)[0]:
            return None
        for index, route in enumerate(self._routes.get(item, ())):
            take = min(route.capacity, deficit)
            if take <= 0 or not self._usable(route, take, inner)[0]:
                continue
            if route.gates:
                return OpenGate(item, index, route.gates[0])
            n = runs(take, route.yield_per)
            for material, per in route.inputs:
                if self._on_hand.get(material, 0) < n * per:
                    return self.step(material, n * per, inner)
            return Act(item, index, take, n)
        return None  # pragma: no cover - a fill of a positive deficit has a contributor


def can_obtain[K: Hashable](item: K, qty: int, on_hand: Mapping[K, int],
                           routes: Mapping[K, Sequence[Route[K]]]) -> bool:
    """Can `qty` of `item` be had (`Decompose.can` at fuel n + 1)?"""
    return _Walker(on_hand, routes).can(item, qty, frozenset())[0]


def next_step[K: Hashable](item: K, qty: int, on_hand: Mapping[K, int],
                          routes: Mapping[K, Sequence[Route[K]]]) -> Step[K] | None:
    """The next step toward `qty` of `item` in the bag (`Decompose.nextStep`):
    None when the bag holds it or it is infeasible, and never None for a
    feasible goal the bag does not hold."""
    return _Walker(on_hand, routes).step(item, qty, frozenset())
