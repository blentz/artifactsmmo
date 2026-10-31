"""8x8 sprite tileset data for the TUI map. Pure data + value object.

Each sprite is 8 rows x 8 cols of palette-key chars. '.' (TRANSPARENT) shows
the terrain color behind it. Behavioral rendering lives in half_block.py;
code->sprite lookup and the procedural fallback live in sprite_registry.py.
"""

import string
from dataclasses import astuple, dataclass
from enum import Enum
from functools import cached_property

from artifactsmmo_cli.tui.glyphs import (
    MONSTER_COLOR,
    NPC_COLOR,
    STRUCTURE_COLOR,
)
from artifactsmmo_cli.tui.palette import (
    AMBER_RAMP,
    BARK,
    BARK_RAMP,
    BLOOD_RAMP,
    BONE_RAMP,
    BREW_RAMP,
    CLOUD_RAMP,
    COPPER_RAMP,
    DOORWOOD_RAMP,
    EMBER_RAMP,
    GLOW,
    GOBLIN_SKIN_RAMP,
    GOLD_RAMP,
    HAIR_RAMP,
    INK,
    KHAKI_RAMP,
    LEAF_RAMP,
    LEATHER_RAMP,
    OGRE_SKIN_RAMP,
    ORC_SKIN_RAMP,
    PINK_RAMP,
    SHINE,
    SKIN_RAMP,
    SLATE_RAMP,
    SLIME_RAMP,
    STEEL,
    STEEL_RAMP,
    STONE,
    STONE_RAMP,
    TUNIC_RAMP,
    WATER_RAMP,
    Ramp,
)

SPRITE_SIZE = 8
TRANSPARENT = "."


class SpriteCategory(Enum):
    PLAYER = "player"
    MONSTER = "monster"
    NPC = "npc"
    STRUCTURE = "structure"
    RESOURCE = "resource"


SpriteKey = tuple[tuple[str, ...], tuple[tuple[str, str], ...]]


@dataclass(frozen=True)
class Sprite:
    """An 8x8 pixel sprite: rows of palette-key chars + a palette map."""

    rows: tuple[str, ...]
    palette: dict[str, str]

    @cached_property
    def key(self) -> SpriteKey:
        """Hashable content identity: rows + sorted palette. Overlays rebuild
        Sprites every animation frame and CPython reuses freed ids, so render
        caches must key on this, never on id()."""
        return (self.rows, tuple(sorted(self.palette.items())))


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


# Replacement keys for overlay collisions, in a fixed order so a merge is
# deterministic (render caches key on sprite content).
_OVERLAY_KEY_POOL = string.digits + string.ascii_letters + "!#$%&*+-=?@^~"


def overlay_sprites(base: Sprite, top: Sprite) -> Sprite:
    """Merge two 8x8 sprites: each non-transparent pixel of `top` wins, else
    `base` shows through. Every pixel keeps the colour of the sprite it came
    from: a `top` key that `base` also uses for a DIFFERENT colour is renamed
    to an unused key (a swung tool's 'h' handle must not repaint a monster's
    'h' hair). Returns a new immutable Sprite (compositor-cache safe)."""
    used = set(base.palette) | set(top.palette) | {TRANSPARENT}
    free = (ch for ch in _OVERLAY_KEY_POOL if ch not in used)
    rename = {
        key: next(free)
        for key in sorted(top.palette)
        if key in base.palette and base.palette[key] != top.palette[key]
    }
    rows = tuple(
        "".join(
            rename.get(top.rows[r][c], top.rows[r][c]) if top.rows[r][c] != TRANSPARENT
            else base.rows[r][c]
            for c in range(SPRITE_SIZE)
        )
        for r in range(SPRITE_SIZE)
    )
    top_palette = {rename.get(key, key): color for key, color in top.palette.items()}
    return Sprite(rows=rows, palette={**base.palette, **top_palette})


def shade_keys(ramp: Ramp, keys: str) -> dict[str, str]:
    """Palette entries for one material: `keys` names the palette keys for the
    ramp's outline, dark, mid and light shades in that order ('_' skips one).
    `shade_keys(ORC_SKIN_RAMP, "odgL")` -> {"o": outline, "d": dark, "g": mid, "L": light}."""
    return {key: shade for key, shade in zip(keys, astuple(ramp), strict=True) if key != "_"}


def palette_of(*parts: dict[str, str]) -> dict[str, str]:
    """Merge palette fragments (later fragments win)."""
    merged: dict[str, str] = {}
    for part in parts:
        merged.update(part)
    return merged


def reramp(base: Sprite, swaps: dict[Ramp, Ramp]) -> Sprite:
    """A family variant: same silhouette as `base`, with every shade of each
    swapped ramp replaced by the same shade of its replacement (outline for
    outline, light for light), so the variant keeps the base's shading. Swaps
    apply by colour value in one pass, so {A: B, B: A} exchanges two ramps."""
    by_shade = {
        old: new
        for old_ramp, new_ramp in swaps.items()
        for old, new in zip(astuple(old_ramp), astuple(new_ramp), strict=True)
    }
    return Sprite(rows=base.rows, palette={key: by_shade.get(color, color) for key, color in base.palette.items()})


BLANK_SPRITE = Sprite(rows=(TRANSPARENT * SPRITE_SIZE,) * SPRITE_SIZE, palette={})

# The player: short hair, eyes inset from the face edge, neck, tunic, boots. The
# tunic is TUNIC_RAMP (keys o/t/b/B) so CharacterRoster reramps it per slot;
# cells (0,7) and (1,7) stay transparent for the planning thought bubble.
PLAYER_SPRITE = Sprite(
    rows=(
        "..hhhh..",
        ".hHhhhd.",
        ".dLsssd.",
        ".dsesed.",
        "oBdssdto",
        "sLbbbbts",
        ".obbtbo.",
        ".ff..ff.",
    ),
    palette=palette_of(shade_keys(HAIR_RAMP, "_hH_"), shade_keys(SKIN_RAMP, "_dsL"), {"e": INK},
                       shade_keys(TUNIC_RAMP, "otbB"), {"f": LEATHER_RAMP.dark}),
)

