"""Differential test: real Python `clamp_into_band` must agree EXACTLY (bit-for-bit)
with the proved Lean `clampIntoBand` over the rational domain.

`clamp_into_band(floor, ceiling, bonus)` clamps `floor + bonus` into
`[floor, ceiling]`. Both the Python core and the Lean model operate over EXACT
rationals (`fractions.Fraction` / `Rat`); we generate fractional triples
(including negative bonus, denominators 1..6 so genuine non-integers appear),
arrange `floor <= ceiling`, assert the Python result equals the Lean oracle
EXACTLY as a Fraction (numerator/denominator identity), AND assert the proven
invariant `floor <= result <= ceiling` directly on the Python value.

Production callsite reality: `GrindCharacterXPGoal.value` lifts
`char_xp * SCALAR_TO_PRIORITY_GAIN` and the band constants `PRIORITY_FLOOR`/
`PRIORITY_CEILING` to `Fraction` before invoking `clamp_into_band`, so every
production invocation uses the same exact-rational arithmetic this test pins.
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.priority_band import clamp_into_band
from formal.diff.oracle_client import run_oracle


def _rat(flat: list[int], frac: Fraction) -> None:
    flat += [frac.numerator, frac.denominator]


def _lean_clamped(floor: Fraction, ceiling: Fraction, bonus: Fraction) -> Fraction:
    flat: list[int] = []
    _rat(flat, floor)
    _rat(flat, ceiling)
    _rat(flat, bonus)
    res = run_oracle("priority_band", [flat])[0]
    return Fraction(res["clamped_num"], res["clamped_den"])


@settings(max_examples=300)
@given(
    floor=st.fractions(min_value=-1000, max_value=1000, max_denominator=6),
    # ceiling >= floor: a real discretionary band; built as floor + nonneg span.
    span=st.fractions(min_value=0, max_value=2000, max_denominator=6),
    # bonus may be negative, zero, or arbitrarily large in magnitude.
    bonus=st.fractions(min_value=-5000, max_value=5000, max_denominator=6),
)
def test_python_matches_lean(floor, span, bonus):
    ceiling = floor + span
    py = clamp_into_band(floor, ceiling, bonus)
    lean = _lean_clamped(floor, ceiling, bonus)
    assert isinstance(py, Fraction), py
    assert py == lean
    # The proven band invariant: result never escapes [floor, ceiling].
    assert floor <= py <= ceiling


def test_large_negative_bonus_clamps_to_floor_against_lean():
    """A hugely negative bonus (e.g. a run of observed-negative char_xp) cannot
    push priority below the floor — pins the lower clamp against Lean."""
    floor, ceiling, bonus = Fraction(30), Fraction(45), Fraction(-100000)
    lean = _lean_clamped(floor, ceiling, bonus)
    assert clamp_into_band(floor, ceiling, bonus) == Fraction(30) == lean


def test_large_positive_bonus_clamps_to_ceiling_against_lean():
    """A hugely positive bonus cannot push priority above the ceiling (so it can
    never reach the survival floor 70) — pins the upper clamp against Lean."""
    floor, ceiling, bonus = Fraction(30), Fraction(45), Fraction(100000)
    lean = _lean_clamped(floor, ceiling, bonus)
    assert clamp_into_band(floor, ceiling, bonus) == Fraction(45) == lean
    assert lean < Fraction(70)  # below the survival floor, by construction


def test_fractional_bonus_bit_exact():
    """Fractional bonus (e.g. char_xp=7/3 * 5) lands at floor + bonus exactly,
    with no float rounding. Pins the EXACT-RATIONAL byte-equivalence."""
    floor, ceiling = Fraction(30), Fraction(45)
    bonus = Fraction(7, 3) * Fraction(5)  # = 35/3, well within the band
    py = clamp_into_band(floor, ceiling, bonus)
    assert py == floor + bonus == Fraction(125, 3)
    lean = _lean_clamped(floor, ceiling, bonus)
    assert py == lean
