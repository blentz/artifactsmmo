"""Player-loop integration tests for stuck-state recovery."""


from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import (
    REPEATED_ACTION_FAILURE_THRESHOLD,
    CycleRecord,
    StuckDetector,
    StuckSignal,
)
from tests.test_ai.fixtures import make_state


def _cycle(goal: str = "GoalA", action: str = "X", succeeded: bool = True,
           state_key: tuple = (0, 0, 5, (), (), None, 0, False)) -> CycleRecord:
    return CycleRecord(
        state_key=state_key, goal_name=goal, action_name=action, action_key=action,
        planned_depth=1, planner_timed_out=False, succeeded=succeeded,
    )


def test_player_has_detector_after_init():
    player = GamePlayer(character="testchar")
    assert isinstance(player._detector, StuckDetector)
    assert player._cycles_without_progress == 0
    assert player._actions_since_full_refresh == 0


def test_detector_record_helper_creates_cycle_record():
    """The helper _make_cycle_record should produce a CycleRecord with state_key from planner."""
    player = GamePlayer(character="testchar")
    player.state = make_state(x=4, y=2)
    record = player._make_cycle_record(
        goal_name="FarmMonster(chicken)",
        action=FightAction(monster_code="chicken", locations=frozenset({(1, 0)})),
        planned_depth=2,
        planner_timed_out=False,
        succeeded=True,
    )
    assert isinstance(record, CycleRecord)
    assert record.goal_name == "FarmMonster(chicken)"
    # `action_name` stays the repr (display/trace); `action_key` is the stable
    # identity the stuck rules count on. They coincide for every action except
    # GatherAction.
    assert record.action_name == "Fight(chicken)"
    assert record.action_key == "Fight(chicken)"
    assert record.planned_depth == 2
    assert record.succeeded is True


def test_make_cycle_record_keys_a_gather_without_its_quantity():
    """The one action whose repr and key diverge — the reason `action_key` exists."""
    player = GamePlayer(character="testchar")
    player.state = make_state()
    record = player._make_cycle_record(
        goal_name="GatherMaterials(copper_dagger)", action=_sized_gather(47),
        planned_depth=1, planner_timed_out=False, succeeded=False,
    )
    assert record.action_name == "Gather(copper_rocks×47)"
    assert record.action_key == "Gather(copper_rocks)"


def test_make_cycle_record_no_plan_sentinel():
    """No action means no plan: both fields carry the sentinel the stuck rules
    exclude, so a no-plan flood cannot masquerade as a repeated action."""
    player = GamePlayer(character="testchar")
    player.state = make_state()
    record = player._make_cycle_record(
        goal_name="<none>", action=None, planned_depth=0,
        planner_timed_out=True, succeeded=False,
    )
    assert record.action_name == "<no_plan>"
    assert record.action_key == "<no_plan>"


def test_handle_stuck_acknowledges_signal():
    """_handle_stuck should acknowledge the signal to prevent re-fire."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()
    # Record some cycles to populate detector internal counter
    record = player._make_cycle_record(goal_name="GoalA", action=RestAction(),
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


def test_handle_stuck_state_frozen_only_refreshes_at_any_level():
    """Phase 4-3c: STATE_FROZEN is a perception fact. Every fire refreshes; the
    L2/L3 goal-suppression rungs are gone."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()
    player._recovery_level[StuckSignal.STATE_FROZEN] = 2
    refreshed: list[bool] = []

    def fake_refresh(c):
        refreshed.append(True)
        return player.state
    player._fetch_world_state = fake_refresh  # type: ignore
    player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)
    assert refreshed == [True]
    assert player._recovery_level[StuckSignal.STATE_FROZEN] == 3


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


