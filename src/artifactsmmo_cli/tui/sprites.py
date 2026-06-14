"""8x8 sprite tileset data for the TUI map. Pure data + value object.

Each sprite is 8 rows x 8 cols of palette-key chars. '.' (TRANSPARENT) shows
the terrain color behind it. Behavioral rendering lives in half_block.py;
code->sprite lookup and the procedural fallback live in sprite_registry.py.
"""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.tui.glyphs import (
    MONSTER_COLOR,
    NPC_COLOR,
    STRUCTURE_COLOR,
)
from artifactsmmo_cli.tui.palette import (
    BARK, DOORWOOD, GOLD, INK, KHAKI, LEAF, SKIN, STONE, TUNIC,
)

SPRITE_SIZE = 8
TRANSPARENT = "."


class SpriteCategory(Enum):
    PLAYER = "player"
    MONSTER = "monster"
    NPC = "npc"
    STRUCTURE = "structure"
    RESOURCE = "resource"


@dataclass(frozen=True)
class Sprite:
    """An 8x8 pixel sprite: rows of palette-key chars + a palette map."""

    rows: tuple[str, ...]
    palette: dict[str, str]


def validate_sprite(name: str, sprite: Sprite) -> None:
    """Raise ValueError if the sprite is not 8x8 or uses an undefined key."""
    if len(sprite.rows) != SPRITE_SIZE:
        raise ValueError(f"sprite {name!r}: expected {SPRITE_SIZE} rows, got {len(sprite.rows)}")
    for i, row in enumerate(sprite.rows):
        if len(row) != SPRITE_SIZE:
            raise ValueError(f"sprite {name!r} row {i}: expected {SPRITE_SIZE} cols, got {len(row)}")
        for ch in row:
            if ch != TRANSPARENT and ch not in sprite.palette:
                raise ValueError(f"sprite {name!r} row {i}: palette key {ch!r} undefined")


BLANK_SPRITE = Sprite(rows=(TRANSPARENT * SPRITE_SIZE,) * SPRITE_SIZE, palette={})

PLAYER_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oyyyyo.",
        ".oeyyeo.",
        ".oyyyyo.",
        "..oooo..",
        ".obbbbo.",
        ".ob..bo.",
        ".oo..oo.",
    ),
    palette={"o": INK, "y": SKIN, "e": INK, "b": TUNIC},
)

GREEN_SLIME_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oggggo.",
        "oggggggo",
        "ogeggego",
        "oggggggo",
        "oggggggo",
        ".oggggo.",
        "..oooo..",
    ),
    palette={"o": INK, "g": LEAF, "e": INK},
)

BANK_SPRITE = Sprite(
    rows=(
        "oooooooo",
        "oyyyyyyo",
        "oooooooo",
        "osssssso",
        "ossddsso",
        "ossddsso",
        "ossddsso",
        "oooooooo",
    ),
    palette={"o": INK, "y": GOLD, "s": STONE, "d": DOORWOOD},
)

DOOR_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oddddo.",
        ".oddddo.",
        ".oddddo.",
        ".odddko.",
        ".oddddo.",
        ".oddddo.",
        "..oooo..",
    ),
    palette={"o": INK, "d": DOORWOOD, "k": GOLD},
)

WOODCUTTING_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oggggo.",
        "oggggggo",
        "oggggggo",
        ".oggggo.",
        "..otto..",
        "..otto..",
        "..oooo..",
    ),
    palette={"o": INK, "g": LEAF, "t": BARK},
)

ARCHAEOLOGIST_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".obbbbo.",
        ".osssso.",
        ".oseeso.",
        ".osssso.",
        "..oooo..",
        ".okkkko.",
        ".ok..ko.",
    ),
    palette={"o": INK, "b": BARK, "s": SKIN, "e": INK, "k": KHAKI},
)

MONSTER_SPRITES: dict[str, Sprite] = {"green_slime": GREEN_SLIME_SPRITE}
NPC_SPRITES: dict[str, Sprite] = {"archaeologist": ARCHAEOLOGIST_SPRITE}
STRUCTURE_SPRITES: dict[str, Sprite] = {"bank": BANK_SPRITE, "door": DOOR_SPRITE}
RESOURCE_SPRITES: dict[str, Sprite] = {"resource_woodcutting": WOODCUTTING_SPRITE}

CURATED_BY_CATEGORY: dict[SpriteCategory, dict[str, Sprite]] = {
    SpriteCategory.MONSTER: MONSTER_SPRITES,
    SpriteCategory.NPC: NPC_SPRITES,
    SpriteCategory.STRUCTURE: STRUCTURE_SPRITES,
    SpriteCategory.RESOURCE: RESOURCE_SPRITES,
}

# Procedural fallback: a rounded blob silhouette + a 2-tone marking.
FALLBACK_SILHOUETTE: tuple[str, ...] = (
    "..####..",
    ".######.",
    "########",
    "########",
    "########",
    "########",
    ".######.",
    "..####..",
)
# Interior pixels toggled to the mark color by bits 0..7 of the code checksum.
MARK_POSITIONS: tuple[tuple[int, int], ...] = (
    (2, 2), (2, 5), (3, 3), (3, 4), (4, 3), (4, 4), (5, 2), (5, 5),
)
MARK_KEY = "M"
MARK_COLOR = "bright_white"
CATEGORY_FALLBACK_COLOR: dict[SpriteCategory, str] = {
    SpriteCategory.MONSTER: MONSTER_COLOR,
    SpriteCategory.NPC: NPC_COLOR,
    SpriteCategory.STRUCTURE: STRUCTURE_COLOR,
    SpriteCategory.RESOURCE: "green",
}

ALL_CURATED_SPRITES: dict[str, Sprite] = {
    "player": PLAYER_SPRITE,
    "green_slime": GREEN_SLIME_SPRITE,
    "bank": BANK_SPRITE,
    "door": DOOR_SPRITE,
    "resource_woodcutting": WOODCUTTING_SPRITE,
    "archaeologist": ARCHAEOLOGIST_SPRITE,
}

for _name, _sprite in ALL_CURATED_SPRITES.items():
    validate_sprite(_name, _sprite)
validate_sprite("blank", BLANK_SPRITE)
