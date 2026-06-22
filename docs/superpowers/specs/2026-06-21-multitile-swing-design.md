# Multi-Tile Swing Animations — Design

Date: 2026-06-21
Status: approved (brainstorm), pending implementation plan
Extends: `2026-06-21-tui-motion-animations-design.md` (the merged single-tile swing system)

## Goal

The merged gather/combat swing draws a tool inside the player's single 8×8 tile —
too small to read as a real weapon. Make the swing a **two-tile tool** (head in a
neighbor tile + a short grip in the player tile) that sweeps a half-circle through
the neighbor tiles, compositing **over whatever occupies those tiles** (resource
node / monster / terrain) so it looks like striking the target.

- **Gather:** pickaxe/axe head sweeps **clockwise** down the RIGHT side, 12→3→6.
- **Combat:** sword head sweeps **counterclockwise** down the LEFT side, 12→9→6.

## Background (current merged state)

- The map is player-centered; the player tile is always grid-center
  (`map_pane.py` `is_player = tcol == half_w and trow == half_h`).
- `_render_viewport` iterates tiles; for each it calls `_tile_sprite_and_terrain`
  then `HalfBlockCompositor.compose(sprite, terrain)` → 4 Rich `Text` rows.
- `HalfBlockCompositor.compose` is single-layer (sprite over terrain), memoized by
  `(sprite.rows, palette, terrain_color)`.
- Animation modes are mutually exclusive in time
  (`swing_frames.current_mode`): only ONE of idle/glide/gather_swing/fight_swing/
  planning is active. The player tile is rendered from `MapPane._player_sprite(now)`.
- Today a swing returns ONE 8×8 sprite for the player tile
  (`GATHER_SWING_FRAMES[i]` / `FIGHT_SWING_FRAMES[i]`); nothing spills past the tile.
- Sprites are 8×8 palette-key grids; `'.'` = `TRANSPARENT`; `validate_sprite`
  enforces 8×8 + defined keys. `Sprite(rows, palette)` is frozen.

## Key decisions (resolved in brainstorm)

- **Reach:** player tile + exactly ONE neighbor tile per frame (tool ≈ 2 tiles).
  The head occupies the arc-neighbor tile; the player tile carries a short grip.
- **Overlay target:** the tool composites OVER whatever is in the neighbor tile
  (resource/monster/terrain); transparent tool pixels still show the content
  behind. (Looks like striking the harvested/fought thing.)
- Modes stay mutually exclusive; glide / planning / idle render unchanged
  (single tile). Only the two swing modes become multi-tile.

## Architecture

Three additive/replacing pieces.

### 1. `overlay_sprites(base, top) -> Sprite` (pure, `sprites.py`)

Returns a new 8×8 `Sprite`: for each cell, `top`'s pixel wins unless it is
`TRANSPARENT`, in which case `base`'s pixel shows. The merged palette is
`base.palette | top.palette` (top keys override on collision). Used by the
renderer to paint a tool overlay onto a tile's existing base sprite before
compositing. Pure, immutable output (new Sprite), so the memoized compositor
stays correct.

### 2. Multi-tile swing frames (`swing_frames.py`, pure)

A swing frame becomes an **overlay map**: `dict[tuple[int, int], Sprite]` keyed by
tile-offset `(dcol, drow)` from the player tile. Each frame contains:
- `(0, 0)` → a **grip** overlay (handle pixels in the player tile, oriented toward
  the head),
- the **head** offset for that frame → the tool-head sprite.

New function:
`swing_overlay(mode: Mode, frame_index: int) -> dict[tuple[int,int], Sprite]`
returning the overlay map for `Mode.GATHER_SWING` / `Mode.FIGHT_SWING`, or `{}` for
any other mode.

Arc offsets (5 frames), **gather** (clockwise, right side):
`(0,-1)` up → `(+1,-1)` up-right → `(+1,0)` right → `(+1,+1)` down-right →
`(0,+1)` down.
**Combat** (counterclockwise, left side) = mirror on X: `(0,-1)`, `(-1,-1)`,
`(-1,0)`, `(-1,+1)`, `(0,+1)`.

The existing `swing_frame_index(elapsed, frame_count, sweep_seconds)` selects the
frame index (frame_count = 5); unchanged.

### 3. Renderer integration (`map_pane.py`)

- `_player_sprite(now)` shrinks to: return the player-tile overlay only — i.e.
  `PLAYER_SPRITE` merged with the swing frame's `(0,0)` grip when in a swing mode,
  else the existing idle/planning sprite. (Glide/idle/planning unchanged.)
