# Dynamic Fill-and-Center Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `MapPane` fill its pane and keep the player centered at any window size, instead of the fixed 41×21 grid.

**Architecture:** Make `_render_viewport` a pure function of `(snap, width, height)` that draws a `width × height` block (1 legend line + `height-1` map rows) with the player centered. `render()` resolves `width/height` from `self.size` (falling back to `41×21` when size is 0), and `on_resize` refreshes so the grid recomputes on window changes.

**Tech Stack:** Python 3.13, `uv`, pytest, Rich/Textual.

---

## File Structure
- Modify `src/artifactsmmo_cli/tui/widgets/map_pane.py` — `_render_viewport(snap, width, height)`, `render()`, `on_resize`; keep `VIEWPORT_W`/`VIEWPORT_H` as fallback defaults.
- Modify `tests/test_tui/test_map_pane.py` — call the new signature; add dimension/fallback/resize tests.

---

## Task 1: `_render_viewport` takes explicit width/height and centers the player

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane.py`

- [ ] **Step 1: Write the failing tests**

The existing `_render_viewport(snap)` tests call it with one arg. Update them to pass dimensions and add new ones. In `tests/test_tui/test_map_pane.py` add a class (and update existing `_render_viewport(...)` calls to pass `VIEWPORT_W, VIEWPORT_H`):

```python
from artifactsmmo_cli.tui.widgets.map_pane import MapPane, VIEWPORT_H, VIEWPORT_W
from artifactsmmo_cli.tui.glyphs import PLAYER_GLYPH