def _player_with_tool(positions: tuple[tuple[int, int], ...], key: str, color: str) -> Sprite:
    """PLAYER_SPRITE with `key` painted at the given (row, col) cells (which must
    be transparent in the base), using `color`. Returns a new immutable Sprite."""
    rows = list(PLAYER_SPRITE.rows)
    for r, c in positions:
        assert rows[r][c] == TRANSPARENT, f"tool cell ({r},{c}) not transparent"
        rows[r] = rows[r][:c] + key + rows[r][c + 1:]
    palette = dict(PLAYER_SPRITE.palette)
    palette[key] = color
    return Sprite(rows=tuple(rows), palette=palette)


# Tool heads (drawn in the arc-neighbor tile, one 8x8 weapon each). 1px haft at
# col 3, head at top, reused at all arc offsets. m=STEEL (medium grey),
# l=STONE (light grey), h=BARK (handle).
AXE_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "........",
        ".mmmmmml",   # head offset on the haft (2px left, 3px right), blade on col 7
        ".mmmmmml",
        ".mmmmmml",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)
PICKAXE_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "........",
        ".lmmml..",   # head centred on haft (cols 2-4); light-grey triangles each side
        "llmmmll.",
        ".lmmml..",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)
HAMMER_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "........",
        "..mmm...",   # pickaxe minus light-grey: solid block on the haft
        "..mmm...",
        "..mmm...",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "h": BARK},
)
FIGHT_HEAD: Sprite = Sprite(
    rows=(
        "...l....",   # light-grey tip
        "..lll...",   # pickaxe-style triangle
        "..mmm...",   # vertical medium-grey blade, centred on haft
        "..mmm...",
        "..mmm...",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)


def grip_overlay(dcol: int, drow: int) -> Sprite:
    """A mostly-transparent 8x8 with a 2-pixel handle ('h'=BARK) stepping from the
    player's hand (4,4) toward the head direction. The player-tile overlay so the
    swung tool reads as held. Combat's negative dcol mirrors for free."""
    grid = [[TRANSPARENT] * SPRITE_SIZE for _ in range(SPRITE_SIZE)]
    for k in (1, 2):
        r, c = 4 + k * drow, 4 + k * dcol
        if 0 <= r < SPRITE_SIZE and 0 <= c < SPRITE_SIZE:
            grid[r][c] = "h"
    return Sprite(rows=tuple("".join(row) for row in grid), palette={"h": BARK})


def rot90cw(sprite: Sprite) -> Sprite:
    """Exact 90° clockwise rotation of an 8x8 sprite: new[i][j] = old[7-j][i]."""
    n = SPRITE_SIZE
    rows = tuple(
        "".join(sprite.rows[n - 1 - j][i] for j in range(n)) for i in range(n)
    )
    return Sprite(rows=rows, palette=dict(sprite.palette))


@dataclass(frozen=True)
class ToolHeads:
    """A tool head in two hand-authored orientations (the rest derive by rot90cw):
    `up` points up (canonical), `ne` points up-right (diagonal)."""

    up: Sprite
    ne: Sprite


_DIR_TO_BASE_TURNS: dict[tuple[int, int], tuple[int, int]] = {
    (0, -1): (0, 0), (1, 0): (0, 1), (0, 1): (0, 2), (-1, 0): (0, 3),
    (1, -1): (1, 0), (1, 1): (1, 1), (-1, 1): (1, 2), (-1, -1): (1, 3),
}


def oriented_head(tool: ToolHeads, dcol: int, drow: int) -> Sprite:
    """The tool head oriented to point in unit direction (dcol, drow) — away from
    the player — so the haft trails back toward the player tile."""
    base_idx, turns = _DIR_TO_BASE_TURNS.get((dcol, drow), (0, 0))
    sprite = tool.up if base_idx == 0 else tool.ne
    for _ in range(turns):
        sprite = rot90cw(sprite)
    return sprite


# Hand-authored NE (up-right) heads: head/blade upper-right, haft trailing to the
# lower-left toward the player. m=STEEL, l=STONE, h=BARK.
AXE_NE: Sprite = Sprite(
    rows=("....mmml", "....mmml", "....mmm.", "...hm...", "..h.....", ".h......",
          "h.......", "........"),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)
PICKAXE_NE: Sprite = Sprite(
    rows=("....mml.", "...lmmml", "....mmm.", "...hm...", "..h.....", ".h......",
          "h.......", "........"),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)
HAMMER_NE: Sprite = Sprite(
    rows=("....mmm.", "....mmm.", "....mmm.", "...hm...", "..h.....", ".h......",
          "h.......", "........"),
    palette={"m": STEEL, "h": BARK},
)
FIGHT_NE: Sprite = Sprite(
    rows=(".....ll.", "....lmm.", "...lmm..", "..hmm...", "..h.....", ".h......",
          "h.......", "........"),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)

AXE: ToolHeads = ToolHeads(AXE_HEAD, AXE_NE)
PICKAXE: ToolHeads = ToolHeads(PICKAXE_HEAD, PICKAXE_NE)
HAMMER: ToolHeads = ToolHeads(HAMMER_HEAD, HAMMER_NE)
SWORD: ToolHeads = ToolHeads(FIGHT_HEAD, FIGHT_NE)


def gather_head(skill: str | None) -> ToolHeads:
    """The gather tool for a resource's skill: woodcutting -> axe, else -> pickaxe."""
    if skill == "woodcutting":
        return AXE
    return PICKAXE


# Thought cloud: ONE lobed cloud spanning two adjacent tiles (CLOUD_RAMP, lit
# from the top-left: three puffs on top, a shadowed scalloped base, and a trail
# bubble at its lower-left that leads down to the planning bubble by the head).
# The left/right halves are fixed seam-mates -- the left half fills its right
# edge (col 7) and the right half its left edge (col 0) so the body rows conjoin
# into a single cloud (never swapped). The "thinking" shimmer is an ellipsis:
# frame A shows two dots, frame B three; the cloud itself never changes.
_CLOUD_PALETTE: dict[str, str] = palette_of(shade_keys(CLOUD_RAMP, "oDlH"), {"d": CLOUD_RAMP.outline})
CLOUD_LEFT_A: Sprite = Sprite(
    rows=("......oo", "...ooHHH", "..oHHoHl", ".oHlllll", "oHlldlld", "olllllll",
          ".oDDoDDD", "H.oo.ooo"),
    palette=_CLOUD_PALETTE,
)
CLOUD_RIGHT_A: Sprite = Sprite(
    rows=("oo......", "llooo...", "llloHoo.", "lllllllo", "lllllllo", "llllllDo",
          "DDoDDDo.", "oo.ooo.."),
    palette=_CLOUD_PALETTE,
)
CLOUD_LEFT_B: Sprite = CLOUD_LEFT_A
CLOUD_RIGHT_B: Sprite = Sprite(
    rows=("oo......", "llooo...", "llloHoo.", "lllllllo", "lldllllo", "llllllDo",
          "DDoDDDo.", "oo.ooo.."),
    palette=_CLOUD_PALETTE,
)


# Thought bubble at 2 o'clock from the head (upper-right transparent cells).
PLANNING_SPRITE: Sprite = _player_with_tool(((0, 7), (1, 7)), "p", CLOUD_RAMP.mid)

# --- Curated art ---------------------------------------------------------------
# Style (docs/PLAN_sprite_refresh.md): every material is a palette Ramp lit from
# the top-left (light upper-left, dark lower-right); a sprite's edge is its main
# material's tinted `outline`, not INK (INK is for eyes); and no two drawings
# share a silhouette. Variants are `reramp`s of a base, so they keep its shading.

_FACE = palette_of(shade_keys(SKIN_RAMP, "_dsL"), {"e": INK})

GREEN_SLIME_SPRITE = Sprite(
    rows=(
        "........",
        "...ooo..",
        "..oHLmo.",
        ".oLmmmdo",
        ".omememd",
        "oLmmmmdo",
        "odmmmddo",
        ".oooooo.",
    ),
    palette=palette_of(shade_keys(SLIME_RAMP, "odmL"), {"H": SHINE, "e": INK}),
)

# Columned bank: gold pediment, stone columns, dark doorway.
BANK_SPRITE = Sprite(
    rows=(
        "...yy...",
        "..yYyy..",
        ".yYyyyd.",
        "oooooooo",
        "oLsLsLso",
        "oLsDDLso",
        "oLsDDLso",
        "oddddddo",
    ),
    palette=palette_of(shade_keys(GOLD_RAMP, "_dyY"), shade_keys(STONE_RAMP, "odsL"),
                       {"D": DOORWOOD_RAMP.outline}),
)

# Arched plank door with a gold handle.
DOOR_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oLwwdo.",
        "oLwdwwdo",
        "oLwdwwdo",
        "oLwdwkdo",
        "oLwdwwdo",
        "oLwdwwdo",
        "oooooooo",
    ),
    palette=palette_of(shade_keys(DOORWOOD_RAMP, "odwL"), {"k": GOLD_RAMP.light}),
)

