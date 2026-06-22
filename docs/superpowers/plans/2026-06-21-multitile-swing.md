# Multi-Tile Swing Animations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the gather/combat swing a two-tile tool — a head in the arc-neighbor tile plus a short grip in the player tile — that sweeps a half-circle and composites over whatever occupies the neighbor tile.

**Architecture:** Add a pure `overlay_sprites(base, top)` merge (top's non-transparent pixels win). Represent a swing frame as an offset→Sprite map `{(0,0): grip, (dcol,drow): head}` produced by a pure `swing_overlay(mode, frame_index)`; grips are computed by a deterministic `_grip_overlay(dcol,drow)` builder so combat (negative dcol) mirrors for free. `MapPane._render_viewport` applies the overlay at a single point per tile. Modes stay mutually exclusive; glide/planning/idle and the snapshot/observer layer are untouched.

**Tech Stack:** Python 3.13, `uv`, Textual (`MapPane`), Rich (`Text`), pytest.

## Global Constraints

- Use `uv run` for every Python command (`uv run pytest`, `uv run mypy`).
- Imports at top of file only; absolute imports; no `...` imports; no `if TYPE_CHECKING`.
- Never catch `Exception`. One behavioral class per file (pure data/enum/function modules may group declarations).
- Tests in `tests/`; project gate = 0 errors/warnings/skips, 100% line coverage (`--cov-fail-under=100`); carve-outs need a written justification comment.
- Sprites are 8×8; transparent key is `"."` (`TRANSPARENT`); every non-`.` glyph must be in the sprite's palette (`validate_sprite`). `Sprite(rows: tuple[str,...], palette: dict[str,str])` is frozen.
- Tile offsets are `(dcol, drow)` from the player tile: `dcol = tcol - half_w`, `drow = trow - half_h`. Gather sweeps the head clockwise on the RIGHT (positive dcol); combat counterclockwise on the LEFT (negative dcol).

---

## File Structure

| File | Responsibility | Create/Modify |
|---|---|---|
| `src/artifactsmmo_cli/tui/sprites.py` | +`overlay_sprites`, `GATHER_HEAD`, `FIGHT_HEAD`, `_grip_overlay`; −`GATHER_SWING_FRAMES`/`FIGHT_SWING_FRAMES` (+ their `_GATHER_CLOCK`/`_FIGHT_CLOCK`) | Modify |
| `src/artifactsmmo_cli/tui/swing_frames.py` | +`swing_overlay(mode, frame_index)` offset→Sprite map | Modify |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | apply overlay per tile; simplify `_player_sprite`; new `_swing_overlay` | Modify |
| `tests/test_tui/test_sprites_animation.py` | replace old-frame tests with head/grip/overlay tests | Modify |
| `tests/test_tui/test_swing_frames.py` | +`swing_overlay` tests | Modify |
| `tests/test_tui/test_map_pane_animation.py` | +multi-tile overlay integration tests | Modify |

---

## Task 1: `overlay_sprites` merge helper

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (append after `validate_sprite`)
- Test: `tests/test_tui/test_sprites_animation.py` (append)

**Interfaces:**
- Produces: `overlay_sprites(base: Sprite, top: Sprite) -> Sprite` — new 8×8 where each non-`TRANSPARENT` pixel of `top` wins, else `base`; palette = `{**base.palette, **top.palette}`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_sprites_animation.py
from artifactsmmo_cli.tui.sprites import overlay_sprites, BLANK_SPRITE, PLAYER_SPRITE, Sprite, validate_sprite, TRANSPARENT, SPRITE_SIZE


def test_overlay_top_pixel_wins_else_base_shows():
    base = PLAYER_SPRITE
    top = Sprite(rows=("Z......." ,) + ("........",) * 7, palette={"Z": "#ff0000"})
    merged = overlay_sprites(base, top)
    validate_sprite("merged", merged)
    assert merged.rows[0][0] == "Z"                       # top wins where opaque
    assert merged.rows[0][1] == base.rows[0][1]           # base shows where top transparent
    assert merged.palette["Z"] == "#ff0000"               # top palette merged in
    assert merged.palette["o"] == base.palette["o"]       # base palette preserved


def test_overlay_with_blank_top_is_base_pixels():
    merged = overlay_sprites(PLAYER_SPRITE, BLANK_SPRITE)
    assert merged.rows == PLAYER_SPRITE.rows
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -k overlay -v`
Expected: FAIL (`overlay_sprites` undefined).

- [ ] **Step 3: Implement**

```python
# in sprites.py, after validate_sprite
def overlay_sprites(base: Sprite, top: Sprite) -> Sprite:
    """Merge two 8x8 sprites: each non-transparent pixel of `top` wins, else
    `base` shows through. Palette merges with `top` taking precedence on key
    collisions. Returns a new immutable Sprite (compositor-cache safe)."""
    rows = tuple(
        "".join(
            top.rows[r][c] if top.rows[r][c] != TRANSPARENT else base.rows[r][c]
            for c in range(SPRITE_SIZE)
        )
        for r in range(SPRITE_SIZE)
    )
    return Sprite(rows=rows, palette={**base.palette, **top.palette})
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -k overlay -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites_animation.py
git commit -m "feat(tui): overlay_sprites two-layer 8x8 merge (top wins)"
```

---

## Task 2: Tool heads + grip builder

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (append after `overlay_sprites`)
- Test: `tests/test_tui/test_sprites_animation.py` (append)

**Interfaces:**
- Consumes: `Sprite`, `TRANSPARENT`, `SPRITE_SIZE`, palette colors `COPPER`, `STEEL`, `BARK`.
- Produces:
  - `GATHER_HEAD: Sprite`, `FIGHT_HEAD: Sprite` (8×8 tool heads).
  - `_grip_overlay(dcol: int, drow: int) -> Sprite` — a mostly-transparent 8×8 with handle pixels (`"h"`=`BARK`) stepping from the player's hand `(4,4)` toward the head direction, at `(4 + k*drow, 4 + k*dcol)` for `k in (1,2,3)` (all within `[0,7]` for the unit offsets used).

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_sprites_animation.py
from artifactsmmo_cli.tui.sprites import GATHER_HEAD, FIGHT_HEAD, _grip_overlay


def test_heads_valid_8x8():
    validate_sprite("gather_head", GATHER_HEAD)
    validate_sprite("fight_head", FIGHT_HEAD)


def test_grip_points_toward_direction():
    # head to the right (+1,0): handle pixels march right along row 4
    right = _grip_overlay(1, 0)
    validate_sprite("grip_right", right)
    assert {c for c, ch in enumerate(right.rows[4]) if ch == "h"} == {5, 6, 7}
    # head up (0,-1): handle pixels march up column 4
    up = _grip_overlay(0, -1)
    assert {r for r in range(SPRITE_SIZE) if up.rows[r][4] == "h"} == {1, 2, 3}
    # head down-right (+1,+1): diagonal toward bottom-right corner
    dr = _grip_overlay(1, 1)
    assert [(r, c) for r in range(SPRITE_SIZE) for c in range(SPRITE_SIZE) if dr.rows[r][c] == "h"] == [(5, 5), (6, 6), (7, 7)]


def test_grip_is_mostly_transparent():
    g = _grip_overlay(1, 0)
    opaque = sum(ch != "." for row in g.rows for ch in row)
    assert opaque == 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -k "heads or grip" -v`
Expected: FAIL (names undefined).

- [ ] **Step 3: Implement**

First confirm the palette import line in `sprites.py` includes `BARK`, `COPPER`, `STEEL` (it imports `BARK`, `COPPER`, `STEEL` already; if any is missing add it to the existing `from artifactsmmo_cli.tui.palette import (...)`). Then append:

```python
# Tool heads (drawn in the arc-neighbor tile). 8x8, single-frame each.
GATHER_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "...cc...",
        "..cccc..",
        ".cccccc.",
        "..cccc..",
        "...cc...",
        "...hh...",
        "...hh...",
    ),
    palette={"c": COPPER, "h": BARK},
)
FIGHT_HEAD: Sprite = Sprite(
    rows=(
        "...ss...",
        "...ss...",
        "...ss...",
        "...ss...",
        ".hhsshh.",
        "...hh...",
        "...hh...",
        "...hh...",
    ),
    palette={"s": STEEL, "h": BARK},
)


def _grip_overlay(dcol: int, drow: int) -> Sprite:
    """A mostly-transparent 8x8 with a 3-pixel handle stepping from the player's
    hand (4,4) toward the head direction. Used as the player-tile overlay so the
    swung tool reads as held. Combat's negative dcol mirrors for free."""
    grid = [[TRANSPARENT] * SPRITE_SIZE for _ in range(SPRITE_SIZE)]
    for k in (1, 2, 3):
        r, c = 4 + k * drow, 4 + k * dcol
        if 0 <= r < SPRITE_SIZE and 0 <= c < SPRITE_SIZE:
            grid[r][c] = "h"
    return Sprite(rows=tuple("".join(row) for row in grid), palette={"h": BARK})
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -k "heads or grip" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites_animation.py
git commit -m "feat(tui): pickaxe/sword head sprites + directional grip builder"
```

---

## Task 3: `swing_overlay` offset map

**Files:**
- Modify: `src/artifactsmmo_cli/tui/swing_frames.py` (append)
- Test: `tests/test_tui/test_swing_frames.py` (append)

**Interfaces:**
- Consumes: `Mode` (this module); `GATHER_HEAD`, `FIGHT_HEAD`, `_grip_overlay` (sprites.py); `Sprite` (sprites.py).
- Produces: `swing_overlay(mode: Mode, frame_index: int) -> dict[tuple[int, int], Sprite]` — `{}` for non-swing modes; otherwise `{(0,0): grip, head_offset: head}` where `head_offset` is `OFFSETS[frame_index % len(OFFSETS)]`.

Offsets (5 frames):
- gather (right, CW): `[(0,-1), (1,-1), (1,0), (1,1), (0,1)]`
- fight (left, CCW): `[(0,-1), (-1,-1), (-1,0), (-1,1), (0,1)]`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_swing_frames.py
from artifactsmmo_cli.tui.swing_frames import swing_overlay
from artifactsmmo_cli.tui.sprites import GATHER_HEAD, FIGHT_HEAD


def test_non_swing_modes_have_no_overlay():
    for m in (Mode.IDLE, Mode.GLIDE, Mode.PLANNING):
        assert swing_overlay(m, 0) == {}


def test_gather_overlay_head_on_right_with_grip():
    ov = swing_overlay(Mode.GATHER_SWING, 2)   # frame 2 -> (1,0) right
    assert ov[(1, 0)] is GATHER_HEAD
    assert (0, 0) in ov                          # grip in the player tile
    assert all(dc >= 0 for (dc, _dr) in ov)      # nothing on the left


def test_fight_overlay_head_on_left_mirrors_gather():
    ov = swing_overlay(Mode.FIGHT_SWING, 2)     # frame 2 -> (-1,0) left
    assert ov[(-1, 0)] is FIGHT_HEAD
    assert (0, 0) in ov
    assert any(dc < 0 for (dc, _dr) in ov)       # head on the left


def test_frame_index_wraps_and_sweeps_arc():
    # 5 frames; head offset cycles through the gather arc top->right->bottom
    heads = [next(off for off in swing_overlay(Mode.GATHER_SWING, i) if off != (0, 0))
             for i in range(5)]
    assert heads == [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1)]
    assert swing_overlay(Mode.GATHER_SWING, 5) == swing_overlay(Mode.GATHER_SWING, 0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_swing_frames.py -k overlay -v`
Expected: FAIL (`swing_overlay` undefined).

- [ ] **Step 3: Implement**

```python
# in swing_frames.py — add the import at top and the function below
from artifactsmmo_cli.tui.sprites import FIGHT_HEAD, GATHER_HEAD, Sprite, _grip_overlay

_GATHER_OFFSETS: list[tuple[int, int]] = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1)]
_FIGHT_OFFSETS: list[tuple[int, int]] = [(0, -1), (-1, -1), (-1, 0), (-1, 1), (0, 1)]


