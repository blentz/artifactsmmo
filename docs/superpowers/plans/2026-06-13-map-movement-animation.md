# Map Movement Animation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Animate the player-centered map gliding from the previous tile to the new tile when the bot moves, instead of jumping instantly.

**Architecture:** A pure `glide_path` function computes the Bresenham, step-capped sequence of viewport-center tiles. `MapPane` diffs consecutive snapshots, and on a positional change drives a `set_interval` timer that advances a center index; `render()`/`_render_viewport` paint at the current interpolated center (player stays at the geometric center). No sprite/engine/bot changes.

**Tech Stack:** Python 3.13, `uv`, Textual (`set_interval`/`Timer`), Rich, pytest (`-W error`, 100% coverage on `src/`), mypy `--strict`.

**Spec:** `docs/superpowers/specs/2026-06-13-map-movement-animation-design.md`

**Conventions (CLAUDE.md):** Prefix commands with `uv run`. Imports at top only — no inline, no `...`, no `TYPE_CHECKING`. Never catch `Exception`. One behavioral class per file (`path_interpolate.py` is a pure-function module — exempt). mypy strict: parameterize all generics. Tests in `tests/`; 0 errors/warnings/skips, 100% coverage on `src/`.

---

## File Structure

| File | Responsibility | New/Modify |
|---|---|---|
| `src/artifactsmmo_cli/tui/path_interpolate.py` | Pure `glide_path` interpolation (Bresenham + sampling) | Create |
| `tests/test_tui/test_path_interpolate.py` | Unit tests for `glide_path` | Create |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | Glide animation state + timer + center-override render | Modify |
| `tests/test_tui/test_map_pane.py` | Animation-state + center-override tests | Modify (add) |

No other files change.

---

## Task 1: Pure glide-path interpolation

**Files:**
- Create: `src/artifactsmmo_cli/tui/path_interpolate.py`
- Test: `tests/test_tui/test_path_interpolate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tui/test_path_interpolate.py`:

```python
"""Pure glide-path interpolation for the map movement animation."""

import pytest

from artifactsmmo_cli.tui.path_interpolate import glide_path


def test_horizontal_excludes_start_ends_at_end():
    assert glide_path((0, 0), (3, 0), 12) == [(1, 0), (2, 0), (3, 0)]


def test_vertical_negative():
    assert glide_path((0, 0), (0, -2), 12) == [(0, -1), (0, -2)]


def test_diagonal_45():
    assert glide_path((0, 0), (3, 3), 12) == [(1, 1), (2, 2), (3, 3)]


def test_adjacent_is_single_frame():
    assert glide_path((0, 0), (1, 0), 12) == [(1, 0)]


def test_equal_start_end_is_empty():
    assert glide_path((2, 2), (2, 2), 12) == []


def test_long_line_caps_to_max_steps_and_ends_at_end():
    g = glide_path((0, 0), (40, 0), 12)
    assert len(g) == 12
    assert g[-1] == (40, 0)
    xs = [p[0] for p in g]
    assert xs == sorted(xs)          # advances monotonically toward end


def test_non_45_diagonal_ends_at_end_within_cap():
    g = glide_path((0, 0), (4, 2), 12)
    assert g[-1] == (4, 2)
    assert 1 <= len(g) <= 12


def test_max_steps_one_long_line_returns_only_end():
    assert glide_path((0, 0), (5, 0), 1) == [(5, 0)]


def test_max_steps_below_one_raises():
    with pytest.raises(ValueError, match="max_steps"):
        glide_path((0, 0), (3, 0), 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tui/test_path_interpolate.py -v`
Expected: FAIL with `ModuleNotFoundError: artifactsmmo_cli.tui.path_interpolate`

- [ ] **Step 3: Write the implementation**

Create `src/artifactsmmo_cli/tui/path_interpolate.py`:

```python
"""Pure interpolation for the map's player-movement glide animation.

`glide_path` returns the sequence of viewport-center tiles to render while the
player-centered map slides from `start` to `end`: a Bresenham line, sampled
down to at most `max_steps` frames, always ending exactly at `end`, with the
`start` tile excluded. No Textual/IO dependency — fully unit-testable.
"""


def _bresenham(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Integer line from start to end inclusive (both endpoints included)."""
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    points: list[tuple[int, int]] = []
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return points


def _sample(frames: list[tuple[int, int]], max_steps: int) -> list[tuple[int, int]]:
    """Evenly pick `max_steps` frames across `frames`, always keeping the last."""
    if max_steps == 1:
        return [frames[-1]]
    n = len(frames)
    return [frames[round(i * (n - 1) / (max_steps - 1))] for i in range(max_steps)]


def glide_path(
    start: tuple[int, int], end: tuple[int, int], max_steps: int
) -> list[tuple[int, int]]:
    """Center tiles to render gliding start -> end (start excluded, ends at end).

    Empty when start == end. Capped to `max_steps` frames. Raises if max_steps < 1.
    """
    if max_steps < 1:
        raise ValueError(f"max_steps must be >= 1, got {max_steps}")
    if start == end:
        return []
    frames = _bresenham(start, end)[1:]   # drop the start tile
    if len(frames) <= max_steps:
        return frames
    return _sample(frames, max_steps)
```