- `_render_viewport` inner loop: compute `dcol = tcol - half_w`,
  `drow = trow - half_h`. Obtain the current swing overlay map once per render
  (`self._swing_overlay(now)` → `{}` when not swinging). For each non-player tile
  whose `(dcol, drow)` is in the overlay map, merge the head overlay onto that
  tile's normal base sprite via `overlay_sprites(base, head)` before `compose`.
  The player tile (`(0,0)`) uses `_player_sprite(now)` as today.
- New small helper `MapPane._swing_overlay(now) -> dict[tuple[int,int], Sprite]`
  bridging widget state → `swing_frames.swing_overlay`.

### Art (`sprites.py`)

- `GATHER_HEAD: Sprite` — pickaxe/axe head, 8×8, reads as a tool head.
- `FIGHT_HEAD: Sprite` — sword blade, 8×8.
- `GATHER_GRIPS: tuple[Sprite, ...]` / `FIGHT_GRIPS: tuple[Sprite, ...]` — 5 short
  grip overlays each (handle pixels in the player tile pointing toward the head's
  offset for that frame); combat grips mirror gather on X.
- The old single-tile `GATHER_SWING_FRAMES` / `FIGHT_SWING_FRAMES` are removed;
  `PLANNING_SPRITE` and the `_player_with_tool` builder stay (the builder can be
  reused for grips). Tool colors: gather head COPPER/BARK, sword STEEL.

## Data flow (per render frame, swing active)

```
now = time.monotonic()
mode = current_mode(snap.action_kind, planning, now - _anim_start, cooldown_remaining)
overlay = swing_overlay(mode, swing_frame_index(elapsed, 5, SWING_SWEEP_SECONDS))  # {} if not swinging
for each visible tile (tcol,trow):
    dcol,drow = tcol-half_w, trow-half_h
    if (dcol,drow) == (0,0): sprite = _player_sprite(now)         # PLAYER + grip
    elif (dcol,drow) in overlay: sprite = overlay_sprites(tile_base, overlay[(dcol,drow)])
    else: sprite = tile_base
    compose(sprite, terrain)
```

## Components & isolation

| Unit | Responsibility | Depends on |
|---|---|---|
| `sprites.overlay_sprites` | merge two 8×8 sprites (top wins) | Sprite |
| `sprites` head/grip data | tool art (heads + 5 grips ×2) | Sprite, palette |
| `swing_frames.swing_overlay` | (mode, frame_idx) → offset→Sprite map | sprites art |
| `MapPane._swing_overlay` / `_player_sprite` / `_render_viewport` | apply overlays per tile | the above |

## Error handling / edge cases

- Neighbor tile off-screen at viewport edge → it's simply not in the render loop,
  so the head is not drawn there (clipped). Harmless; no crash.
- Not-swinging modes → `swing_overlay` returns `{}`; loop behaves exactly as today.
- Overlay onto a tile holding a resource/monster sprite → tool pixels win, content
  shows through tool-transparent pixels (intended).
- Compositor cache: merged sprites are new immutable Sprites; keys stay valid.
  Bounded growth: 5 frames × {head over distinct tile-contents} × terrain colors.
- `overlay_sprites` palette-key collision → top's color wins (documented).

## Testing

- `overlay_sprites`: top non-transparent pixel wins; transparent shows base;
  result is 8×8 and `validate_sprite`-clean; palette merged with top precedence.
- `swing_overlay`: gather frames put the head at the 5 right/up/down offsets in
  order and a grip at `(0,0)`; combat frames mirror on X (negative dcol); non-swing
  modes → `{}`; frame_index in range.
- art: heads + grips are 8×8 with defined palette keys (`validate_sprite`); combat
  grips mirror gather grips on X.
- `MapPane` integration (fake clock): during a gather swing, the tile at the
  current arc offset renders with tool pixels merged in (assert the composed
  neighbor differs from its plain base / the player tile carries the grip); during
  a fight swing the offset is on the left; idle/glide/planning render no overlays.
- 100% line coverage held (project gate); the existing `on_mount` pragma carve-out
  remains the only one.

## Out of scope (YAGNI)

- Rotation engine / sub-pixel angles — 5 hand-placed arc frames only.
- Second neighbor tile / 3×3 reach.
- Multi-layer compositor generalization beyond `overlay_sprites` (two-layer merge
  is enough; modes remain exclusive).
- Any change to glide, planning bubble, movement timing, or the snapshot/observer
  layer.
