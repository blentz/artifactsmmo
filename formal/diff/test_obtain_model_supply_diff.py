"""Differential: the real `supply_core.can_supply` (with its memo) must agree
with the kernel-proved `Formal.ObtainModelSupply.canSupply` on random graphs.

Graphs have up to 7 items with random stock (0-4), each with up to 3 supplies
of yield 1-3, capacity 0-12 (small, so it binds) or unbounded, and 0-3 inputs
among the graph's own items with amounts 1-3. Cycles, self-loops, shared
subtrees and capacity cuts all occur, so the memo is exercised where a stale
reuse would change an answer. Item codes are the decimal strings of their
Lean indices; every item is queried at quantities 0-6.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.obtain_model.supply_core import Supply, can_supply
from formal.diff.oracle_client import run_oracle

UNBOUNDED = 10**9

_Graph = tuple[int, list[int], list[list[tuple[int, int, list[tuple[int, int]]]]]]


@st.composite
def _graph(draw: st.DrawFn) -> _Graph:
    n = draw(st.integers(1, 7))
    stock = draw(st.lists(st.integers(0, 4), min_size=n, max_size=n))
    item = st.integers(0, n - 1)
    supply = st.tuples(st.integers(1, 3), st.one_of(st.integers(0, 12), st.just(UNBOUNDED)),
                       st.lists(st.tuples(item, st.integers(1, 3)), max_size=3))
    supplies = [draw(st.lists(supply, max_size=3)) for _ in range(n)]
    return n, stock, supplies


def _python(graph: _Graph, queries: list[tuple[int, int]]) -> list[bool]:
    n, stock, supplies = graph
    on_hand = {str(i): stock[i] for i in range(n)}
    table = {str(i): [Supply(y, c, tuple((str(x), k) for x, k in ins)) for y, c, ins in supplies[i]]
             for i in range(n)}
    return [can_supply(str(i), q, on_hand, table) for i, q in queries]


def _lean(graph: _Graph, queries: list[tuple[int, int]]) -> list[bool]:
    n, stock, supplies = graph
    encoded = [[[y, c, [[x, k] for x, k in ins]] for y, c, ins in per_item] for per_item in supplies]
    return run_oracle("obtain_model_supply", [[n, stock, encoded, [list(q) for q in queries]]])[0]["can"]


@settings(max_examples=500)
@given(graph=_graph())
def test_can_supply_matches_oracle(graph: _Graph) -> None:
    queries = [(i, q) for i in range(graph[0]) for q in range(7)]
    assert _python(graph, queries) == _lean(graph, queries), graph


def test_a_cut_answer_is_not_reused_on_both_sides() -> None:
    """Item 1 is first reached under a path holding 2 (its only way in, cut),
    then directly from 0, where 2 is open through ore 3: the answer is yes."""
    graph: _Graph = (4, [0, 0, 0, 0], [[(1, UNBOUNDED, [(2, 1), (1, 1)])],
                                        [(1, UNBOUNDED, [(2, 1)])],
                                        [(1, UNBOUNDED, [(1, 1)]), (1, UNBOUNDED, [(3, 1)])],
                                        [(1, UNBOUNDED, [])]])
    assert _python(graph, [(0, 1)]) == _lean(graph, [(0, 1)]) == [True]


def test_stock_and_yield_bound_the_amount_on_both_sides() -> None:
    """Item 0 crafts 2 per application from 1 of item 1, of which 3 are held:
    up to 6 units, not 7."""
    graph: _Graph = (2, [0, 3], [[(2, UNBOUNDED, [(1, 1)])], []])
    queries = [(0, 6), (0, 7)]
    assert _python(graph, queries) == _lean(graph, queries) == [True, False]
