"""Differential: the real `decompose_core` (joint feasibility AND next step) must
agree with the kernel-proved `Formal.Decompose` on random graphs.

Graphs have up to 7 items with random bag stock (0-4), each with up to 3 routes
of yield 0-3 (0 reads as 1 on both sides), capacity 0-12 (small, so it binds)
or unbounded, 0-3 inputs among the graph's own items with amounts 1-3, and 0-2
gates. Cycles, self-loops, shared subtrees, capacity cuts, gates and the
deficit all occur. Item codes are the Lean indices; every item is queried at
quantities 0-8, and both the feasibility answer and the step must match.
"""

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.decompose_core import Act, OpenGate, Route, Step, can_obtain, next_step
from formal.diff.oracle_client import run_oracle

UNBOUNDED = 10**9

_RouteT = tuple[int, int, int, list[tuple[int, int]], list[int]]
_Graph = tuple[int, list[int], list[list[_RouteT]]]
"""(n, bag, routes). A capped route plays a bank's WITHDRAW (or a licensed
recycle): the greedy fill mixes it with the routes after it."""


@st.composite
def _graph(draw: st.DrawFn) -> _Graph:
    n = draw(st.integers(1, 7))
    stock = draw(st.lists(st.integers(0, 4), min_size=n, max_size=n))
    item = st.integers(0, n - 1)
    route = st.tuples(st.integers(0, 9), st.integers(0, 3),
                      st.one_of(st.integers(0, 12), st.just(UNBOUNDED)),
                      st.lists(st.tuples(item, st.integers(1, 3)), max_size=3),
                      st.lists(st.integers(0, 4), max_size=2))
    routes = [draw(st.lists(route, max_size=3)) for _ in range(n)]
    return n, stock, routes


def _table(graph: _Graph) -> tuple[dict[int, int], dict[int, list[Route[int]]]]:
    n, stock, routes = graph
    table = {i: [Route(tag, y, c, tuple(ins), tuple(gates)) for tag, y, c, ins, gates in routes[i]]
             for i in range(n)}
    return {i: stock[i] for i in range(n)}, table


def _encode(step: Step | None) -> object:
    if step is None:
        return None
    if isinstance(step, Act):
        return {"act": [step.item, step.route, step.amount, step.runs]}
    assert isinstance(step, OpenGate)
    return {"open": [step.item, step.route, step.gate]}


def _python(graph: _Graph, queries: list[tuple[int, int]]) -> list[dict]:
    on_hand, table = _table(graph)
    return [{"can": can_obtain(i, q, on_hand, table), "step": _encode(next_step(i, q, on_hand, table))}
            for i, q in queries]


def _lean(graph: _Graph, queries: list[tuple[int, int]]) -> list[dict]:
    n, stock, routes = graph
    encoded = [[[tag, y, c, [[x, k] for x, k in ins], gates] for tag, y, c, ins, gates in per_item]
               for per_item in routes]
    return run_oracle("decompose", [[n, stock, encoded, [list(q) for q in queries]]])[0]


@settings(max_examples=500)
@given(graph=_graph())
def test_the_walk_matches_the_oracle(graph: _Graph) -> None:
    queries = [(i, q) for i in range(graph[0]) for q in range(9)]
    assert _python(graph, queries) == _lean(graph, queries), graph


