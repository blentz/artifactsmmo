"""ChildState: one child's status, as the TUI roster line reads it."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ChildState:
    character: str
    alive: bool
    restarts: int
    last_reason: str | None
    stderr_tail: tuple[str, ...]
