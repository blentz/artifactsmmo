# Dynamic fill-and-center map viewport

Date: 2026-05-21
Status: Approved (design)

## Goal

The TUI map (`MapPane`) must always fill its pane and keep the player centered,
at any window size — instead of the fixed `41×21` grid it renders today.

## Current state

`map_pane.py` renders a hardcoded `VIEWPORT_W=41 × VIEWPORT_H=21` grid: a top
legend line plus 21 rows of 41 cells, player at the exact center
(`half_w`/`half_h` offsets). On a larger window the map leaves blank space; on a
smaller one it is cropped (the grid is already `no_wrap=True, overflow="crop"`).

## Design

### Sizing source
At render time, read the pane's cell dimensions from `self.size` (Textual sets
the widget's region size before `render()`):
- `width = self.size.width`
- map rows `map_h = self.size.height - 1` (the top line remains the
  coords+legend header)

When `self.size` is `(0, 0)` — the pre-layout first paint — fall back to the
current `VIEWPORT_W=41`, `VIEWPORT_H=21` so the first frame is not blank.
`VIEWPORT_W`/`VIEWPORT_H` are kept solely as these fallback defaults.

### Centering
Per the approved decision, use the full width/height as-is (no shrink-to-odd):
- player column = `width // 2`, player row = `map_h // 2`
- cell `(col, row)` maps to world
  `(cx + col - width // 2, cy + row - map_h // 2)`

On an even axis the player is up to half a cell off true center — accepted.
`no_wrap=True, overflow="crop"` is retained so nothing wraps.

### Re-render on resize
Add `on_resize(self, event)` → `self.refresh()` so the grid recomputes whenever
the pane/window changes size.

### Structure (testability)
Split rendering into:
- `_render_viewport(snap, width, height) -> Text` — **pure**: renders a
  `width × height` block = 1 header line + `(height - 1)` map rows, player at
  (`width//2`, `(height-1)//2`), using the existing glyph/tile-index/known-tile
  logic. No dependency on a running app.
- `render()` — resolves `width, height` from `self.size` (fallback to
  `VIEWPORT_W/VIEWPORT_H` when either is `0`), then returns
  `_render_viewport(snap, width, height)`; still returns the "Waiting for first
  cycle..." text when there is no snapshot.

### Edge cases
- `height <= 1` → header only, no map rows (`range(0)` is empty).
- `width <= 0` → empty rows.
- Both handled naturally by the `range()` bounds; no special-casing needed.

## Testing

Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- `_render_viewport(snap, w, h)` with explicit dimensions:
  - odd `w,h` (e.g. 41,21): line count `== h`; every body row width `== w`;
    player glyph at column `w//2` of row `1 + (h-1)//2`.
  - even `w,h` (e.g. 40,20): line count `== h`; row width `== w`; player at
    `w//2` (near-center).
  - tiny: `h == 1` → only the header line, no map rows; `h == 2` → header + 1
    row; `w == 1` → single-column rows.
  - world-mapping: a content tile placed at a known offset from the player
    appears at the expected `(col,row)` for a given `w,h`.
- `render()` falls back to `41×21` when `self.size` is `(0,0)` (construct the
  pane without a running app, as existing `test_map_pane.py` tests do).
- `render()` with no snapshot still returns "Waiting for first cycle...".
- Existing tests that assumed `41×21` are updated to call `_render_viewport`
  with explicit dimensions (or rely on the `(0,0)`-size fallback).

## Files

- `src/artifactsmmo_cli/tui/widgets/map_pane.py` — `render`, new pure
  `_render_viewport(snap, width, height)`, `on_resize`; `VIEWPORT_W/H` demoted
  to fallback defaults.
- `tests/test_tui/test_map_pane.py` — updated/added per above.

## Out of scope
- `app.py` grid/layout (the pane already receives its grid cell; this fills
  whatever cell it is given).
- Glyph scheme, legend content (unchanged).
