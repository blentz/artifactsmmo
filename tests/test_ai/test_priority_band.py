"""Tests for `clamp_into_band`: the discretionary-band clamp shared by goals.

The clamp must keep `floor + bonus` inside `[floor, ceiling]` regardless of the
bonus sign or magnitude, so a learned bonus can never push a discretionary goal
above the survival floor. Inputs are EXACT Fractions (matches the Lean Rat model
byte-for-byte; see `formal/Formal/PriorityBand.lean`).
"""
from fractions import Fraction

from artifactsmmo_cli.ai.priority_band import clamp_into_band

SURVIVAL_FLOOR = Fraction(70)
FLOOR = Fraction(30)
CEILING = Fraction(45)


def test_bonus_within_band_passes_through():
    # floor + bonus = 35, strictly inside [30, 45].
    assert clamp_into_band(FLOOR, CEILING, Fraction(5)) == Fraction(35)


def test_zero_bonus_returns_floor():
    assert clamp_into_band(FLOOR, CEILING, Fraction(0)) == Fraction(30)


def test_large_positive_bonus_clamped_to_ceiling():
    assert clamp_into_band(FLOOR, CEILING, Fraction(1000)) == Fraction(45)


def test_negative_bonus_clamped_to_floor():
    assert clamp_into_band(FLOOR, CEILING, Fraction(-1000)) == Fraction(30)


def test_bonus_exactly_reaching_ceiling():
    assert clamp_into_band(FLOOR, CEILING, Fraction(15)) == Fraction(45)


def test_result_never_escapes_band_for_any_bonus():
    bonuses = [Fraction(-10**9), Fraction(-100), Fraction(-1),
               Fraction(0), Fraction(1), Fraction(15, 2),
               Fraction(100), Fraction(10**9)]
    for bonus in bonuses:
        result = clamp_into_band(FLOOR, CEILING, bonus)
        assert FLOOR <= result <= CEILING


def test_result_stays_below_survival_floor():
    # Discretionary ceiling (45) sits below the survival floor (70): no bonus
    # can ever lift the clamped result to or above the survival floor.
    for bonus in (Fraction(-10**9), Fraction(0), Fraction(10**9)):
        assert clamp_into_band(FLOOR, CEILING, bonus) < SURVIVAL_FLOOR


def test_fractional_bonus_is_exact():
    """Fractional bonus inside the band is preserved EXACTLY (no rounding)."""
    bonus = Fraction(7, 3)  # 30 + 7/3 = 97/3 ≈ 32.33, well inside [30, 45]
    result = clamp_into_band(FLOOR, CEILING, bonus)
    assert result == Fraction(97, 3)
