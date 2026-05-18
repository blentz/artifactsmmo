"""BlockerState + BlockerRegistry. See `blockers/__init__.py` for context."""

import time
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.learning.store import LearningStore


@dataclass
class BlockerState:
    """One learned gated dependency."""

    code: str
    """Logical name for the gate (e.g. "bank", "workshop:weaponcrafting")."""

    unlock_monster: str | None = None
    """Monster whose achievement satisfies this blocker, if any."""

    required_level: int = 0
    """Character level required to plausibly attempt the unlock."""

    blocked_since_monotonic: float | None = None
    """time.monotonic() when this blocker was last observed active.

    Used by the retry timer — caller (player) decides when to re-test the
    gate based on this + a delay constant.
    """

    blocked_at_char_level: int = 0
    """Character level at the moment of the block.

    Used by the retry gate: don't auto-retry until the char has gained at
    least one level since this point.
    """


@dataclass
class BlockerRegistry:
    """Per-character map of learned blockers."""

    blockers: dict[str, BlockerState] = field(default_factory=dict)

    def is_blocked(self, code: str) -> bool:
        return code in self.blockers

    def get(self, code: str) -> BlockerState | None:
        return self.blockers.get(code)

    def mark_blocked(
        self,
        code: str,
        char_level: int,
        unlock_monster: str | None = None,
        required_level: int = 0,
        store: LearningStore | None = None,
    ) -> None:
        """Record (or update) a blocker. Optionally persists via the store
        so future sessions remember this dependency without re-discovering."""
        self.blockers[code] = BlockerState(
            code=code,
            unlock_monster=unlock_monster,
            required_level=required_level,
            blocked_since_monotonic=time.monotonic(),
            blocked_at_char_level=char_level,
        )
        if store is not None and required_level > 0:
            store.set_blocker(
                blocker_code=code,
                unlock_monster=unlock_monster,
                required_level=required_level,
            )

    def clear(self, code: str) -> None:
        self.blockers.pop(code, None)

    @classmethod
    def load(cls, store: LearningStore, known_codes: list[str]) -> "BlockerRegistry":
        """Load persisted blockers for the given codes from the store."""
        reg = cls()
        for code in known_codes:
            b = store.get_blocker(code)
            if b is not None and b.required_level > 0:
                reg.blockers[code] = BlockerState(
                    code=code,
                    unlock_monster=b.unlock_monster,
                    required_level=b.required_level,
                )
        return reg
