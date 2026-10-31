"""CharacterRoster: the account's characters, with a stable slot, colour, and
sprite for each.

All characters share one silhouette and are told apart by tunic colour, so the
map reads as "the same player, five of them" rather than five species. Order
comes from the account and is never re-sorted: it is the deterministic tiebreak
for which sprite draws on top when two characters share a tile.
"""

from collections.abc import Sequence

from artifactsmmo_cli.tui.palette import AMBER_RAMP, BLOOD_RAMP, BREW_RAMP, LEAF_RAMP, TUNIC_RAMP, Ramp
from artifactsmmo_cli.tui.sprites import PLAYER_SPRITE, Sprite, reramp

MAX_CHARACTERS = 5
"""The account limit. Also the number of `1`-`5` focus keys."""

ROSTER_RAMPS: tuple[Ramp, ...] = (TUNIC_RAMP, BLOOD_RAMP, LEAF_RAMP, BREW_RAMP, AMBER_RAMP)
"""Tunic ramp per roster index: five visually distinct materials."""

ROSTER_COLORS: tuple[str, ...] = tuple(ramp.mid for ramp in ROSTER_RAMPS)
"""Tunic colour per roster index (each ramp's mid), for text and markers."""


class CharacterRoster:
    def __init__(self, names: Sequence[str]) -> None:
        if not names:
            raise ValueError("a roster needs at least one character")
        if len(names) > MAX_CHARACTERS:
            raise ValueError(
                f"an account holds at most {MAX_CHARACTERS} characters, got {len(names)}"
            )
        if len(set(names)) != len(names):
            raise ValueError(f"duplicate character names in roster: {list(names)}")
        self.names: tuple[str, ...] = tuple(names)
        self._index = {name: i for i, name in enumerate(self.names)}
        # Built once rather than per frame. The whole tunic ramp is swapped, so
        # every character keeps the player's shading and tinted outline.
        self._sprites = {
            name: reramp(PLAYER_SPRITE, {TUNIC_RAMP: ROSTER_RAMPS[i]})
            for i, name in enumerate(self.names)
        }

    def index(self, name: str) -> int:
        return self._index[name]

    def color(self, name: str) -> str:
        return ROSTER_COLORS[self._index[name]]

    def sprite(self, name: str) -> Sprite:
        return self._sprites[name]

    def at(self, slot: int) -> str | None:
        """The character on 1-based `slot`, or None when the roster is shorter."""
        if 1 <= slot <= len(self.names):
            return self.names[slot - 1]
        return None