class TestRenderViewportDimensions:
    def test_fills_exact_dimensions_odd(self):
        pane = MapPane(_gd_typed())          # _gd_typed exists in this file
        out = pane._render_viewport(_snap(0, 0), 41, 21)
        lines = out.plain.split("\n")
        assert len(lines) == 21                       # 1 header + 20 map rows
        assert all(len(row) == 41 for row in lines[1:])

    def test_fills_exact_dimensions_even(self):
        pane = MapPane(_gd_typed())
        out = pane._render_viewport(_snap(0, 0), 40, 20)
        lines = out.plain.split("\n")
        assert len(lines) == 20
        assert all(len(row) == 40 for row in lines[1:])

    def test_player_centered(self):
        pane = MapPane(_gd_typed())
        w, h = 41, 21
        lines = pane._render_viewport(_snap(0, 0), w, h).plain.split("\n")
        map_h = h - 1
        player_row = lines[1 + map_h // 2]            # +1 for the header line
        assert player_row[w // 2] == PLAYER_GLYPH

    def test_height_one_is_header_only(self):
        pane = MapPane(_gd_typed())
        lines = pane._render_viewport(_snap(0, 0), 41, 1).plain.split("\n")
        assert len(lines) == 1                        # header only, no map rows

    def test_world_offset_maps_to_centered_cell(self):
        # Monster at (2,0); player at (0,0); width 41 -> player col 20,
        # monster col 20+2 = 22 on the player's row.
        pane = MapPane(_gd_typed())                   # _gd_typed has green_slime at (2,0)
        w, h = 41, 21
        lines = pane._render_viewport(_snap(0, 0), w, h).plain.split("\n")
        map_h = h - 1
        assert lines[1 + map_h // 2][w // 2 + 2] == "s"   # green_slime glyph
```

If `_gd_typed`/`_snap` differ in this file, reuse the file's existing builders (it has `_gd_typed()` and `_snap(x, y)` from earlier work).

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_tui/test_map_pane.py -k "Dimensions or centered or header_only or world_offset" -v`
Expected: FAIL — `_render_viewport()` takes 1 positional arg, not 3.

- [ ] **Step 3: Implement the parameterized renderer**

In `src/artifactsmmo_cli/tui/widgets/map_pane.py`, replace `_render_viewport` with:

```python
    def _render_viewport(self, snap: CycleSnapshot, width: int, height: int) -> Text:
        """Render a width x height block: 1 legend line + (height-1) map rows,
        player centered at (width//2, (height-1)//2)."""
        map_h = height - 1
        half_w = width // 2
        half_h = map_h // 2
        cx, cy = snap.x, snap.y
        text = Text(no_wrap=True, overflow="crop")
        text.append(
            f" ({cx},{cy})  @ you  A-Z npc  a-z monster  ╬ structure  + door  T/*/~/% resource\n",
            style="dim",
        )
        for row in range(map_h):
            for col in range(width):
                world_x = cx + col - half_w
                world_y = cy + row - half_h
                if col == half_w and row == half_h:
                    text.append(PLAYER_GLYPH, style=PLAYER_COLOR)
                    continue
                cell = self._tile_index.get((world_x, world_y))
                if cell is not None:
                    glyph, color = cell
                    text.append(glyph, style=color)
                elif (world_x, world_y) in self._known_tiles:
                    text.append(WALKABLE_GLYPH, style=WALKABLE_COLOR)
                else:
                    text.append(UNMAPPED_GLYPH)
            if row != map_h - 1:
                text.append("\n")
        return text
```

(Note: no trailing newline after the last map row, matching the current behavior; the header always ends with `\n`. When `map_h <= 0` the loop body is skipped and only the header line is returned.)

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_tui/test_map_pane.py -k "Dimensions or centered or header_only or world_offset" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): parameterize map viewport by width/height, center the player"
```

---

## Task 2: `render()` sizes from the pane, with fallback; `on_resize` refreshes

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane.py`

- [ ] **Step 1: Write the failing tests**

```python
class TestRenderSizing:
    def test_render_uses_pane_size(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        # Simulate a laid-out pane size (Textual Size has .width/.height).
        from textual.geometry import Size
        pane._size = Size(30, 12)  # render() reads self.size
        lines = pane.render().plain.split("\n")
        assert len(lines) == 12
        assert all(len(row) == 30 for row in lines[1:])

    def test_render_falls_back_when_size_zero(self):
        pane = MapPane(_gd_typed())
        pane.update_snapshot(_snap(0, 0))
        from textual.geometry import Size
        pane._size = Size(0, 0)
        lines = pane.render().plain.split("\n")
        assert len(lines) == VIEWPORT_H                  # 21 fallback
        assert all(len(row) == VIEWPORT_W for row in lines[1:])

    def test_render_no_snapshot_waiting(self):
        pane = MapPane(_gd_typed())
        assert "Waiting" in pane.render().plain
```

NOTE: confirm how to set the size in a no-app unit test. `Static.size` is a property derived from the widget's region. First check what attribute backs it: run `uv run python -c "import inspect, textual.widget as w; print(inspect.getsource(w.Widget.size.fget))"`. If `size` reads `self._size`/`self.region`, set that in the test (e.g. `pane._size = Size(...)` or monkeypatch `type(pane).size`). If it cannot be set without an app, instead `monkeypatch.setattr(type(pane), "size", Size(30,12))` via a `property`/`PropertyMock`, or test `render()` by monkeypatching a tiny helper. Pick the approach that works against the installed Textual version; keep the asserted behavior identical.

- [ ] **Step 2: Run, confirm FAIL**

Run: `uv run pytest tests/test_tui/test_map_pane.py -k "Sizing" -v`
Expected: FAIL — `render()` still draws fixed `VIEWPORT_W/H` (line count 21 even when size is 30×12).

- [ ] **Step 3: Implement size resolution + resize refresh**

In `map_pane.py`, replace `render()` and add `on_resize`:

```python
    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or VIEWPORT_W
        height = self.size.height or VIEWPORT_H
        return self._render_viewport(snap, width, height)

    def on_resize(self, event: object) -> None:
        """Recompute the grid whenever the pane is resized."""
        self.refresh()
```

(`self.size.width`/`.height` are `0` before layout; `or VIEWPORT_W/VIEWPORT_H` supplies the fallback.) Update the class docstring from "VIEWPORT_W x VIEWPORT_H grid" to "a grid that fills the pane, centered on the player."

- [ ] **Step 4: Run, confirm PASS**

Run: `uv run pytest tests/test_tui/test_map_pane.py -k "Sizing" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py
git commit -m "feat(tui): map fills the pane and re-renders on resize"
```

---

## Task 3: Update remaining existing tests + verify

**Files:**
- Modify: `tests/test_tui/test_map_pane.py`
- Test: same

- [ ] **Step 1: Find stale callers**

Run: `grep -n "_render_viewport(" tests/test_tui/test_map_pane.py`
Any call still using the 1-arg form `_render_viewport(snap)` must pass dimensions, e.g. `_render_viewport(snap, VIEWPORT_W, VIEWPORT_H)`. Existing tests that asserted "22 lines" / "41-wide rows" / "no trailing blank" should now assert against `VIEWPORT_H`/`VIEWPORT_W` explicitly (1 header + `VIEWPORT_H-1` rows = `VIEWPORT_H` lines).

- [ ] **Step 2: Update them, run the file**

Run: `uv run pytest tests/test_tui/test_map_pane.py -q`
Expected: all pass.

- [ ] **Step 3: Full verification**

Run: `uv run pytest -q` → all pass, 0 skipped.
Run: `uv run pytest --cov=artifactsmmo_cli.tui.widgets.map_pane --cov-report=term-missing -q` → `map_pane.py` 100% (add a test for any missed branch, e.g. `width<=0`).
Run: `uv run ruff check src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane.py` → clean. `uv run mypy src/artifactsmmo_cli/tui/widgets/map_pane.py` → no new errors.

- [ ] **Step 4: Commit**

```bash
git add tests/test_tui/test_map_pane.py
git commit -m "test(tui): update map tests for dynamic viewport sizing"
```

---

## Self-review notes
- Spec coverage: sizing from `self.size` + fallback (Task 2), centering & full-fill (Task 1), `on_resize` refresh (Task 2), pure `_render_viewport(snap,w,h)` (Task 1), edge cases h≤1/w≤0 (Task 1 ranges + Task 3 coverage), no-snapshot text (Task 2). All mapped.
- Type consistency: `_render_viewport(self, snap, width, height)` used identically in Tasks 1-3; `render()` calls it with resolved ints.
- Open implementation detail (flagged, not a placeholder): the exact way to inject `self.size` in a no-app unit test depends on the installed Textual version — Task 2 Step 1 gives a concrete command to determine it and two fallback approaches. The implementer resolves it before writing the test.
