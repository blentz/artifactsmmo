"""Tests for scalar_priority.yield_bonus — the band-clamp bonus computed from a
learned per-cycle Yield."""

from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import Yield
from artifactsmmo_cli.ai.scalar_priority import (
    yield_bonus,
    yield_bonus_for_goal,
)
from tests.test_ai.fixtures import make_state


def test_yield_bonus_zero_for_cold_yield():
    """A Yield with no samples earns no bonus regardless of its averages."""
    y = Yield(char_xp=100.0, sample_count=0)
    bonus = yield_bonus(y, make_state(), GameData(), None)
    assert bonus == Fraction(0)


def test_yield_bonus_zero_when_scalar_at_or_below_baseline():
    """An observed scalar at/below the 1.0 baseline lifts nothing -> 0 bonus."""
    # char_xp 0, no skill/gold/coins -> scalar 0 < baseline 1.0.
    y = Yield(char_xp=0.0, sample_count=5)
    bonus = yield_bonus(y, make_state(), GameData(), None)
    assert bonus == Fraction(0)


def test_yield_bonus_positive_above_baseline():
    """A well-sampled, high-char-XP yield lifts above baseline and returns a
    strictly-positive Fraction (line 53-57)."""
    # scalar = char_xp * CHARACTER_XP_LEVEL_SCALAR(=1) * (level+1) = 50 * 6 = 300.
    y = Yield(char_xp=50.0, sample_count=10)
    state = make_state(level=5)
    bonus = yield_bonus(y, state, GameData(), None)
    assert isinstance(bonus, Fraction)
    assert bonus > Fraction(0)
    # lifted = 300 - 1 = 299; BAND_GAIN = 1.
    assert bonus == Fraction(299)


def test_yield_bonus_for_goal_zero_without_history():
    """No learning store -> no observed cycles -> zero bonus."""
    assert yield_bonus_for_goal("PursueTask(x)", make_state(), GameData(), None) == Fraction(0)
