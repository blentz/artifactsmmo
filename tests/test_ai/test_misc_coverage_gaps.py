"""Coverage-gap closers for small remaining branches."""

from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scalar_priority import yield_bonus_for_goal
from tests.test_ai.fixtures import make_state


def test_yield_bonus_for_goal_history_none_returns_zero():
    """yield_bonus_for_goal short-circuits to 0 when history is absent."""
    state = make_state()
    gd = GameData()
    assert yield_bonus_for_goal("AcceptTask", state, gd, None) == Fraction(0)
