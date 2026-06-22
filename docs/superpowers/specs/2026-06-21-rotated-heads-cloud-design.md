# Rotated Swing Heads + Craft-by-Category + Animated Thought Cloud — Design

Date: 2026-06-21
Status: approved (brainstorm), pending implementation plan
Extends: `2026-06-21-tool-head-redesign-design.md` (merged tool-head system)

## Goal

Three polish passes on the merged map-TUI swing/planning animations:

1. **Rotate the swing head** so the haft points back at the player at every arc
   position (it currently always points down) — the tool reads as held.
2. **Pick the craft tool by item category:** cooking → sword, every other craft
   → hammer (replaces the bar-only hammer rule).
3. **Animated thought cloud:** planning shows a 2-tile grey-white bubbly cloud
   (up-right of the player) plus the existing white dot, drifting once per second.

## Background (merged state)

- `swing_overlay(mode, frame_index, head: Sprite)` (`swing_frames.py`) →
  `{(0,0): grip_overlay(*off), off: head}` where `off` is the per-frame arc
  offset (`_GATHER_OFFSETS` right/CW = `[(0,-1),(1,-1),(1,0),(1,1),(0,1)]`;
  `_FIGHT_OFFSETS` left/CCW = the X-mirror). `head` is placed **unrotated**.
- `grip_overlay(dcol, drow)` already orients the player-tile handle toward the
  head direction.
- `MapPane._swing_overlay(now)` selects a head via `select_swing_head(mode,
  action_target, game_data)` and calls `swing_overlay`. `_render_viewport` merges
  the per-offset overlay sprite onto each tile via `overlay_sprites`.
- Planning: `current_mode` → `Mode.PLANNING`; `_player_sprite` returns
  `PLANNING_SPRITE` (player + a white dot 'p'=BONE at (0,7),(1,7) in the player
  tile). No neighbor-tile cloud. `set_planning(active)` toggles `_planning_active`.
- `ItemStats` (`item_catalog.py`) has `crafting_skill: str | None`
  (weaponcrafting / gearcrafting / jewelrycrafting / cooking / mining /
  woodcutting / alchemy) and `type_: str`. `game_data.item_stats(code)` returns it.
