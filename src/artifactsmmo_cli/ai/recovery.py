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
    state_key: tuple
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
        """Return the first matching signal, or None. Detection rules added in later tasks."""
        return None

    def acknowledge(self, signal: StuckSignal) -> None:
        """Mark this signal as handled — reset its detection window to the current cycle."""
        self._ack_index[signal] = self._cycle_counter
