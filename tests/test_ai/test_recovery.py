"""Tests for recovery module: CycleRecord, StuckSignal, StuckDetector."""

from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal


def make_record(state_key=(0, 0, 5, (), (), None, 0, False),
                goal_name="GoalA", action_name="Fight(chicken)",
                planned_depth=2, planner_timed_out=False, succeeded=True,
                action_key=None) -> CycleRecord:
    """`action_key` defaults to `action_name`, which is what `learning_key()`
    returns for every action except GatherAction; pass it explicitly to model a
    gather whose repr carries a per-cycle batch size."""
    return CycleRecord(
        state_key=state_key, goal_name=goal_name, action_name=action_name,
        action_key=action_name if action_key is None else action_key,
        planned_depth=planned_depth, planner_timed_out=planner_timed_out, succeeded=succeeded,
    )


class TestStuckDetectorBasics:
    def test_empty_detector_returns_no_signal(self):
        det = StuckDetector()
        assert det.detect() is None

    def test_record_appends_to_history(self):
        det = StuckDetector(history_size=5)
        det.record(make_record())
        det.record(make_record())
        # No assertion fails — history is internal but we can confirm via detect() below
        assert det.detect() is None  # 2 records, no rule fires yet

    def test_history_size_bounded(self):
        det = StuckDetector(history_size=3)
        for i in range(10):
            det.record(make_record(state_key=(i, 0, 5, (), (), None, 0, False)))
        # No state repeats since each key is unique; should not fire
        assert det.detect() is None


class TestStateFrozenDetection:
    def test_fires_when_same_state_key_5_of_last_10(self):
        det = StuckDetector(history_size=30)
        repeated = (1, 1, 5, (), (), None, 0, False)
        other = (2, 2, 5, (), (), None, 0, False)
        # 5 cycles of repeated state + 5 cycles of other state, interleaved
        for i in range(10):
            key = repeated if i % 2 == 0 else other
            det.record(make_record(state_key=key))
        assert det.detect() == StuckSignal.STATE_FROZEN

    def test_no_fire_when_state_key_varies(self):
        det = StuckDetector(history_size=30)
        for i in range(10):
            key = (i, i, 5, (), (), None, 0, False)
            det.record(make_record(state_key=key))
        assert det.detect() is None

    def test_no_fire_when_only_4_of_10_repeat(self):
        det = StuckDetector(history_size=30)
        repeated = (1, 1, 5, (), (), None, 0, False)
        for i in range(10):
            key = repeated if i < 4 else (i, i, 5, (), (), None, 0, False)
            det.record(make_record(state_key=key))
        assert det.detect() is None

    def test_acknowledge_resets_state_frozen_window(self):
        """After acknowledging STATE_FROZEN, the detector should only count post-ack cycles."""
        det = StuckDetector(history_size=30)
        repeated = (1, 1, 5, (), (), None, 0, False)
        # Trigger first detection
        for i in range(10):
            key = repeated if i % 2 == 0 else (i, i, 5, (), (), None, 0, False)
            det.record(make_record(state_key=key))
        assert det.detect() == StuckSignal.STATE_FROZEN

        # Acknowledge, then add a small number of post-ack records.
        det.acknowledge(StuckSignal.STATE_FROZEN)
        # Even though the buffer still contains the repeated cycles, the ack-cutoff means
        # they don't count anymore. With <10 post-ack records, no fire yet.
        for _ in range(3):
            det.record(make_record(state_key=repeated))
        assert det.detect() is None

        # Add more post-ack repeats to re-trigger.
        for _ in range(7):
            det.record(make_record(state_key=repeated))
        assert det.detect() == StuckSignal.STATE_FROZEN