def test_handle_stuck_no_progress_never_exits():
    """Phase 4-3c: NO_PROGRESS refreshes and clears the bank blocker at every
    level; the only StuckExit is the intention one."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.state = make_state()
    player._fetch_world_state = lambda c: player.state  # type: ignore
    player._recovery_level[StuckSignal.NO_PROGRESS] = 2
    player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)
    assert player._recovery_level[StuckSignal.NO_PROGRESS] == 3


def _wedge(player: GamePlayer, *, goal: str = "GatherMaterials", fails: int = 10,
           use_record_cycle: bool = False) -> None:
    """Record a 20-cycle window where `Withdraw(ash_plank)` (driven by `goal`)
    fails `fails` times amid succeeding `Move` cycles, state varying each cycle."""
    for i in range(20):
        if i % 2 == 0 and i < fails * 2:
            rec = CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False), goal_name=goal,
                action_name="Withdraw(ash_plank)", action_key="Withdraw(ash_plank)", planned_depth=1,
                planner_timed_out=False, succeeded=False)
        else:
            rec = CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False), goal_name=goal,
                action_name="Move", action_key="Move", planned_depth=1,
                planner_timed_out=False, succeeded=True)
        if use_record_cycle:
            player._record_cycle(rec)
        else:
            player._detector.record(rec)


def test_handle_stuck_repeated_action_level1_blocks_for_ten_cycles():
    """REPEATED_ACTION_FAILURE L1 blocks the failing action for 10 cycles and
    acknowledges the signal. It suppresses no goal (Phase 4-3c)."""
    player = GamePlayer(character="testchar")
    _wedge(player, goal="GatherMaterials", fails=10)
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert player._failed_action_backoff.get("Withdraw(ash_plank)") == 10
    assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 1
    assert player._detector._ack_index.get(StuckSignal.REPEATED_ACTION_FAILURE) is not None


def test_handle_stuck_repeated_action_level2_blocks_longer():
    player = GamePlayer(character="testchar")
    player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 1
    _wedge(player, goal="GatherMaterials", fails=10)
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert player._failed_action_backoff.get("Withdraw(ash_plank)") == 30
    assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 2


def test_handle_stuck_repeated_action_level3_keeps_blocking_and_never_exits():
    """L3 used to raise StuckExit; since Phase 4-3c the only exit is the
    intention one, so L3 keeps the 30-cycle block."""
    player = GamePlayer(character="testchar")
    _wedge(player, goal="GatherMaterials", fails=10, use_record_cycle=True)
    player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    assert player._failed_action_backoff.get("Withdraw(ash_plank)") == 30
    assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 3


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


def _sized_gather(qty: int) -> GatherAction:
    """A closure gather as the two consuming goals now emit it: the SAME logical
    action, re-sized to the outstanding deficit each cycle."""
    return GatherAction(resource_code="copper_rocks",
                        locations=frozenset({(2, 0)}), quantity=qty)


def test_repeated_action_failure_tallies_across_varying_batch_sizes():
    """Guard-spin protection must see ONE repeatedly-failing gather even though
    its `repr` changes every cycle.

    Closure sizing means the same logical gather is emitted as
    `Gather(copper_rocks×60)`, then `×47`, then `×31`, ... as the deficit
    shrinks (or as inventory headroom moves). Keyed on `repr`, ten failures
    fragment into ten buckets of one, `REPEATED_ACTION_FAILURE_THRESHOLD` (10)
    is never reached, and the livelock protection silently switches off. The
    tally therefore keys on `Action.learning_key()`, which `GatherAction`
    overrides to be quantity-free.
    """
    player = GamePlayer(character="testchar")
    quantities = [60, 47, 31, 22, 18, 13, 9, 6, 4, 2]
    assert len({repr(_sized_gather(q)) for q in quantities}) == len(quantities), \
        "fixture is vacuous: the reprs must all differ for this to discriminate"
    assert len(quantities) >= REPEATED_ACTION_FAILURE_THRESHOLD

    for i, qty in enumerate(quantities):
        # Vary the state so STATE_FROZEN (checked first) cannot pre-empt the
        # signal under test.
        player.state = make_state(x=i)
        player._record_cycle(player._make_cycle_record(
            goal_name="GatherMaterials(copper_dagger)",
            action=_sized_gather(qty),
            planned_depth=1, planner_timed_out=False, succeeded=False,
        ))

    assert player._detector.detect() is StuckSignal.REPEATED_ACTION_FAILURE
    player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
    # Blocked under the quantity-free identity — unreachable if the tally
    # fragmented.
    assert player._failed_action_backoff.get("Gather(copper_rocks)", 0) > 0


def test_backoff_blocks_a_gather_built_at_a_different_quantity():
    """The block is recorded from a SIZED gather but `_build_actions` builds the
    factory's unsized one, so a repr-keyed filter can never match. Filtering on
    `learning_key()` makes the two halves agree."""
    player = GamePlayer(character="testchar")
    gd = GameData()
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    player.game_data = gd
    player.state = make_state()

    unblocked = [a for a in player._build_actions()
                 if isinstance(a, GatherAction) and a.resource_code == "copper_rocks"]
    assert unblocked, "baseline: the factory builds a copper_rocks gather"
    assert all(repr(a) != "Gather(copper_rocks)" for a in unblocked), \
        "fixture is vacuous: the built repr must differ from the blocked key"

    player._failed_action_backoff = {"Gather(copper_rocks)": 5}
    blocked = [a for a in player._build_actions()
               if isinstance(a, GatherAction) and a.resource_code == "copper_rocks"]
    assert blocked == []


def test_action_backoff_decrements_per_cycle():
    """The per-action block decays each cycle (like goal suppression) so the
    block is temporary — a transient failure is not blocked forever."""
    player = GamePlayer(character="testchar")
    player._failed_action_backoff = {"Withdraw(ash_plank)": 3, "UseConsumable": 1}
    player._decrement_suppressions()
    assert player._failed_action_backoff == {"Withdraw(ash_plank)": 2}  # 1 pruned at zero


class TestEscalationDecay:
    """_recovery_level[signal] decays: a full detection window (20 for
    REPEATED_ACTION_FAILURE) of CONSECUTIVE counter-evidence since the signal
    last fired resets escalation to L0 before the next fire counts. Trace
    2026-06-10: 67 productive cycles between L2 and L3 bought nothing and L3
    raised SystemExit(2); since Phase 4-3c the level sets only the action-block
    length. (These used GOAL_OSCILLATION, retired in Phase
    4-2a-ii; the decay rule is per signal and unchanged.)"""

    def _flap_window(self, player: GamePlayer, start: int) -> None:
        """Record a window of one action failing every cycle (would fire
        REPEATED_ACTION_FAILURE)."""
        for i in range(20):
            player._record_cycle(_cycle(
                goal="GoalA", action="X", succeeded=False,
                state_key=(start + i, 0, 5, (), (), None, 0, False),
            ))

    def test_productive_run_resets_escalation(self):
        """L2, then 20+ productive cycles, then a fire → L1, not L3."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
        for i in range(22):  # 22 consecutive productive cycles >= window 20
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 1

    def test_sixty_seven_productive_cycles_clear_history(self):
        """Trace-locked: the 67 productive cycles between L2 and L3 in the
        2026-06-10 session must clear escalation history."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
        for i in range(67):
            player._record_cycle(_cycle(
                goal="GrindCharacterXP(chicken)", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 1

    def test_failing_refill_does_not_decay(self):
        """A genuine livelock refill window (all failures) provides no
        counter-evidence: L2 escalates to L3."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
        self._flap_window(player, start=0)  # refill is itself the evidence
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 3

    def test_short_productive_run_does_not_decay(self):
        """Fewer than window-size consecutive successes is not a full window
        of counter-evidence — escalation history is kept."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
        for i in range(19):  # one short of the 20-cycle window
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 3

    def test_interrupted_successes_do_not_accumulate(self):
        """The counter-evidence run must be CONSECUTIVE: successes split by a
        failure never reach the window size, so no decay."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
        for i in range(40):  # 4 ok, 1 fail, repeated: max streak 4 < 20
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=(i % 5 != 4),
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 3

    def test_streak_resets_when_signal_fires(self):
        """Each fire consumes the streak bookkeeping: decay-then-fire leaves
        the NEXT fire without counter-evidence unless a fresh full window
        accumulates."""
        player = GamePlayer(character="testchar")
        player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] = 2
        for i in range(22):
            player._record_cycle(_cycle(
                goal="GoalA", succeeded=True,
                state_key=(i, 0, 5, (), (), None, 0, False)))
        self._flap_window(player, start=100)
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 1
        # Second fire immediately after another failing window: no decay.
        self._flap_window(player, start=200)
        player._handle_stuck(StuckSignal.REPEATED_ACTION_FAILURE, client=None)
        assert player._recovery_level[StuckSignal.REPEATED_ACTION_FAILURE] == 2

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
        player.game_data = GameData()
        player.state = make_state()
        player._fetch_world_state = lambda c: player.state  # type: ignore
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
            action_key="OptimizeLoadout(yellow_slime)",
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