WOODCUTTING_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oLLmmo.",
        "oLmmmmdo",
        "ommmmddo",
        "omddmddo",
        ".oddddo.",
        "...bt...",
        "..obtto.",
    ),
    palette=palette_of(shade_keys(LEAF_RAMP, "odmL"), {"b": BARK_RAMP.mid, "t": BARK_RAMP.dark}),
)

# Wide-brimmed explorer hat, satchel strap.
ARCHAEOLOGIST_SPRITE = Sprite(
    rows=(
        "..oLko..",
        "oLkkkkko",
        ".dLsssd.",
        ".dsesed.",
        "..dssd..",
        "oLnkkkdo",
        ".okkndo.",
        ".ff..ff.",
    ),
    palette=palette_of(shade_keys(KHAKI_RAMP, "odkL"), _FACE,
                       {"n": LEATHER_RAMP.mid, "f": LEATHER_RAMP.dark}),
)

# Hair bun, dyed dress with a narrow apron, scissors in hand. The dress is the
# dyed material (BREW) so the merchant reramps below read as different trades.
TAILOR_SPRITE = Sprite(
    rows=(
        "...hh...",
        "..hHhh..",
        ".hLsssh.",
        ".hsesed.",
        "..dssd.y",
        ".oMmwDoy",
        ".omwwDo.",
        "..ff.ff.",
    ),
    palette=palette_of(shade_keys(HAIR_RAMP, "_hH_"), _FACE, shade_keys(BREW_RAMP, "oDmM"),
                       {"w": BONE_RAMP.mid, "y": STONE_RAMP.light, "f": LEATHER_RAMP.dark}),
)

# Tall pointed brimmed hat, white beard, staff with a glowing tip.
CULTIST_WIZARD_SPRITE = Sprite(
    rows=(
        "...o...g",
        "..oLo..s",
        ".oLhhdos",
        "ohhhhhhs",
        ".dsesd.s",
        ".owwwwos",
        ".oLbbbds",
        ".oobbdos",
    ),
    palette=palette_of(shade_keys(SLATE_RAMP, "o_hL"), _FACE, shade_keys(BREW_RAMP, "_dbL"),
                       {"w": BONE_RAMP.light, "g": GLOW, "s": BARK_RAMP.mid}),
)

