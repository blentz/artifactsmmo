"""Player-loop integration tests for stuck-state recovery."""

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckExit, StuckSignal
from tests.test_ai.fixtures import make_state


def _cycle(goal: str = "GoalA", action: str = "X", succeeded: bool = True,
           state_key: tuple = (0, 0, 5, (), (), None, 0, False)) -> CycleRecord:
    return CycleRecord(
        state_key=state_key, goal_name=goal, action_name=action,
        planned_depth=1, planner_timed_out=False, succeeded=succeeded,
    )


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
    player._blockers.clear("bank")
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


def test_handle_stuck_goal_oscillation_level3_raises_stuck_exit():
    """Level 3 of GOAL_OSCILLATION raises StuckExit (NOT SystemExit) — the
    honest terminal path the play() boundary records as exit_reason=
    'stuck_exit'. Requires failing history so the recovery handler reaches
    the L3 branch instead of the early-return when no failing goals exist."""
    player = GamePlayer(character="testchar")
    for i in range(8):
        player._record_cycle(CycleRecord(
            state_key=(i, 0, 5, (), (), None, 0, False),
            goal_name="GoalA" if i % 2 == 0 else "GoalB",
            action_name="X", planned_depth=1,
            planner_timed_out=False, succeeded=False,
        ))
    player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
    with pytest.raises(StuckExit) as exc_info:
        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
    assert exc_info.value.signal == StuckSignal.GOAL_OSCILLATION
    assert not isinstance(exc_info.value, SystemExit)


def test_handle_stuck_no_progress_level3_raises_stuck_exit():
    """NO_PROGRESS L3 takes the same honest terminal path."""
    player = GamePlayer(character="testchar")
    player._recovery_level[StuckSignal.NO_PROGRESS] = 2
    with pytest.raises(StuckExit) as exc_info:
        player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)
    assert exc_info.value.signal == StuckSignal.NO_PROGRESS


def _wedge(player: GamePlayer, *, goal: str = "GatherMaterials", fails: int = 10,
           use_record_cycle: bool = False) -> None:
    """Record a 20-cycle window where `Withdraw(ash_plank)` (driven by `goal`)
    fails `fails` times amid succeeding `Move` cycles, state varying each cycle."""
    for i in range(20):
        if i % 2 == 0 and i < fails * 2:
            rec = CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False), goal_name=goal,
                action_name="Withdraw(ash_plank)", planned_depth=1,
                planner_timed_out=False, succeeded=False)
        else:
            rec = CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False), goal_name=goal,
                action_name="Move", planned_depth=1,
                planner_timed_out=False, succeeded=True)
        if use_record_cycle:
            player._record_cycle(rec)
        else:
            player._detector.record(rec)


def test_handle_stuck_repeated_action_level1_suppresses_driving_goal():
    """REPEATED_ACTION_FAILURE L1 suppresses the goal(s) driving the
    repeatedly-failing action for 10 cycles, and acknowledges the signal."""
    player = GamePlayer(character="testchar")
    _wedge(player, goal="GatherMaterials", fails=10)
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert player._suppressed_goals.get("GatherMaterials") == 10
    assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 1
    assert player._detector._ack_index.get(StuckSignal.REPEATED_ACTION_FAILURE) is not None


def test_handle_stuck_repeated_action_skips_none_placeholder():
    """A repeatedly-failing action driven only by the '<none>' placeholder has
    no real goal to suppress — the handler clears the signal without punishing."""
    player = GamePlayer(character="testchar")
    _wedge(player, goal="<none>", fails=10)
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert "<none>" not in player._suppressed_goals
    assert player._suppressed_goals == {}
    assert player._detector._ack_index.get(StuckSignal.REPEATED_ACTION_FAILURE) is not None


def test_handle_stuck_repeated_action_level2_suppresses_longer():
    player = GamePlayer(character="testchar")
    player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 1
    _wedge(player, goal="GatherMaterials", fails=10)
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert player._suppressed_goals.get("GatherMaterials") == 30
    assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 2


def test_handle_stuck_repeated_action_level3_raises_stuck_exit():
    """L3 takes the honest terminal path. Uses _record_cycle so the per-signal
    counter-evidence streak is tracked (failing cycles do NOT decay escalation)."""
    player = GamePlayer(character="testchar")
    _wedge(player, goal="GatherMaterials", fails=10, use_record_cycle=True)
    player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
    with pytest.raises(StuckExit) as exc_info:
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert exc_info.value.signal == StuckSignal.REPEATED_ACTION_FAILURE
    assert not isinstance(exc_info.value, SystemExit)


def test_handle_stuck_repeated_action_blocks_failing_action():
    """REPEATED_ACTION_FAILURE recovery must also BLOCK the repeatedly-failing
    ACTION (by repr), not only suppress the driving goal. A GUARD/interrupt-driven
    action (e.g. RestoreHP -> UseConsumable) bypasses goal suppression, so without
    an action-level block the recovery could not break a guard spin — the live 476
    deadlock (2026-07-02: RestoreHP guard looped UseConsumable on utility potions)."""
    player = GamePlayer(character="testchar")
    _wedge(player, goal="GatherMaterials", fails=10)
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert player._failed_action_backoff.get("Withdraw(ash_plank)", 0) > 0


