# TUI Half-Block Sprite Tileset Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single-glyph NetHack map with an 8×8 half-block sprite tileset and enlarge the map via a 3×3 grid layout.

**Architecture:** Each tile renders as an 8×8 pixel sprite drawn with the `▀` (upper half block) char — fg = top pixel, bg = bottom pixel — so one tile = 8 chars wide × 4 char-rows tall. Two layers per tile: a terrain fill color (floor/void) and an entity sprite composited over it (transparent pixels show terrain). Sprites are curated for iconic entities; unknown codes get a deterministic, checksum-marked tinted silhouette. Static render-on-snapshot (no animation clock).

**Tech Stack:** Python 3.13, `uv`, Textual (`Static` widget), Rich (`Text`), pytest (`-W error`, 100% coverage).

**Spec:** `docs/superpowers/specs/2026-06-13-tui-map-sprites-design.md`

**Conventions (from CLAUDE.md):** Prefix every command with `uv run`. One behavioral class per file (pure-data/enum/value-object modules are exempt). Imports at top of file only — no inline, no `...`, no `TYPE_CHECKING`. Never catch `Exception`. Use only API data or fail. Tests: 0 errors, 0 warnings, 0 skipped, 100% coverage; put tests in `tests/`.

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `src/artifactsmmo_cli/tui/sprites.py` | Pure data: `Sprite` value object, `SpriteCategory` enum, validator, curated sprite tables, fallback template + palettes | Create |
| `src/artifactsmmo_cli/tui/half_block.py` | `HalfBlockCompositor` — sprite → 4 half-block `Text` rows, memoized | Create |
| `src/artifactsmmo_cli/tui/sprite_registry.py` | `SpriteRegistry` — curated lookup + checksum-marked fallback | Create |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | `MapPane` — two-layer tile renderer + HUD; index stores `(category, code)` | Modify (rewrite render) |
| `src/artifactsmmo_cli/tui/app.py` | 3×3 grid layout | Modify (CSS) |
| `src/artifactsmmo_cli/tui/glyphs.py` | Keep color constants; remove now-dead letter helpers if unused | Modify (cleanup) |
| `tests/test_tui/test_sprites.py` | Sprite integrity + validator | Create |
| `tests/test_tui/test_half_block.py` | Compositor output + memoization | Create |
| `tests/test_tui/test_sprite_registry.py` | Curated + fallback determinism | Create |
| `tests/test_tui/test_map_pane.py` | Tile-model viewport, HUD, terrain, sizing | Rewrite |
| `tests/test_tui/test_app.py` | 3×3 layout panes | Modify |
| `tests/test_tui/test_glyphs.py` | Drop tests for removed helpers (only if removed) | Modify (conditional) |

---

## Task 1: Sprite value object, enum, validator, curated data

**Files:**
- Create: `src/artifactsmmo_cli/tui/sprites.py`
- Test: `tests/test_tui/test_sprites.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_sprites.py`:

```python
"""Sprite tileset data integrity + validator."""

import pytest

from artifactsmmo_cli.tui.sprites import (
    ALL_CURATED_SPRITES,
    BLANK_SPRITE,
    PLAYER_SPRITE,
    SPRITE_SIZE,
    TRANSPARENT,
    Sprite,
    SpriteCategory,
    validate_sprite,
)


def test_every_curated_sprite_is_8x8():
    for name, sprite in ALL_CURATED_SPRITES.items():
        assert len(sprite.rows) == SPRITE_SIZE, name
        assert all(len(row) == SPRITE_SIZE for row in sprite.rows), name


def test_every_used_palette_key_is_defined():
    for name, sprite in ALL_CURATED_SPRITES.items():
        for row in sprite.rows:
            for ch in row:
                if ch != TRANSPARENT:
                    assert ch in sprite.palette, f"{name}: {ch!r} undefined"


def test_blank_sprite_is_all_transparent():
    assert all(set(row) == {TRANSPARENT} for row in BLANK_SPRITE.rows)
    assert BLANK_SPRITE.palette == {}


def test_player_sprite_is_curated():
    assert PLAYER_SPRITE in ALL_CURATED_SPRITES.values()


def test_validate_rejects_wrong_row_count():
    bad = Sprite(rows=("#" * 8,) * 7, palette={"#": "white"})
    with pytest.raises(ValueError, match="rows"):
        validate_sprite("bad", bad)


def test_validate_rejects_wrong_col_count():
    bad = Sprite(rows=("#" * 7,) * 8, palette={"#": "white"})
    with pytest.raises(ValueError, match="cols"):
        validate_sprite("bad", bad)


def test_validate_rejects_undefined_palette_key():
    bad = Sprite(rows=("Z" + "." * 7,) + ("." * 8,) * 7, palette={})
    with pytest.raises(ValueError, match="palette"):
        validate_sprite("bad", bad)


def test_category_members():
    assert {c.value for c in SpriteCategory} == {
        "player", "monster", "npc", "structure", "resource",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites.py -v`
