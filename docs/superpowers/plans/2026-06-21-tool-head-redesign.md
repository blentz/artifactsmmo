# Tool-Head Redesign + Craft Hammer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the comical copper gather head with real tool heads (axe/pickaxe/hammer), redesign the sword, select the head by what the bot is doing, add a hammer swing for bar crafts, and never show a tool while walking.

**Architecture:** New 8×8 head sprites + a pure `gather_head(skill)` map in `sprites.py`. `swing_overlay` becomes head-agnostic (takes the head sprite to place). A new `Mode.CRAFT_SWING` (CraftAction → `("craft", code)`). `MapPane` selects the head from action-kind + target + game_data via a testable module function `select_swing_head`, gates non-bar crafts and the walking case to `{}`.

**Tech Stack:** Python 3.13, `uv`, Textual (`MapPane`), Rich, pytest.

## Global Constraints

- Use `uv run` for every Python command (`uv run pytest`, `uv run mypy`).
- Imports at top only; absolute imports; no `...` imports; no `if TYPE_CHECKING`; never catch `Exception`.
- One behavioral class per file (pure data/enum/function modules may group declarations).
- Tests in `tests/`; project gate = 0 errors/warnings/skips, 100% line coverage (`--cov-fail-under=100`); carve-outs need a written justification comment.
- Sprites are 8×8; transparent key `"."` (`TRANSPARENT`); every non-`.` glyph in the palette (`validate_sprite`). Colors: medium-grey `STEEL = "#888a85"`, light-grey `STONE = "#babdb6"`, handle `BARK`.
- Selection rules: gather → woodcutting=axe, mining=pickaxe, else pickaxe (fishing/alchemy/unknown). combat → sword. craft → hammer **iff** the crafted item code ends `_bar` and exists; else no swing. No tool overlay while a glide is in progress.

---

## File Structure

| File | Responsibility | Create/Modify |
|---|---|---|
| `src/artifactsmmo_cli/tui/sprites.py` | new AXE/PICKAXE/HAMMER heads, redesigned FIGHT_HEAD, `gather_head(skill)`, grip 2px; remove GATHER_HEAD | Modify |
| `src/artifactsmmo_cli/ai/action_kind.py` | +`CraftAction → ("craft", code)` | Modify |
| `src/artifactsmmo_cli/tui/swing_frames.py` | +`Mode.CRAFT_SWING`, craft mapping, `swing_overlay(mode, frame_index, head)` | Modify |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | `select_swing_head` + `_is_bar` module fns; `_swing_overlay` rewrite (glide guard + selection) | Modify |
| `tests/test_tui/test_sprites_animation.py` | head art + gather_head + grip-2px tests | Modify |
| `tests/test_ai/test_action_kind.py` | +craft case | Modify |
| `tests/test_tui/test_swing_frames.py` | head-agnostic swing_overlay + craft mode tests | Modify |
| `tests/test_tui/test_map_pane_animation.py` | select_swing_head + walking-guard + _swing_overlay wiring | Modify |

---

## Task 1: New tool head sprites + gather_head + grip 2px

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py`
- Test: `tests/test_tui/test_sprites_animation.py`

**Interfaces:**
- Consumes: `Sprite`, `TRANSPARENT`, `SPRITE_SIZE`, palette `STEEL`, `STONE`, `BARK`.
- Produces: `AXE_HEAD`, `PICKAXE_HEAD`, `HAMMER_HEAD`, `FIGHT_HEAD` (redesigned sword: Sprite); `gather_head(skill: str | None) -> Sprite`. Removes `GATHER_HEAD`.

- [ ] **Step 1: Write the failing test**

Replace the head/grip tests in `tests/test_tui/test_sprites_animation.py` (keep the `overlay_*` and planning tests). New/changed tests:

```python
from artifactsmmo_cli.tui.sprites import (
    AXE_HEAD, PICKAXE_HEAD, HAMMER_HEAD, FIGHT_HEAD, gather_head,
    SPRITE_SIZE, TRANSPARENT, grip_overlay, validate_sprite,
)


