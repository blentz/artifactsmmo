"""The fight-seconds core (spec 2026-10-18 §2.9): a fight's seconds from its
turns and the fighter's haste, and the fit of both coefficients and the floor
from observed fights."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.fight_seconds_core import expected_turns, fight_seconds, fit, server_turns
from artifactsmmo_cli.ai.fight_terms_core import MAX_TURNS


def test_seconds_are_turns_times_the_hasted_turn() -> None:
    assert fight_seconds(Fraction(5), Fraction(2), Fraction(1, 100), 8, Fraction(3)) == Fraction(46, 5)


def test_a_short_fight_costs_the_floor() -> None:
    assert fight_seconds(Fraction(1), Fraction(2), Fraction(0), 0, Fraction(3)) == 3


def test_a_haste_that_removes_the_fight_leaves_the_floor() -> None:
    assert fight_seconds(Fraction(10), Fraction(2), Fraction(1, 2), 3, Fraction(3)) == 3


@pytest.mark.parametrize(("turns", "s_turn", "h", "haste", "floor"), [
    (Fraction(-1), Fraction(2), Fraction(0), 0, Fraction(3)),
    (Fraction(1), Fraction(-2), Fraction(0), 0, Fraction(3)),
    (Fraction(1), Fraction(2), Fraction(-1, 10), 0, Fraction(3)),
    (Fraction(1), Fraction(2), Fraction(1), 0, Fraction(3)),
    (Fraction(1), Fraction(2), Fraction(0), -1, Fraction(3)),
    (Fraction(1), Fraction(2), Fraction(0), 0, Fraction(-3)),
])
def test_out_of_range_inputs_raise(turns: Fraction, s_turn: Fraction, h: Fraction, haste: int,
                                   floor: Fraction) -> None:
    with pytest.raises(ValueError, match="fight_seconds out of range"):
        fight_seconds(turns, s_turn, h, haste, floor)


def test_the_fit_recovers_an_exact_law() -> None:
    """Cooldowns made by 2 s a turn less 5% a haste point are read back exactly."""
    samples = [(t, a, float(Fraction(2 * t) * (1 - Fraction(a, 20))))
               for t in (5, 10) for a in (0, 4, 10)]
    assert fit(samples) == (Fraction(2), Fraction(1, 20), Fraction(5))


def test_a_constant_haste_fits_the_seconds_at_that_haste() -> None:
    """The haste never varies, so its effect is not identified: h is 0 and the
    seconds per turn are the least-squares slope at that haste."""
    assert fit([(5, 8, 9.0), (7, 8, 13.0)]) == (Fraction(5 * 9 + 7 * 13, 25 + 49), Fraction(0),
                                                 Fraction(9))


def test_a_haste_that_slows_is_clamped_to_none() -> None:
    """More haste, more seconds: the fitted h is negative, so h is 0 and the
    slope is refitted alone."""
    assert fit([(5, 0, 10.0), (5, 10, 12.0)]) == (Fraction(11, 5), Fraction(0), Fraction(10))


def test_a_negative_slope_raises() -> None:
    with pytest.raises(ValueError, match="is not positive"):
        fit([(2, 2, 8.0), (2, 3, 10.0), (1, 3, 18.0)])


def test_a_non_positive_cooldown_is_no_observation() -> None:
    """A 0 s row is dropped from the floor and the fit: the floor is the least
    positive cooldown."""
    assert fit([(5, 0, 10.0), (3, 0, 0.0), (4, 0, -1.0)]) == (Fraction(2), Fraction(0), Fraction(10))


@pytest.mark.parametrize("samples", [[], [(5, 0, 0.0)]])
def test_no_observation_raises(samples: list[tuple[int, int, float]]) -> None:
    with pytest.raises(ValueError, match="no fight with a positive cooldown"):
        fit(samples)


def test_a_negative_turn_or_haste_raises() -> None:
    with pytest.raises(ValueError, match="negative turns or haste"):
        fit([(-1, 0, 5.0)])


def test_fights_of_no_turns_raise() -> None:
    with pytest.raises(ValueError, match="0 turns"):
        fit([(0, 0, 5.0)])


@pytest.mark.parametrize(("rounds", "win", "player_first", "turns"), [
    (3, True, True, 5),    # live Robby v wolf: the player's third attack, turn 5
    (3, True, False, 6),
    (3, False, True, 6),
    (3, False, False, 5),
    (0, False, True, 0),
])
def test_a_round_is_one_turn_of_each_side(rounds: int, win: bool, player_first: bool,
                                         turns: int) -> None:
    assert server_turns(rounds, win, player_first) == turns


def test_expected_turns_weigh_the_endings() -> None:
    endings = [(Fraction(1, 4), True, 3), (Fraction(3, 4), False, 2)]
    assert expected_turns(endings, True) == Fraction(1, 4) * 5 + Fraction(3, 4) * 4


def test_expected_turns_are_capped() -> None:
    assert expected_turns([(Fraction(1), False, 100)], True) == MAX_TURNS