def test_the_differential_is_not_vacuous() -> None:
    """Over a seeded sweep, every answer shape occurs: infeasible, satisfied,
    an act, an open-gate, and an act found by DESCENDING into an input (the
    step's item differs from the query's), and COMPLETE holds on the Python
    side (a feasible unmet query always has a step)."""
    rng = random.Random(20260929)
    shapes: set[str] = set()
    for _ in range(400):
        n = rng.randint(1, 6)
        stock = [rng.randint(0, 4) for _ in range(n)]
        routes = [[(rng.randint(0, 9), rng.randint(0, 3), rng.choice([rng.randint(0, 12), UNBOUNDED]),
                    [(rng.randint(0, n - 1), rng.randint(1, 3)) for _ in range(rng.randint(0, 2))],
                    [rng.randint(0, 4)] if rng.random() < 0.2 else [])
                   for _ in range(rng.randint(0, 3))] for _ in range(n)]
        graph: _Graph = (n, stock, routes)
        queries = [(i, q) for i in range(n) for q in range(7)]
        got = _python(graph, queries)
        assert got == _lean(graph, queries), graph
        for (i, q), answer in zip(queries, got, strict=True):
            step = answer["step"]
            if q <= stock[i]:
                shapes.add("satisfied")
            elif not answer["can"]:
                shapes.add("infeasible")
            else:
                assert step is not None, ("COMPLETE violated", graph, i, q)
                if "open" in step:
                    shapes.add("open")
                elif step["act"][0] != i:
                    shapes.add("descended")
                elif step["act"][2] < q - stock[i]:
                    shapes.add("partial")
                else:
                    shapes.add("act")
    assert shapes == {"satisfied", "infeasible", "open", "partial", "descended", "act"}, shapes


def test_an_answer_cut_by_the_path_is_not_the_answer_elsewhere() -> None:
    """Item 1 is first reached under a path holding 2 (its only way in, cut),
    then directly from 0, where 2 is open through ore 3: the answer is yes, and
    the step descends to the ore."""
    graph: _Graph = (4, [0, 0, 0, 0], [[(0, 1, UNBOUNDED, [(2, 1), (1, 1)], [])],
                                        [(0, 1, UNBOUNDED, [(2, 1)], [])],
                                        [(0, 1, UNBOUNDED, [(1, 1)], []),
                                         (1, 1, UNBOUNDED, [(3, 1)], [])],
                                        [(2, 1, UNBOUNDED, [], [])]])
    queries = [(0, 1)]
    got = _python(graph, queries)
    assert got == _lean(graph, queries)
    assert got == [{"can": True, "step": {"act": [3, 0, 1, 1]}}]


def test_siblings_sharing_a_material_cannot_both_count_it() -> None:
    """JOINT: 0 needs 2 of item 2 and one 1; 1 needs 2 of item 2; item 2 has no
    route. Two in the bag cover one ask, not both; four cover both, and the
    first leaf is the 1. The same holds for a bank's capacity (item 4: two asks
    of 2 from a bank of 3)."""
    shared: _Graph = (3, [0, 0, 2], [[(0, 1, UNBOUNDED, [(2, 2), (1, 1)], [])],
                                     [(1, 1, UNBOUNDED, [(2, 2)], [])], []])
    assert _python(shared, [(0, 1)]) == _lean(shared, [(0, 1)]) == [{"can": False, "step": None}]
    richer: _Graph = (3, [0, 0, 4], shared[2])
    assert _python(richer, [(0, 1)]) == _lean(richer, [(0, 1)]) == [
        {"can": True, "step": {"act": [1, 0, 1, 1]}}]
    bank: _Graph = (2, [0, 0], [[(0, 1, UNBOUNDED, [(1, 2), (1, 2)], [])], [(1, 1, 3, [], [])]])
    assert _python(bank, [(0, 1)]) == _lean(bank, [(0, 1)]) == [{"can": False, "step": None}]


def test_the_walk_is_greedy_so_holding_more_can_turn_yes_into_no() -> None:
    """The contract decided 2026-09-30: X's first route (M + Z) is taken as soon
    as a Z is held, spending the one M its sibling Y needed."""
    def greedy(z: int) -> _Graph:
        return (5, [0, 0, 0, 1, z], [[(0, 1, UNBOUNDED, [(1, 1), (2, 1)], [])],
                                     [(1, 1, UNBOUNDED, [(3, 1), (4, 1)], []), (2, 1, UNBOUNDED, [], [])],
                                     [(3, 1, UNBOUNDED, [(3, 1)], [])], [], []])
    for z, expected in ((0, True), (1, False)):
        got = _python(greedy(z), [(0, 1)])
        assert got == _lean(greedy(z), [(0, 1)])
        assert got[0]["can"] is expected