# Deep cowl, glowing eyes, a rune held out front.
RUNE_VENDOR_SPRITE = Sprite(
    rows=(
        "..oooo..",
        ".oLttdo.",
        "oLtkktdo",
        "otkeektd",
        "oLttttdo",
        "oLtggtdo",
        ".ottgtdo",
        ".oooooo.",
    ),
    palette=palette_of(shade_keys(TUNIC_RAMP, "odtL"),
                       {"k": INK, "e": GLOW, "g": GOLD_RAMP.light}),
)

# Turban, veiled face, wide sleeves.
SANDWHISPER_TRADER_SPRITE = Sprite(
    rows=(
        "..oLLo..",
        ".oLaaado",
        ".dssesd.",
        ".avvvva.",
        "aLaaaada",
        "aoLaadoa",
        ".oaaado.",
        ".ff..ff.",
    ),
    palette=palette_of(shade_keys(AMBER_RAMP, "odaL"), _FACE,
                       {"v": BONE_RAMP.mid, "f": LEATHER_RAMP.dark}),
)

# Flat cap, holding a big task scroll.
TASKS_TRADER_SPRITE = Sprite(
    rows=(
        "........",
        "..oLko..",
        ".okkkkko",
        ".dsesd..",
        "..dsd.pp",
        ".oLkkoPp",
        ".okkdoPp",
        ".ff..f..",
    ),
    palette=palette_of(shade_keys(KHAKI_RAMP, "odkL"), _FACE,
                       {"p": BONE_RAMP.mid, "P": BONE_RAMP.dark, "f": LEATHER_RAMP.dark}),
)

# Market stall: striped awning, goods on the counter.
GRAND_EXCHANGE_SPRITE = Sprite(
    rows=(
        "rwrwrwrw",
        "rwrwrwrw",
        "o......o",
        "o.y.g..o",
        "oLmmmmdo",
        "oLmmmmdo",
        "o.oooo.o",
        "o......o",
    ),
    palette=palette_of(shade_keys(BARK_RAMP, "odmL"),
                       {"r": BLOOD_RAMP.mid, "w": BONE_RAMP.light, "y": GOLD_RAMP.mid,
                        "g": LEAF_RAMP.mid}),
)

# Anvil on a stump.
WORKSHOP_SPRITE = Sprite(
    rows=(
        "........",
        "........",
        ".oLaaao.",
        "LLaaaaao",
        "...oado.",
        "..oLado.",
        "..oLbdo.",
        ".oLbbbdo",
    ),
    palette=palette_of(shade_keys(SLATE_RAMP, "odaL"), {"b": BARK_RAMP.mid}),
)

# Notice board on two posts, pinned papers.
TASKS_MASTER_SPRITE = Sprite(
    rows=(
        "oooooooo",
        "oLbbbbdo",
        "obpbPpbo",
        "obPpbpbo",
        "oLbbbbdo",
        "oooooooo",
        ".od..do.",
        ".od..do.",
    ),
    palette=palette_of(shade_keys(BARK_RAMP, "odbL"), {"p": BONE_RAMP.light, "P": BONE_RAMP.mid}),
)

# Boulder with copper veins.
MINING_SPRITE = Sprite(
    rows=(
        "........",
        "...ooo..",
        "..oLssoo",
        ".oLscssd",
        "oLsscsdd",
        "osccssdo",
        "osssddco",
        ".oooooo.",
    ),
    palette=palette_of(shade_keys(SLATE_RAMP, "odsL"), {"c": COPPER_RAMP.light}),
)

# Pond with a leaping fish.
FISHING_SPRITE = Sprite(
    rows=(
        "...aa...",
        "..aAaa..",
        ".a..a...",
        "..oooo..",
        ".oLwwwo.",
        "oLwWwwdo",
        "owwwwwdo",
        ".oooooo.",
    ),
    palette=palette_of(shade_keys(WATER_RAMP, "odwL"),
                       {"W": SHINE, "a": AMBER_RAMP.mid, "A": AMBER_RAMP.light}),
)

# Round flask of bubbling brew.
ALCHEMY_SPRITE = Sprite(
    rows=(
        "...oo...",
        "...ww...",
        "...ow...",
        "..oLwo..",
        ".oLbbdo.",
        "oLbHbbdo",
        "obbbbddo",
        ".oooooo.",
    ),
    palette=palette_of(shade_keys(BREW_RAMP, "odbL"), {"w": STONE_RAMP.light, "H": SHINE}),
)

BLUE_SLIME_SPRITE = reramp(GREEN_SLIME_SPRITE, {SLIME_RAMP: TUNIC_RAMP})
RED_SLIME_SPRITE = reramp(GREEN_SLIME_SPRITE, {SLIME_RAMP: BLOOD_RAMP})
YELLOW_SLIME_SPRITE = reramp(GREEN_SLIME_SPRITE, {SLIME_RAMP: GOLD_RAMP})

