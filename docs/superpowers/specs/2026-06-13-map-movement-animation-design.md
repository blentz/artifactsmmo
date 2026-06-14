# Map Movement Animation

**Date:** 2026-06-13
**Status:** Design — pending user review
**Topic:** Animate the player's movement on the TUI map by gliding the player-centered viewport from the previous tile to the new tile between bot cycles.

## Goal

When the bot moves the character, the map currently jumps instantly from the old position to the new one. Animate that transition: the player-centered viewport glides diagonally from the previous tile to the destination over a short window inside the move cooldown, so movement reads as travel rather than a teleport. Watcher-only cosmetic; the bot is unaffected.

## Decisions (locked during brainstorming)

| Decision | Choice |
|---|---|
| Camera style | **World scrolls, player fixed at center** (player `@` never leaves center; world slides under it) |
| Scroll path | **Diagonal glide** — Bresenham-interpolated straight line from start to destination |
| Trigger | Only when the new snapshot's `(x,y)` differs from the prior snapshot's |
| Pacing | Fixed budget inside the ≥5s move cooldown: ≤12 sampled steps, ~50 ms/frame → ≤ ~600 ms total |
| Interruption | New snapshot mid-glide cancels and snaps to latest; cancel on unmount |
| HUD | Coordinates tick along with the glide, settling on the real destination |
| Config | Always on, no flag (passive watcher; YAGNI) |
| Engine | No sprite/layout/engine changes; render path centers on an interpolated tile |

## Background (current behavior)

- `MapPane._render_viewport` centers strictly on `snap.x, snap.y`; the player tile is the geometric center of the viewport.
- `MapPane.update_snapshot(snap)` is called once per bot cycle (cycles are cooldown-driven, ≥5 s for a move; a move's cooldown ≈ Manhattan distance × 5 s).
- `CycleSnapshot` carries only the current `x, y` — no prior position, no route. `MapPane` already holds the previous snapshot via its reactive `snapshot`, so the prior position is available to diff against the new one.
- A `MOVE` is atomic server-side (one API call to an arbitrary destination); there is no per-tile route in the bot loop. Intermediate tiles for the animation are therefore interpolated client-side.
- Textual `set_interval` is available and already used by `StatusPane` for its cooldown tick.

## Architecture

### New file: `src/artifactsmmo_cli/tui/path_interpolate.py` (pure functions)

Pure-data/logic module (no behavioral class — exempt, like `palette.py`).

```
glide_path(start: tuple[int, int], end: tuple[int, int], max_steps: int) -> list[tuple[int, int]]
```

- Computes the Bresenham line from `start` to `end`.
- Excludes `start`; the returned list is the sequence of viewport-center tiles to render, **always ending exactly at `end`**.
- If the line has more than `max_steps` points, sample evenly down to `max_steps` (keeping the final point = `end`), so long/teleport jumps still finish in a bounded number of frames.
- Returns `[]` when `start == end` (caller does not animate).
- Raises `ValueError` if `max_steps < 1`.

This is the entire animation math, isolated and unit-testable with no Textual/IO dependency.

### Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py` (`MapPane`)

Add animation state: `_anim_frames: list[tuple[int, int]]`, `_anim_index: int`, `_anim_timer` (the Textual timer handle, or `None`).

- **`_render_viewport(self, snap, width, height, center=None)`**: when `center` is provided, use it as `(cx, cy)` instead of `snap.x, snap.y`; otherwise behave exactly as today. The player sprite is still drawn at the center tile (it represents the current glide position). The HUD line uses the active center's coordinates.
- **`render()`**: if an animation is active, pass the current frame (`_anim_frames[_anim_index]`) as `center`; otherwise render at the snapshot position (current behavior).
- **`update_snapshot(self, snap)`**:
  - Capture the prior position from the existing `self.snapshot` (if any) before assigning the new one.
  - Assign `self.snapshot = snap`.
  - If a prior position exists and differs from the new one: `_start_glide(prior, (snap.x, snap.y))`.
  - Otherwise (first snapshot, or no positional change): cancel any active animation and let the normal render run.
- **`_start_glide(prior, dest)`**: cancel any in-flight timer; `frames = glide_path(prior, dest, MAX_ANIM_STEPS)`; if `frames` is non-empty, set `_anim_frames`/`_anim_index = 0`, and `_anim_timer = self.set_interval(ANIM_FRAME_SECONDS, self._tick)`; else render at rest.
- **`_tick()`**: if at the last frame, stop the timer, clear anim state, and `refresh()` (settles on `snap`); else advance `_anim_index` and `refresh()`.
- **Cancel** the timer in `_start_glide` (before starting a new one) and on unmount (`on_unmount`).

Constants in `map_pane.py`: `MAX_ANIM_STEPS = 12`, `ANIM_FRAME_SECONDS = 0.05`.

### No other files change

`half_block.py`, `sprite_registry.py`, `sprites.py`, `palette.py`, `glyphs.py`, `app.py` are untouched. The bot, snapshots, and `CycleSnapshot` are untouched.

## Error handling (CLAUDE.md)

- Pure visual feature; no game/API data involved, so no defaulting-over-missing-data concerns.
- `glide_path` raises `ValueError` on `max_steps < 1` (programmer error); no silent clamping. No `except Exception` anywhere. No inline imports, no `TYPE_CHECKING`.

## Testing (0 errors / 0 warnings / 0 skipped / 100% coverage on `src/`)

`tests/test_tui/test_path_interpolate.py` (new):
- Horizontal, vertical, and diagonal moves return the expected tile sequence, each ending exactly at `end`.
- Adjacent move (distance 1) → exactly one frame == `end`.
- `start == end` → `[]`.
- A long line (e.g. 40 tiles) caps to `max_steps` frames, last frame == `end`, frames advance monotonically toward `end`.
- `max_steps < 1` raises `ValueError`.

`tests/test_tui/test_map_pane.py` (additions):
- `_render_viewport` with a `center` override shifts the world by the expected offset (a known feature lands at the offset implied by `center`, not by `snap`).
- `update_snapshot` with a changed position populates `_anim_frames` (index 0, last frame == new pos); with an unchanged position or as the first snapshot, no frames are created.
- Calling `_tick` repeatedly to the end clears the animation state and the final `render()` centers on `snap` (driven by direct calls, no real sleep).
- A new `update_snapshot` mid-glide cancels the prior animation and re-targets (or snaps) to the latest position.
- HUD shows the gliding coordinates mid-animation and the destination coordinates at rest.
- One Textual `run_test` pilot mounts the pane, fires a move snapshot, and unmounts — covering the real `set_interval` call and the unmount cancel without asserting on wall-clock timing.

## Out of scope (YAGNI)

- Player-slides-across-static-map style (option B) — rejected in favor of world-scroll.
- Real pathfinding routes around obstacles — rejected; diagonal interpolation is used.
- Sub-tile / pixel-smooth scrolling (the char grid is tile-granular).
- Animating non-move state changes (combat hits, gathering); only positional moves animate.
- A config flag / toggle.
