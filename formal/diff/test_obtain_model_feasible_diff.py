"""Differential: the real `feasible_core.feasible_items` must agree with the
kernel-proved `Formal.ObtainModelFeasible.feasible` on random item graphs.

Graphs have up to 8 items with random holdings and random ready routes, each
route naming 0-3 inputs among the graph's own items, so cycles, self-loops,
routes with no inputs, and items with no route all occur. Item codes are the
decimal strings of their Lean indices.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.obtain_model.feasible_core import feasible_items
from formal.diff.oracle_client import run_oracle


@st.composite
def _graph(draw: st.DrawFn) -> tuple[int, list[bool], list[list[list[int]]]]:
    n = draw(st.integers(0, 8))
    held = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    item = st.integers(0, max(n - 1, 0))
    routes = [draw(st.lists(st.lists(item, max_size=3), max_size=3)) if n else [] for _ in range(n)]
    return n, held, routes


def _python(n: int, held: list[bool], routes: list[list[list[int]]]) -> list[bool]:
    found = feasible_items([str(i) for i in range(n)], {str(i) for i in range(n) if held[i]},
                           {str(i): [[str(x) for x in r] for r in routes[i]] for i in range(n)})
    return [str(i) in found for i in range(n)]


def _lean(n: int, held: list[bool], routes: list[list[list[int]]]) -> list[bool]:
    return run_oracle("obtain_model_feasible", [[n, [int(h) for h in held], routes]])[0]["feasible"]


@settings(max_examples=500)
@given(graph=_graph())
def test_feasible_items_matches_oracle(graph: tuple[int, list[bool], list[list[list[int]]]]) -> None:
    n, held, routes = graph
    assert _python(n, held, routes) == _lean(n, held, routes), graph


def test_a_cycle_needs_a_way_in_on_both_sides() -> None:
    """0 needs 1 and 1 needs 0: infeasible until one of them is held."""
    routes = [[[1]], [[0]]]
    assert _python(2, [False, False], routes) == _lean(2, [False, False], routes) == [False, False]
    assert _python(2, [False, True], routes) == _lean(2, [False, True], routes) == [True, True]


def test_a_long_chain_resolves_on_both_sides() -> None:
    """Item i needs i+1, the last is free: the fixpoint must run the full length,
    which a bounded number of rounds too small for n would miss."""
    n = 8
    routes = [[[i + 1]] for i in range(n - 1)] + [[[]]]
    assert _python(n, [False] * n, routes) == _lean(n, [False] * n, routes) == [True] * n