def test_tool_heads_valid_8x8():
    for name, s in [("axe", AXE_HEAD), ("pickaxe", PICKAXE_HEAD),
                    ("hammer", HAMMER_HEAD), ("sword", FIGHT_HEAD)]:
        validate_sprite(name, s)


def test_hammer_has_no_light_grey():
    # hammer = pickaxe minus all light-grey ('l') pixels
    assert all("l" not in row for row in HAMMER_HEAD.rows)
    assert any("m" in row for row in HAMMER_HEAD.rows)


def test_pickaxe_has_light_grey_triangles_both_sides():
    cols = {c for r, row in enumerate(PICKAXE_HEAD.rows)
            for c, ch in enumerate(row) if ch == "l"}
    assert any(c < SPRITE_SIZE // 2 for c in cols)        # left triangle
    assert any(c >= SPRITE_SIZE // 2 for c in cols)       # right triangle


def test_sword_tip_is_light_grey_blade_medium():
    assert "l" in FIGHT_HEAD.rows[0]                       # light-grey tip
    assert "m" in FIGHT_HEAD.rows[3] and "l" not in FIGHT_HEAD.rows[3]  # medium blade


def test_gather_head_selects_by_skill():
    assert gather_head("woodcutting") is AXE_HEAD
    assert gather_head("mining") is PICKAXE_HEAD
    assert gather_head("fishing") is PICKAXE_HEAD          # fallback
    assert gather_head(None) is PICKAXE_HEAD               # fallback


def test_grip_haft_is_two_pixels():
    # haft shortened 15%: grip drops from 3px to 2px
    g = grip_overlay(1, 0)
    assert sum(ch != TRANSPARENT for row in g.rows for ch in row) == 2
    assert {c for c, ch in enumerate(g.rows[4]) if ch == "h"} == {5, 6}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -v`
Expected: FAIL (`AXE_HEAD`/`gather_head` undefined; old `GATHER_HEAD` import gone).

- [ ] **Step 3: Implement**

In `sprites.py`, replace the `GATHER_HEAD`/`FIGHT_HEAD` definitions (the block at ~lines 95-122) with:

```python
# Tool heads (drawn in the arc-neighbor tile, one 8x8 weapon each). 1px haft at
# col 3, head at top, reused at all arc offsets. m=STEEL (medium grey),
# l=STONE (light grey), h=BARK (handle).
AXE_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "........",
        ".mmmmmml",   # head offset on the haft (2px left, 3px right), blade on col 7
        ".mmmmmml",
        ".mmmmmml",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)
PICKAXE_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "........",
        ".lmmml..",   # head centred on haft (cols 2-4); light-grey triangles each side
        "llmmmll.",
        ".lmmml..",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)
HAMMER_HEAD: Sprite = Sprite(
    rows=(
        "........",
        "........",
        "..mmm...",   # pickaxe minus light-grey: solid block on the haft
        "..mmm...",
        "..mmm...",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "h": BARK},
)
FIGHT_HEAD: Sprite = Sprite(
    rows=(
        "...l....",   # light-grey tip
        "..lll...",   # pickaxe-style triangle
        "..mmm...",   # vertical medium-grey blade, centred on haft
        "..mmm...",
        "..mmm...",
        "...h....",
        "...h....",
        "........",
    ),
    palette={"m": STEEL, "l": STONE, "h": BARK},
)


def gather_head(skill: str | None) -> Sprite:
    """The gather tool head for a gathered resource's skill: woodcutting -> axe,
    mining -> pickaxe; everything else (fishing/alchemy/unknown) -> pickaxe."""
    if skill == "woodcutting":
        return AXE_HEAD
    return PICKAXE_HEAD
```

Then shorten the grip in `grip_overlay` — change the step range from `(1, 2, 3)` to `(1, 2)`:

```python
    for k in (1, 2):
        r, c = 4 + k * drow, 4 + k * dcol
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -v`
Expected: PASS.

- [ ] **Step 5: Verify no dangling GATHER_HEAD refs (will be wired in later tasks)**

Run: `grep -rn "GATHER_HEAD" src tests`
Expected: only `swing_frames.py` + `test_swing_frames.py` + `test_map_pane_animation.py` (fixed in Tasks 3-4). Note them; do not edit here.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites_animation.py
git commit -m "feat(tui): axe/pickaxe/hammer heads + redesigned sword + gather_head; grip 2px"
```

