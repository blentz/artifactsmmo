"""Differential test: the real Python pure core
`artifactsmmo_cli.ai.bag_clear_core` (`clear_route`, `slots_freed`) must agree
with the proved Lean core `Formal.BagClear` (`clearRoute`, `freed`) on EVERY
row (Task 13e: a full bag frees every slot the plan does not use).

The route domain is Bool³, so every single-stack input is enumerated
exhaustively; whole bags (route list + slots freed) are fuzzed.
"""
from itertools import product

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.bag_clear_core import ClearRoute, clear_route, slots_freed
from formal.diff.oracle_client import run_oracle

_CODE = {ClearRoute.KEEP: 0, ClearRoute.DEPOSIT: 1, ClearRoute.DISPOSE: 2}

Row = tuple[bool, bool, bool]


def _lean(bag: list[Row]) -> tuple[list[int], int]:
    args: list[int] = [len(bag)]
    for related, bank_takes, disposable in bag:
        args += [int(related), int(bank_takes), int(disposable)]
    out = run_oracle("bag_clear", [args])[0]
    return list(out["routes"]), int(out["freed"])


def _python(bag: list[Row]) -> tuple[list[int], int]:
    routes = [clear_route(*row) for row in bag]
    return [_CODE[r] for r in routes], slots_freed(routes)


def test_every_single_stack_input_matches_lean() -> None:
    for row in product((False, True), repeat=3):
        assert _python([row]) == _lean([row]), row


def test_r2d2_shape_matches_lean() -> None:
    """Live R2D2: the porkchop inputs and the kept amulet related, 18 junk
    stacks the bank takes."""
    bag: list[Row] = [(True, False, False), (True, False, False)] + [(False, True, False)] * 18
    py = _python(bag)
    assert py == _lean(bag)
    assert py[1] == 18


def test_all_related_frees_nothing() -> None:
    bag: list[Row] = [(True, True, True), (True, False, True), (True, False, False)]
    assert _python(bag) == _lean(bag) == ([0, 0, 0], 0)


@settings(max_examples=200)
@given(st.lists(st.tuples(st.booleans(), st.booleans(), st.booleans()), max_size=25))
def test_bags_match_lean(bag: list[Row]) -> None:
    assert _python(bag) == _lean(bag)
