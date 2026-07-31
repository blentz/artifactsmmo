"""MultiSnapshotStore: per-character snapshot, log, and fight buffers."""

from collections import deque
from collections.abc import Sequence

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord

LOG_BUFFER = 500
FIGHT_BUFFER = 200


class MultiSnapshotStore:
    """What WatchApp keeps about every character it watches.

    Buffers are PER CHARACTER, not shared: a shared cycle deque would let one
    busy character silently evict another's history. Fights keep their own
    buffer for the same reason the single-character app did — a long stretch of
    non-fight cycles must not push old fights out.
    """

    def __init__(
        self,
        characters: Sequence[str],
        log_buffer: int = LOG_BUFFER,
        fight_buffer: int = FIGHT_BUFFER,
    ) -> None:
        self._last: dict[str, CycleSnapshot | None] = {c: None for c in characters}
        self._recent: dict[str, deque[CycleSnapshot]] = {
            c: deque(maxlen=log_buffer) for c in characters
        }
        self._fights: dict[str, deque[FightRecord]] = {
            c: deque(maxlen=fight_buffer) for c in characters
        }

    def record(self, snap: CycleSnapshot) -> None:
        character = snap.character
        if character not in self._last:
            raise KeyError(f"snapshot for {character!r}, who is not in this roster")
        self._last[character] = snap
        self._recent[character].append(snap)
        if snap.fight is not None:
            self._fights[character].append(snap.fight)

    def last(self, character: str) -> CycleSnapshot | None:
        return self._last[character]

    def recent(self, character: str) -> deque[CycleSnapshot]:
        return self._recent[character]

    def fights(self, character: str) -> deque[FightRecord]:
        return self._fights[character]

    def latest_all(self) -> dict[str, CycleSnapshot]:
        """Every character that has produced at least one cycle."""
        return {c: snap for c, snap in self._last.items() if snap is not None}
