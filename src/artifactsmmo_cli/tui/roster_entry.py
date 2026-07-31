"""RosterEntry: one character's line in the multi-character roster strip."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RosterEntry:
    slot: int
    character: str
    color: str
    level: int
    x: int
    y: int
    alive: bool
    restarts: int
    focused: bool
    last_reason: str | None = None
    """Why the child last exited. Populated only once it has died; None while
    alive or before any state has been observed."""
    last_stderr_line: str | None = None
    """The child's most recent stderr line. Where a dead character is shown,
    this is the operator's only visibility into why -- captured stderr was
    otherwise gathered and discarded with no consumer."""