---

## Task 2: Map CraftAction in action_kind_of

**Files:**
- Modify: `src/artifactsmmo_cli/ai/action_kind.py`
- Test: `tests/test_ai/test_action_kind.py`

**Interfaces:**
- Produces: `action_kind_of(CraftAction(code=...)) == ("craft", code)`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_ai/test_action_kind.py
from artifactsmmo_cli.ai.actions.crafting import CraftAction


def test_craft_kind_and_target():
    assert action_kind_of(CraftAction(code="copper_bar")) == ("craft", "copper_bar")
```

> Check `CraftAction`'s constructor first (`grep -n "class CraftAction\|code\|quantity" src/artifactsmmo_cli/ai/actions/crafting.py`). It is a dataclass with `code` and `quantity=1`; construct it as the real signature requires (e.g. `CraftAction(code="copper_bar")`), keeping the asserted output `("craft", "copper_bar")`.

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_action_kind.py -k craft -v`
Expected: FAIL (returns `("other", None)`).

- [ ] **Step 3: Implement**

In `action_kind.py`, add the import and a branch before the `return "other", None`:

```python
from artifactsmmo_cli.ai.actions.crafting import CraftAction
```
```python
    if isinstance(action, CraftAction):
        return "craft", action.code
    return "other", None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_action_kind.py -v`
Expected: PASS (all cases incl. craft).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/action_kind.py tests/test_ai/test_action_kind.py
git commit -m "feat(tui): map CraftAction to (craft, code) for the animation layer"
```

---

## Task 3: CRAFT_SWING mode + head-agnostic swing_overlay

**Files:**
- Modify: `src/artifactsmmo_cli/tui/swing_frames.py`
- Test: `tests/test_tui/test_swing_frames.py`

**Interfaces:**
- Consumes: `Sprite` (sprites).
- Produces: `Mode.CRAFT_SWING`; `current_mode("craft", …) -> Mode.CRAFT_SWING`; `swing_overlay(mode: Mode, frame_index: int, head: Sprite) -> dict[tuple[int,int], Sprite]` (head-agnostic — places the passed `head`; `{}` for non-swing modes; gather+craft use the right/CW offsets, fight the left/CCW).

- [ ] **Step 1: Write the failing test**

Replace the existing `swing_overlay` tests (which import `GATHER_HEAD`/`FIGHT_HEAD` and call the 2-arg form) with:

```python
# in tests/test_tui/test_swing_frames.py — replace the swing_overlay block
from artifactsmmo_cli.tui.swing_frames import swing_overlay
from artifactsmmo_cli.tui.sprites import PICKAXE_HEAD, HAMMER_HEAD


def test_non_swing_modes_have_no_overlay():
    for m in (Mode.IDLE, Mode.GLIDE, Mode.PLANNING):
        assert swing_overlay(m, 0, PICKAXE_HEAD) == {}


def test_swing_overlay_places_passed_head_on_right_for_gather_and_craft():
    for mode in (Mode.GATHER_SWING, Mode.CRAFT_SWING):
        ov = swing_overlay(mode, 2, HAMMER_HEAD)   # frame 2 -> (1,0)
        assert ov[(1, 0)] is HAMMER_HEAD
        assert (0, 0) in ov
        assert all(dc >= 0 for (dc, _dr) in ov)    # right side


def test_swing_overlay_fight_on_left():
    ov = swing_overlay(Mode.FIGHT_SWING, 2, PICKAXE_HEAD)
    assert ov[(-1, 0)] is PICKAXE_HEAD
    assert any(dc < 0 for (dc, _dr) in ov)