Expected: FAIL with `ModuleNotFoundError: artifactsmmo_cli.tui.sprites`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/tui/sprites.py`:

```python
"""8x8 sprite tileset data for the TUI map. Pure data + value object.

Each sprite is 8 rows x 8 cols of palette-key chars. '.' (TRANSPARENT) shows
the terrain color behind it. Behavioral rendering lives in half_block.py;
code->sprite lookup and the procedural fallback live in sprite_registry.py.
"""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.tui.glyphs import (
    DOOR_COLOR,
    MONSTER_COLOR,
    NPC_COLOR,
    PLAYER_COLOR,
    STRUCTURE_COLOR,
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
        "..####..",
        ".######.",
        ".#e##e#.",
        ".######.",
        "..####..",
        ".#.##.#.",
        "..#..#..",
        "..#..#..",
    ),
    palette={"#": PLAYER_COLOR, "e": "black"},
)

GREEN_SLIME_SPRITE = Sprite(
    rows=(
        "........",
        "..####..",
        ".######.",
        "########",
        "#e####e#",
        "########",
        ".######.",
        "........",
    ),
    palette={"#": "green", "e": "black"},
)

BANK_SPRITE = Sprite(
    rows=(
        "########",
        "#dddddd#",
        "#d####d#",
        "#d####d#",
        "#d####d#",
        "#d####d#",
        "#dddddd#",
        "########",
    ),
    palette={"#": STRUCTURE_COLOR, "d": "yellow"},
)

DOOR_SPRITE = Sprite(
    rows=(
        "..####..",
        ".#dddd#.",
        ".#dddd#.",
        ".#dddd#.",
        ".#dddd#.",
        ".#dddd#.",
        ".#dd#d#.",
        ".######.",
    ),
    palette={"#": STRUCTURE_COLOR, "d": DOOR_COLOR},
)

WOODCUTTING_SPRITE = Sprite(
    rows=(
        "...##...",
        "..####..",
        ".######.",
        "..####..",
        "...##...",
        "...tt...",
        "...tt...",
        "...tt...",
    ),
    palette={"#": "green", "t": "yellow"},
)

