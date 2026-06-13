# TUI Map: Half-Block Sprite Tileset

**Date:** 2026-06-13
**Status:** Design — pending user review
**Topic:** Replace the single-glyph NetHack map with an 8×8 half-block sprite tileset, and enlarge the map pane via a 3×3 layout.

## Goal

Make the map view read as a real game tilemap instead of a field of single letters, while staying entirely within an ANSI/Textual TUI. Every tile becomes an 8×8 sprite rendered with Unicode half-block characters. Sprites are curated for iconic entities and procedurally generated (tinted silhouette + code letter) for the long tail.

## Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Primary goal | Detail / sprite fidelity |
| Sprite scope | Full tileset — every tile is a sprite (zoomed tactical view) |
| Sprite resolution | 8×8 px (NES-class): tile = 8 chars wide × 4 char-rows tall |
| Sprite source | Curated set + procedural tinted-silhouette fallback |
| Animation | Static v1 (render on cycle snapshot only; no clock) |
| Layout | 3×3 grid (see below) |

## Rendering technique: half-block pixels

Each terminal character cell renders **two vertical pixels** using `▀` (UPPER HALF BLOCK):
- foreground color = top pixel
- background color = bottom pixel

A char cell is ~2× taller than wide, so half its height ≈ its width → each pixel is roughly **square**. An 8-wide × 8-tall pixel sprite therefore occupies **8 chars wide × 4 char-rows tall** and reads as a square 8×8 sprite.

Transparent sprite pixels (`.`) show the **terrain fill color behind them**, so entity sprites composite over the terrain layer.

## Architecture

Two layers composited per tile:
1. **Terrain layer** — floor (known/explored), void (unmapped), door/transition. Sourced from `GameData.known_tiles` + `transition_tiles`, exactly as today.
2. **Entity layer** — monster / NPC / structure / resource / player sprite, composited over terrain. Sourced from the existing `(x,y) → content` index.

Data flow is unchanged: `GameData` startup index → `MapPane.update_snapshot(snap)` → `render()`. Only the per-cell renderer changes from "1 glyph" to "8×8 composited sprite".

### New files

**`src/artifactsmmo_cli/tui/sprites.py`** — pure-data module (qualifies for the CLAUDE.md data-module exemption: value object + data dicts, no behavioral class).
- `@dataclass(frozen=True) class Sprite`: `rows: tuple[str, ...]` (8 strings of 8 chars), `palette: dict[str, str]` (palette-key char → Rich color). `.` is the reserved transparent key.
- Module-level validation at import: every sprite is exactly 8×8 and every non-`.` char in `rows` exists in `palette`. On violation `raise ValueError` (programmer error; no defaulting, no `except`).
- Curated sprite dicts by category: `PLAYER_SPRITE`, `MONSTER_SPRITES`, `NPC_SPRITES`, `STRUCTURE_SPRITES`, `RESOURCE_SPRITES`, `TERRAIN_SPRITES` (floor / void / door).
- Category palettes for the procedural fallback (`MONSTER_PALETTE` red family, `NPC_PALETTE` cyan, etc.), reusing the color intent from today's `glyphs.py`.

