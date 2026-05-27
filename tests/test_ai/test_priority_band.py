"""Tests for `clamp_into_band`: the discretionary-band clamp shared by goals.

The clamp must keep `floor + bonus` inside `[floor, ceiling]` regardless of the
bonus sign or magnitude, so a learned bonus can never push a discretionary goal
above the survival floor.
"""
from artifactsmmo_cli.ai.priority_band import clamp_into_band

SURVIVAL_FLOOR = 70.0


def test_bonus_within_band_passes_through():
    # floor + bonus = 35, strictly inside [30, 45].
    assert clamp_into_band(30.0, 45.0, 5.0) == 35.0


def test_zero_bonus_returns_floor():
    assert clamp_into_band(30.0, 45.0, 0.0) == 30.0


def test_large_positive_bonus_clamped_to_ceiling():
    assert clamp_into_band(30.0, 45.0, 1000.0) == 45.0


def test_negative_bonus_clamped_to_floor():
    assert clamp_into_band(30.0, 45.0, -1000.0) == 30.0


def test_bonus_exactly_reaching_ceiling():
    assert clamp_into_band(30.0, 45.0, 15.0) == 45.0


def test_result_never_escapes_band_for_any_bonus():
    floor, ceiling = 30.0, 45.0
    for bonus in (-1e9, -100.0, -1.0, 0.0, 1.0, 7.5, 100.0, 1e9):
        result = clamp_into_band(floor, ceiling, bonus)
        assert floor <= result <= ceiling


def test_result_stays_below_survival_floor():
    # Discretionary ceiling (45) sits below the survival floor (70): no bonus
    # can ever lift the clamped result to or above the survival floor.
    floor, ceiling = 30.0, 45.0
    for bonus in (-1e9, 0.0, 1e9):
        assert clamp_into_band(floor, ceiling, bonus) < SURVIVAL_FLOOR
