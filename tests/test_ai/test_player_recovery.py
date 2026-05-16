"""Player-loop integration tests for stuck-state recovery."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import StuckDetector
from tests.test_ai.fixtures import make_state


def test_player_has_detector_after_init():
    player = GamePlayer(character="testchar")
    assert isinstance(player._detector, StuckDetector)
    assert player._suppressed_goals == {}
    assert player._actions_since_full_refresh == 0


def test_build_goals_filters_suppressed_goals():
    """Goals with names in _suppressed_goals (with positive counter) are excluded."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._monster_level = {"chicken": 1}
    player._bank_accessible = True
    player.state = make_state()
    # Suppress FarmMonster for 5 cycles
    player._suppressed_goals = {"FarmMonster(chicken)": 5}

    goals = player._build_goals()
    names = [repr(g) for g in goals]
    assert not any("FarmMonster(chicken)" in n for n in names)


def test_suppression_counter_decrements_per_cycle():
    """Each cycle should decrement suppression counters; zeros should be pruned."""
    player = GamePlayer(character="testchar")
    player._suppressed_goals = {"GoalA": 3, "GoalB": 1}
    player._decrement_suppressions()
    assert player._suppressed_goals == {"GoalA": 2}  # GoalB pruned at zero
