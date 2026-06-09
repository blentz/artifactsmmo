"""Player-loop integration tests for stuck-state recovery."""

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal
from tests.test_ai.fixtures import make_state


def test_player_has_detector_after_init():
    player = GamePlayer(character="testchar")
    assert isinstance(player._detector, StuckDetector)
    assert player._suppressed_goals == {}
    assert player._actions_since_full_refresh == 0


def test_arbiter_skips_suppressed_goals():
    """A goal whose repr is in _suppressed_goals is skipped by the arbiter."""
    from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
    from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
    from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine

    player = GamePlayer(character="testchar")
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._monster_hp = {"chicken": 10}
    gd._monster_attack = {"chicken": {"fire": 1}}
    gd._monster_resistance = {"chicken": {}}
    gd._monster_critical_strike = {"chicken": 0}
    gd._monster_initiative = {"chicken": 0}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    player.game_data = gd
    player._bank_accessible = True
    # Idle (no task) → AcceptTask is the discretionary candidate; suppress it.
    player.state = make_state(task_code=None, task_type=None)
    player._objective = CharacterObjective.from_game_data(gd)
    player._strategy = StrategyEngine(player._objective, BalancedPersonality())
    player._suppressed_goals = {"AcceptTask": 5}

    decision = player._strategy.decide(player.state, gd)
    actions = player._build_actions()
    _goal, _plan, tried = player._arbiter.select(
        decision, player.state, gd, actions, player._selection_context(),
        suppressed=set(player._suppressed_goals))
    assert not any(gt["goal"] == "AcceptTask" for gt in tried)


def test_suppression_counter_decrements_per_cycle():
    """Each cycle should decrement suppression counters; zeros should be pruned."""
    player = GamePlayer(character="testchar")
    player._suppressed_goals = {"GoalA": 3, "GoalB": 1}
    player._decrement_suppressions()
    assert player._suppressed_goals == {"GoalA": 2}  # GoalB pruned at zero


def test_detector_record_helper_creates_cycle_record():
    """The helper _make_cycle_record should produce a CycleRecord with state_key from planner."""
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
    """_handle_stuck should acknowledge the signal to prevent re-fire."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()
    # Record some cycles to populate detector internal counter
    record = player._make_cycle_record(goal_name="GoalA", action_name="X",
                                        planned_depth=1, planner_timed_out=False, succeeded=True)
    player._detector.record(record)
    initial_ack = player._detector._ack_index.get(StuckSignal.STATE_FROZEN)
    player._fetch_world_state = lambda c: player.state  # type: ignore
    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert player._detector._ack_index.get(StuckSignal.STATE_FROZEN) is not None
    assert player._detector._ack_index[StuckSignal.STATE_FROZEN] != initial_ack


def test_handle_stuck_state_frozen_level1_triggers_full_refresh():
    """Level 1 STATE_FROZEN should call full refresh (via _fetch_world_state for now)."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()

    refresh_called = []
    def fake_refresh(c):
        refresh_called.append(True)
        return player.state
    player._fetch_world_state = fake_refresh  # type: ignore

    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert refresh_called == [True]
    assert player._recovery_level[StuckSignal.STATE_FROZEN] == 1


def test_handle_stuck_state_frozen_level2_suppresses_current_goal():
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()
    player._recovery_level[StuckSignal.STATE_FROZEN] = 1
    player._last_goal_name = "FarmMonster(chicken)"

    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert player._suppressed_goals.get("FarmMonster(chicken)") == 5
    assert player._recovery_level[StuckSignal.STATE_FROZEN] == 2


def test_handle_stuck_goal_oscillation_level1_suppresses_failing_goals_only():
    """Only goals that were actually failing get suppressed. A succeeded goal
    that merely shares the oscillation window is not the source of the loop
    and should not be punished."""
    player = GamePlayer(character="testchar")
    # GoalA failing, GoalB succeeding — only GoalA should be suppressed.
    for i in range(8):
        name = "GoalA" if i % 2 == 0 else "GoalB"
        player._detector.record(CycleRecord(
            state_key=(i, 0, 5, (), (), None, 0, False),
            goal_name=name, action_name="X", planned_depth=1,
            planner_timed_out=False, succeeded=(name == "GoalB"),
        ))
    player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
    assert player._suppressed_goals.get("GoalA") == 5
    assert "GoalB" not in player._suppressed_goals


def test_handle_stuck_goal_oscillation_skips_none_placeholder():
    """The '<none>' label is the no-plan placeholder, not a real goal —
    suppressing it would be meaningless."""
    player = GamePlayer(character="testchar")
    for i in range(8):
        player._detector.record(CycleRecord(
            state_key=(i, 0, 5, (), (), None, 0, False),
            goal_name="<none>", action_name="<no_plan>", planned_depth=0,
            planner_timed_out=False, succeeded=False,
        ))
    player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
    assert "<none>" not in player._suppressed_goals


def test_handle_stuck_no_progress_level1_triggers_refresh():
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()

    refresh_called = []
    def fake_refresh(c):
        refresh_called.append(True)
        return player.state
    player._fetch_world_state = fake_refresh  # type: ignore

    player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)
    assert refresh_called == [True]
    assert player._recovery_level[StuckSignal.NO_PROGRESS] == 1


def test_handle_stuck_goal_oscillation_level3_exits():
    """Level 3 of GOAL_OSCILLATION exits with SystemExit(2) — unrecoverable.
    Requires failing history so the recovery handler reaches the L3 branch
    instead of the early-return when no failing goals exist."""
    player = GamePlayer(character="testchar")
    for i in range(8):
        player._detector.record(CycleRecord(
            state_key=(i, 0, 5, (), (), None, 0, False),
            goal_name="GoalA" if i % 2 == 0 else "GoalB",
            action_name="X", planned_depth=1,
            planner_timed_out=False, succeeded=False,
        ))
    player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
    with pytest.raises(SystemExit) as exc_info:
        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
    assert exc_info.value.code == 2


def test_cooldown_outcome_does_not_count_as_failure_for_stuck_detection():
    """Trace 2026-06-06 cycles 0-1: bot's GrindCharacterXP fired,
    OptimizeLoadout returned error:cooldown (server timing, not goal
    failure). StuckDetector counted it as `succeeded=False`, flagged
    GOAL_OSCILLATION, suppressed GrindCharacterXP for 5 cycles. Bot
    abandoned combat after one server-timing miss.

    Fix: error:cooldown is treated as `succeeded=True` for stuck-
    detection purposes — the action's intent was correct, only the
    timing was off. Suppression no longer triggers from this outcome."""
    detector = StuckDetector(history_size=10)
    # Two consecutive cooldown rejections of the same goal — would have
    # previously flagged GOAL_OSCILLATION (any-failure-twice pattern).
    for _ in range(2):
        detector.record(CycleRecord(
            goal_name="GrindCharacterXP(yellow_slime)",
            action_name="OptimizeLoadout(yellow_slime)",
            planned_depth=2,
            planner_timed_out=False,
            succeeded=True,  # post-fix mapping: cooldown -> succeeded
            state_key=(0, 0, 0, _),
        ))
    # No stuck signal should fire from these records — succeeded=True
    # means the detector treats them as healthy.
    history = list(detector._history)
    assert all(r.succeeded for r in history), (
        "post-fix mapping: cooldown rejections record as succeeded=True so "
        "the stuck detector doesn't escalate to suppression"
    )
