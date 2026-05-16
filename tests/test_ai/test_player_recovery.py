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


def test_detector_record_helper_creates_cycle_record():
    """The helper _make_cycle_record should produce a CycleRecord with state_key from planner."""
    from artifactsmmo_cli.ai.recovery import CycleRecord

    player = GamePlayer(character="testchar")
    player.state = make_state(x=4, y=2)
    record = player._make_cycle_record(
        goal_name="FarmMonster(chicken)",
        action_name="Fight(chicken)",
        planned_depth=2,
        planner_timed_out=False,
        succeeded=True,
    )
    assert isinstance(record, CycleRecord)
    assert record.goal_name == "FarmMonster(chicken)"
    assert record.action_name == "Fight(chicken)"
    assert record.planned_depth == 2
    assert record.succeeded is True


def test_handle_stuck_acknowledges_signal():
    """_handle_stuck (stub for C7) should at minimum acknowledge the signal to prevent re-fire."""
    from artifactsmmo_cli.ai.recovery import StuckSignal

    player = GamePlayer(character="testchar")
    player.state = make_state()
    # Record some cycles to populate detector internal counter
    record = player._make_cycle_record(goal_name="GoalA", action_name="X",
                                        planned_depth=1, planner_timed_out=False, succeeded=True)
    player._detector.record(record)
    initial_ack = player._detector._ack_index.get(StuckSignal.STATE_FROZEN)
    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert player._detector._ack_index.get(StuckSignal.STATE_FROZEN) is not None
    assert player._detector._ack_index[StuckSignal.STATE_FROZEN] != initial_ack