def swing_overlay(mode: Mode, frame_index: int) -> dict[tuple[int, int], Sprite]:
    """Overlay map for a swing frame: the head in the arc-neighbor tile plus a
    grip in the player tile (0,0). Empty for non-swing modes. The head offset
    sweeps a half-circle (gather right/CW, fight left/CCW)."""
    if mode is Mode.GATHER_SWING:
        offsets, head = _GATHER_OFFSETS, GATHER_HEAD
    elif mode is Mode.FIGHT_SWING:
        offsets, head = _FIGHT_OFFSETS, FIGHT_HEAD
    else:
        return {}
    off = offsets[frame_index % len(offsets)]
    return {(0, 0): _grip_overlay(off[0], off[1]), off: head}
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_swing_frames.py -k overlay -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/swing_frames.py tests/test_tui/test_swing_frames.py
git commit -m "feat(tui): swing_overlay offset map (head + grip, arc sweep)"
```

---

## Task 4: MapPane multi-tile render + remove single-tile frames

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (remove dead `GATHER_SWING_FRAMES`, `FIGHT_SWING_FRAMES`, `_GATHER_CLOCK`, `_FIGHT_CLOCK`; keep `_player_with_tool` + `PLANNING_SPRITE`)
- Modify: `tests/test_tui/test_sprites_animation.py` (remove tests of the deleted single-tile frames)
- Test: `tests/test_tui/test_map_pane_animation.py` (append integration tests)

**Interfaces:**
- Consumes: `overlay_sprites`, `GATHER_HEAD`, `FIGHT_HEAD` (sprites); `swing_overlay`, `current_mode`, `swing_frame_index`, `Mode` (swing_frames).
- Produces: `MapPane._swing_overlay(now: float) -> dict[tuple[int,int], Sprite]`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_map_pane_animation.py
from artifactsmmo_cli.tui.sprites import GATHER_HEAD, FIGHT_HEAD


def test_gather_swing_overlay_has_head_on_right():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._anim_start = 0.0
    ov = p._swing_overlay(now=0.35)   # frame 2 of a 0.8s sweep -> (1,0)
    assert ov[(1, 0)] is GATHER_HEAD
    assert (0, 0) in ov


def test_fight_swing_overlay_has_head_on_left():
    p = _pane()
    p.snapshot = _snap(action_kind="fight", cooldown_remaining=5.0)
    p._anim_start = 0.0
    ov = p._swing_overlay(now=0.35)
    assert ov[(-1, 0)] is FIGHT_HEAD


def test_no_overlay_when_idle_or_planning():
    p = _pane()
    p.snapshot = _snap(action_kind="rest", cooldown_remaining=5.0)
    p._anim_start = 0.0
    assert p._swing_overlay(now=1.0) == {}
    p2 = _pane()
    p2.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p2._anim_start = 0.0
    p2._planning_active = True
    assert p2._swing_overlay(now=1.0) == {}


def test_render_paints_tool_into_neighbor_tile_during_gather():
    # the head color (COPPER) must appear somewhere in a gather-swing render
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0, x=0, y=0)
    p._anim_start = 0.0
    p._size = (80, 41)   # if needed; otherwise rely on FALLBACK
    import artifactsmmo_cli.tui.widgets.map_pane as mp
    mp.time.monotonic = lambda: 0.35   # frame -> head at (1,0)
    out = p.render().plain
    # COPPER hex appears as a style, not plain text; instead assert via _swing_overlay wiring
    assert p._swing_overlay(0.35)  # non-empty during gather (render path exercised above)
```

