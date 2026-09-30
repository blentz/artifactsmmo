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
runs `ceil(deficit / yield)` times; a yes only ever spends the bag; and the fuel
bound under which the Lean walk equals this unbounded one.

DEFICIT semantics, filled GREEDILY across routes: `qty` of `item` can be had when
the bag holds that many, or when the routes, in the order given, fill the deficit
`qty - bag[item]`: each usable route takes as much of what is left as its
remaining capacity allows, provided every input can be had in the amount its runs
consume. A WITHDRAW route's capacity is the bank's stock, so banked stock mixes
with production (21 banked, 33 needed: withdraw 21, gather 12), and a licensed
RECYCLE covers what it can while a gather covers the rest. A CRAFT route's inputs
are its recipe. The adapter puts ready routes before gate-blocked ones. An item
already asked about further up the same path is not obtainable through itself.

JOINT (Phase 2d-L1): the walk threads what is left of the bag and of each
route's capacity through every question it asks, so sibling inputs that share a
material cannot both count the same stock. GREEDY: a usable route is taken even
when a later sibling then goes short, so a yes is sound but holding more can
turn a yes into a no (decided 2026-09-30; exact answers need a search
exponential in fan-out).
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

def runs(deficit: int, yield_per: int) -> int:
    """Applications that deliver `deficit` units at `yield_per` each; a yield of
    0 in the data reads as 1."""
    return -(-deficit // max(1, yield_per))


@dataclass(frozen=True)
class _State[K: Hashable]:
    """What the walk has left (`Decompose.St`): the bag, and the capacity spent
    on each (item, route index)."""

    bag: Mapping[K, int]
    used: Mapping[tuple[K, int], int]

    def reserve(self, item: K, qty: int) -> "_State[K]":
        bag = dict(self.bag)
        bag[item] = self.bag.get(item, 0) - qty
        return _State(bag, self.used)

    def use(self, item: K, index: int, amount: int) -> "_State[K]":
        used = dict(self.used)
        used[(item, index)] = self.used.get((item, index), 0) + amount
        return _State(self.bag, used)


class _Walker[K: Hashable]:
    """One question's walk over its graph (`Decompose.can` / `Decompose.step`)."""

    def __init__(self, routes: Mapping[K, Sequence[Route[K]]]) -> None:
        self._routes = routes

    @staticmethod
    def _take(st: _State[K], item: K, index: int, route: Route[K], deficit: int) -> int:
        return min(route.capacity - st.used.get((item, index), 0), deficit)

    def can(self, item: K, qty: int, st: _State[K], path: frozenset[K]) -> _State[K] | None:
        """`Decompose.can`: the state left once `qty` of `item` is had, or None."""
        have = st.bag.get(item, 0)
        if have >= qty:
            return st.reserve(item, qty)
        if item in path:
            return None
        return self._fill(item, qty - have, st.reserve(item, have), path | {item})

    def _fill(self, item: K, deficit: int, st: _State[K], inner: frozenset[K]) -> _State[K] | None:
        """`Decompose.fill`: `item`'s routes, in order, cover `deficit`; a route
        that contributes takes its share, one that fails changes nothing."""
        for index, route in enumerate(self._routes.get(item, ())):
            if deficit == 0:
                return st
            after = self._use(item, index, route, deficit, st, inner)
            if after is not None:
                deficit -= self._take(st, item, index, route, deficit)
                st = after
        return st if deficit == 0 else None

    def _use(self, item: K, index: int, route: Route[K], deficit: int, st: _State[K],
             inner: frozenset[K]) -> _State[K] | None:
        """`Decompose.useRoute`: the state after the route's share of its
        capacity and its inputs are spent, or None when it takes nothing or an
        input fails."""
        take = self._take(st, item, index, route, deficit)
        if take <= 0:
            return None
        n = runs(take, route.yield_per)
        cur: _State[K] | None = st.use(item, index, take)
        for material, per in route.inputs:
            assert cur is not None
            cur = self.can(material, n * per, cur, inner)
            if cur is None:
                return None
        return cur

    def step(self, item: K, qty: int, st: _State[K], path: frozenset[K]) -> Step[K] | None:
        """`Decompose.step`: the first leaf of the supply the walk finds: the
        first contributing route's gate, its first input the state lacks, or
        the route itself."""
        have = st.bag.get(item, 0)
        if have >= qty or item in path:
            return None
        deficit = qty - have
        start = st.reserve(item, have)
        inner = path | {item}
        if self._fill(item, deficit, start, inner) is None:
            return None
        for index, route in enumerate(self._routes.get(item, ())):
            if self._use(item, index, route, deficit, start, inner) is None:
                continue
            if route.gates:
                return OpenGate(item, index, route.gates[0])
            take = self._take(start, item, index, route, deficit)
            n = runs(take, route.yield_per)
            cur = start.use(item, index, take)
            for material, per in route.inputs:
                if cur.bag.get(material, 0) < n * per:
                    return self.step(material, n * per, cur, inner)
                cur = cur.reserve(material, n * per)
            return Act(item, index, take, n)
        return None  # pragma: no cover - a fill of a positive deficit has a contributor


def can_obtain[K: Hashable](item: K, qty: int, on_hand: Mapping[K, int],
                           routes: Mapping[K, Sequence[Route[K]]]) -> bool:
    """Can `qty` of `item` be had, jointly (`Decompose.feasible`)?"""
    return _Walker(routes).can(item, qty, _State(on_hand, {}), frozenset()) is not None


def next_step[K: Hashable](item: K, qty: int, on_hand: Mapping[K, int],
                          routes: Mapping[K, Sequence[Route[K]]]) -> Step[K] | None:
    """The next step toward `qty` of `item` in the bag (`Decompose.nextStep`):
    None when the bag holds it or it is infeasible, and never None for a
    feasible goal the bag does not hold."""
    return _Walker(routes).step(item, qty, _State(on_hand, {}), frozenset())