# White hen: comb, beak, folded wing, legs.
CHICKEN_SPRITE = Sprite(
    rows=("..rr....", ".oLwo...", ".owew...", "aawwwo..", ".oLwwwwo", ".owwwddo", "..oddo..", "...a.a.."),
    palette=palette_of(shade_keys(BONE_RAMP, "odwL"),
                       {"r": BLOOD_RAMP.mid, "a": AMBER_RAMP.mid, "e": INK}),
)
# Side-on cow: horns, spots, pink muzzle.
COW_SPRITE = Sprite(
    rows=("h......h", ".oLww...", "ewwkwwwo", "ppwwwkwo", ".oLwwwdo", ".okwwwdo", ".w.d.w.d", ".o.o.o.o"),
    palette=palette_of(shade_keys(BONE_RAMP, "odwL"),
                       {"k": INK, "e": INK, "h": BONE_RAMP.light, "p": PINK_RAMP.mid}),
)
# Round pig: snout, curly tail.
PIG_SPRITE = Sprite(
    rows=("........", ".o.oooo.", "oLpppppo", "nnepLpdt", "nnppppdo", ".oppppdo", ".p.d.d..", ".o.o.o.."),
    palette=palette_of(shade_keys(PINK_RAMP, "odpL"), {"n": PINK_RAMP.dark, "e": INK, "t": PINK_RAMP.dark}),
)
# Fluffy fleece, dark face and legs.
SHEEP_SPRITE = Sprite(
    rows=("........", "..owwow.", ".oLwwwwo", "ffLwwwwo", "efwwwwdo", ".owwwddo", "..f..f..", "..f..f.."),
    palette=palette_of(shade_keys(BONE_RAMP, "odwL"), {"f": SLATE_RAMP.dark, "e": INK}),
)
# Grey wolf: pricked ears, snout, tail.
WOLF_SPRITE = Sprite(
    rows=(".o.o....", ".oLwo...", "kwewwo.t", ".owwwwwt", "..oLwwdo", "..owwddo", "..w.d.d.", "..o.o.o."),
    palette=palette_of(shade_keys(STONE_RAMP, "odwL"),
                       {"e": AMBER_RAMP.light, "k": INK, "t": STONE_RAMP.dark}),
)
# Bulky bear body with an owl's face disk and beak.
OWLBEAR_SPRITE = Sprite(
    rows=(".o....o.", "oLbbbbdo", "obaybado", "obbkbbdo", "oLbbbbdo", "oLbccbdo", ".ob..do.", ".oo..oo."),
    palette=palette_of(shade_keys(BARK_RAMP, "odbL"),
                       {"a": AMBER_RAMP.light, "y": INK, "k": AMBER_RAMP.mid, "c": BARK_RAMP.light}),
)
# Round body, eight legs, glowing eyes. Legs use the dark shade, not the
# outline, so the spider still shows on the void.
SPIDER_SPRITE = Sprite(
    rows=("o......o", ".o.oo.o.", "o.oLmo.o", ".omrrmo.", "o.oddo.o", ".o.oo.o.", "o......o", "........"),
    palette=palette_of(shade_keys(SLATE_RAMP, "_dmL"), {"o": SLATE_RAMP.dark, "r": GLOW}),
)
# Winged green serpent coiling down.
FLYING_SNAKE_SPRITE = Sprite(
    rows=("..oLgo..", "w.ogego.", "ww.oggo.", "www.ogdo", "..oLgdo.", ".oLgdo..", ".ogdo...", "..oo...."),
    palette=palette_of(shade_keys(LEAF_RAMP, "odgL"), {"e": INK, "w": AMBER_RAMP.light}),
)
# Coiled sand snake, raised head, forked tongue.
SAND_SNAKE_SPRITE = Sprite(
    rows=(".oLao...", ".oeaao..", "..oado..", "r..oado.", "..oLaado", ".oLaaado", "oLaaddo.", ".ooooo.."),
    palette=palette_of(shade_keys(AMBER_RAMP, "odaL"), {"e": INK, "r": BLOOD_RAMP.mid}),
)

