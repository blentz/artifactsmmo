"""Tracer ABC: write per-cycle records for postmortem analysis of the GOAP loop."""

from abc import ABC, abstractmethod


class Tracer(ABC):
    """Write per-cycle records for postmortem analysis."""

    @abstractmethod
    def write_cycle(self, record: dict[str, object]) -> None:
        """Write one cycle's record."""

    @abstractmethod
    def close(self) -> None:
        """Release any resources."""
