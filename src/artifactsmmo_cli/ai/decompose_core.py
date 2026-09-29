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

DEFICIT semantics: `qty` of `item` can be had when that many are on hand, or
when some route can deliver the deficit `qty - on_hand[item]` (its capacity
allows it) and every input can be had in the amount its runs consume. A CRAFT
route's inputs are its recipe; a WITHDRAW route's capacity is the bank's stock,
and `on_hand` is the bag. Routes are tried in the order given (the adapter puts
ready routes before gate-blocked ones). An item already asked about further up
the same path is not obtainable through itself.
"""

from collections.abc import Hashable, Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Route:
    """One route to an item as the walk sees it. `tag` names the concrete
    action that serves it (opaque to the walk); `gates` are the openable gates
    that still block it (empty when it is ready)."""

    tag: Hashable
    yield_per: int
    capacity: int
    inputs: tuple[tuple[Hashable, int], ...]
    gates: tuple[Hashable, ...] = ()


@dataclass(frozen=True)
class Act:
    """Run route `route` (its index in `item`'s list) `runs` times, serving a
    deficit of `need` units."""

    item: Hashable
    route: int
    need: int
    runs: int


@dataclass(frozen=True)
class OpenGate:
    """Open `gate`, which blocks route `route` of `item`: a sub-task."""

    item: Hashable
    route: int
    gate: Hashable


Step = Act | OpenGate

_Walk = tuple[bool, frozenset[Hashable], frozenset[Hashable]]
"""(answer, items visited, visited items found on the path)."""


def runs(deficit: int, yield_per: int) -> int:
    """Applications that deliver `deficit` units at `yield_per` each; a yield of
    0 in the data reads as 1."""
    return -(-deficit // max(1, yield_per))


class _Walker:
    """One question's walk: the graph plus the feasibility memo, shared by the
    feasibility answer and the step so both read the same verdicts."""

    def __init__(self, on_hand: Mapping[Hashable, int],
                 routes: Mapping[Hashable, Sequence[Route]]) -> None:
        self._on_hand = on_hand
        self._routes = routes
        self._memo: dict[tuple[Hashable, int], _Walk] = {}

    def can(self, item: Hashable, qty: int, path: frozenset[Hashable]) -> _Walk:
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
        inner = path | {item}
        deficit = qty - have
        visited = {item}
        cuts: set[Hashable] = set()
        answer = False
        for route in self._routes.get(item, ()):
            ok, seen, hit = self._usable(route, deficit, inner)
            visited |= seen
            cuts |= hit - {item}
            if ok:
                answer = True
                break
        result = (answer, frozenset(visited), frozenset(cuts))
        self._memo[(item, qty)] = result
        return result

    def _usable(self, route: Route, deficit: int, inner: frozenset[Hashable]) -> _Walk:
        """`Decompose.usable`: the route can deliver the deficit and every input
        can be had in the amount its runs consume (checked in order, stopping
        at the first that cannot, as `List.all` does)."""
        if route.capacity < deficit:
            return False, frozenset(), frozenset()
        n = runs(deficit, route.yield_per)
        visited: set[Hashable] = set()
        cuts: set[Hashable] = set()
        for material, per in route.inputs:
            found, seen, hit = self.can(material, n * per, inner)
            visited |= seen
            cuts |= hit
            if not found:
                return False, frozenset(visited), frozenset(cuts)
        return True, frozenset(visited), frozenset(cuts)

    def step(self, item: Hashable, qty: int, path: frozenset[Hashable]) -> Step | None:
        """The first leaf of the supply tree (`Decompose.step`)."""
        have = self._on_hand.get(item, 0)
        if have >= qty or item in path:
            return None
        deficit = qty - have
        inner = path | {item}
        for index, route in enumerate(self._routes.get(item, ())):
            if not self._usable(route, deficit, inner)[0]:
                continue
            if route.gates:
                return OpenGate(item, index, route.gates[0])
            n = runs(deficit, route.yield_per)
            for material, per in route.inputs:
                if self._on_hand.get(material, 0) < n * per:
                    return self.step(material, n * per, inner)
            return Act(item, index, deficit, n)
        return None


def can_obtain(item: Hashable, qty: int, on_hand: Mapping[Hashable, int],
               routes: Mapping[Hashable, Sequence[Route]]) -> bool:
    """Can `qty` of `item` be had (`Decompose.can` at fuel n + 1)?"""
    return _Walker(on_hand, routes).can(item, qty, frozenset())[0]


def next_step(item: Hashable, qty: int, on_hand: Mapping[Hashable, int],
              routes: Mapping[Hashable, Sequence[Route]]) -> Step | None:
    """The next step toward `qty` of `item` (`Decompose.nextStep`): None when
    satisfied or infeasible, and never None for a feasible unmet goal."""
    return _Walker(on_hand, routes).step(item, qty, frozenset())
