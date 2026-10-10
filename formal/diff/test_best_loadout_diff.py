"""Differential tests for consumable utility increment 4: the live
`ai/best_loadout_core.pick_best` must agree with the proved
`Formal.BestLoadout.pick` — the highest XP rate, then the fewer units, then the
earlier candidate. Rates are drawn from a small grid so equal rates (and full
ties) are common, which is where the tie rules bite."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.best_loadout_core import pick_best
from formal.diff.oracle_client import run_oracle

_rate = st.fractions(min_value=0, max_value=3, max_denominator=4)
_cand = st.tuples(_rate, st.integers(min_value=0, max_value=4))


def _args(cands: list[tuple[Fraction, int]]) -> list[int]:
    args = [len(cands)]
    for rate, units in cands:
        args += [rate.numerator, rate.denominator, units]
    return args


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(st.lists(_cand, max_size=8), min_size=1, max_size=30))
def test_pick_matches_lean(cases: list[list[tuple[Fraction, int]]]) -> None:
    rows = run_oracle("best_loadout_pick", [_args(c) for c in cases])
    for cands, row in zip(cases, rows, strict=True):
        live = pick_best(cands)
        assert (-1 if live is None else live) == row["pick"], cands


def test_pick_witnesses_against_lean() -> None:
    """The Lean file's witnesses, through the oracle and the live code."""
    cases = [
        [(Fraction(1, 4), 0), (Fraction(1, 3), 5), (Fraction(2, 6), 2)],
        [(Fraction(1, 3), 2), (Fraction(2, 6), 2)],
        [(Fraction(0), 0), (Fraction(0), 0)],
        [],
    ]
    rows = run_oracle("best_loadout_pick", [_args(c) for c in cases])
    assert [row["pick"] for row in rows] == [2, 0, 0, -1]
    assert [pick_best(c) for c in cases] == [2, 0, 0, None]