def test_craft_mode_from_action_kind():
    assert current_mode("craft", False, 1.0, 5.0) == Mode.CRAFT_SWING
    assert current_mode("craft", False, 6.0, 5.0) == Mode.IDLE     # cooldown elapsed
    assert current_mode("craft", True, 1.0, 5.0) == Mode.PLANNING  # planning overrides
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_swing_frames.py -k "overlay or craft" -v`
Expected: FAIL (`CRAFT_SWING` undefined; `swing_overlay` is 2-arg).

- [ ] **Step 3: Implement**

(a) Add the mode to the `Mode` enum:
```python
class Mode(Enum):
    IDLE = "idle"
    GLIDE = "glide"
    GATHER_SWING = "gather_swing"
    FIGHT_SWING = "fight_swing"
    CRAFT_SWING = "craft_swing"
    PLANNING = "planning"
```
(b) Add craft to the kind→mode map:
```python
_KIND_TO_MODE = {
    "move": Mode.GLIDE,
    "gather": Mode.GATHER_SWING,
    "fight": Mode.FIGHT_SWING,
    "craft": Mode.CRAFT_SWING,
}
```
(c) Replace `swing_overlay` to take a `head` and drop the hardcoded sprites import. The import line becomes just `from artifactsmmo_cli.tui.sprites import Sprite` (remove `FIGHT_HEAD, GATHER_HEAD, grip_overlay`)... keep `grip_overlay`:
```python
from artifactsmmo_cli.tui.sprites import Sprite, grip_overlay
```
```python
def swing_overlay(mode: Mode, frame_index: int, head: Sprite) -> dict[tuple[int, int], Sprite]:
    """Overlay map for a swing frame: the given `head` in the arc-neighbor tile plus
    a grip in the player tile (0,0). Empty for non-swing modes. Gather and craft sweep
    the right/CW arc; fight sweeps the left/CCW arc (mirrored)."""
    if mode is Mode.FIGHT_SWING:
        offsets = _FIGHT_OFFSETS
    elif mode in (Mode.GATHER_SWING, Mode.CRAFT_SWING):
        offsets = _GATHER_OFFSETS
    else:
        return {}
    off = offsets[frame_index % len(offsets)]
    return {(0, 0): grip_overlay(off[0], off[1]), off: head}
```
(The `_GATHER_OFFSETS`/`_FIGHT_OFFSETS` lists and `SWING_FRAME_COUNT` stay as-is.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_swing_frames.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/swing_frames.py tests/test_tui/test_swing_frames.py
git commit -m "feat(tui): CRAFT_SWING mode + head-agnostic swing_overlay(head)"
```

---

## Task 4: MapPane head selection + walking guard

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane_animation.py`

**Interfaces:**
- Consumes: `AXE_HEAD`, `PICKAXE_HEAD`, `HAMMER_HEAD`, `FIGHT_HEAD`, `gather_head` (sprites); `Mode`, `swing_overlay`, `swing_frame_index`, `current_mode`, `SWING_FRAME_COUNT` (swing_frames).
- Produces: module fns `select_swing_head(mode: Mode, action_target: str | None, game_data: GameData) -> Sprite | None` and `_is_bar(code: str | None, game_data: GameData) -> bool`; rewritten `MapPane._swing_overlay`.

- [ ] **Step 1: Write the failing test**

```python
# in tests/test_tui/test_map_pane_animation.py
# replace the GATHER_HEAD/FIGHT_HEAD import + the two swing-head tests
from artifactsmmo_cli.tui.sprites import (
    PLAYER_SPRITE, PLANNING_SPRITE, AXE_HEAD, PICKAXE_HEAD, HAMMER_HEAD, FIGHT_HEAD,
)
from artifactsmmo_cli.tui.widgets.map_pane import select_swing_head, _is_bar
from artifactsmmo_cli.tui.swing_frames import Mode


class _GD:
    """Minimal game_data double for head selection."""
    def __init__(self, skills=None, items=()):
        self._skills = skills or {}
        self._items = set(items)
    def resource_skill_level(self, code):
        return self._skills.get(code)
    def item_stats(self, code):
        return object() if code in self._items else None