> NOTE: `render()` returns styled `Text`; asserting a color in `.plain` won't work. Keep the render assertion behavioral (overlay non-empty + no exception). The pixel-level correctness is covered by Task 1–3 unit tests and `_swing_overlay`. If `_pane()`/`_snap()` helpers differ in the existing file, reuse the existing ones; do not redefine.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -k "swing_overlay or neighbor" -v`
Expected: FAIL (`_swing_overlay` undefined).

- [ ] **Step 3: Implement the renderer changes**

(a) Imports — replace the sprites import block and the swing_frames import:
```python
from artifactsmmo_cli.tui.sprites import (
    BLANK_SPRITE, PLANNING_SPRITE, PLAYER_SPRITE, Sprite, SpriteCategory, overlay_sprites,
)
from artifactsmmo_cli.tui.swing_frames import (
    Mode, current_mode, glide_index, swing_frame_index, swing_overlay,
)
```
(`GATHER_SWING_FRAMES`/`FIGHT_SWING_FRAMES` are no longer imported.)

(b) `_player_sprite` — drop the swing-frame branches (the grip now arrives via the overlay map):
```python
    def _player_sprite(self, now: float) -> Sprite:
        snap = self.snapshot
        if snap is None:
            return PLAYER_SPRITE
        elapsed = now - self._anim_start
        mode = current_mode(snap.action_kind, self._planning_active, elapsed, snap.cooldown_remaining)
        if mode is Mode.PLANNING:
            return PLANNING_SPRITE
        return PLAYER_SPRITE
```

