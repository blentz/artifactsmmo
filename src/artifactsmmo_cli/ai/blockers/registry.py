"""BlockerState + BlockerRegistry. See `blockers/__init__.py` for context."""

import time
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.learning.store import LearningStore


@dataclass
class BlockerState:
    """One learned or documented gated dependency.

    Prereq fields are independent — a blocker may have any combination:
    - `required_level` (character XP level) for fight gates and equip gates
    - `required_skill` + `required_skill_level` for craft / gather gates
    - `unlock_monster` when an achievement on that monster is the gate
    - `required_item` when an item drop / craft is the gate (e.g. dungeon key)
    """

    code: str
    """Logical name for the gate. Convention:
      - "bank" — bank access
      - "fight:<monster_code>" — combat with monster
      - "craft:<item_code>" — craft this item
      - "gather:<resource_code>" — gather this resource
      - "equip:<item_code>" — equip this item
      - "transition:<map_code>" — enter this map
    """

    unlock_monster: str | None = None
    """Monster whose achievement satisfies this blocker, if any."""

    required_level: int = 0
    """Character level required (combat or equip prereq)."""

    required_skill: str | None = None
    """Per-skill prereq name (e.g. "weaponcrafting") for craft / gather gates."""

    required_skill_level: int = 0
    """Level required in `required_skill`. 0 = no skill prereq."""

    required_item: str | None = None
    """Item code that must be in inventory to clear this blocker (dungeon key, etc)."""

    source: str = "discovered"
    """"discovered" (learned via API error like 496) or "documented" (seeded from game_data)."""

    blocked_since_monotonic: float | None = None
    """time.monotonic() when this blocker was last observed active."""

    blocked_at_char_level: int = 0
    """Character level at the moment of the block (only meaningful for `discovered`)."""


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
