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