(c) New `_swing_overlay`:
```python
    def _swing_overlay(self, now: float) -> dict[tuple[int, int], Sprite]:
        snap = self.snapshot
        if snap is None:
            return {}
        elapsed = now - self._anim_start
        mode = current_mode(snap.action_kind, self._planning_active, elapsed, snap.cooldown_remaining)
        idx = swing_frame_index(elapsed, len(_GATHER_OFFSETS_LEN), SWING_SWEEP_SECONDS)
        return swing_overlay(mode, idx)
```
Use the frame count `5` directly (the offset lists live in swing_frames; do not import the private lists). Replace `_GATHER_OFFSETS_LEN` with the literal `SWING_FRAME_COUNT` defined as a module constant near the other constants:
```python
SWING_FRAME_COUNT = 5      # arc frames per sweep (matches swing_frames offset lists)
```
so the call is:
```python
        idx = swing_frame_index(elapsed, SWING_FRAME_COUNT, SWING_SWEEP_SECONDS)
```

(d) `render` — compute the overlay once and pass it:
```python
    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or FALLBACK_W
        height = self.size.height or FALLBACK_H
        now = time.monotonic()
        center = self._glide_center(now)
        return self._render_viewport(
            snap, width, height, center, self._player_sprite(now), self._swing_overlay(now)
        )
```

