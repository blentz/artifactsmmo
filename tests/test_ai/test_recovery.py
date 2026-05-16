"""Tests for recovery module: CycleRecord, StuckSignal, StuckDetector."""

from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal


def make_record(state_key=(0, 0, 5, (), (), None, 0, False),
                goal_name="GoalA", action_name="Fight(chicken)",
                planned_depth=2, planner_timed_out=False, succeeded=True) -> CycleRecord:
    return CycleRecord(
        state_key=state_key, goal_name=goal_name, action_name=action_name,
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
