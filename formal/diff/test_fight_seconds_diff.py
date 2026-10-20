"""Differential test for spec 2026-10-18 §2.9: the live
`ai/fight_seconds_core.fight_seconds` must agree with the proved
`Formal.FightSeconds.fightSeconds` on random turns, coefficients, haste and
floors, including a haste that removes the whole fight and the floor tie."""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.fight_seconds_core import fight_seconds
from formal.diff.oracle_client import run_oracle

_case = st.tuples(
    st.fractions(min_value=0, max_value=100, max_denominator=40),        # turns
    st.fractions(min_value=0, max_value=5, max_denominator=40),          # s_turn
    st.fractions(min_value=0, max_value=Fraction(99, 100), max_denominator=100),  # h
    st.integers(min_value=0, max_value=200),                             # haste
    st.fractions(min_value=0, max_value=30, max_denominator=20),         # floor
)


def _args(turns: Fraction, s_turn: Fraction, h: Fraction, haste: int,
          floor: Fraction) -> list[int]:
    return [turns.numerator, turns.denominator, s_turn.numerator, s_turn.denominator,
            h.numerator, h.denominator, haste, floor.numerator, floor.denominator]


def _lean(row: dict[str, object]) -> Fraction:
    return Fraction(int(row["num"]), int(row["den"]))  # type: ignore[call-overload]


@settings(max_examples=300, deadline=None)
@given(cases=st.lists(_case, min_size=1, max_size=30))
def test_fight_seconds_matches_lean(
        cases: list[tuple[Fraction, Fraction, Fraction, int, Fraction]]) -> None:
    rows = run_oracle("fight_seconds", [_args(*case) for case in cases])
    for case, row in zip(cases, rows, strict=True):
        assert fight_seconds(*case) == _lean(row), case


def test_edges_against_lean() -> None:
    """A 5-turn fight at 2 s a turn less 1% for 8 haste (46/5 s); the floor
    over a short fight; a haste that removes the fight (the floor); a tie."""
    cases = [
        (Fraction(5), Fraction(2), Fraction(1, 100), 8, Fraction(3)),
        (Fraction(1), Fraction(2), Fraction(0), 0, Fraction(3)),
        (Fraction(10), Fraction(2), Fraction(1, 2), 3, Fraction(3)),
        (Fraction(3, 2), Fraction(2), Fraction(0), 0, Fraction(3)),
    ]
    rows = run_oracle("fight_seconds", [_args(*case) for case in cases])
    expected = [Fraction(46, 5), Fraction(3), Fraction(3), Fraction(3)]
    assert [_lean(row) for row in rows] == expected
    assert [fight_seconds(*case) for case in cases] == expected