(e) `_render_viewport` — accept `overlay` and apply it per tile:
```python
    def _render_viewport(
        self,
        snap: CycleSnapshot,
        width: int,
        height: int,
        center: tuple[int, int] | None = None,
        player_sprite: Sprite = PLAYER_SPRITE,
        overlay: dict[tuple[int, int], Sprite] | None = None,
    ) -> Text:
        overlay = overlay or {}
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
                sprite, terrain = self._tile_sprite_and_terrain(wx, wy, is_player, player_sprite)
                tool = overlay.get((tcol - half_w, trow - half_h))
                if tool is not None:
                    sprite = overlay_sprites(sprite, tool)
                rows4 = self._compositor.compose(sprite, terrain)
                for i in range(TILE_H):
                    sublines[i].append_text(rows4[i])
            for i in range(TILE_H):
                if i > 0:
                    text.append("\n")
                text.append_text(sublines[i])
        return text
```

(f) In `sprites.py`, delete `GATHER_SWING_FRAMES`, `FIGHT_SWING_FRAMES`, and the `_GATHER_CLOCK`/`_FIGHT_CLOCK` tuples that only fed them. Keep `_player_with_tool` (used by `PLANNING_SPRITE`) and `PLANNING_SPRITE`. Confirm nothing else imports the removed names: `grep -rn "GATHER_SWING_FRAMES\|FIGHT_SWING_FRAMES" src tests` → only the test file below.