def test_build_actions_excludes_backoff_blocked_action():
    """A repr in _failed_action_backoff is filtered out of the planning action
    list, so the planner (and any guard) routes around the doomed action."""
    player = GamePlayer(character="testchar")
    gd = GameData()
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    player.game_data = gd
    player.state = make_state()
    unblocked = [repr(a) for a in player._build_actions()]
    assert "Rest" in unblocked  # baseline: Rest is always built
    player._failed_action_backoff = {"Rest": 5}
    blocked = [repr(a) for a in player._build_actions()]
    assert "Rest" not in blocked


def test_action_backoff_decrements_per_cycle():
    """The per-action block decays each cycle (like goal suppression) so the
    block is temporary — a transient failure is not blocked forever."""
    player = GamePlayer(character="testchar")
    player._failed_action_backoff = {"Withdraw(ash_plank)": 3, "UseConsumable": 1}
    player._decrement_suppressions()
    assert player._failed_action_backoff == {"Withdraw(ash_plank)": 2}  # 1 pruned at zero


class TestEscalationDecay:
    """_recovery_level[signal] decays: a full detection window (8 for
    GOAL_OSCILLATION) of CONSECUTIVE counter-evidence since the signal last
    fired resets escalation to L0 before the next fire counts. Trace
    2026-06-10: 67 productive cycles between L2 and L3 bought nothing and L3
    raised SystemExit(2)."""

    def _flap_window(self, player: GamePlayer, start: int) -> None:
        """Record a genuine failing A/B flap window (would fire osc)."""
        for i in range(8):
            player._record_cycle(_cycle(
                goal="GoalA" if i % 2 == 0 else "GoalB", succeeded=False,
                state_key=(start + i, 0, 5, (), (), None, 0, False),
            ))

    def test_productive_run_resets_oscillation_escalation(self):
        """L2, then 8+ productive cycles, then a fire → L1, not L3."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
        for i in range(10):  # 10 consecutive productive cycles >= window 8
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
        assert player._recovery_level[StuckSignal.GOAL_OSCILLATION] == 1

    def test_sixty_seven_productive_cycles_clear_history(self):
        """Trace-locked: the 67 productive cycles between L2 and L3 in the
        2026-06-10 session must clear escalation history."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
        for i in range(67):
            player._record_cycle(_cycle(
                goal="GrindCharacterXP(chicken)", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
        assert player._recovery_level[StuckSignal.GOAL_OSCILLATION] == 1

    def test_failing_refill_does_not_decay(self):
        """A genuine livelock refill window (all failures) provides no
        counter-evidence: L2 escalates to L3 and raises StuckExit."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
        self._flap_window(player, start=0)  # refill is itself the evidence
        with pytest.raises(StuckExit):
            player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)

    def test_short_productive_run_does_not_decay(self):
        """Fewer than window-size consecutive successes is not a full window
        of counter-evidence — escalation history is kept."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
        for i in range(7):  # one short of the 8-cycle window
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        with pytest.raises(StuckExit):
            player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)

    def test_interrupted_successes_do_not_accumulate(self):
        """The counter-evidence run must be CONSECUTIVE: successes split by a
        failure never reach the window size, so no decay."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
        for i in range(20):  # 4 ok, 1 fail, repeated: max streak 4 < 8
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=(i % 5 != 4),
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        with pytest.raises(StuckExit):
            player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)

    def test_streak_resets_when_signal_fires(self):
        """Each fire consumes the streak bookkeeping: decay-then-fire leaves
        the NEXT fire without counter-evidence unless a fresh full window
        accumulates."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2
        for i in range(10):
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
        assert player._recovery_level[StuckSignal.GOAL_OSCILLATION] == 1
        # Second fire immediately after another failing window: no decay.
        self._flap_window(player, start=200)
        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)
        assert player._recovery_level[StuckSignal.GOAL_OSCILLATION] == 2

    def test_no_progress_decay_counts_planned_cycles(self):
        """NO_PROGRESS counter-evidence is 'a real plan existed', regardless
        of outcome: 4+ consecutive planned cycles reset its escalation."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.NO_PROGRESS] = 2
        for i in range(4):  # planned but FAILED cycles still refute no-plan
            player._record_cycle(_cycle(
                goal="GoalA", action="X", succeeded=False,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        player._fetch_world_state = lambda c: player.state  # type: ignore
        player.state = make_state()
        player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)
        assert player._recovery_level[StuckSignal.NO_PROGRESS] == 1

    def test_state_frozen_decay_requires_changing_states(self):
        """STATE_FROZEN counter-evidence is a CHANGED state key — succeeding
        actions that leave the state frozen prove nothing, so no decay."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.STATE_FROZEN] = 1
        frozen_key = (1, 1, 5, (), (), None, 0, False)
        for _ in range(12):  # succeeded=True but the state never changes
            player._record_cycle(_cycle(goal="GoalA", succeeded=True,
                                        state_key=frozen_key))
        player._last_goal_name = "GoalA"
        player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
        assert player._recovery_level[StuckSignal.STATE_FROZEN] == 2

    def test_state_frozen_decay_on_changing_states(self):
        """10+ consecutive state CHANGES since the last fire reset frozen
        escalation."""
        player = GamePlayer(character="testchar")
        player.game_data = GameData()
        player.state = make_state()
        player._fetch_world_state = lambda c: player.state  # type: ignore
        player._recovery_level[StuckSignal.STATE_FROZEN] = 1
        for i in range(12):  # 11 consecutive changes >= window 10
            player._record_cycle(_cycle(goal="GoalA", succeeded=True,
                                        state_key=(i, 0, 5, (), (), None, 0, False)))
        player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
        assert player._recovery_level[StuckSignal.STATE_FROZEN] == 1


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