# Goblin: long pointed ears, short body, leather jerkin.
GOBLIN_SPRITE = Sprite(
    rows=("........", "L.oooo.d", "oLgggddo", ".grggrd.", "..oddo..", ".ommmko.", "..m..k..", ".oo..oo."),
    palette=palette_of(shade_keys(GOBLIN_SKIN_RAMP, "odgL"), {"r": GLOW},
                       shade_keys(LEATHER_RAMP, "_km_")),
)
# A goblin head riding a grey wolf (wide quadruped).
GOBLIN_WOLFRIDER_SPRITE = Sprite(
    rows=("..g.g...", "..ogo...", "..grg...", ".Lwwwww.", "Lwwwwwdo", "wewwwwdo", ".w.d.d..", ".o.o.o.."),
    palette=palette_of(shade_keys(GOBLIN_SKIN_RAMP, "__g_"), shade_keys(STONE_RAMP, "odwL"),
                       {"r": GLOW, "e": AMBER_RAMP.mid}),
)
# Orc: separate head, tusks, broad shoulders, belt.
ORC_SPRITE = Sprite(
    rows=("..oooo..", ".oLggdo.", ".grggrd.", ".gwddwd.", "oLggggdo", "olkkkkko", ".og..do.", ".oo..oo."),
    palette=palette_of(shade_keys(ORC_SKIN_RAMP, "odgL"), {"r": GLOW, "w": BONE_RAMP.light},
                       shade_keys(LEATHER_RAMP, "_kl_")),
)
# Ogre: tiny head sunk into a huge hunched body, short legs.
OGRE_SPRITE = Sprite(
    rows=("...oo...", "..oLmo..", ".oemedoo", "oLmmmmdo", "LmmmmmmD", "ommkkddo", ".om..do.", ".oo..oo."),
    palette=palette_of(shade_keys(OGRE_SKIN_RAMP, "odmL"), {"e": INK, "D": OGRE_SKIN_RAMP.outline},
                       shade_keys(LEATHER_RAMP, "_k__")),
)
# Cyclops: one great eye, a horn, broad shoulders.
CYCLOPS_SPRITE = Sprite(
    rows=("...oo...", ".ooLmoo.", "oLwwwmdo", "omwppwdo", ".omwwdo.", "oLmmmmdo", ".om..do.", ".oo..oo."),
    palette=palette_of(shade_keys(SKIN_RAMP, "odmL"), {"w": BONE_RAMP.light, "p": INK}),
)
# Imp: small horned devil, tail curling right.
IMP_SPRITE = Sprite(
    rows=("........", "o.oooo.o", ".oLiido.", ".oyiiyo.", "..odio..", ".oLiido.", "..i..d.t", ".oo..oot"),
    palette=palette_of(shade_keys(BLOOD_RAMP, "odiL"), {"y": GOLD_RAMP.light, "t": BLOOD_RAMP.dark}),
)
# Highwayman: wide-brimmed hat, masked eyes, cloak.
HIGHWAYMAN_SPRITE = Sprite(
    rows=("...oo...", "..oLho..", "ohhhhhho", ".skkkks.", ".osssdo.", "oLccccdo", ".occcdo.", ".ff..ff."),
    palette=palette_of(shade_keys(SLATE_RAMP, "o_hL"), shade_keys(SKIN_RAMP, "_dsL"),
                       {"k": INK, "c": SLATE_RAMP.mid, "f": LEATHER_RAMP.dark}),
)
# Cultist acolyte: pointed hood, glowing eyes, robe flaring to the ground.
CULTIST_ACOLYTE_SPRITE = Sprite(
    rows=("...o....", "..oLo...", "..Lbbo..", ".obrrbo.", ".oLbbdo.", ".Lbbbbdo", "oLbbbbdo", "oooooooo"),
    palette=palette_of(shade_keys(BREW_RAMP, "odbL"), {"r": GLOW}),
)
# Skeleton: skull, spine and ribs, thin legs.
SKELETON_SPRITE = Sprite(
    rows=("..oooo..", ".oLwwdo.", ".oeweeo.", "..owdo..", ".owowo..", "..owdo..", "..w..d..", ".ww..dd."),
    palette=palette_of(shade_keys(BONE_RAMP, "odwL"), {"e": INK}),
)
# Death knight: horned helm, glowing visor slit, broad pauldrons.
DEATH_KNIGHT_SPRITE = Sprite(
    rows=("o......o", "Lo.oo.od", ".oLaado.", ".arrrra.", "LLaaaadd", "oLaaaado", ".oa..do.", ".oo..oo."),
    palette=palette_of(shade_keys(STEEL_RAMP, "odaL"), {"r": GLOW}),
)
# Vampire: widow's peak, pale face, high collar, flared cape with a red lining.
VAMPIRE_SPRITE = Sprite(
    rows=("..hhhh..", ".hhwwhh.", ".hwrwrh.", "c.wwww.c", "cc.oo.cc", "ccrbbrcc", "cccbbccc", "cc.oo.cc"),
    palette={"h": INK, "w": BONE_RAMP.light, "r": GLOW, "c": SLATE_RAMP.dark,
             "o": SLATE_RAMP.outline, "b": BLOOD_RAMP.dark},
)
# Hellhound: black hound wreathed in fire.
HELLHOUND_SPRITE = Sprite(
    rows=("f.o.o...", ".foLbo..", "kbebbo.f", ".obbbbbf", "..oLbbdo", "..obbddo", "..b.d.d.", "..f.f.f."),
    palette=palette_of(shade_keys(SLATE_RAMP, "odbL"),
                       {"e": EMBER_RAMP.light, "k": INK, "f": EMBER_RAMP.mid}),
)
# Cursed tree: dead grey trunk, glowing face, grasping branches.
CURSED_TREE_SPRITE = Sprite(
    rows=("o.o..o.o", ".oLoo.o.", "..oLmdo.", "..mrmrd.", "..omkdo.", "...omd..", "..omdd..", ".oo..oo."),
    palette=palette_of(shade_keys(SLATE_RAMP, "odmL"), {"r": GLOW, "k": INK}),
)
# Mushmush: red spotted cap over a little face.
MUSHMUSH_SPRITE = Sprite(
    rows=("..oooo..", ".oLrwro.", "orwrrrdo", "oooooooo", "..sese..", "..ssss..", ".os..so.", ".oo..oo."),
    palette=palette_of(shade_keys(BLOOD_RAMP, "odrL"),
                       {"w": BONE_RAMP.light, "s": BONE_RAMP.mid, "e": INK}),
)
# Desert scorpion: pincers forward, segmented tail arcing over.
DESERT_SCORPION_SPRITE = Sprite(
    rows=("......t.", ".....o.t", "aa....oa", "oa.ooao.", ".oLaaado", "aoeaeado", ".a.a.a..", "........"),
    palette=palette_of(shade_keys(AMBER_RAMP, "odaL"), {"e": INK, "t": BLOOD_RAMP.mid}),
)
# Sandwarden: turbaned guard with a tall spear.
SANDWARDEN_SPRITE = Sprite(
    rows=(".oLLko.y", "oLkkkdo.", ".osesdos", ".osssdos", "oLkkkkds", "oLkkkkds", ".ok..dos", ".oo..oos"),
    palette=palette_of(shade_keys(KHAKI_RAMP, "odkL"), shade_keys(SKIN_RAMP, "__s_"),
                       {"e": INK, "s": BARK_RAMP.mid, "y": STEEL_RAMP.light}),
)
# King slime: a purple slime wearing a crown.
KING_SLIME_SPRITE = Sprite(
    rows=(".y.y.y..", ".yyyyy..", "..oHLmo.", ".oLmmmdo", ".omememd", "oLmmmmdo", "odmmmddo", ".oooooo."),
    palette=palette_of(shade_keys(BREW_RAMP, "odmL"), {"H": SHINE, "e": INK, "y": GOLD_RAMP.mid}),
)

# --- Base shapes reramped into the bat and dragon families below ---
_BAT_BASE = Sprite(
    rows=(
        "........",
        ".o....o.",
        "wwoLbow.",
        "wwbebeww",
        "w.obdo.w",
        "...od...",
        "........",
        "........",
    ),
    palette=palette_of(shade_keys(BARK_RAMP, "odbL"), {"e": EMBER_RAMP.mid, "w": SLATE_RAMP.mid}),
)
_DRAGON_BASE = Sprite(
    rows=(
        "...hh...",
        "..oLmo..",
        "w.omemw.",
        "wwoLmdww",
        "wwmmmdww",
        ".oLmmdo.",
        ".m.mm.d.",
        "mo....od",
    ),
    palette=palette_of(shade_keys(BLOOD_RAMP, "odmL"),
                       {"h": GOLD_RAMP.light, "e": GOLD_RAMP.mid, "w": BLOOD_RAMP.dark}),
)

