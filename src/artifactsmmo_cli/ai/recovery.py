"""Stuck-state detection and escalating recovery for the GOAP player."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise


class StuckSignal(Enum):
    """Distinct stuck-state classes the detector can identify."""
    STATE_FROZEN = "state_frozen"
    GOAL_OSCILLATION = "goal_oscillation"
    NO_PROGRESS = "no_progress"


# Detection window sizes: how many recent cycles each check examines. Exported
# (via SIGNAL_WINDOWS) so the player's escalation decay keys off the SAME
# windows — once a full window's worth of CONSECUTIVE counter-evidence has
# accumulated since a signal last fired, the detector itself would judge that
# span healthy, so older escalation history is stale and must be reset.
STATE_FROZEN_WINDOW = 10
GOAL_OSCILLATION_WINDOW = 8
NO_PROGRESS_WINDOW = 4

SIGNAL_WINDOWS: dict[StuckSignal, int] = {
    StuckSignal.STATE_FROZEN: STATE_FROZEN_WINDOW,
    StuckSignal.GOAL_OSCILLATION: GOAL_OSCILLATION_WINDOW,
    StuckSignal.NO_PROGRESS: NO_PROGRESS_WINDOW,
}

# Genuine-oscillation gates (see _check_goal_oscillation). OSC_MIN_SWITCHES=3
# means the goal sequence leaves-and-returns at least twice (>= 2 overlapping
# A->B->A round-trips: A->B->A and B->A->B both need 3 adjacent switches).
# OSC_MIN_FAILURES=2 means the flapping must be failure-driven: a single
# transient error inside an otherwise productive window is not a livelock.
OSC_MIN_SWITCHES = 3
OSC_MIN_FAILURES = 2


class StuckExit(Exception):
    """Terminal stuck-recovery escalation (L3): recovery options are exhausted
    and the run must stop for manual intervention.

    Raised by the player's stuck handler INSTEAD of SystemExit so the play()
    boundary can record an honest exit_reason="stuck_exit" (trace 2026-06-10:
    SystemExit(2) from a detector false-positive was recorded as
    exit_reason="crash"). Narrow by design — only the run-loop boundary
    catches it.
    """

    def __init__(self, signal: StuckSignal) -> None:
        super().__init__(f"stuck recovery exhausted at L3 for {signal.value}")
        self.signal = signal


@dataclass(frozen=True)
class CycleRecord:
    """One cycle of the player loop, for stuck-state analysis."""
    state_key: tuple[object, ...]
    goal_name: str
    action_name: str          # "<no_plan>" when planning failed
    planned_depth: int
    planner_timed_out: bool
    succeeded: bool


class StuckDetector:
    """Tracks recent cycles and reports stuck-state signals."""

    def __init__(self, history_size: int = 30) -> None:
        self._history: deque[CycleRecord] = deque(maxlen=history_size)
        self._ack_index: dict[StuckSignal, int] = {}
        self._cycle_counter = 0

    def record(self, cycle: CycleRecord) -> None:
        self._history.append(cycle)
        self._cycle_counter += 1

    def detect(self) -> StuckSignal | None:
        """Return the first matching signal, or None."""
        if self._check_state_frozen():
            return StuckSignal.STATE_FROZEN
        if self._check_goal_oscillation():
            return StuckSignal.GOAL_OSCILLATION
        if self._check_no_progress():
            return StuckSignal.NO_PROGRESS
        return None

    def _check_no_progress(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.NO_PROGRESS, 0)
        window = self._recent_since(cutoff, count=NO_PROGRESS_WINDOW)
        if len(window) < NO_PROGRESS_WINDOW:
            return False
        return all(r.action_name == "<no_plan>" for r in window)

    def _check_goal_oscillation(self) -> bool:
        """Genuine oscillation only: exactly 2 distinct goals that flap
        A->B->A at least twice (>= OSC_MIN_SWITCHES adjacent goal switches)
        AND >= OSC_MIN_FAILURES failed cycles in the window.

        Both gates exist because "2 distinct goals in the last 8 cycles" alone
        false-fired on benign windows (trace 2026-06-10, replayed): a clean
        goal switch (7x GrindCharacterXP then 1x TaskExchange, 1 switch) and a
        mostly-productive window (7 ok + 1 other) both escalated toward
        SystemExit. With exactly 2 distinct goals every window record belongs
        to a flapping goal, so the window failure count IS the flapping-goal
        failure count (same filter the L1 handler applies when choosing what
        to suppress).
        """
        cutoff = self._ack_index.get(StuckSignal.GOAL_OSCILLATION, 0)
        window = self._recent_since(cutoff, count=GOAL_OSCILLATION_WINDOW)
        if len(window) < GOAL_OSCILLATION_WINDOW:
            return False
        goals = [r.goal_name for r in window]
        if len(set(goals)) != 2:
            return False
        switches = sum(1 for a, b in pairwise(goals) if a != b)
        if switches < OSC_MIN_SWITCHES:
            return False
        failures = sum(1 for r in window if not r.succeeded)
        return failures >= OSC_MIN_FAILURES

    def _check_state_frozen(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.STATE_FROZEN, 0)
        window = self._recent_since(cutoff, count=STATE_FROZEN_WINDOW)
        if len(window) < STATE_FROZEN_WINDOW:
            return False
        counts: dict[tuple[object, ...], int] = {}
        for rec in window:
            counts[rec.state_key] = counts.get(rec.state_key, 0) + 1
        return any(c >= 5 for c in counts.values())

    def _recent_since(self, cutoff_cycle: int, count: int) -> list[CycleRecord]:
        """Return up to `count` most-recent records added after `cutoff_cycle`."""
        history_list = list(self._history)
        # The most recent record was added at counter-1; oldest in buffer at counter - len(history).
        start_idx = self._cycle_counter - len(history_list)
        post_ack = [
            rec for i, rec in enumerate(history_list)
            if start_idx + i >= cutoff_cycle
        ]
        return post_ack[-count:]

    def acknowledge(self, signal: StuckSignal) -> None:
        """Mark this signal as handled — reset its detection window to the current cycle."""
        self._ack_index[signal] = self._cycle_counter