def test_select_head_gather_by_skill():
    gd = _GD(skills={"ash_tree": ("woodcutting", 1), "copper_rocks": ("mining", 1)})
    assert select_swing_head(Mode.GATHER_SWING, "ash_tree", gd) is AXE_HEAD
    assert select_swing_head(Mode.GATHER_SWING, "copper_rocks", gd) is PICKAXE_HEAD
    assert select_swing_head(Mode.GATHER_SWING, "shrimp_spot", gd) is PICKAXE_HEAD  # fallback
    assert select_swing_head(Mode.GATHER_SWING, None, gd) is PICKAXE_HEAD


def test_select_head_fight_is_sword():
    assert select_swing_head(Mode.FIGHT_SWING, "chicken", _GD()) is FIGHT_HEAD


def test_select_head_craft_hammer_only_for_bars():
    gd = _GD(items=("copper_bar", "copper_boots"))
    assert select_swing_head(Mode.CRAFT_SWING, "copper_bar", gd) is HAMMER_HEAD
    assert select_swing_head(Mode.CRAFT_SWING, "copper_boots", gd) is None
    assert select_swing_head(Mode.IDLE, "copper_bar", gd) is None


def test_is_bar():
    gd = _GD(items=("copper_bar",))
    assert _is_bar("copper_bar", gd) is True
    assert _is_bar("copper_boots", gd) is False
    assert _is_bar(None, gd) is False
    assert _is_bar("ghost_bar", gd) is False              # endswith _bar but no item


def test_no_tool_overlay_while_gliding():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", x=0, y=0, cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = [(1, 0), (2, 0)]                      # glide in progress
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_frames = [(1, 0), (2, 0)]
    assert p._swing_overlay(now=0.5) == {}                # walking -> no tool
    # after the glide window, the tool returns
    assert p._swing_overlay(now=6.0) == {}                # cooldown elapsed -> idle anyway