**`src/artifactsmmo_cli/tui/sprite_registry.py`** — one behavioral class `SpriteRegistry`.
- `sprite_for(code: str, category: SpriteCategory) -> Sprite`: curated lookup; on miss, calls the procedural generator.
- Procedural generator: builds a generic category-tinted silhouette (fixed body shape per category) and overlays a **deterministic 2-tone marking pattern** derived from a stable checksum of `code` (sum of byte values — NOT Python's salted `hash()`), so distinct unknown codes stay visually distinct. Deterministic across processes. A legible letter at 8px needs a 3×5 micro-font and is cramped anyway; a marking pattern distinguishes codes with far less machinery. (Letter micro-font deferred — future enhancement alongside animation.)

**`src/artifactsmmo_cli/tui/half_block.py`** — one behavioral class `HalfBlockCompositor`.
- `compose(sprite: Sprite, terrain_color: str) -> tuple[Text, Text, Text, Text]`: pairs pixel rows (0,1)(2,3)(4,5)(6,7); for each of the 8 columns emits `▀` styled `fg(top) on bg(bottom)`; transparent pixel resolves to `terrain_color`. Returns the 4 char-rows as Rich `Text`.
- Memoized by `(id-of-sprite-or-code, terrain_color)` — static art is composited once and reused every frame (key perf optimization; ~12×9 tiles × redraw every cycle).

### Changed files

**`src/artifactsmmo_cli/tui/widgets/map_pane.py`** — rewrite `_render_viewport`.
- Visible tiles: `tiles_w = width // 8`, `tiles_h = map_h // 4`, player tile centered (`tiles_w//2`, `tiles_h//2`).
- For each tile-row: resolve each tile's terrain color + entity sprite, composite into 4 char-rows, concatenate the 4 rows across all columns in the tile-row, append the 4 assembled rows to the output `Text`.
- Player rendered as `PLAYER_SPRITE` over its tile's terrain.
- `_build_tile_index` stays (it still maps `(x,y) → content`), but stores the **content code + category** rather than a `(glyph, color)` pair, so the renderer can fetch a sprite.

**`src/artifactsmmo_cli/tui/glyphs.py`** — terrain/category colors are retained and imported by `sprites.py`. The per-entity single-letter dicts are repurposed as the procedural-fallback letter source (or moved into `sprites.py`); no dead code left behind.

**`src/artifactsmmo_cli/tui/app.py`** — layout rework (below).

## Layout: 3×3 grid

Cells numbered row-major 1–9:

```
┌───┬───────────┐
│ 1 │   2   3   │   status = cell 1
│ 4 │   5   6   │   inventory = cell 4
├───┴───────────┤   map = cells 2,3,5,6 (col 2-3 × row 1-2)
│   7   8   9   │   log = cells 7,8,9 (full-width bottom row, ~5 lines)
└───────────────┘
```

Textual CSS:
- `grid-size: 3 3;`
- `grid-columns: 1fr 2fr 2fr;` — left column narrow; map spans the two wide columns.
- `grid-rows: 1fr 1fr 7;` — top two rows flex; bottom row fixed ~7 cells (≈5 log lines + border).
- `#status`: `column: 1; row: 1;` (`column-span: 1; row-span: 1`).
- `#inv`: `column: 1; row: 2;`.
- `#map`: `column: 2; row: 1; column-span: 2; row-span: 2; width: 1fr; height: 1fr;` (must fill the cell so the renderer sizes from `self.size`).
- `#log`: `column: 1; row: 3; column-span: 3;`.

On a 120×45 terminal: map ≈ 96 chars wide × ≈ 36 char-rows → **~12 × 9 tiles** visible. Resizes gracefully (renderer already recomputes on `Resize`).

## HUD / legend

The letter legend (`A-Z npc  a-z monster ...`) is obsolete with sprites. Replace the legend line with one dim HUD line:

```
(x,y) · <name of content on the player's current tile>
```

e.g. `(3,-4) · copper rocks`. Name comes from `GameData` content for the player tile; if the tile has no content, show just the coords. A full sprite key is **deferred** to a future toggle overlay — sprites should read on their own.

## Error handling (per CLAUDE.md)

- Missing curated sprite → procedural fallback. This is intended behavior, not error masking.
- Malformed sprite data (wrong dimensions, undefined palette key) → `raise ValueError` at module import. No `except Exception`. No silent defaulting.
- Terrain/content still sourced from `GameData`; no defaulting layered over missing API data.
- No multi-level error handling; no inline imports; no `TYPE_CHECKING`.

## Testing (0 errors / 0 warnings / 0 skipped / 100% coverage)

In `tests/`, using the real test suite (no "simple" throwaway tests, no mocking the unit under test):

1. **`sprites.py` integrity** — parametrized over every curated sprite: asserts 8 rows × 8 chars and every non-`.` palette key is defined. Asserts the import-time validator raises on a malformed fixture sprite.
2. **`HalfBlockCompositor`** — known sprite + known terrain color → exact expected sequence of `▀` segments with fg/bg styles; transparent pixel resolves to terrain color; memoization returns the identical cached object.
3. **`SpriteRegistry`** — curated code returns the curated sprite; unknown code returns a deterministic tinted silhouette with a checksum-derived marking; same code twice returns the identical cached sprite; two codes with different checksums differ.
4. **`MapPane._render_viewport`** — viewport tile-range math (correct tile count for a given size), player tile centered, content placed at the correct tile, floor vs. void terrain fill chosen correctly, HUD line content. Asserted via Rich `Text` segment inspection — no real terminal required.

## Performance

~12×9 ≈ 108 tiles × 32 cells = ~3,500 styled cells per frame. Renders only on cycle snapshot (game acts every few seconds), and composited sprite rows are memoized by `(sprite, terrain_color)`, so per-frame work is concatenation of cached `Text` fragments. Comfortably within budget.

## Out of scope (YAGNI v1)

- Animation (idle bounce, water shimmer) — clean future extension on a Textual interval.
- Directional player facing.
- Biome / terrain-type art — the API exposes only floor / void / door today; use only API data.
- Sprite-key help overlay.

## Build sequence

1. `sprites.py` — `Sprite` value object, validator, a minimal curated set (player, one slime, floor, void, door) + category palettes. Tests for integrity.
2. `half_block.py` — `HalfBlockCompositor` + memoization. Tests.
3. `sprite_registry.py` — curated lookup + procedural fallback. Tests.
4. `map_pane.py` — rewrite `_render_viewport` over the two-layer compositor; update `_build_tile_index` to store code+category; HUD line. Tests.
5. `app.py` — 3×3 layout CSS.
6. Flesh out the curated sprite set (remaining monsters/NPCs/structures/resources) iteratively; fallback covers anything unauthored.
