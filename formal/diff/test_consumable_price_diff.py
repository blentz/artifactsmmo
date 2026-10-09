"""Differential test for consumable utility increment 2: the live
`ai/consumable_price_core.consumable_price` must agree with the proved
`Formal.ConsumablePrice.consumablePrice` on random sides, including held stock,
absent sides, a zero or negative gold rate and exact ties."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.consumable_price_core import consumable_price
from formal.diff.oracle_client import run_oracle

_frac = st.fractions(min_value=0, max_value=500, max_denominator=40)
_case = st.tuples(
    st.integers(min_value=-2, max_value=3),                       # held
    st.one_of(st.none(), _frac),                                  # make seconds
    st.one_of(st.none(), st.integers(min_value=0, max_value=400)),  # buy gold
    st.one_of(st.just(Fraction(0)), st.fractions(min_value=-2, max_value=6,
                                                 max_denominator=30)),  # gold/second
)


def _args(held: int, make: Fraction | None, gold: int | None, rate: Fraction) -> list[int]:
    positive = rate if rate > 0 else Fraction(0)
    return [max(0, held),
            0 if make is None else 1, 0 if make is None else make.numerator,
            1 if make is None else make.denominator,
            0 if gold is None else 1, 0 if gold is None else gold,
            positive.numerator, positive.denominator]


def _lean(row: dict[str, object]) -> Fraction | None:
    if row["none"]:
        return None
    return Fraction(int(row["num"]), int(row["den"]))  # type: ignore[call-overload]


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_case, min_size=1, max_size=30))
def test_consumable_price_matches_lean(cases: list[tuple[int, Fraction | None, int | None, Fraction]]) -> None:
    rows = run_oracle("consumable_price", [_args(*case) for case in cases])
    for case, row in zip(cases, rows, strict=True):
        assert consumable_price(*case) == _lean(row), case


def test_ties_and_edges_against_lean() -> None:
    """Make 80 s against 40 gold at 1/2 gold a second (80 s): the shared value."""
    cases = [
        (0, Fraction(80), 40, Fraction(1, 2)),   # tie
        (0, Fraction(81), 40, Fraction(1, 2)),   # buy
        (0, Fraction(79), 40, Fraction(1, 2)),   # make
        (2, None, None, Fraction(0)),            # held
        (0, None, 40, Fraction(0)),              # no rate, no make: unpriceable
        (0, None, 40, Fraction(-1)),             # a negative rate is no rate
    ]
    rows = run_oracle("consumable_price", [_args(*case) for case in cases])
    assert [_lean(row) for row in rows] == [80, 80, 79, 0, None, None]
    assert [consumable_price(*case) for case in cases] == [80, 80, 79, 0, None, None]