The `max_steps == 1` guard in `_sample` avoids a divide-by-zero on a long line capped to a single frame (covered by `test_max_steps_one_long_line_returns_only_end`).

- [ ] **Step 4: Run the whole file to verify it passes**

Run: `uv run pytest tests/test_tui/test_path_interpolate.py -v`
Expected: PASS (9 tests). Then `uv run mypy src/artifactsmmo_cli/tui/path_interpolate.py` → clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/path_interpolate.py tests/test_tui/test_path_interpolate.py
git commit -m "feat(tui): pure glide_path interpolation for map movement animation"
```

---

## Task 2: MapPane glide animation

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane.py` (add a class)

The current `MapPane` renders statically, centered on `snap.x, snap.y`. Add animation state, a `set_interval` driver, a `center` override on the render path, and a coordinate-driven HUD.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_tui/test_map_pane.py`. The file already imports `App`, `ComposeResult`, `Size`, `CycleSnapshot`, `GameData`, `MapPane`, and defines `_gd_typed()` and `_snap(x, y)`; reuse them.

```python
class TestGlideAnimation:
    def test_center_override_hud_shows_center_coords(self):
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(0, 0), 80, 41, (5, -3)).plain.split("\n")[0]
        assert hud.startswith("(5,-3)")

    def test_center_override_hud_shows_content_at_center(self):
        # _gd_typed has the woodcutting resource at (2,2).
        pane = MapPane(_gd_typed())
        hud = pane._render_viewport(_snap(0, 0), 80, 41, (2, 2)).plain.split("\n")[0]
        assert "resource_woodcutting" in hud

    def test_first_snapshot_no_animation(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        assert pane._anim_frames == []

    def test_move_builds_glide_frames(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        pane.update_snapshot(_snap(3, 0))
        assert pane._anim_frames == [(1, 0), (2, 0), (3, 0)]
        assert pane._anim_index == 0

    def test_no_move_clears_animation(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        pane.update_snapshot(_snap(2, 0))
        pane.update_snapshot(_snap(2, 0))      # same tile -> no glide
        assert pane._anim_frames == []

    def test_midglide_new_move_retargets(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        pane.update_snapshot(_snap(5, 0))
        pane._tick()                            # advance one frame
        pane.update_snapshot(_snap(5, 3))       # new move from (5,0)
        assert pane._anim_frames == [(5, 1), (5, 2), (5, 3)]
        assert pane._anim_index == 0

    def test_tick_advances_then_settles(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        pane.update_snapshot(_snap(2, 0))       # frames [(1,0),(2,0)]
        assert pane._anim_index == 0
        pane._tick()
        assert pane._anim_index == 1
        pane._tick()                            # at last frame -> stop
        assert pane._anim_frames == []
        assert pane._anim_timer is None

    def test_render_centers_on_glide_then_snap(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        pane.update_snapshot(_snap(2, 0))
        assert pane.render().plain.split("\n")[0].startswith("(1,0)")   # frame 0
        pane._tick()
        pane._tick()                            # settle
        assert pane.render().plain.split("\n")[0].startswith("(2,0)")   # snap

    async def test_timer_created_when_mounted_and_unmount_cancels(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))

        class _Host(App):
            def compose(self) -> ComposeResult:
                yield pane

        async with _Host().run_test(size=(90, 45)):
            pane.update_snapshot(_snap(4, 0))   # mounted -> real timer created
            assert pane._anim_timer is not None
        assert pane._anim_timer is None         # on_unmount -> _stop_anim
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tui/test_map_pane.py::TestGlideAnimation -v`
Expected: FAIL — `AttributeError: 'MapPane' object has no attribute '_anim_frames'` / `_render_viewport` takes no `center` arg.

- [ ] **Step 3: Edit `map_pane.py`**

(a) Extend imports — replace the import block lines:

```python
from typing import Any

from rich.text import Text
from textual.events import Resize
from textual.reactive import reactive
from textual.widgets import Static
```

with:

```python
from typing import Any

from rich.text import Text
from textual.events import Resize
from textual.reactive import reactive
from textual.timer import Timer
from textual.widgets import Static
```

and add, after the existing `from artifactsmmo_cli.tui.sprites import ...` line:

```python
from artifactsmmo_cli.tui.path_interpolate import glide_path
```

(b) Add two constants after `FALLBACK_H = 41`:

```python
MAX_ANIM_STEPS = 12       # cap glide frames so big jumps still finish fast
ANIM_FRAME_SECONDS = 0.05  # ~50ms/frame -> <= ~600ms total, well inside the move cooldown
```

(c) In `__init__`, after `self._compositor = HalfBlockCompositor()`, add:

```python
        self._anim_frames: list[tuple[int, int]] = []
        self._anim_index = 0
        self._anim_timer: Timer | None = None
```

(d) Replace `update_snapshot`:

```python
    def update_snapshot(self, snap: CycleSnapshot) -> None:
        prior = self.snapshot
        self.snapshot = snap
        self._stop_anim()
        if prior is not None and (prior.x, prior.y) != (snap.x, snap.y):
            self._anim_frames = glide_path((prior.x, prior.y), (snap.x, snap.y), MAX_ANIM_STEPS)
            self._anim_index = 0
            if self.is_mounted:
                self._anim_timer = self.set_interval(ANIM_FRAME_SECONDS, self._tick)
        self.refresh()
```

(e) Add three methods after `update_snapshot`:

```python
    def _stop_anim(self) -> None:
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer = None
        self._anim_frames = []
        self._anim_index = 0

    def _tick(self) -> None:
        if self._anim_index >= len(self._anim_frames) - 1:
            self._stop_anim()
        else:
            self._anim_index += 1
        self.refresh()

    def on_unmount(self) -> None:
        self._stop_anim()
```

(f) Replace `render`:

```python
    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or FALLBACK_W
        height = self.size.height or FALLBACK_H
        center = self._anim_frames[self._anim_index] if self._anim_frames else None
        return self._render_viewport(snap, width, height, center)
```

(g) Replace `_hud_line` (now coordinate-driven):

```python
    def _hud_line(self, cx: int, cy: int) -> str:
        content = self._tile_index.get((cx, cy))
        coords = f"({cx},{cy})"
        if content is None:
            return coords
        return f"{coords} · {content[1]}"
```

(h) Replace `_render_viewport`'s signature and its `cx, cy` / HUD lines. New version:

```python
    def _render_viewport(
        self,
        snap: CycleSnapshot,
        width: int,
        height: int,
        center: tuple[int, int] | None = None,
    ) -> Text:
        tiles_w = width // TILE_W
        tiles_h = (height - 1) // TILE_H
        half_w = tiles_w // 2
        half_h = tiles_h // 2
        cx, cy = center if center is not None else (snap.x, snap.y)
        text = Text(no_wrap=True, overflow="crop")
        text.append(self._hud_line(cx, cy), style="dim")
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

- [ ] **Step 4: Run the map-pane tests**

Run: `uv run pytest tests/test_tui/test_map_pane.py -v`
Expected: PASS — the new `TestGlideAnimation` class plus all pre-existing map-pane tests (they call `_render_viewport` without `center`, which defaults to the snapshot position, and read the HUD which is unchanged for the no-animation case).

- [ ] **Step 5: Full gate**

Run: `uv run pytest && uv run mypy src/`
Expected: 0 fail, 0 warn, 0 skip, 100% coverage on `src/`; mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): glide the map between tiles on player movement"
```

---

## Final verification

- [ ] **Full gate:** `uv run pytest` → 0 errors, 0 warnings, 0 skipped, 100% coverage on `src/`.
- [ ] **Types:** `uv run mypy src/` → clean.
- [ ] **Manual smoke (optional):** run the TUI watch mode and confirm the map glides diagonally when the character moves and is instant/static for in-place actions (fight/gather). The bot's behavior is unchanged.

## Notes

- **Coverage map** (why each branch is hit): `update_snapshot` — first snapshot (`prior is None`), a move (`prior != dest`), and an in-place cycle (`prior == dest`); `is_mounted` True via the pilot test, False via the unmounted unit tests; `_tick` advance + terminal branches; `_stop_anim` timer-present (pilot/unmount) + timer-absent (unit); `render` center-active + center-inactive; `_render_viewport` `center` default + override; `_hud_line` content + no-content; `glide_path`/`_sample` short, capped, and `max_steps==1` paths.
- **No dead code:** `_stop_anim` is always called at the top of `update_snapshot`, so the timer is cancelled before any retarget; because `update_snapshot` only builds frames when `prior != dest`, `glide_path` there never returns `[]` (no unreachable empty-guard needed).
- **No engine/bot changes.** Only `path_interpolate.py` (new) and `map_pane.py` (modified) plus their tests.
```