class TestNoProgress:
    def test_fires_after_4_consecutive_no_plan(self):
        det = StuckDetector()
        for i in range(4):
            det.record(make_record(action_name="<no_plan>", goal_name="<none>",
                                    state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() == StuckSignal.NO_PROGRESS

    def test_no_fire_after_3_no_plan(self):
        det = StuckDetector()
        for i in range(3):
            det.record(make_record(action_name="<no_plan>", goal_name="<none>",
                                    state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() is None

    def test_no_fire_when_no_plan_interleaved_with_progress(self):
        det = StuckDetector()
        for i in range(5):
            name = "<no_plan>" if i % 2 == 0 else "Fight"
            det.record(make_record(action_name=name, state_key=(i, 0, 5, (), (), None, 0, False)))
        # Last 4 cycles: <no_plan>, Fight, <no_plan>, Fight → not all <no_plan>
        assert det.detect() is None


class TestRepeatedActionFailure:
    """The 4th signal: a single named action failing >= 10 times in the last 20
    cycles, regardless of interspersed progress (the 478 bank-loop class)."""

    def _wedged(self, det, fails: int):
        # 20 cycles: `fails` failing Withdraw(ash_plank), the rest succeeding
        # Move, every cycle a distinct state (frozen quiet), one goal (osc quiet).
        for i in range(20):
            if i % 2 == 0 and i < fails * 2:
                det.record(make_record(
                    action_name="Withdraw(ash_plank)", goal_name="GatherMaterials",
                    succeeded=False, state_key=(i, 0, 5, (), (), None, 0, False)))
            else:
                det.record(make_record(
                    action_name="Move", goal_name="GatherMaterials",
                    succeeded=True, state_key=(i, 0, 5, (), (), None, 0, False)))

    def test_fires_when_one_action_fails_10_of_20(self):
        det = StuckDetector()
        self._wedged(det, fails=10)
        assert det.detect() == StuckSignal.REPEATED_ACTION_FAILURE

    def test_fires_when_the_repr_varies_but_the_key_does_not(self):
        """A closure gather is re-sized every cycle, so `action_name` is
        `Gather(copper_rocks×60)`, then `×47`, ... — 10 distinct reprs for ONE
        repeatedly-failing action. The tally keys on `action_key`, so it still
        reaches the threshold; on the repr it would see ten buckets of one."""
        det = StuckDetector()
        quantities = [60, 47, 31, 22, 18, 13, 9, 6, 4, 2]
        for i in range(20):
            if i % 2 == 0:
                det.record(make_record(
                    action_name=f"Gather(copper_rocks×{quantities[i // 2]})",
                    action_key="Gather(copper_rocks)", goal_name="GatherMaterials",
                    succeeded=False, state_key=(i, 0, 5, (), (), None, 0, False)))
            else:
                det.record(make_record(
                    action_name="Move", goal_name="GatherMaterials",
                    succeeded=True, state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() == StuckSignal.REPEATED_ACTION_FAILURE

    def test_no_fire_at_9_failures(self):
        det = StuckDetector()
        self._wedged(det, fails=9)
        assert det.detect() != StuckSignal.REPEATED_ACTION_FAILURE
        assert det.detect() is None

    def test_no_plan_flood_excluded(self):
        # 10 <no_plan> failures interspersed with successes so the last 4 are not
        # all <no_plan> (noprog quiet). <no_plan> is excluded from the tally.
        det = StuckDetector()
        # Same goal on every cycle so the 2-distinct-goal oscillation gate stays
        # quiet — this isolates the <no_plan> exclusion from the repeated tally.
        for i in range(20):
            if i % 2 == 0:
                det.record(make_record(action_name="<no_plan>", goal_name="GatherMaterials",
                                       succeeded=False,
                                       state_key=(i, 0, 5, (), (), None, 0, False)))
            else:
                det.record(make_record(action_name="Move", goal_name="GatherMaterials",
                                       succeeded=True,
                                       state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() is None

    def test_tolerates_interspersed_progress(self):
        # The defining property: 10 failures of one action even with 10 successes
        # of OTHER actions between them still fires (state varies the whole time).
        det = StuckDetector()
        self._wedged(det, fails=10)
        assert det._check_repeated_action_failure() is True

    def test_acknowledge_resets_window(self):
        det = StuckDetector()
        self._wedged(det, fails=10)
        assert det.detect() == StuckSignal.REPEATED_ACTION_FAILURE
        det.acknowledge(StuckSignal.REPEATED_ACTION_FAILURE)
        # post-ack window is empty → cannot re-fire until fresh failures accrue
        assert det.detect() != StuckSignal.REPEATED_ACTION_FAILURE

    def test_noprog_beats_repeated(self):
        # 16 failing Withdraws (repeated would fire) then 4 <no_plan> (noprog):
        # NO_PROGRESS has strict precedence.
        det = StuckDetector()
        for i in range(16):
            det.record(make_record(action_name="Withdraw(ash_plank)",
                                    goal_name="GatherMaterials", succeeded=False,
                                    state_key=(i, 0, 5, (), (), None, 0, False)))
        for i in range(16, 20):
            det.record(make_record(action_name="<no_plan>", goal_name="<none>",
                                    succeeded=False,
                                    state_key=(i, 0, 5, (), (), None, 0, False)))
        assert det.detect() == StuckSignal.NO_PROGRESS
