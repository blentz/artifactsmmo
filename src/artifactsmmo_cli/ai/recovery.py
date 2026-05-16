"""Stuck-state detection and escalating recovery for the GOAP player."""

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Deque


class StuckSignal(Enum):
    """Distinct stuck-state classes the detector can identify."""
    STATE_FROZEN = "state_frozen"
    GOAL_OSCILLATION = "goal_oscillation"
    NO_PROGRESS = "no_progress"


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
        self._history: Deque[CycleRecord] = deque(maxlen=history_size)
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
        window = self._recent_since(cutoff, count=4)
        if len(window) < 4:
            return False
        return all(r.action_name == "<no_plan>" for r in window)

    def _check_goal_oscillation(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.GOAL_OSCILLATION, 0)
        window = self._recent_since(cutoff, count=8)
        if len(window) < 8:
            return False
        goals = [r.goal_name for r in window]
        distinct = set(goals)
        return len(distinct) == 2

    def _check_state_frozen(self) -> bool:
        cutoff = self._ack_index.get(StuckSignal.STATE_FROZEN, 0)
        window = self._recent_since(cutoff, count=10)
        if len(window) < 10:
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