- Sprites are 8×8; `validate_sprite`; colors include `STONE` (#babdb6 light grey),
  `SLATE` (#6b6f6a dark grey), `STEEL`, `BARK`, `BONE`.

## Decisions (resolved in brainstorm)

- Rotation uses **exact 90° rotations only** (no lossy 45°). One canonical
  head-up sprite + one hand-authored head-up-right (NE) sprite per tool; all 8
  directions derive by `rot90cw` (cardinals from `up`, diagonals from `ne`).
- Craft tool: **cooking → sword, every other craft → hammer.**
- Cloud: **one** hand-authored cloud sprite; the second tile is it **rotated 90°**;
  the animation **swaps the two tiles each second** (2-frame, no extra art).
  Shadow pixel count ~doubled vs a plain cloud. Cloud spans tiles `(1,-1)` and
  `(2,-1)`; the white dot stays in the player tile.

## Part 1 — Rotation

### Helpers (`sprites.py`, pure)
- `rot90cw(sprite: Sprite) -> Sprite`: exact 90° clockwise — `new[i][j] =
  old[SPRITE_SIZE-1-j][i]` over the rows; palette carried unchanged.
- `ToolHeads` (frozen dataclass): `up: Sprite`, `ne: Sprite` — the two
  hand-authored orientations of a tool head.
- `oriented_head(tool: ToolHeads, dcol: int, drow: int) -> Sprite`: returns the
  head pointing in `(dcol, drow)` (away from the player), by `(base, turns)`:
  - `(0,-1)`→`(up,0)`, `(1,0)`→`(up,1)`, `(0,1)`→`(up,2)`, `(-1,0)`→`(up,3)`
  - `(1,-1)`→`(ne,0)`, `(1,1)`→`(ne,1)`, `(-1,1)`→`(ne,2)`, `(-1,-1)`→`(ne,3)`
  applying `rot90cw` `turns` times. (Cardinals are 90° apart from up; diagonals
  90° apart from NE.)

### Tool heads
The existing `AXE_HEAD`/`PICKAXE_HEAD`/`HAMMER_HEAD`/`FIGHT_HEAD` become the `up`
sprites. Add a hand-authored NE sprite per tool: `AXE_NE`, `PICKAXE_NE`,
`HAMMER_NE`, `FIGHT_NE` (head in the upper-right, haft trailing to the lower-left
toward the player). Bundle as `AXE = ToolHeads(AXE_HEAD, AXE_NE)`, etc. Sample
NE axe (`m`=STEEL, `l`=STONE blade, `h`=BARK haft):
```
....mmml
....mmml
....mmm.
...hm...
..h.....
.h......
h.......
........
```

### Wiring
- `swing_overlay(mode, frame_index, tool: ToolHeads)`: compute `off`, place
  `oriented_head(tool, *off)` at `off` (+ grip at `(0,0)`). Non-swing → `{}`.
- `MapPane.select_swing_head(...) -> ToolHeads | None` returns the tool bundle.

## Part 2 — Craft tool by category

`select_swing_head` for `Mode.CRAFT_SWING`: look up `game_data.item_stats(code)`;
- `crafting_skill == "cooking"` → the sword (`FIGHT` tool bundle / `FIGHT_HEAD`),
- any other craftable item (stats present) → the hammer (`HAMMER` bundle),
- unknown item (stats None) → `None` (no tool).
Gather (axe/pickaxe by resource skill) and fight (sword) unchanged. The bar-only
`_is_bar` gate is removed.

## Part 3 — Animated thought cloud

### Art (`sprites.py`)
- `CLOUD_SPRITE`: one 8×8 grey-white bubbly rounded rectangle — light body
  `STONE` ('l'), irregular bumps on the edges, dark-grey `SLATE` ('d') shading
  curving inward to accent the bump curves (~double the shadow pixel count of a
  plain shaded blob). Sample:
```
..llll..
.llllll.
llldllll
lldddlll
llldddll
.lddll..
..llll..
........
```
- `CLOUD_SPRITE_R = rot90cw(CLOUD_SPRITE)` (the second tile; asymmetric → looks
  irregular).

### Overlay
- `MapPane._planning_start: float` — stamped (`time.monotonic()`) when
  `set_planning(True)` fires AND was previously inactive (so the cycle starts at
  planning onset, not every toggle).
- `MapPane._planning_overlay(now) -> dict[tuple[int,int], Sprite]`: `{}` unless
  `_planning_active`; else swap the two cloud sprites each second:
  - `f = int(now - _planning_start) % 2`
  - `f == 0` → `{(1,-1): CLOUD_SPRITE, (2,-1): CLOUD_SPRITE_R}`
  - `f == 1` → `{(1,-1): CLOUD_SPRITE_R, (2,-1): CLOUD_SPRITE}`
- The white dot stays via `_player_sprite` → `PLANNING_SPRITE` (unchanged).
- `_render_viewport` overlay source: `_planning_overlay(now)` when planning else
  `_swing_overlay(now)` (mutually exclusive — planning vs a swing). A single
  `MapPane._active_overlay(now)` chooses which.

## Data flow (per render frame)

```
now = time.monotonic()
if _planning_active:  overlay = _planning_overlay(now)     # cloud + (dot via _player_sprite)
else:                 overlay = _swing_overlay(now)        # oriented head + grip, or {}
_render_viewport(..., player_sprite=_player_sprite(now), overlay=overlay)
```

## Components & isolation

| Unit | Responsibility | Depends on |
|---|---|---|
| `sprites.rot90cw` | exact 90° rotation | Sprite |
| `sprites.ToolHeads` / `oriented_head` | per-direction head orientation | rot90cw |
| `sprites` NE heads + `CLOUD_SPRITE` | new art | Sprite, palette |
| `swing_frames.swing_overlay(…, tool)` | orient head per arc offset | sprites |
| `MapPane.select_swing_head` | tool bundle by activity/category | game_data, sprites |
| `MapPane._planning_overlay` / `_active_overlay` | cloud overlay + chooser | sprites |

## Edge cases

- `oriented_head` with a non-unit `(dcol,drow)` never occurs (offsets are unit);
  the mapping covers all 8 unit directions; a lookup miss returns `tool.up`
  (defensive, documented).
- `rot90cw` is its own inverse to the 4th power: `rot90cw⁴ == identity` (tested).
- Cloud tiles off-screen at the viewport edge → not in the render loop (clipped).
- Planning ends → `_planning_overlay` returns `{}`; swap state resets next onset.
- `_planning_start` unset before first planning → guarded by `_planning_active`.

## Testing

- `rot90cw`: 4 applications == identity; head-up sprite → head-right after one
  CW turn (assert the top row's content moves to the right column).
- `oriented_head`: each of the 8 unit directions returns the expected
  `rot90cw^turns(base)`; cardinals use `up`, diagonals use `ne`.
- NE/up heads + cloud are valid 8×8; `CLOUD_SPRITE` has dark 'd' shadow pixels
  (count ≥ a threshold) and light 'l' body.
- `swing_overlay(mode, i, tool)`: head at the arc offset is
  `oriented_head(tool, *off)`; grip at `(0,0)`; `{}` non-swing.
- `select_swing_head` craft: cooking item → sword bundle; non-cooking craftable →
  hammer bundle; unknown → None. Gather/fight unchanged.
- `_planning_overlay`: `{}` when not planning; at `f=0` cloud at (1,-1)=CLOUD,
  (2,-1)=R; at `f=1` swapped; cycles each second from `_planning_start`.
- `set_planning(True)` stamps `_planning_start` once (not re-stamped while already
  planning).
- `_active_overlay`: planning → cloud; swinging → head; idle → {}.
- 100% coverage held; the `on_mount` pragma remains the only carve-out.

## Out of scope (YAGNI)

- Lossy 45° rotation / per-pixel interpolation (exact 90° only; NE hand-drawn).
- More than 2 cloud frames (swap is the animation).
- Rotating the cloud beyond the single rot90cw second tile.
- Any change to glide, movement timing, the snapshot/observer layer, or combat
  arc sides.
