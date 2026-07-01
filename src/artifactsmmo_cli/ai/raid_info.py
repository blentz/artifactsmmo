"""RaidInfo: one raid's live state captured from GET /raids (visibility only)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class RaidInfo:
    """A single raid with its current status. `remaining_hp` / `total_hp` /
    `window_ends_at` are populated only while the raid has an active instance."""

    code: str
    name: str
    monster: str
    status: str
    next_start_at: datetime
    remaining_hp: int | None
    total_hp: int | None
    window_ends_at: datetime | None

    def is_active(self) -> bool:
        """True when the raid is currently running (has an active instance)."""
        return self.status == "active"