ARCHAEOLOGIST_SPRITE = Sprite(
    rows=(
        "..####..",
        ".######.",
        ".#e##e#.",
        ".######.",
        "..####..",
        ".#####..",
        "..#.#...",
        "..#.#...",
    ),
    palette={"#": NPC_COLOR, "e": "black"},
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
```

Note: this imports `MONSTER_COLOR`, `NPC_COLOR`, `STRUCTURE_COLOR`, `DOOR_COLOR`, `PLAYER_COLOR` from `glyphs.py` — all already defined there (`glyphs.py:10-15`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites.py -v`
Expected: PASS (all 8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites.py
git commit -m "feat(tui): Sprite value object + curated 8x8 tileset data"
```

---

## Task 2: HalfBlockCompositor

**Files:**
- Create: `src/artifactsmmo_cli/tui/half_block.py`
- Test: `tests/test_tui/test_half_block.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_half_block.py`:

```python
"""HalfBlockCompositor: sprite -> 4 half-block Text rows, memoized."""

from artifactsmmo_cli.tui.half_block import HALF_BLOCK, HalfBlockCompositor
from artifactsmmo_cli.tui.sprites import BLANK_SPRITE, GREEN_SLIME_SPRITE


def test_compose_returns_four_rows_of_eight():
    comp = HalfBlockCompositor()
    rows = comp.compose(BLANK_SPRITE, "grey50")
    assert len(rows) == 4
    assert all(row.plain == HALF_BLOCK * 8 for row in rows)


def test_transparent_pixels_show_terrain_both_fg_and_bg():
    comp = HalfBlockCompositor()
    rows = comp.compose(BLANK_SPRITE, "grey50")
    # Blank sprite: every pixel transparent -> fg and bg are the terrain color.
    for row in rows:
        assert all(span.style == "grey50 on grey50" for span in row.spans)


def test_opaque_pixel_uses_palette_color():
    comp = HalfBlockCompositor()
    rows = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    styles = [span.style for row in rows for span in row.spans]
    # The slime body is green; at least one half-block carries a green pixel.
    assert any("green" in style for style in styles)


def test_memoized_same_args_returns_identical_object():
    comp = HalfBlockCompositor()
    a = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    b = comp.compose(GREEN_SLIME_SPRITE, "grey50")
    assert a is b


def test_different_terrain_color_is_a_distinct_entry():
    comp = HalfBlockCompositor()
    a = comp.compose(BLANK_SPRITE, "grey50")
    b = comp.compose(BLANK_SPRITE, "grey15")
    assert a is not b
    assert a[0].spans[0].style == "grey50 on grey50"
    assert b[0].spans[0].style == "grey15 on grey15"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_half_block.py -v`
Expected: FAIL with `ModuleNotFoundError: artifactsmmo_cli.tui.half_block`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/tui/half_block.py`:

```python
"""Composites 8x8 sprites into half-block character rows for the map pane.

Each char cell is two vertical pixels: '▀' with fg = top pixel, bg = bottom
pixel. An 8px-tall sprite becomes 4 char-rows. Transparent pixels resolve to
the terrain color so sprites composite over terrain. Results are memoized by
(rows, palette, terrain_color) since the art is static.
"""

from rich.text import Text

from artifactsmmo_cli.tui.sprites import SPRITE_SIZE, TRANSPARENT, Sprite

HALF_BLOCK = "▀"  # ▀ UPPER HALF BLOCK


class HalfBlockCompositor:
    """Turns sprites into cached tuples of 4 Rich Text rows."""

    def __init__(self) -> None:
        self._cache: dict[tuple, tuple[Text, Text, Text, Text]] = {}

    def compose(self, sprite: Sprite, terrain_color: str) -> tuple[Text, Text, Text, Text]:
        key = (sprite.rows, tuple(sorted(sprite.palette.items())), terrain_color)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        built = self._build(sprite, terrain_color)
        self._cache[key] = built
        return built

    @staticmethod
    def _pixel_color(sprite: Sprite, row: int, col: int, terrain_color: str) -> str:
        ch = sprite.rows[row][col]
        if ch == TRANSPARENT:
            return terrain_color
        return sprite.palette[ch]

    def _build(self, sprite: Sprite, terrain_color: str) -> tuple[Text, Text, Text, Text]:
        out: list[Text] = []
        for top in range(0, SPRITE_SIZE, 2):
            line = Text(no_wrap=True, overflow="crop")
            for col in range(SPRITE_SIZE):
                fg = self._pixel_color(sprite, top, col, terrain_color)
                bg = self._pixel_color(sprite, top + 1, col, terrain_color)
                line.append(HALF_BLOCK, style=f"{fg} on {bg}")
            out.append(line)
        return (out[0], out[1], out[2], out[3])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_half_block.py -v`
Expected: PASS (all 5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/half_block.py tests/test_tui/test_half_block.py
git commit -m "feat(tui): HalfBlockCompositor renders sprites as half-block rows"
```

---

## Task 3: SpriteRegistry (curated lookup + fallback)

**Files:**
- Create: `src/artifactsmmo_cli/tui/sprite_registry.py`
- Test: `tests/test_tui/test_sprite_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_sprite_registry.py`:

```python
"""SpriteRegistry: curated hits + deterministic checksum-marked fallback."""

from artifactsmmo_cli.tui.sprite_registry import SpriteRegistry
from artifactsmmo_cli.tui.sprites import (
    GREEN_SLIME_SPRITE,
    MARK_COLOR,
    MARK_KEY,
    PLAYER_SPRITE,
    SpriteCategory,
    validate_sprite,
)


def test_player_category_returns_player_sprite():
    reg = SpriteRegistry()
    assert reg.sprite_for("hero", SpriteCategory.PLAYER) is PLAYER_SPRITE


def test_curated_code_returns_curated_sprite():
    reg = SpriteRegistry()
    assert reg.sprite_for("green_slime", SpriteCategory.MONSTER) is GREEN_SLIME_SPRITE


def test_unknown_code_returns_valid_fallback_sprite():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("orc", SpriteCategory.MONSTER)
    validate_sprite("orc-fallback", sprite)  # raises if malformed


def test_fallback_is_cached_identical():
    reg = SpriteRegistry()
    a = reg.sprite_for("orc", SpriteCategory.MONSTER)
    b = reg.sprite_for("orc", SpriteCategory.MONSTER)
    assert a is b


def test_fallback_marking_differs_by_code():
    reg = SpriteRegistry()
    a = reg.sprite_for("orc", SpriteCategory.MONSTER)       # checksum 324
    b = reg.sprite_for("wolf", SpriteCategory.MONSTER)      # checksum 440
    assert a.rows != b.rows


def test_fallback_uses_category_color_and_mark_palette():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("orc", SpriteCategory.MONSTER)
    assert sprite.palette[MARK_KEY] == MARK_COLOR
    assert "#" in sprite.palette


def test_empty_code_fallback_has_no_marks():
    reg = SpriteRegistry()
    sprite = reg.sprite_for("", SpriteCategory.MONSTER)  # checksum 0 -> no marks
    assert all(MARK_KEY not in row for row in sprite.rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprite_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: artifactsmmo_cli.tui.sprite_registry`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/tui/sprite_registry.py`:

```python
"""Resolves entity codes to sprites: curated lookup, else a tinted fallback.

The fallback is a category-colored blob with a deterministic 2-tone marking
derived from a stable checksum of the code (sum of UTF-8 bytes — NOT Python's
salted hash(), which varies across processes). Mirrors glyphs.py's first-letter
fallback in spirit. Curated misses are expected behavior, not errors.
"""

from artifactsmmo_cli.tui.sprites import (
    CATEGORY_FALLBACK_COLOR,
    CURATED_BY_CATEGORY,
    FALLBACK_SILHOUETTE,
    MARK_COLOR,
    MARK_KEY,
    MARK_POSITIONS,
    PLAYER_SPRITE,
    Sprite,
    SpriteCategory,
)


class SpriteRegistry:
    """Maps (code, category) to a Sprite; caches procedural fallbacks."""

    def __init__(self) -> None:
        self._fallback_cache: dict[tuple[SpriteCategory, str], Sprite] = {}

    def sprite_for(self, code: str, category: SpriteCategory) -> Sprite:
        if category is SpriteCategory.PLAYER:
            return PLAYER_SPRITE
        curated = CURATED_BY_CATEGORY[category].get(code)
        if curated is not None:
            return curated
        return self._fallback(code, category)

    def _fallback(self, code: str, category: SpriteCategory) -> Sprite:
        key = (category, code)
        cached = self._fallback_cache.get(key)
        if cached is not None:
            return cached
        sprite = self._build_fallback(code, category)
        self._fallback_cache[key] = sprite
        return sprite

    @staticmethod
    def _build_fallback(code: str, category: SpriteCategory) -> Sprite:
        checksum = sum(code.encode("utf-8"))
        grid = [list(row) for row in FALLBACK_SILHOUETTE]
        for i, (r, c) in enumerate(MARK_POSITIONS):
            if (checksum >> i) & 1:
                grid[r][c] = MARK_KEY
        rows = tuple("".join(row) for row in grid)
        palette = {"#": CATEGORY_FALLBACK_COLOR[category], MARK_KEY: MARK_COLOR}
        return Sprite(rows=rows, palette=palette)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprite_registry.py -v`
Expected: PASS (all 7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprite_registry.py tests/test_tui/test_sprite_registry.py
git commit -m "feat(tui): SpriteRegistry with checksum-marked procedural fallback"
```

---

## Task 4: MapPane two-layer tile renderer + HUD

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py` (rewrite index + render)
- Rewrite: `tests/test_tui/test_map_pane.py`

The current tests assert single-glyph behavior and the current `_build_tile_index` returns `(glyph, color)` tuples. Both change under the tile model, so the test file is rewritten in the same task (no deferral).

- [ ] **Step 1: Rewrite the test file**

Replace the entire contents of `tests/test_tui/test_map_pane.py`:

```python
"""MapPane tile-model viewport tests (mostly app-free; sizing uses run_test)."""

from textual.app import App, ComposeResult
from textual.geometry import Size

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import UNMAPPED_COLOR, WALKABLE_COLOR
from artifactsmmo_cli.tui.sprites import SpriteCategory
from artifactsmmo_cli.tui.widgets.map_pane import (
    FALLBACK_H,
    FALLBACK_W,
    TILE_H,
    TILE_W,
    MapPane,
)


def _gd_typed() -> GameData:
    gd = GameData()
    gd._monster_locations = {"green_slime": [(2, 0)], "chicken": [(0, 2)]}
    gd._npc_locations = {"archaeologist": (-1, 0)}
    gd._bank_location = (4, 1)
    gd._taskmaster_location = (1, 2)
    gd._workshop_locations = {"mining": (3, 3)}
    gd._grand_exchange_location = (-2, -2)
    gd._transition_tiles = {(0, -3)}
    gd._resource_locations = {"ash_tree": [(2, 2)]}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _snap(x: int, y: int) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=0, timestamp="2026-05-18T00:00:00Z", character="hero",
        x=x, y=y, level=1, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        selected_goal="X", action="Y", outcome="ok",
    )


def _styles(text) -> list[str]:
    return [span.style for span in text.spans]


class TestBuildTileIndex:
    def test_index_stores_category_and_code(self):
        idx = MapPane._build_tile_index(_gd_typed())
        assert idx[(2, 0)] == (SpriteCategory.MONSTER, "green_slime")
        assert idx[(0, 2)] == (SpriteCategory.MONSTER, "chicken")
        assert idx[(-1, 0)] == (SpriteCategory.NPC, "archaeologist")
        assert idx[(4, 1)] == (SpriteCategory.STRUCTURE, "bank")
        assert idx[(-2, -2)] == (SpriteCategory.STRUCTURE, "grand_exchange")
        assert idx[(3, 3)] == (SpriteCategory.STRUCTURE, "workshop")
        assert idx[(1, 2)] == (SpriteCategory.STRUCTURE, "tasks_master")
        assert idx[(0, -3)] == (SpriteCategory.STRUCTURE, "door")
        assert idx[(2, 2)] == (SpriteCategory.RESOURCE, "resource_woodcutting")


class TestViewportGeometry:
    def test_row_count_and_width_match_tiles(self):
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        lines = out.plain.split("\n")
        tiles_h = (41 - 1) // TILE_H
        tiles_w = 80 // TILE_W
        assert len(lines) == 1 + tiles_h * TILE_H        # 1 HUD + tile rows
        assert all(len(row) == tiles_w * TILE_W for row in lines[1:])

    def test_height_too_small_is_hud_only(self):
        pane = MapPane(_gd_typed())
        lines = pane._render_viewport(_snap(0, 0), 80, 1).plain.split("\n")
        assert len(lines) == 1                            # HUD only, no tile rows

    def test_render_is_no_wrap_and_cropped(self):
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert out.no_wrap is True
        assert out.overflow == "crop"


class TestLayers:
    def test_player_sprite_at_center(self):
        # PLAYER_COLOR (bright_yellow) appears only from the player sprite.
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any("bright_yellow" in s for s in _styles(out))

    def test_monster_sprite_in_view(self):
        # green_slime at (2,0) is in view from (0,0) -> green pixels present.
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any("green" in s for s in _styles(out))

    def test_unmapped_tiles_use_void_color(self):
        gd = GameData()  # nothing known, no content
        pane = MapPane(gd)
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any(UNMAPPED_COLOR in s for s in _styles(out))

    def test_known_empty_tile_uses_floor_color(self):
        gd = _gd_typed()
        gd._known_tiles = {(1, 0)}  # in view from (0,0), no content there
        pane = MapPane(gd)
        out = pane._render_viewport(_snap(0, 0), 80, 41)
        assert any(WALKABLE_COLOR in s for s in _styles(out))


class TestHud:
    def test_hud_shows_coords(self):
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(3, -4), 80, 41).plain.split("\n")[0]
        assert "(3,-4)" in hud

    def test_hud_shows_content_under_player(self):
        # Player standing on the woodcutting resource at (2,2).
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(2, 2), 80, 41).plain.split("\n")[0]
        assert "resource_woodcutting" in hud

    def test_hud_no_content_on_empty_tile(self):
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(9, 9), 80, 41).plain.split("\n")[0]
        assert hud.strip() == "(9,9)"


class TestRenderEntry:
    def test_render_without_snapshot_shows_waiting(self):
        assert "Waiting" in MapPane(_gd_typed()).render().plain

    def test_render_falls_back_when_size_zero(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        assert pane.size == Size(0, 0)
        lines = pane.render().plain.split("\n")
        tiles_h = (FALLBACK_H - 1) // TILE_H
        tiles_w = FALLBACK_W // TILE_W
        assert len(lines) == 1 + tiles_h * TILE_H
        assert all(len(row) == tiles_w * TILE_W for row in lines[1:])

    async def test_render_uses_pane_size(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))

        class _Host(App):
            CSS = "MapPane { width: 80; height: 41; }"

            def compose(self) -> ComposeResult:
                yield pane

        async with _Host().run_test(size=(100, 50)):
            assert pane.size == Size(80, 41)
            lines = pane.render().plain.split("\n")
        tiles_h = (41 - 1) // TILE_H
        assert len(lines) == 1 + tiles_h * TILE_H
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui/test_map_pane.py -v`
Expected: FAIL — `ImportError` for `TILE_W`/`FALLBACK_W`/etc. (renderer not yet rewritten)

- [ ] **Step 3: Rewrite `map_pane.py`**

Replace the entire contents of `src/artifactsmmo_cli/tui/widgets/map_pane.py`:

```python
"""Tile-map pane: each tile is an 8x8 half-block sprite, centered on the player."""

from typing import Any

from rich.text import Text
from textual.events import Resize
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.glyphs import UNMAPPED_COLOR, WALKABLE_COLOR
from artifactsmmo_cli.tui.half_block import HalfBlockCompositor
from artifactsmmo_cli.tui.sprite_registry import SpriteRegistry
from artifactsmmo_cli.tui.sprites import BLANK_SPRITE, PLAYER_SPRITE, Sprite, SpriteCategory

TILE_W = 8   # chars per tile column (8 pixels wide)
TILE_H = 4   # char-rows per tile (8 pixels tall, 2 px per char-row)
FALLBACK_W = 80
FALLBACK_H = 41

_SKILL_TO_RESOURCE_KEY = {
    "woodcutting": "resource_woodcutting",
    "mining": "resource_mining",
    "fishing": "resource_fishing",
    "alchemy": "resource_alchemy",
}
TileContent = tuple[SpriteCategory, str]


class MapPane(Static):
    """Renders an 8x8-sprite tile grid that fills the pane, centered on player."""

    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def __init__(self, game_data: GameData, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._game_data = game_data
        self._tile_index = self._build_tile_index(game_data)
        self._known_tiles = game_data.known_tiles
        self._registry = SpriteRegistry()
        self._compositor = HalfBlockCompositor()

    @staticmethod
    def _build_tile_index(gd: GameData) -> dict[tuple[int, int], TileContent]:
        """Map (x,y) -> (category, code). Player resolved at render time."""
        index: dict[tuple[int, int], TileContent] = {}
        for code, locs in gd.all_resource_locations.items():
            skill = gd.resource_skills.get(code)
            key = _SKILL_TO_RESOURCE_KEY.get(skill[0], "resource_mining") if skill else "resource_mining"
            for xy in locs:
                index[xy] = (SpriteCategory.RESOURCE, key)
        for _skill, loc in gd.workshop_locations.items():
            if loc is not None:
                index[loc] = (SpriteCategory.STRUCTURE, "workshop")
        for npc_code, loc in gd.npc_locations.items():
            index[loc] = (SpriteCategory.NPC, npc_code)
        bank_loc = gd.bank_location_or_none
        if bank_loc is not None:
            index[bank_loc] = (SpriteCategory.STRUCTURE, "bank")
        ge_loc = gd.grand_exchange_location()
        if ge_loc is not None:
            index[ge_loc] = (SpriteCategory.STRUCTURE, "grand_exchange")
        taskmaster_loc = gd.taskmaster_location_or_none
        if taskmaster_loc is not None:
            index[taskmaster_loc] = (SpriteCategory.STRUCTURE, "tasks_master")
        for code, locs in gd.all_monster_locations.items():
            for xy in locs:
                index[xy] = (SpriteCategory.MONSTER, code)
        for xy in gd.transition_tiles:
            index[xy] = (SpriteCategory.STRUCTURE, "door")
        return index

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.snapshot = snap

    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or FALLBACK_W
        height = self.size.height or FALLBACK_H
        return self._render_viewport(snap, width, height)

    def on_resize(self, event: Resize) -> None:
        self.refresh()

    def _hud_line(self, snap: CycleSnapshot) -> str:
        content = self._tile_index.get((snap.x, snap.y))
        coords = f"({snap.x},{snap.y})"
        if content is None:
            return coords
        return f"{coords} · {content[1]}"

    def _tile_sprite_and_terrain(self, wx: int, wy: int, is_player: bool) -> tuple[Sprite, str]:
        if is_player:
            return PLAYER_SPRITE, WALKABLE_COLOR
        content = self._tile_index.get((wx, wy))
        if content is None:
            terrain = WALKABLE_COLOR if (wx, wy) in self._known_tiles else UNMAPPED_COLOR
            return BLANK_SPRITE, terrain
        category, code = content
        return self._registry.sprite_for(code, category), WALKABLE_COLOR

    def _render_viewport(self, snap: CycleSnapshot, width: int, height: int) -> Text:
        tiles_w = width // TILE_W
        tiles_h = (height - 1) // TILE_H
        half_w = tiles_w // 2
        half_h = tiles_h // 2
        cx, cy = snap.x, snap.y
        text = Text(no_wrap=True, overflow="crop")
        text.append(self._hud_line(snap), style="dim")
        for trow in range(tiles_h):
            text.append("\n")
            sublines = [Text(no_wrap=True, overflow="crop") for _ in range(TILE_H)]
            for tcol in range(tiles_w):
                wx = cx + tcol - half_w
                wy = cy + trow - half_h
                is_player = tcol == half_w and trow == half_h
                sprite, terrain = self._tile_sprite_and_terrain(wx, wy, is_player)
                rows4 = self._compositor.compose(sprite, terrain)
                for i in range(TILE_H):
                    sublines[i].append_text(rows4[i])
            for i in range(TILE_H):
                if i > 0:
                    text.append("\n")
                text.append_text(sublines[i])
        return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui/test_map_pane.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): MapPane renders 8x8 half-block sprite tiles + HUD"
```

---

## Task 5: 3×3 grid layout

**Files:**
- Modify: `src/artifactsmmo_cli/tui/app.py:22-65` (CSS block)
- Modify: `tests/test_tui/test_app.py`

Layout: status=cell 1, inventory=cell 4, map=cells 2,3,5,6 (cols 2-3 × rows 1-2), log=cells 7,8,9 (full-width bottom row, ~5 lines).

- [ ] **Step 1: Inspect the existing app test**

Run: `uv run pytest tests/test_tui/test_app.py -v` and read `tests/test_tui/test_app.py`.
Expected: currently PASS. Note which assertions reference layout/pane sizes so Step 4 can adjust them.

- [ ] **Step 2: Add the failing layout test**

Append to `tests/test_tui/test_app.py` (imports `WatchApp`, `GameData`, `MapPane`, `InventoryPane`, `Size` as the file already does — add any missing import at the top):

```python
class TestThreeByThreeLayout:
    async def test_map_spans_wide_right_block_and_log_is_full_width(self):
        app = WatchApp("hero", GameData())
        async with app.run_test(size=(120, 45)) as pilot:
            map_pane = app.query_one("#map", MapPane)
            inv_pane = app.query_one("#inv")
            log_pane = app.query_one("#log")
            # Map occupies the wide right block: wider than the left column inv.
            assert map_pane.size.width > inv_pane.size.width
            # Map spans both top rows: taller than the single-row inventory.
            assert map_pane.size.height > inv_pane.size.height
            # Log is the full-width bottom strip, ~5 lines.
            assert log_pane.size.width > map_pane.size.width
            assert log_pane.size.height <= 7
            await pilot.pause()
```

- [ ] **Step 3: Run the new test to verify it fails**

Run: `uv run pytest tests/test_tui/test_app.py::TestThreeByThreeLayout -v`
Expected: FAIL (current 2×2 layout: log is not full-width; map not taller than inv).

- [ ] **Step 4: Rewrite the CSS block**

In `src/artifactsmmo_cli/tui/app.py`, replace the `CSS = """ ... """` block (lines 22-65) with:

```python
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 3;
        grid-columns: 1fr 2fr 2fr;
        grid-rows: 1fr 1fr 7;
    }
    /* The bare `Screen` grid above also matches pushed modals; reset them to a
       full-screen vertical layout. App CSS outranks a screen's DEFAULT_CSS. */
    #character-modal, #log-modal, #plan-modal {
        layout: vertical;
    }
    #status {
        column: 1;
        row: 1;
        border: solid white;
        padding: 0 1;
    }
    #map {
        column: 2;
        row: 1;
        column-span: 2;
        row-span: 2;
        border: solid white;
        padding: 0 1;
        /* Fill the cell so the renderer sizes its grid from self.size. */
        width: 1fr;
        height: 1fr;
    }
    #inv {
        column: 1;
        row: 2;
        border: solid white;
        padding: 0 1;
    }
    #log {
        column: 1;
        row: 3;
        column-span: 3;
        border: solid white;
        padding: 0 1;
    }
    """
```

If Step 1 surfaced assertions that hard-code the old 2×2 geometry (e.g. specific pane widths), update them to the 3×3 expectations in this step.

- [ ] **Step 5: Run the full app test to verify it passes**

Run: `uv run pytest tests/test_tui/test_app.py -v`
Expected: PASS (existing tests + `TestThreeByThreeLayout`)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/app.py tests/test_tui/test_app.py
git commit -m "feat(tui): 3x3 grid — map spans right block, log full-width bottom"
```

---

## Task 6: Remove dead glyph helpers

**Files:**
- Modify: `src/artifactsmmo_cli/tui/glyphs.py`
- Modify: `tests/test_tui/test_glyphs.py` (only if helpers are removed)

The sprite path no longer uses the single-letter glyph helpers. Remove them only if nothing else imports them; the color constants stay (sprites.py imports them).

- [ ] **Step 1: Find remaining importers of the letter helpers**

Run:
```bash
uv run grep -rn "npc_glyph\|monster_glyph\|structure_glyph\|NPC_GLYPHS\|MONSTER_GLYPHS\|STRUCTURE_GLYPHS\|RESOURCE_GLYPHS\|GENERIC_STRUCTURE_GLYPH\|PLAYER_GLYPH\|DOOR_GLYPH\|WALKABLE_GLYPH\|UNMAPPED_GLYPH" src tests
```
Expected: hits only in `glyphs.py` itself and `tests/test_tui/test_glyphs.py` (map_pane no longer imports them after Task 4). If any **other** `src/` module imports them, STOP — they are not dead; skip this task and note it.

- [ ] **Step 2: Confirm the color constants are still used**

Run:
```bash
uv run grep -rn "WALKABLE_COLOR\|UNMAPPED_COLOR\|MONSTER_COLOR\|NPC_COLOR\|STRUCTURE_COLOR\|DOOR_COLOR\|PLAYER_COLOR" src
```
Expected: hits in `sprites.py` and `map_pane.py`. These constants MUST be kept.

- [ ] **Step 3: Remove the dead glyph functions, letter/glyph dicts, and glyph-char constants**

Edit `src/artifactsmmo_cli/tui/glyphs.py`: delete `npc_glyph`, `monster_glyph`, `structure_glyph`, the `NPC_GLYPHS`/`MONSTER_GLYPHS`/`STRUCTURE_GLYPHS`/`RESOURCE_GLYPHS` dicts, and the now-unused glyph-char constants (`PLAYER_GLYPH`, `DOOR_GLYPH`, `GENERIC_STRUCTURE_GLYPH`, `WALKABLE_GLYPH`, `UNMAPPED_GLYPH`). Keep all `*_COLOR` constants. Update the module docstring to describe a color-only palette module.

- [ ] **Step 4: Delete the dead-helper tests**

Edit `tests/test_tui/test_glyphs.py`: remove tests that exercise the deleted functions/dicts/glyph constants. Keep any test that asserts color-constant values. If the file becomes empty, delete it (`git rm`).

- [ ] **Step 5: Run the full TUI suite**

Run: `uv run pytest tests/test_tui/ -v`
Expected: PASS, 0 warnings, 0 skipped.

- [ ] **Step 6: Commit**

```bash
git add -A src/artifactsmmo_cli/tui/glyphs.py tests/test_tui/test_glyphs.py
git commit -m "refactor(tui): drop dead single-glyph helpers, keep color palette"
```

---

## Final verification

- [ ] **Full suite + coverage gate**

Run: `uv run pytest`
Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage (`--cov-fail-under=100` is configured in `pyproject.toml`).

- [ ] **Type check**

Run: `uv run mypy src/artifactsmmo_cli/tui`
Expected: no errors.

- [ ] **Manual smoke (optional)**

Launch watch mode against a character and confirm the map renders as sprite tiles, the map fills the wide right block, and the log sits as a ~5-line full-width strip. The `/run` skill can drive this.

---

## Remaining content (out of this plan — mechanical, engine is complete)

Adding the rest of the curated art is pure data entry in the established `Sprite` format (8 rows × 8 cols + palette), one entry per code in the matching `*_SPRITES` dict in `sprites.py`, plus its name in `ALL_CURATED_SPRITES` so the import-time validator covers it. Until added, every uncurated code renders via the checksum-marked fallback. Candidates: remaining monsters (`MONSTER_GLYPHS` keys from git history), NPCs, `grand_exchange`/`workshop`/`tasks_master` structures, and `resource_mining`/`resource_fishing`/`resource_alchemy`.

## Deferred enhancements (YAGNI v1, per spec)

- Idle animation on a Textual interval timer.
- Directional player facing.
- Biome terrain art (API exposes only floor/void/door today).
- Sprite-key help overlay; letter micro-font for the fallback.