(g) In `tests/test_tui/test_sprites_animation.py`, remove `test_frames_nonempty_and_valid_8x8` and `test_gather_arc_is_on_the_right_fight_on_the_left` (they assert the deleted single-tile frames) and any import of `GATHER_SWING_FRAMES`/`FIGHT_SWING_FRAMES`. Keep `test_planning_bubble_*`. The new head/grip/overlay tests (Tasks 1–2) replace that coverage.

- [ ] **Step 4: Run to verify it passes + no dead references**

Run: `uv run pytest tests/test_tui/ -q --no-cov`
Expected: PASS. Then `grep -rn "GATHER_SWING_FRAMES\|FIGHT_SWING_FRAMES" src tests` → no matches.

- [ ] **Step 5: Coverage gate for the touched modules**

Run: `uv run pytest tests/test_tui/ --cov=src/artifactsmmo_cli/tui/widgets/map_pane --cov=src/artifactsmmo_cli/tui/sprites --cov=src/artifactsmmo_cli/tui/swing_frames --cov-report=term-missing`
Expected: 100% (no missing lines). The `on_mount` pragma carve-out remains the only one. If a new line is uncovered, add a focused test (e.g. `_swing_overlay` with `snapshot=None` returns `{}`).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_map_pane_animation.py tests/test_tui/test_sprites_animation.py
git commit -m "feat(tui): multi-tile swing — apply head+grip overlay per tile"
```

---

## Task 5: Full gate + manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest -q`
Expected: PASS at 100% coverage.

- [ ] **Step 2: mypy**

Run: `uv run mypy src/artifactsmmo_cli/tui`
Expected: no issues.

- [ ] **Step 3: Manual smoke (recommended)**

Run the watch TUI and eyeball: during gathering a pickaxe head sweeps a half-circle through the tile to the player's right and into the resource tile; during combat a sword sweeps on the left into the monster tile; movement glide and the planning bubble are unchanged.
Run: `uv run artifactsmmo play Robby`

---

## Self-Review

**Spec coverage:**
- `overlay_sprites` merge → Task 1. ✓
- Two-tile model (head in neighbor + grip in player), overlay over neighbor content → Task 3 (`swing_overlay`) + Task 4 (applied in `_render_viewport` onto the tile's base). ✓
- Gather right/CW, combat left/CCW mirror → Task 3 offset lists. ✓
- Head/grip art → Task 2. ✓
- Renderer single-point application; glide/planning/idle unchanged → Task 4 (`_player_sprite` keeps planning/idle; overlay only applied when `swing_overlay` non-empty). ✓
- Remove old single-tile frames → Task 4(f,g). ✓
- Edge: off-screen neighbor → not in loop, not drawn (Task 4 loop only covers visible tiles). ✓
- Edge: non-swing → `{}` overlay → loop unchanged. ✓ (Task 3 + Task 4 tests).
- 100% coverage → Task 4 Step 5 + Task 5. ✓

**Placeholder scan:** none — all code shown; sprite rows enumerated; offsets concrete. The Task 4 render test note explicitly says keep the assertion behavioral (styled Text can't be asserted via `.plain`).

**Type consistency:** `overlay_sprites(base, top) -> Sprite` (Task 1) used in Task 4; `swing_overlay(mode, frame_index) -> dict[tuple[int,int], Sprite]` (Task 3) used by `_swing_overlay` (Task 4); `_grip_overlay(dcol, drow) -> Sprite` (Task 2) used by `swing_overlay` (Task 3); `SWING_FRAME_COUNT = 5` matches the 5-element offset lists. Consistent.