def test_swing_overlay_gather_axe_when_not_gliding():
    p = _pane()
    p._game_data = _GD(skills={"ash_tree": ("woodcutting", 1)})
    p.snapshot = _snap(action_kind="gather", action_target="ash_tree", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._anim_frames = []                                    # not gliding
    ov = p._swing_overlay(now=0.35)                        # frame 2 -> (1,0)
    assert ov[(1, 0)] is AXE_HEAD
```

> Reuse the existing `_pane()`/`_snap()` helpers in the file. Remove the old `test_gather_swing_overlay_has_head_on_right`/`test_fight_swing_overlay_has_head_on_left` (they asserted the removed `GATHER_HEAD`); the new tests above replace them. Keep `test_idle_shows_player_sprite`, `test_planning_shows_bubble`, `test_no_overlay_when_idle_or_planning`, `test_swing_overlay_empty_without_snapshot`, `test_render_viewport_overlay_changes_neighbor_tile` (update its overlay to `{(1, 0): AXE_HEAD}`).

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -v`
Expected: FAIL (`select_swing_head`/`_is_bar` undefined; `GATHER_HEAD` import gone).

- [ ] **Step 3: Implement**

(a) Imports — drop `BLANK`-unrelated, add the heads + selection deps:
```python
from artifactsmmo_cli.tui.sprites import (
    AXE_HEAD, BLANK_SPRITE, FIGHT_HEAD, HAMMER_HEAD, PICKAXE_HEAD, PLANNING_SPRITE,
    PLAYER_SPRITE, Sprite, SpriteCategory, gather_head, overlay_sprites,
)
from artifactsmmo_cli.tui.swing_frames import (
    SWING_FRAME_COUNT, Mode, current_mode, glide_index, swing_frame_index, swing_overlay,
)
```
(b) Add the two module-level functions (above the `MapPane` class):
```python
def _is_bar(code: str | None, game_data: GameData) -> bool:
    """True when `code` names a craftable bar (all in-game bars end '_bar')."""
    return code is not None and code.endswith("_bar") and game_data.item_stats(code) is not None


def select_swing_head(mode: Mode, action_target: str | None, game_data: GameData) -> Sprite | None:
    """The tool head for a swing mode + target, or None when no tool should show:
    gather -> axe/pickaxe by the resource's skill; fight -> sword; craft -> hammer
    only for a bar; anything else -> None."""
    if mode is Mode.GATHER_SWING:
        skill_req = game_data.resource_skill_level(action_target) if action_target else None
        return gather_head(skill_req[0] if skill_req is not None else None)
    if mode is Mode.FIGHT_SWING:
        return FIGHT_HEAD
    if mode is Mode.CRAFT_SWING and _is_bar(action_target, game_data):
        return HAMMER_HEAD
    return None
```
(c) Rewrite `_swing_overlay` (walking guard + selection):
```python
    def _swing_overlay(self, now: float) -> dict[tuple[int, int], Sprite]:
        snap = self.snapshot
        if snap is None:
            return {}
        elapsed = now - self._anim_start
        # No tool while walking: a glide animation in progress suppresses the swing.
        if self._anim_frames and elapsed < snap.cooldown_remaining:
            return {}
        mode = current_mode(snap.action_kind, self._planning_active, elapsed, snap.cooldown_remaining)
        head = select_swing_head(mode, snap.action_target, self._game_data)
        if head is None:
            return {}
        idx = swing_frame_index(elapsed, SWING_FRAME_COUNT, SWING_SWEEP_SECONDS)
        return swing_overlay(mode, idx, head)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -v`
Expected: PASS.

- [ ] **Step 5: Full TUI suite + coverage**

Run: `uv run pytest tests/test_tui/ -q --no-cov` → PASS; then
`uv run pytest tests/test_tui/ --cov=src/artifactsmmo_cli/tui/widgets/map_pane --cov=src/artifactsmmo_cli/tui/sprites --cov=src/artifactsmmo_cli/tui/swing_frames --cov-report=term-missing` → 100% (no missing). If `select_swing_head`'s craft-non-bar or fallback branch is uncovered, the Task-4 tests above already exercise them; add a focused case if term-missing flags a line.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane_animation.py
git commit -m "feat(tui): select axe/pickaxe/sword/hammer head; no tool while walking"
```

---

## Task 5: Full gate + manual smoke

**Files:** none.

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest -q`
Expected: PASS at 100% coverage.

- [ ] **Step 2: mypy**

Run: `uv run mypy src/artifactsmmo_cli/tui src/artifactsmmo_cli/ai/action_kind.py`
Expected: no issues.

- [ ] **Step 3: Manual smoke (recommended)**

Run the watch TUI: woodcutting shows an axe, mining a pickaxe, smelting bars a hammer, combat the redesigned sword; nothing shows while the player walks.
Run: `uv run artifactsmmo play Robby`

---

## Self-Review

**Spec coverage:**
- Axe/pickaxe/hammer/sword art → Task 1. ✓
- Haft −15% (grip 2px) → Task 1. ✓
- `gather_head(skill)` woodcutting/mining/fallback → Task 1. ✓
- CraftAction → ("craft", code) → Task 2. ✓
- CRAFT_SWING + head-agnostic swing_overlay → Task 3. ✓
- Head selection (gather by skill, sword, hammer for `*_bar`, else none) → Task 4 `select_swing_head` + `_is_bar`. ✓
- No tool while walking → Task 4 `_swing_overlay` glide guard. ✓
- 100% coverage → Task 4 Step 5 + Task 5. ✓
- Glide/planning/movement-timing/snapshot untouched (beyond action_kind craft mapping) → no task changes them. ✓

**Placeholder scan:** none — full sprite rows, full function bodies, concrete test doubles.

**Type consistency:** `gather_head(str|None)->Sprite` (T1) used by `select_swing_head` (T4); `swing_overlay(mode, frame_index, head)` (T3) called by `_swing_overlay` (T4); `select_swing_head(mode, action_target, game_data)->Sprite|None` and `_is_bar(code, game_data)->bool` consistent T4; `resource_skill_level(code)->tuple[str,int]|None` (real game_data) consumed via `skill_req[0]`. `Mode.CRAFT_SWING` consistent T3/T4.
