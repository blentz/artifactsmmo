"""Rest before a fight, or fight now: the pure comparison (`rest_first_core`)."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.rest_first_core import kill_seconds, rest_first


def test_kill_seconds_is_the_try_over_its_odds() -> None:
    assert kill_seconds(Fraction(1), Fraction(86)) == 86
    assert kill_seconds(Fraction(1, 2), Fraction(124)) == 248


def test_a_fight_that_cannot_be_won_has_no_kill_seconds() -> None:
    assert kill_seconds(Fraction(0), Fraction(30)) is None


@pytest.mark.parametrize(("p_win", "try_seconds"), [
    (Fraction(-1, 10), Fraction(30)),
    (Fraction(11, 10), Fraction(30)),
    (Fraction(1, 2), Fraction(-1)),
])
def test_kill_seconds_refuses_out_of_range_terms(p_win: Fraction, try_seconds: Fraction) -> None:
    with pytest.raises(ValueError, match="out of range"):
        kill_seconds(p_win, try_seconds)


def test_rest_first_when_the_rest_buys_back_more_than_it_costs() -> None:
    """R2D2 v king_slime at 452/890 HP, 2026-10-17: ~211 s a kill fighting
    now, a 50 s rest and ~86 s from full."""
    assert rest_first(50, Fraction(211), Fraction(86)) is True


def test_fight_now_when_the_rest_buys_back_less() -> None:
    assert rest_first(50, Fraction(120), Fraction(86)) is False


def test_a_tie_fights_now() -> None:
    """A sure win from either HP costs the same seconds (one second per
    percent rested either way): the rest buys nothing, so the fight runs."""
    assert rest_first(50, Fraction(136), Fraction(86)) is False


def test_a_fight_lost_from_full_never_rests_for() -> None:
    """Resting cannot win a fight that full HP loses: that is a gear question."""
    assert rest_first(50, None, None) is False
    assert rest_first(50, Fraction(100), None) is False


def test_a_fight_lost_now_but_won_from_full_rests() -> None:
    assert rest_first(50, None, Fraction(86)) is True
