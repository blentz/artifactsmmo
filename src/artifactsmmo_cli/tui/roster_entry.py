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