# Lich: crowned skull, glowing eyes, robe, staff.
LICH_SPRITE = Sprite(
    rows=(
        "y.y.y...",
        "yyyyy...",
        "oLwwdo..",
        "orwwro..",
        ".owdo..s",
        "oLbbbdos",
        "oLbbbbds",
        "ooooooos",
    ),
    palette=palette_of(shade_keys(BONE_RAMP, "odwL"), shade_keys(BREW_RAMP, "_dbL"),
                       {"r": GLOW, "y": GOLD_RAMP.mid, "s": BARK_RAMP.mid}),
)
# Demon: swept horns and spread bat wings.
DEMON_SPRITE = Sprite(
    rows=(
        "oo....oo",
        ".oooooo.",
        "woLiidow",
        "wwyiiyww",
        "wwoLdoww",
        ".oiiiido",
        "..i..d..",
        ".oo..oo.",
    ),
    palette=palette_of(shade_keys(BLOOD_RAMP, "odiL"), {"y": GOLD_RAMP.light, "w": SLATE_RAMP.dark}),
)

MONSTER_SPRITES: dict[str, Sprite] = {
    "green_slime": GREEN_SLIME_SPRITE,
    "blue_slime": BLUE_SLIME_SPRITE,
    "red_slime": RED_SLIME_SPRITE,
    "yellow_slime": YELLOW_SLIME_SPRITE,
    "chicken": CHICKEN_SPRITE,
    "cow": COW_SPRITE,
    "pig": PIG_SPRITE,
    "sheep": SHEEP_SPRITE,
    "wolf": WOLF_SPRITE,
    "owlbear": OWLBEAR_SPRITE,
    "spider": SPIDER_SPRITE,
    "flying_snake": FLYING_SNAKE_SPRITE,
    "sand_snake": SAND_SNAKE_SPRITE,
    "goblin": GOBLIN_SPRITE,
    "goblin_wolfrider": GOBLIN_WOLFRIDER_SPRITE,
    "orc": ORC_SPRITE,
    "ogre": OGRE_SPRITE,
    "cyclops": CYCLOPS_SPRITE,
    "imp": IMP_SPRITE,
    "highwayman": HIGHWAYMAN_SPRITE,
    "cultist_acolyte": CULTIST_ACOLYTE_SPRITE,
    "skeleton": SKELETON_SPRITE,
    "death_knight": DEATH_KNIGHT_SPRITE,
    "vampire": VAMPIRE_SPRITE,
    "hellhound": HELLHOUND_SPRITE,
    "cursed_tree": CURSED_TREE_SPRITE,
    "mushmush": MUSHMUSH_SPRITE,
    "desert_scorpion": DESERT_SCORPION_SPRITE,
    "sandwarden": SANDWARDEN_SPRITE,
    "king_slime": KING_SLIME_SPRITE,
    # --- 28 missing monsters from roster-gap.md ---
    # Giants
    "corrupted_ogre": reramp(OGRE_SPRITE, {OGRE_SKIN_RAMP: BREW_RAMP}),
    "efreet_sultan": reramp(CYCLOPS_SPRITE, {SKIN_RAMP: AMBER_RAMP}),
    "sonnengott": reramp(CYCLOPS_SPRITE, {SKIN_RAMP: GOLD_RAMP}),
    # Beasts
    "corrupted_owlbear": reramp(OWLBEAR_SPRITE, {BARK_RAMP: BREW_RAMP}),
    "rat": reramp(WOLF_SPRITE, {STONE_RAMP: SLATE_RAMP}),
    "fennec": reramp(WOLF_SPRITE, {STONE_RAMP: KHAKI_RAMP}),
    "grimlet": reramp(WOLF_SPRITE, {STONE_RAMP: SLATE_RAMP, AMBER_RAMP: EMBER_RAMP}),
    "bandit_lizard": reramp(WOLF_SPRITE, {STONE_RAMP: LEAF_RAMP, AMBER_RAMP: BLOOD_RAMP}),
    # Undead
    "full_moon_vampire": reramp(VAMPIRE_SPRITE, {SLATE_RAMP: STONE_RAMP, BLOOD_RAMP: BONE_RAMP}),
    "lich": LICH_SPRITE,
    # Humanoids
    "demon": DEMON_SPRITE,
    "goblin_guard": reramp(GOBLIN_SPRITE, {LEATHER_RAMP: STEEL_RAMP}),
    "goblin_priestess": reramp(GOBLIN_SPRITE, {LEATHER_RAMP: BREW_RAMP}),
    "cultist_emperor": reramp(CULTIST_ACOLYTE_SPRITE, {BREW_RAMP: BLOOD_RAMP}),
    "cultist_alchemist": reramp(CULTIST_ACOLYTE_SPRITE, {BREW_RAMP: LEAF_RAMP}),
    "sea_marauder": reramp(HIGHWAYMAN_SPRITE, {SLATE_RAMP: WATER_RAMP}),
    "sandwhisper_empress": reramp(SANDWARDEN_SPRITE, {KHAKI_RAMP: GOLD_RAMP}),
    # Serpents
    "duskworm": reramp(SAND_SNAKE_SPRITE, {AMBER_RAMP: BREW_RAMP}),
    # Insects
    "dusk_beetle": reramp(SPIDER_SPRITE, {SLATE_RAMP: BREW_RAMP}),
    "solar_desert_scorpion": reramp(DESERT_SCORPION_SPRITE, {AMBER_RAMP: GOLD_RAMP, BLOOD_RAMP: EMBER_RAMP}),
    # Plants
    "dryad": reramp(CURSED_TREE_SPRITE, {SLATE_RAMP: LEAF_RAMP}),
    "rosenblood": reramp(CURSED_TREE_SPRITE, {SLATE_RAMP: BLOOD_RAMP}),
    # Elementals
    "flameche": reramp(GREEN_SLIME_SPRITE, {SLIME_RAMP: AMBER_RAMP}),
    # Flyers (bat family)
    "bat": _BAT_BASE,
    "echoless_bat": reramp(_BAT_BASE, {BARK_RAMP: SLATE_RAMP}),
    "pixie": reramp(_BAT_BASE, {BARK_RAMP: PINK_RAMP, SLATE_RAMP: BONE_RAMP}),
    # Dragons
    "red_dragon": _DRAGON_BASE,
    "baby_red_dragon": reramp(_DRAGON_BASE, {BLOOD_RAMP: AMBER_RAMP}),
}
NPC_SPRITES: dict[str, Sprite] = {
    "archaeologist": ARCHAEOLOGIST_SPRITE,
    "tailor": TAILOR_SPRITE,
    "cultist_wizard": CULTIST_WIZARD_SPRITE,
    "rune_vendor": RUNE_VENDOR_SPRITE,
    "sandwhisper_trader": SANDWHISPER_TRADER_SPRITE,
    "tasks_trader": TASKS_TRADER_SPRITE,
    # --- 7 missing NPCs from roster-gap.md ---
    # Trader: green explorer (archaeologist base)
    "beastmaster": reramp(ARCHAEOLOGIST_SPRITE, {KHAKI_RAMP: LEAF_RAMP}),
    # Trader: violet hat, pink robe (cultist_wizard base)
    "sorceress": reramp(CULTIST_WIZARD_SPRITE, {SLATE_RAMP: BREW_RAMP, BREW_RAMP: PINK_RAMP}),
    # Merchants (tailor base, apron colour by trade)
    "fish_merchant": reramp(TAILOR_SPRITE, {BREW_RAMP: WATER_RAMP}),
    "gemstone_merchant": reramp(TAILOR_SPRITE, {BREW_RAMP: GOLD_RAMP}),
    "herbal_merchant": reramp(TAILOR_SPRITE, {BREW_RAMP: LEAF_RAMP}),
    "nomadic_merchant": reramp(TAILOR_SPRITE, {BREW_RAMP: KHAKI_RAMP}),
    "timber_merchant": reramp(TAILOR_SPRITE, {BREW_RAMP: BARK_RAMP}),
}
STRUCTURE_SPRITES: dict[str, Sprite] = {
    "bank": BANK_SPRITE,
    "door": DOOR_SPRITE,
    "grand_exchange": GRAND_EXCHANGE_SPRITE,
    "workshop": WORKSHOP_SPRITE,
    "tasks_master": TASKS_MASTER_SPRITE,
}
RESOURCE_SPRITES: dict[str, Sprite] = {
    "resource_woodcutting": WOODCUTTING_SPRITE,
    "resource_mining": MINING_SPRITE,
    "resource_fishing": FISHING_SPRITE,
    "resource_alchemy": ALCHEMY_SPRITE,
}

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
    "blue_slime": BLUE_SLIME_SPRITE,
    "red_slime": RED_SLIME_SPRITE,
    "yellow_slime": YELLOW_SLIME_SPRITE,
    "chicken": CHICKEN_SPRITE,
    "cow": COW_SPRITE,
    "pig": PIG_SPRITE,
    "sheep": SHEEP_SPRITE,
    "wolf": WOLF_SPRITE,
    "owlbear": OWLBEAR_SPRITE,
    "spider": SPIDER_SPRITE,
    "flying_snake": FLYING_SNAKE_SPRITE,
    "sand_snake": SAND_SNAKE_SPRITE,
    "bank": BANK_SPRITE,
    "door": DOOR_SPRITE,
    "resource_woodcutting": WOODCUTTING_SPRITE,
    "archaeologist": ARCHAEOLOGIST_SPRITE,
    "grand_exchange": GRAND_EXCHANGE_SPRITE,
    "workshop": WORKSHOP_SPRITE,
    "tasks_master": TASKS_MASTER_SPRITE,
    "resource_mining": MINING_SPRITE,
    "resource_fishing": FISHING_SPRITE,
    "resource_alchemy": ALCHEMY_SPRITE,
    "tailor": TAILOR_SPRITE,
    "cultist_wizard": CULTIST_WIZARD_SPRITE,
    "rune_vendor": RUNE_VENDOR_SPRITE,
    "sandwhisper_trader": SANDWHISPER_TRADER_SPRITE,
    "tasks_trader": TASKS_TRADER_SPRITE,
    "goblin": GOBLIN_SPRITE,
    "goblin_wolfrider": GOBLIN_WOLFRIDER_SPRITE,
    "orc": ORC_SPRITE,
    "ogre": OGRE_SPRITE,
    "cyclops": CYCLOPS_SPRITE,
    "imp": IMP_SPRITE,
    "highwayman": HIGHWAYMAN_SPRITE,
    "cultist_acolyte": CULTIST_ACOLYTE_SPRITE,
    "skeleton": SKELETON_SPRITE,
    "death_knight": DEATH_KNIGHT_SPRITE,
    "vampire": VAMPIRE_SPRITE,
    "hellhound": HELLHOUND_SPRITE,
    "cursed_tree": CURSED_TREE_SPRITE,
    "mushmush": MUSHMUSH_SPRITE,
    "desert_scorpion": DESERT_SCORPION_SPRITE,
    "sandwarden": SANDWARDEN_SPRITE,
    "king_slime": KING_SLIME_SPRITE,
}

for _category_sprites in CURATED_BY_CATEGORY.values():
    for _code, _sprite in _category_sprites.items():
        validate_sprite(_code, _sprite)
validate_sprite("player", PLAYER_SPRITE)
validate_sprite("blank", BLANK_SPRITE)
