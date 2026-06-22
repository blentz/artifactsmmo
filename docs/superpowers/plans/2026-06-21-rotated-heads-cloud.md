# Rotated Heads + Craft-by-Category + Thought Cloud Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rotate the swing head so the haft points at the player at every arc position, pick the craft tool by item category (cooking→sword, else→hammer), and add an animated 2-tile thought cloud while planning.

**Architecture:** Exact 90° rotation (`rot90cw`) + `oriented_head(ToolHeads, dcol, drow)` derive all 8 directions from a canonical up sprite + one hand-authored NE sprite per tool. `swing_overlay` orients the head per arc offset. `select_swing_head` returns a `ToolHeads` bundle chosen by activity/category. A `_planning_overlay` draws one cloud sprite + its `rot90cw` across two up-right tiles, swapping each second.

**Tech Stack:** Python 3.13, `uv`, Textual (`MapPane`), Rich, pytest.

## Global Constraints

- Use `uv run` for every Python command. Imports top-only; absolute; no `...` imports; no `if TYPE_CHECKING`; never catch `Exception`. One behavioral class per file (pure data/enum/function modules may group).
- Tests in `tests/`; gate = 0 errors/warnings/skips, 100% line coverage; carve-outs need a written justification comment. Run `uv run ruff check src/artifactsmmo_cli/tui` and `uv run mypy src/artifactsmmo_cli/tui` — both must be clean (the pre-commit hook only lints `ai/`, so check `tui/` explicitly).
- Sprites 8×8; transparent `"."`; palette keys defined (`validate_sprite`). Colors: `STEEL` medium grey, `STONE` light grey (#babdb6), `SLATE` dark grey (#6b6f6a), `BARK` handle, `BONE` white.
- Rotation is exact 90° only. Direction→`(base, turns)`: cardinals from `up` [(0,-1)→0, (1,0)→1, (0,1)→2, (-1,0)→3]; diagonals from `ne` [(1,-1)→0, (1,1)→1, (-1,1)→2, (-1,-1)→3]; `rot90cw` applied `turns` times.
- Craft tool: cooking → sword, every other craftable item → hammer, unknown item → no tool.
- Cloud: one `CLOUD_SPRITE`; second tile is `rot90cw(CLOUD_SPRITE)`; swap the two tiles each second (`int(now - _planning_start) % 2`). Cloud at tiles `(1,-1)`/`(2,-1)`; white dot stays in the player tile.

---

## File Structure

| File | Responsibility | Modify |
|---|---|---|
| `src/artifactsmmo_cli/tui/sprites.py` | `rot90cw`, `ToolHeads`, `oriented_head`, 4 NE heads + tool bundles, `CLOUD_SPRITE`/`CLOUD_SPRITE_R`; `gather_head`→bundle | Modify |
| `src/artifactsmmo_cli/tui/swing_frames.py` | `swing_overlay(mode, idx, tool)` orients per offset | Modify |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | `select_swing_head`→bundle + craft category; `_planning_start`/`_planning_overlay`/`_active_overlay` | Modify |
| `tests/test_tui/test_sprites_animation.py` | rot90cw/oriented_head/NE/bundle/cloud tests | Modify |
| `tests/test_tui/test_swing_frames.py` | swing_overlay(tool) tests | Modify |
| `tests/test_tui/test_map_pane_animation.py` | selection bundle + craft category + cloud overlay tests | Modify |

---

## Task 1: Rotation primitives + NE heads + cloud art (additive)

Purely additive to `sprites.py` — nothing is rewired yet, so the build stays green.

**Files:** Modify `src/artifactsmmo_cli/tui/sprites.py`; Test `tests/test_tui/test_sprites_animation.py`.

**Interfaces — Produces:**
- `rot90cw(sprite: Sprite) -> Sprite`
- `ToolHeads` (frozen dataclass: `up: Sprite`, `ne: Sprite`)
- `oriented_head(tool: ToolHeads, dcol: int, drow: int) -> Sprite`
- `AXE_NE`, `PICKAXE_NE`, `HAMMER_NE`, `FIGHT_NE: Sprite`
- `AXE`, `PICKAXE`, `HAMMER`, `SWORD: ToolHeads`
- `CLOUD_SPRITE`, `CLOUD_SPRITE_R: Sprite`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_sprites_animation.py
from artifactsmmo_cli.tui.sprites import (
    AXE, AXE_HEAD, AXE_NE, CLOUD_SPRITE, CLOUD_SPRITE_R, FIGHT_HEAD, HAMMER, HAMMER_NE,
    PICKAXE, PICKAXE_NE, SWORD, FIGHT_NE, ToolHeads, oriented_head, rot90cw, validate_sprite,
)


def test_rot90cw_four_turns_is_identity():
    s = AXE_HEAD
    r = s
    for _ in range(4):
        r = rot90cw(r)
    assert r.rows == s.rows


def test_rot90cw_moves_top_row_to_right_column():
    # a sprite with only its top row filled -> after one CW turn only the right column is filled
    s = Sprite(rows=("mmmmmmmm",) + ("........",) * 7, palette={"m": "#888a85"})
    r = rot90cw(s)
    assert all(row[7] == "m" for row in r.rows)
    assert all(row[:7] == "......." for row in r.rows)


def test_oriented_head_cardinals_and_diagonals():
    t = AXE
    assert oriented_head(t, 0, -1).rows == AXE_HEAD.rows               # up = base
    assert oriented_head(t, 1, 0).rows == rot90cw(AXE_HEAD).rows       # right = 1 CW
    assert oriented_head(t, 0, 1).rows == rot90cw(rot90cw(AXE_HEAD)).rows   # down = 2
    assert oriented_head(t, 1, -1).rows == AXE_NE.rows                 # NE = ne base
    assert oriented_head(t, 1, 1).rows == rot90cw(AXE_NE).rows         # SE = ne 1 CW


def test_ne_heads_and_bundles_valid():
    for name, s in [("axe_ne", AXE_NE), ("pick_ne", PICKAXE_NE),
                    ("ham_ne", HAMMER_NE), ("sword_ne", FIGHT_NE)]:
        validate_sprite(name, s)
    assert AXE == ToolHeads(AXE_HEAD, AXE_NE)
    assert SWORD == ToolHeads(FIGHT_HEAD, FIGHT_NE)


def test_cloud_sprites_valid_with_shadow():
    validate_sprite("cloud", CLOUD_SPRITE)
    assert CLOUD_SPRITE_R.rows == rot90cw(CLOUD_SPRITE).rows
    dark = sum(ch == "d" for row in CLOUD_SPRITE.rows for ch in row)
    light = sum(ch == "l" for row in CLOUD_SPRITE.rows for ch in row)
    assert dark >= 6 and light >= dark            # bumpy body + doubled shadow
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -k "rot90 or oriented or ne_heads or cloud" -v`
Expected: FAIL (names undefined).

- [ ] **Step 3: Implement** (append after `gather_head` in `sprites.py`; add `SLATE` to the palette import if missing — it is already imported)

```python
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

# Thought cloud: light-grey bubbly rounded rectangle with doubled dark-grey shading.
# The second cloud tile is this rotated 90° (asymmetric -> irregular).
CLOUD_SPRITE: Sprite = Sprite(
    rows=("..llll..", ".llllll.", "llldllll", "lldddlll", "llldddll", ".lddll..",
          "..llll..", "........"),
    palette={"l": STONE, "d": SLATE},
)
CLOUD_SPRITE_R: Sprite = rot90cw(CLOUD_SPRITE)
```

Confirm `dataclass` is imported (it is, for `Sprite`) and `SLATE` is in the palette import (`grep -n "SLATE" src/artifactsmmo_cli/tui/sprites.py`; add to the `from ...palette import (...)` list if absent).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -k "rot90 or oriented or ne_heads or cloud" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites_animation.py
git commit -m "feat(tui): rot90cw + oriented_head + ToolHeads + NE heads + cloud art"
```

---

## Task 2: Wire rotation + craft-by-category (atomic signature migration)

This rewires `gather_head`, `swing_overlay`, and `select_swing_head` to bundles in one commit (pre-commit's all-files mypy requires the migration be atomic).

**Files:** Modify `sprites.py`, `swing_frames.py`, `map_pane.py`; Tests `test_swing_frames.py`, `test_map_pane_animation.py`.

**Interfaces:**
- Consumes: `ToolHeads`, `oriented_head`, `AXE`, `PICKAXE`, `HAMMER`, `SWORD` (Task 1).
- Produces: `gather_head(skill) -> ToolHeads`; `swing_overlay(mode, frame_index, tool: ToolHeads) -> dict`; `select_swing_head(mode, action_target, game_data) -> ToolHeads | None`. Removes `_is_bar`.

- [ ] **Step 1: Write the failing test** (replace the existing swing_overlay + selection tests)

```python
# tests/test_tui/test_swing_frames.py — replace the swing_overlay block
from artifactsmmo_cli.tui.swing_frames import swing_overlay
from artifactsmmo_cli.tui.sprites import HAMMER, PICKAXE, oriented_head


def test_non_swing_modes_have_no_overlay():
    for m in (Mode.IDLE, Mode.GLIDE, Mode.PLANNING):
        assert swing_overlay(m, 0, PICKAXE) == {}


def test_swing_overlay_places_oriented_head():
    ov = swing_overlay(Mode.GATHER_SWING, 2, HAMMER)        # frame 2 -> (1,0)
    assert ov[(1, 0)].rows == oriented_head(HAMMER, 1, 0).rows
    assert (0, 0) in ov
    ne = swing_overlay(Mode.GATHER_SWING, 1, HAMMER)        # frame 1 -> (1,-1) diagonal
    assert ne[(1, -1)].rows == oriented_head(HAMMER, 1, -1).rows


def test_fight_overlay_oriented_on_left():
    ov = swing_overlay(Mode.FIGHT_SWING, 2, PICKAXE)        # frame 2 -> (-1,0)
    assert ov[(-1, 0)].rows == oriented_head(PICKAXE, -1, 0).rows
    assert (0, 0) in ov


def test_gather_arc_order_and_index_wrap():
    expected = [(0, -1), (1, -1), (1, 0), (1, 1), (0, 1)]
    arc = [next(off for off in swing_overlay(Mode.GATHER_SWING, i, PICKAXE) if off != (0, 0))
           for i in range(5)]
    assert arc == expected
    assert (swing_overlay(Mode.GATHER_SWING, 5, PICKAXE)
            == swing_overlay(Mode.GATHER_SWING, 0, PICKAXE))
```

```python
# tests/test_tui/test_map_pane_animation.py — replace the head-import line and the
# select_swing_head / _is_bar tests
from artifactsmmo_cli.tui.sprites import (
    PLAYER_SPRITE, PLANNING_SPRITE, AXE, PICKAXE, HAMMER, SWORD,
)
from artifactsmmo_cli.tui.widgets.map_pane import select_swing_head
from artifactsmmo_cli.tui.swing_frames import Mode


class _Stats:
    def __init__(self, crafting_skill):
        self.crafting_skill = crafting_skill


class _GD:
    def __init__(self, skills=None, items=None):
        self._skills = skills or {}
        self._items = items or {}            # code -> crafting_skill
    def resource_skill_level(self, code):
        return self._skills.get(code)
    def item_stats(self, code):
        return _Stats(self._items[code]) if code in self._items else None


def test_select_head_gather_by_skill_returns_bundle():
    gd = _GD(skills={"ash_tree": ("woodcutting", 1), "copper_rocks": ("mining", 1)})
    assert select_swing_head(Mode.GATHER_SWING, "ash_tree", gd) is AXE
    assert select_swing_head(Mode.GATHER_SWING, "copper_rocks", gd) is PICKAXE
    assert select_swing_head(Mode.GATHER_SWING, "shrimp", gd) is PICKAXE          # fallback
    assert select_swing_head(Mode.GATHER_SWING, None, gd) is PICKAXE


def test_select_head_fight_is_sword_bundle():
    assert select_swing_head(Mode.FIGHT_SWING, "chicken", _GD()) is SWORD


def test_select_head_craft_cooking_sword_else_hammer():
    gd = _GD(items={"cooked_chicken": "cooking", "copper_bar": "mining",
                    "copper_boots": "gearcrafting"})
    assert select_swing_head(Mode.CRAFT_SWING, "cooked_chicken", gd) is SWORD
    assert select_swing_head(Mode.CRAFT_SWING, "copper_bar", gd) is HAMMER
    assert select_swing_head(Mode.CRAFT_SWING, "copper_boots", gd) is HAMMER
    assert select_swing_head(Mode.CRAFT_SWING, "unknown", gd) is None             # no stats
    assert select_swing_head(Mode.IDLE, "copper_bar", gd) is None
```

Update `test_swing_overlay_gather_axe_when_not_gliding` and `test_render_viewport_overlay_changes_neighbor_tile` to use bundles: build `p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})` and assert `ov[(1,0)].rows == oriented_head(AXE, 1, 0).rows`; pass an oriented head to `_render_viewport` (e.g. `{(1, 0): oriented_head(AXE, 1, 0)}`). Remove `test_is_bar` and the `_is_bar` import (the helper is deleted).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_swing_frames.py tests/test_tui/test_map_pane_animation.py -q --no-cov`
Expected: FAIL (signatures/`_is_bar`).

- [ ] **Step 3: Implement**

(a) `sprites.py` `gather_head` → bundle:
```python
def gather_head(skill: str | None) -> ToolHeads:
    """The gather tool for a resource's skill: woodcutting -> axe, else -> pickaxe."""
    if skill == "woodcutting":
        return AXE
    return PICKAXE
```

(b) `swing_frames.py` — import `ToolHeads, oriented_head` (drop `Sprite` if now unused — keep it if the return annotation needs it; it does, for the dict value type, so keep `Sprite`); rewrite:
```python
from artifactsmmo_cli.tui.sprites import Sprite, ToolHeads, grip_overlay, oriented_head
```
```python
def swing_overlay(mode: Mode, frame_index: int, tool: ToolHeads) -> dict[tuple[int, int], Sprite]:
    """Overlay map for a swing frame: the tool head ORIENTED toward the arc offset
    (haft trailing to the player) + a grip in the player tile. {} for non-swing modes."""
    if mode is Mode.FIGHT_SWING:
        offsets = _FIGHT_OFFSETS
    elif mode in (Mode.GATHER_SWING, Mode.CRAFT_SWING):
        offsets = _GATHER_OFFSETS
    else:
        return {}
    off = offsets[frame_index % len(offsets)]
    return {(0, 0): grip_overlay(off[0], off[1]), off: oriented_head(tool, off[0], off[1])}
```

(c) `map_pane.py` — remove `_is_bar`; rewrite `select_swing_head` to return a bundle; update imports (drop `AXE_HEAD`-style head constants no longer used; import the bundles + `ToolHeads`):
```python
from artifactsmmo_cli.tui.sprites import (
    AXE, BLANK_SPRITE, HAMMER, PICKAXE, PLANNING_SPRITE, PLAYER_SPRITE, SWORD, Sprite,
    SpriteCategory, ToolHeads, gather_head, overlay_sprites,
)
```
```python
def select_swing_head(mode: Mode, action_target: str | None, game_data: GameData) -> ToolHeads | None:
    """The tool bundle for a swing mode + target, or None when no tool shows:
    gather -> axe/pickaxe by the resource's skill; fight -> sword; craft -> sword for
    cooking else hammer (unknown item -> None)."""
    if mode is Mode.GATHER_SWING:
        skill_req = game_data.resource_skill_level(action_target) if action_target else None
        return gather_head(skill_req[0] if skill_req is not None else None)
    if mode is Mode.FIGHT_SWING:
        return SWORD
    if mode is Mode.CRAFT_SWING:
        stats = game_data.item_stats(action_target) if action_target else None
        if stats is None:
            return None
        return SWORD if stats.crafting_skill == "cooking" else HAMMER
    return None
```
`_swing_overlay`'s body is unchanged (it already calls `select_swing_head` then `swing_overlay(mode, idx, head)`; `head` is now a `ToolHeads`, which `swing_overlay` now expects). `gather_head` is no longer imported by tests of map_pane; keep its import in map_pane only if referenced — it is not (select uses bundles), so do NOT import `gather_head` into map_pane unless used. (select_swing_head calls `gather_head` — keep the import.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/ -q --no-cov` → PASS.

- [ ] **Step 5: ruff + mypy on tui**

Run: `uv run ruff check src/artifactsmmo_cli/tui && uv run mypy src/artifactsmmo_cli/tui`
Expected: clean. (Fix any unused-import F401 — e.g. a head constant no longer referenced.)

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py src/artifactsmmo_cli/tui/swing_frames.py src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_swing_frames.py tests/test_tui/test_map_pane_animation.py
git commit -m "feat(tui): orient swing head per arc offset; craft tool by category"
```

---

## Task 3: Animated thought-cloud overlay

**Files:** Modify `map_pane.py`; Test `test_map_pane_animation.py`.

**Interfaces:**
- Consumes: `CLOUD_SPRITE`, `CLOUD_SPRITE_R` (Task 1).
- Produces: `MapPane._planning_start: float`; `MapPane._planning_overlay(now) -> dict`; `MapPane._active_overlay(now) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_map_pane_animation.py
from artifactsmmo_cli.tui.sprites import CLOUD_SPRITE, CLOUD_SPRITE_R


def test_planning_overlay_two_tiles_swap_each_second():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._planning_active = True
    p._planning_start = 0.0
    f0 = p._planning_overlay(now=0.5)                 # second 0
    assert f0 == {(1, -1): CLOUD_SPRITE, (2, -1): CLOUD_SPRITE_R}
    f1 = p._planning_overlay(now=1.5)                 # second 1 -> swapped
    assert f1 == {(1, -1): CLOUD_SPRITE_R, (2, -1): CLOUD_SPRITE}
    f2 = p._planning_overlay(now=2.5)                 # second 2 -> back
    assert f2 == f0


def test_planning_overlay_empty_when_not_planning():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._planning_active = False
    assert p._planning_overlay(now=1.0) == {}


def test_set_planning_stamps_start_once(monkeypatch):
    p = _pane()
    monkeypatch.setattr("artifactsmmo_cli.tui.widgets.map_pane.time.monotonic", lambda: 10.0)
    p.set_planning(True)
    assert p._planning_start == 10.0
    monkeypatch.setattr("artifactsmmo_cli.tui.widgets.map_pane.time.monotonic", lambda: 20.0)
    p.set_planning(True)                              # already planning -> not re-stamped
    assert p._planning_start == 10.0
    p.set_planning(False)


def test_active_overlay_picks_planning_then_swing():
    p = _pane()
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = []
    # planning active -> cloud
    p._planning_active = True
    p._planning_start = 0.0
    assert (1, -1) in p._active_overlay(now=0.5)
    # planning off -> swing head
    p._planning_active = False
    ov = p._active_overlay(now=0.35)
    assert (1, 0) in ov
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -k "planning_overlay or set_planning_stamps or active_overlay" -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

(a) Import the cloud sprites (add to the sprites import in map_pane.py): `CLOUD_SPRITE, CLOUD_SPRITE_R`.

(b) `__init__`: add `self._planning_start = 0.0`.

(c) `set_planning` — stamp the start only on the rising edge:
```python
    def set_planning(self, active: bool) -> None:
        if active and not self._planning_active:
            self._planning_start = time.monotonic()
        self._planning_active = active
        self.refresh()
```

(d) New overlays:
```python
    def _planning_overlay(self, now: float) -> dict[tuple[int, int], Sprite]:
        if not self._planning_active:
            return {}
        if int(now - self._planning_start) % 2 == 0:
            return {(1, -1): CLOUD_SPRITE, (2, -1): CLOUD_SPRITE_R}
        return {(1, -1): CLOUD_SPRITE_R, (2, -1): CLOUD_SPRITE}

    def _active_overlay(self, now: float) -> dict[tuple[int, int], Sprite]:
        if self._planning_active:
            return self._planning_overlay(now)
        return self._swing_overlay(now)
```

(e) `render` — use `_active_overlay`:
```python
        return self._render_viewport(
            snap, width, height, center, self._player_sprite(now), self._active_overlay(now)
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -q --no-cov` → PASS.

- [ ] **Step 5: TUI suite + coverage**

Run: `uv run pytest tests/test_tui/ -q --no-cov` → PASS; then
`uv run pytest tests/test_tui/ --cov=src/artifactsmmo_cli/tui/widgets/map_pane --cov=src/artifactsmmo_cli/tui/sprites --cov=src/artifactsmmo_cli/tui/swing_frames --cov-report=term-missing` → 100%. If `_active_overlay`'s swing branch or `_planning_overlay`'s odd-second branch is uncovered, the Task-3 tests above already exercise both; add a focused case if term-missing flags a line.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane_animation.py
git commit -m "feat(tui): animated 2-tile thought cloud (swap each second) while planning"
```

---

## Task 4: Full gate + manual smoke

**Files:** none.

- [ ] **Step 1:** `uv run pytest -q` → 100% coverage, all pass.
- [ ] **Step 2:** `uv run mypy src/artifactsmmo_cli/tui` → clean; `uv run ruff check src/artifactsmmo_cli/tui` → clean.
- [ ] **Step 3 (smoke):** `uv run artifactsmmo play Robby` — the swing tool's haft points at the player through the whole arc; cooking shows the sword, other crafts the hammer; while the planner thinks, a two-tile cloud drifts up-right of the player (swapping each second) alongside the white dot.

---

## Self-Review

**Spec coverage:** rotation helpers + oriented heads + bundles → Task 1+2; `swing_overlay` orients → Task 2; craft cooking→sword/else→hammer (remove `_is_bar`) → Task 2; gather/fight unchanged behavior with bundles → Task 2; cloud 1-sprite + rot90 second tile + swap each second + `_planning_start` rising-edge + 2-tile overlay + dot kept + `_active_overlay` chooser → Task 3; 100% coverage + ruff/mypy → every task + Task 4. ✓

**Placeholder scan:** none — full code, exact sprite rows, concrete test doubles.

**Type consistency:** `ToolHeads`/`oriented_head`/`rot90cw` (T1) consumed by `swing_overlay(…, tool: ToolHeads)` and `select_swing_head(...) -> ToolHeads | None` (T2); `gather_head(str|None) -> ToolHeads` (T2) used by `select_swing_head`; `CLOUD_SPRITE`/`CLOUD_SPRITE_R` (T1) used by `_planning_overlay` (T3); `_active_overlay` calls `_swing_overlay` (unchanged) and `_planning_overlay` (T3). `item_stats(code).crafting_skill` matches the real `ItemStats`.
