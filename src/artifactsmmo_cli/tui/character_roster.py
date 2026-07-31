"""CharacterRoster: the account's characters, with a stable slot, colour, and
sprite for each.

All characters share one silhouette and are told apart by tunic colour, so the
map reads as "the same player, five of them" rather than five species. Order
comes from the account and is never re-sorted: it is the deterministic tiebreak
for which sprite draws on top when two characters share a tile.
"""

from collections.abc import Sequence

from artifactsmmo_cli.tui.palette import AMBER, BLOOD, BREW, LEAF, TUNIC
from artifactsmmo_cli.tui.sprites import PLAYER_SPRITE, Sprite, recolor

MAX_CHARACTERS = 5
"""The account limit. Also the number of `1`-`5` focus keys."""

ROSTER_COLORS: tuple[str, ...] = (TUNIC, BLOOD, LEAF, BREW, AMBER)
"""Tunic colour per roster index. Five visually distinct palette entries."""


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
        # Built once: MapPane's per-line Strip cache keys on sprite IDENTITY,
        # so recolouring per frame would defeat it.
        self._sprites = {
            name: recolor(
                PLAYER_SPRITE, {**PLAYER_SPRITE.palette, "b": ROSTER_COLORS[i]}
            )
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
