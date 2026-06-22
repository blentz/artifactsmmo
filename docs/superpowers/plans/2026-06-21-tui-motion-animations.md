# TUI Motion Animations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four map-TUI animations — cooldown-scaled movement glide, gather swing (pickaxe CW), combat swing (sword CCW), and a "planner thinking" thought-bubble.

**Architecture:** Three additive layers. (1) Data: `CycleSnapshot` gains `action_kind`/`action_target`; a new planning on/off signal flows bot→bridge→`MapPane`. (2) Timer: `MapPane` runs ONE persistent ~50ms tick. (3) Frame selection: a pure `swing_frames.py` maps (mode, elapsed-vs-cooldown) → which player-sprite frame; new 8×8 swing/planning sprites in `sprites.py`. Animation modes are mutually exclusive in time, so each maps to exactly one frame-selected player sprite — no multi-layer compositing.

**Tech Stack:** Python 3.13, `uv`, pydantic (`CycleSnapshot`), Textual (`MapPane`/`WatchApp`), Rich (`Text`), pytest.

## Global Constraints

- Use `uv run` for every Python command (`uv run pytest`, `uv run mypy`).
- Imports at top of file only; no inline imports; no `...`/triple-dot imports; absolute imports.
- ONE behavioral class per file (pure data/enum modules may group declarations).
- Never catch `Exception`; no `if TYPE_CHECKING`.
- Tests live in `tests/`; use the real suite (no throwaway scripts). Project gate = 0 errors/warnings/skips, 100% coverage; carve-outs need written justification.
- Sprites are 8×8; transparent key is `"."`; every non-`.` glyph must be in the sprite palette (`validate_sprite`).
- Time base for animation is wall-clock elapsed since snapshot ARRIVAL captured by `MapPane` (`time.monotonic()`), using the snapshot's existing `cooldown_remaining` as the duration. Do NOT add a serialized timestamp to the snapshot.

---

## File Structure

| File | Responsibility | Create/Modify |
|---|---|---|
| `src/artifactsmmo_cli/ai/action_kind.py` | pure `Action` → `(kind, target)` | Create |
| `src/artifactsmmo_cli/ai/cycle_snapshot.py` | +`action_kind`, `action_target` fields | Modify |
| `src/artifactsmmo_cli/ai/player.py` | populate fields; emit planning(True) | Modify |
| `src/artifactsmmo_cli/tui/observer.py` | +`notify_planning` channel | Modify |
| `src/artifactsmmo_cli/tui/app.py` | `set_planning` → MapPane | Modify |
| `src/artifactsmmo_cli/commands/play.py` | wire planning observer | Modify |
| `src/artifactsmmo_cli/tui/swing_frames.py` | pure mode + frame-index + glide-index math | Create |
| `src/artifactsmmo_cli/tui/sprites.py` | swing/planning 8×8 frames + builder | Modify |
| `src/artifactsmmo_cli/tui/widgets/map_pane.py` | persistent timer; mode-driven frame selection; glide timing | Modify |
| `tests/test_ai/test_action_kind.py` | action mapper | Create |
| `tests/test_tui/test_swing_frames.py` | pure animation math | Create |
| `tests/test_tui/test_sprites_animation.py` | new sprite shapes | Create |
| `tests/test_tui/test_map_pane_animation.py` | mode → sprite integration | Create |
| existing `tests/test_tui/test_observer.py`, `tests/test_ai/test_cycle_snapshot*.py` | extend | Modify |

---

## Task 1: Action-kind mapper (pure)

**Files:**
- Create: `src/artifactsmmo_cli/ai/action_kind.py`
- Test: `tests/test_ai/test_action_kind.py`

**Interfaces:**
- Produces: `action_kind_of(action: object) -> tuple[str, str | None]` returning `(kind, target)` where `kind ∈ {"move","gather","fight","rest","other"}`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_action_kind.py
from artifactsmmo_cli.ai.action_kind import action_kind_of
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction


def test_move_kind_and_target():
    assert action_kind_of(MoveAction(x=3, y=4)) == ("move", "3,4")


def test_gather_kind_and_target():
    assert action_kind_of(GatherAction(resource_code="copper_rocks")) == ("gather", "copper_rocks")


def test_fight_kind_and_target():
    assert action_kind_of(FightAction(monster_code="chicken")) == ("fight", "chicken")


def test_rest_kind_no_target():
    assert action_kind_of(RestAction()) == ("rest", None)


def test_unknown_action_is_other():
    assert action_kind_of(object()) == ("other", None)
```

> NOTE: check each Action's constructor signature first (`grep -n "def __init__\|@dataclass" src/artifactsmmo_cli/ai/actions/<file>.py`). If they are dataclasses with positional fields, adapt the constructor calls (e.g. `MoveAction(3, 4)`); keep the asserted `(kind, target)` outputs identical.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_action_kind.py -v`
Expected: FAIL (`No module named ...action_kind`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/action_kind.py
"""Pure mapping from an executed Action to a (kind, target) pair for the TUI.

One source of truth so the renderer never string-parses repr(action)."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction


def action_kind_of(action: object) -> tuple[str, str | None]:
    """Return (kind, target) for the TUI animation layer.

    kind ∈ {"move","gather","fight","rest","other"}; target is the gather
    resource / fight monster / "x,y" destination, or None."""
    if isinstance(action, MoveAction):
        return "move", f"{action.x},{action.y}"
    if isinstance(action, GatherAction):
        return "gather", action.resource_code
    if isinstance(action, FightAction):
        return "fight", action.monster_code
    if isinstance(action, RestAction):
        return "rest", None
    return "other", None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_action_kind.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/action_kind.py tests/test_ai/test_action_kind.py
git commit -m "feat(tui): pure action_kind_of mapper for animation layer"
```

---

## Task 2: Snapshot fields + populate

**Files:**
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py` (the `CycleSnapshot` model, after `action: str` ~line 64)
- Modify: `src/artifactsmmo_cli/ai/player.py` (`_notify_observer` ~1060; the two call sites ~480, ~595)
- Test: extend `tests/test_ai/` snapshot coverage (add `tests/test_ai/test_cycle_snapshot_action_kind.py`)

**Interfaces:**
- Consumes: `action_kind_of` (Task 1).
- Produces: `CycleSnapshot.action_kind: str` (default `"other"`), `CycleSnapshot.action_target: str | None` (default `None`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_cycle_snapshot_action_kind.py
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def _min(**kw):
    base = dict(cycle_index=0, timestamp="t", character="c", x=0, y=0, level=1,
                xp=0, max_xp=1, hp=1, max_hp=1, gold=0, selected_goal="g",
                action="Rest", outcome="ok")
    base.update(kw)
    return CycleSnapshot(**base)


def test_defaults():
    s = _min()
    assert s.action_kind == "other" and s.action_target is None


def test_set_fields():
    s = _min(action_kind="gather", action_target="copper_rocks")
    assert s.action_kind == "gather" and s.action_target == "copper_rocks"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_ai/test_cycle_snapshot_action_kind.py -v`
Expected: FAIL (`action_kind` not a field / unexpected kwarg).

- [ ] **Step 3: Add the fields**

In `cycle_snapshot.py`, immediately after `action: str` (~line 64):

```python
    action: str
    action_kind: str = "other"          # move|gather|fight|rest|other (TUI animation)
    action_target: str | None = None    # gather resource / fight monster / "x,y"
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_ai/test_cycle_snapshot_action_kind.py -v`
Expected: PASS.

- [ ] **Step 5: Populate at the snapshot build**

In `player.py`, change `_notify_observer` to accept the executed action and derive the fields. Add params to the signature (after `action_name: str`):

```python
    def _notify_observer(
        self,
        selected_goal_name: str,
        action_name: str,
        outcome: str,
        goal_rank_trace: list[dict[str, Any]],
        planner_stats: dict[str, object] | None = None,
        action: object | None = None,
    ) -> None:
```

Add the import at top of `player.py`:

```python
from artifactsmmo_cli.ai.action_kind import action_kind_of
```

Just before `snap = CycleSnapshot(` (~line 1094):

```python
        action_kind, action_target = action_kind_of(action) if action is not None else ("other", None)
```

Inside the `CycleSnapshot(...)` call, next to `action=action_name,` (~line 1113):

```python
            action=action_name,
            action_kind=action_kind,
            action_target=action_target,
```

At BOTH `self._notify_observer(...)` call sites (~480, ~595), pass the executed action object. Find the local `action` variable (the same one used for `action_name = repr(action)`) and add `action=action,` to the call. Example:

```python
                    self._notify_observer(
                        selected_goal_name, action_name, outcome,
                        goal_rank_trace, planner_stats, action=action,
                    )
```

> If a call site has no `action` in scope (e.g. an early-out path), pass nothing — the default `("other", None)` applies.

- [ ] **Step 6: Run the AI suite**

Run: `uv run pytest tests/test_ai/ -q --no-cov`
Expected: PASS (existing snapshot/player tests still green with the new optional param).

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/cycle_snapshot.py src/artifactsmmo_cli/ai/player.py tests/test_ai/test_cycle_snapshot_action_kind.py
git commit -m "feat(tui): carry action_kind/action_target on CycleSnapshot"
```

---

## Task 3: Planning signal (bot → bridge → MapPane)

**Files:**
- Modify: `src/artifactsmmo_cli/tui/observer.py` (add `notify_planning`)
- Modify: `src/artifactsmmo_cli/tui/app.py` (add `set_planning`)
- Modify: `src/artifactsmmo_cli/ai/player.py` (planning observer + emit True before decide)
- Modify: `src/artifactsmmo_cli/commands/play.py` (wire it; ~135-137)
- Test: extend `tests/test_tui/test_observer.py`

**Interfaces:**
- Produces:
  - `ThreadSafeBridge.notify_planning(active: bool) -> None`
  - `WatchApp.set_planning(active: bool) -> None`
  - `GamePlayer.set_planning_observer(cb: Callable[[bool], None] | None) -> None`

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_tui/test_observer.py
from artifactsmmo_cli.tui.observer import ThreadSafeBridge


class _StubApp:
    def __init__(self):
        self.planning_calls = []
    # no call_from_thread -> bridge invokes handler directly


def test_notify_planning_forwards_to_handler():
    app = _StubApp()
    seen = []
    bridge = ThreadSafeBridge(app, lambda s: None, planning_handler=seen.append)
    bridge.notify_planning(True)
    bridge.notify_planning(False)
    assert seen == [True, False]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_observer.py -v`
Expected: FAIL (`planning_handler` unexpected kwarg).

- [ ] **Step 3: Extend the bridge**

In `observer.py`:

```python
    def __init__(self, app: Any, handler: Callable[[CycleSnapshot], None],
                 planning_handler: Callable[[bool], None] | None = None) -> None:
        self._app = app
        self._handler = handler
        self._planning_handler = planning_handler

    def notify_planning(self, active: bool) -> None:
        if self._planning_handler is None:
            return
        call_from_thread = getattr(self._app, "call_from_thread", None)
        if call_from_thread is None:
            self._planning_handler(active)
        else:
            call_from_thread(self._planning_handler, active)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_observer.py -v`
Expected: PASS.

- [ ] **Step 5: App + MapPane setter**

In `app.py` (`WatchApp`), add:

```python
    def set_planning(self, active: bool) -> None:
        """Bot-thread signal (via ThreadSafeBridge): planner is deciding."""
        self.query_one("#map", MapPane).set_planning(active)
```

In `map_pane.py` (`MapPane`), add the state field in `__init__` and a setter (timer logic lands in Task 6):

```python
        self._planning_active = False
```
```python
    def set_planning(self, active: bool) -> None:
        self._planning_active = active
        self.refresh()
```

- [ ] **Step 6: Player planning observer**

In `player.py.__init__`, add:

```python
        self._planning_observer: "Callable[[bool], None] | None" = None
```
Add a setter near `set_cycle_observer` (~176):

```python
    def set_planning_observer(self, observer: "Callable[[bool], None] | None") -> None:
        self._planning_observer = observer

    def _notify_planning(self, active: bool) -> None:
        if self._planning_observer is not None:
            self._planning_observer(active)
```
In the run loop, immediately BEFORE `decision = self._strategy.decide(` (~382):

```python
                self._notify_planning(True)
```
The snapshot arrival clears it (MapPane.update_snapshot, Task 6), so no explicit False is required; but add one right after the action executes for symmetry if an `action`-executed point is obvious — optional.

- [ ] **Step 7: Wire in play.py**

After line ~137 (`player.set_cycle_observer(bridge.notify)`):

```python
    bridge = ThreadSafeBridge(app, app.update_snapshot, planning_handler=app.set_planning)
    player.set_cycle_observer(bridge.notify)
    player.set_planning_observer(bridge.notify_planning)
```
(Replace the existing `ThreadSafeBridge(app, app.update_snapshot)` line with the 3-arg form.)

- [ ] **Step 8: Run TUI + AI suites**

Run: `uv run pytest tests/test_tui/ tests/test_ai/test_player*.py -q --no-cov`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/tui/observer.py src/artifactsmmo_cli/tui/app.py src/artifactsmmo_cli/tui/widgets/map_pane.py src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/commands/play.py tests/test_tui/test_observer.py
git commit -m "feat(tui): planning on/off signal bot->bridge->MapPane"
```

---

## Task 4: Pure animation math (`swing_frames.py`)

**Files:**
- Create: `src/artifactsmmo_cli/tui/swing_frames.py`
- Test: `tests/test_tui/test_swing_frames.py`

**Interfaces:**
- Produces:
  - `class Mode(Enum)`: `IDLE, GLIDE, GATHER_SWING, FIGHT_SWING, PLANNING`
  - `current_mode(action_kind: str, planning_active: bool, elapsed: float, duration: float) -> Mode`
  - `swing_frame_index(elapsed: float, frame_count: int, sweep_seconds: float) -> int`
  - `glide_index(elapsed: float, duration: float, frame_count: int, arrive_fraction: float = 0.9) -> int`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui/test_swing_frames.py
from artifactsmmo_cli.tui.swing_frames import (
    Mode, current_mode, swing_frame_index, glide_index,
)


def test_planning_overrides_everything():
    assert current_mode("gather", True, 0.1, 5.0) == Mode.PLANNING


def test_kind_within_cooldown():
    assert current_mode("gather", False, 1.0, 5.0) == Mode.GATHER_SWING
    assert current_mode("fight", False, 1.0, 5.0) == Mode.FIGHT_SWING
    assert current_mode("move", False, 1.0, 5.0) == Mode.GLIDE


def test_idle_after_cooldown_or_rest():
    assert current_mode("gather", False, 6.0, 5.0) == Mode.IDLE   # cooldown elapsed
    assert current_mode("rest", False, 1.0, 5.0) == Mode.IDLE
    assert current_mode("gather", False, 1.0, 0.0) == Mode.IDLE   # no cooldown


def test_swing_loops_and_clamps_into_range():
    # 5 frames, 0.8s sweep -> 0.16s/frame
    assert swing_frame_index(0.0, 5, 0.8) == 0
    assert swing_frame_index(0.16, 5, 0.8) == 1
    assert swing_frame_index(0.8, 5, 0.8) == 0           # wraps to next sweep
    assert 0 <= swing_frame_index(123.4, 5, 0.8) < 5      # always in range


def test_swing_index_degenerate_sweep_is_zero():
    assert swing_frame_index(1.0, 5, 0.0) == 0


def test_glide_reaches_last_frame_at_arrive_fraction():
    # arrive_fraction 0.9 of a 10s cooldown -> done by t=9s
    assert glide_index(0.0, 10.0, 5) == 0
    assert glide_index(9.0, 10.0, 5) == 4                 # last frame (index 4)
    assert glide_index(10.0, 10.0, 5) == 4               # clamps past the end
    assert glide_index(4.5, 10.0, 5) == 2                 # halfway -> middle frame


def test_glide_single_frame_is_zero():
    assert glide_index(5.0, 10.0, 1) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_swing_frames.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# src/artifactsmmo_cli/tui/swing_frames.py
"""Pure animation-mode + frame-index math for the map TUI player sprite.

No Textual, no time, no I/O — just numbers. The MapPane supplies elapsed
seconds (monotonic since snapshot arrival) and the snapshot's cooldown
duration; these functions decide the mode and which sprite frame to show."""

from enum import Enum


class Mode(Enum):
    IDLE = "idle"
    GLIDE = "glide"
    GATHER_SWING = "gather_swing"
    FIGHT_SWING = "fight_swing"
    PLANNING = "planning"


_KIND_TO_MODE = {
    "move": Mode.GLIDE,
    "gather": Mode.GATHER_SWING,
    "fight": Mode.FIGHT_SWING,
}


def current_mode(action_kind: str, planning_active: bool,
                 elapsed: float, duration: float) -> Mode:
    """Planning overrides all. Otherwise, while the action's cooldown is still
    running (0 < elapsed < duration), the kind picks the animation; once the
    cooldown has elapsed (or there is none, or it is rest/other) → IDLE."""
    if planning_active:
        return Mode.PLANNING
    if duration <= 0.0 or elapsed >= duration:
        return Mode.IDLE
    return _KIND_TO_MODE.get(action_kind, Mode.IDLE)


def swing_frame_index(elapsed: float, frame_count: int, sweep_seconds: float) -> int:
    """Looping sweep position in [0, frame_count). Each sweep takes
    sweep_seconds and repeats. Degenerate sweep -> frame 0."""
    if frame_count <= 1 or sweep_seconds <= 0.0:
        return 0
    phase = (elapsed % sweep_seconds) / sweep_seconds   # [0,1)
    return min(int(phase * frame_count), frame_count - 1)


def glide_index(elapsed: float, duration: float, frame_count: int,
                arrive_fraction: float = 0.9) -> int:
    """Index into glide frames so the last frame is reached at
    arrive_fraction*duration (arrives just before the next action), clamped."""
    if frame_count <= 1:
        return 0
    window = duration * arrive_fraction
    if window <= 0.0:
        return frame_count - 1
    progress = min(elapsed / window, 1.0)               # [0,1]
    return min(int(round(progress * (frame_count - 1))), frame_count - 1)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_swing_frames.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/swing_frames.py tests/test_tui/test_swing_frames.py
git commit -m "feat(tui): pure mode + swing/glide frame-index math"
```

---

## Task 5: Swing + planning sprites (`sprites.py`)

**Files:**
- Modify: `src/artifactsmmo_cli/tui/sprites.py` (append after `PLAYER_SPRITE` ~line 67)
- Test: `tests/test_tui/test_sprites_animation.py`

**Interfaces:**
- Consumes: `PLAYER_SPRITE`, `Sprite`, `validate_sprite`, palette colors `COPPER`, `STEEL`, `BONE`.
- Produces:
  - `GATHER_SWING_FRAMES: tuple[Sprite, ...]` (pickaxe, clockwise right-side arc)
  - `FIGHT_SWING_FRAMES: tuple[Sprite, ...]` (sword, counterclockwise left-side arc)
  - `PLANNING_SPRITE: Sprite` (player + bubble at 2 o'clock from head)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui/test_sprites_animation.py
from artifactsmmo_cli.tui.sprites import (
    GATHER_SWING_FRAMES, FIGHT_SWING_FRAMES, PLANNING_SPRITE,
    PLAYER_SPRITE, validate_sprite, SPRITE_SIZE,
)


def test_frames_nonempty_and_valid_8x8():
    assert len(GATHER_SWING_FRAMES) >= 3
    assert len(FIGHT_SWING_FRAMES) == len(GATHER_SWING_FRAMES)
    for i, s in enumerate(GATHER_SWING_FRAMES + FIGHT_SWING_FRAMES + (PLANNING_SPRITE,)):
        validate_sprite(f"anim{i}", s)           # raises if not 8x8 / bad key


def test_gather_arc_is_on_the_right_fight_on_the_left():
    # the tool pixel ('t') sits in the right half for gather, left half for fight
    def tool_cols(sprite):
        return {c for row in sprite.rows for c, ch in enumerate(row) if ch == "t"}
    g = set().union(*[tool_cols(s) for s in GATHER_SWING_FRAMES])
    f = set().union(*[tool_cols(s) for s in FIGHT_SWING_FRAMES])
    assert min(g) >= SPRITE_SIZE // 2            # gather tool on right half
    assert max(f) < SPRITE_SIZE // 2             # fight tool on left half


def test_planning_bubble_upper_right_and_keeps_player_body():
    # bubble ('p') appears in the top-right; body rows still match the player
    bubble = {(r, c) for r, row in enumerate(PLANNING_SPRITE.rows)
              for c, ch in enumerate(row) if ch == "p"}
    assert bubble and all(r <= 1 and c >= SPRITE_SIZE - 2 for (r, c) in bubble)
    assert PLANNING_SPRITE.rows[6] == PLAYER_SPRITE.rows[6]   # legs unchanged
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -v`
Expected: FAIL (names not exported).

- [ ] **Step 3: Implement (builder + frames)**

Add `COPPER, STEEL, BONE` to the palette import at the top of `sprites.py` if not already imported (they are in `palette.py`; `COPPER`/`STEEL` are already imported — add `BONE` if missing). Then append after `PLAYER_SPRITE`:

```python
def _player_with_tool(positions: tuple[tuple[int, int], ...], key: str, color: str) -> Sprite:
    """PLAYER_SPRITE with `key` painted at the given (row, col) cells (which must
    be transparent in the base), using `color`. Returns a new immutable Sprite."""
    rows = list(PLAYER_SPRITE.rows)
    for r, c in positions:
        assert rows[r][c] == TRANSPARENT, f"tool cell ({r},{c}) not transparent"
        rows[r] = rows[r][:c] + key + rows[r][c + 1:]
    palette = dict(PLAYER_SPRITE.palette)
    palette[key] = color
    return Sprite(rows=tuple(rows), palette=palette)


# Clockwise right-side arc, 12 -> 1:30 -> 3 -> 4:30 -> 6 o'clock. Each entry is the
# transparent cell that holds the pickaxe head for that frame (verified against
# PLAYER_SPRITE: these cells are '.').
_GATHER_CLOCK: tuple[tuple[int, int], ...] = ((0, 6), (1, 7), (3, 7), (5, 7), (6, 7))
# Mirror on X (col -> 7-col) for the counterclockwise left-side sword arc.
_FIGHT_CLOCK: tuple[tuple[int, int], ...] = tuple((r, 7 - c) for (r, c) in _GATHER_CLOCK)

GATHER_SWING_FRAMES: tuple[Sprite, ...] = tuple(
    _player_with_tool((rc,), "t", COPPER) for rc in _GATHER_CLOCK
)
FIGHT_SWING_FRAMES: tuple[Sprite, ...] = tuple(
    _player_with_tool((rc,), "t", STEEL) for rc in _FIGHT_CLOCK
)
# Thought bubble at 2 o'clock from the head (upper-right transparent cells).
PLANNING_SPRITE: Sprite = _player_with_tool(((0, 7), (1, 7)), "p", BONE)
```

> Before running: confirm each `_GATHER_CLOCK` cell is `'.'` in `PLAYER_SPRITE.rows` (rows listed in `sprites.py:56-65`). `(0,6)`, `(1,7)`, `(3,7)`, `(5,7)`, `(6,7)` and the planning cells `(0,7)`,`(1,7)` are all transparent there. If a future PLAYER_SPRITE edit fills one, pick the nearest transparent cell on the same arc and update the tuple.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_sprites_animation.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/sprites.py tests/test_tui/test_sprites_animation.py
git commit -m "feat(tui): gather/fight swing frames + planning bubble sprite"
```

---

## Task 6: MapPane integration — persistent timer + mode-driven frames

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/map_pane.py`
- Test: `tests/test_tui/test_map_pane_animation.py`

**Interfaces:**
- Consumes: `swing_frames.current_mode/swing_frame_index/glide_index/Mode` (Task 4); `sprites.GATHER_SWING_FRAMES/FIGHT_SWING_FRAMES/PLANNING_SPRITE` (Task 5); `_planning_active`/`set_planning` (Task 3).
- Produces: `MapPane._player_sprite(now: float) -> Sprite` (pure-ish given widget state; the seam the test drives with a fake clock).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tui/test_map_pane_animation.py
from artifactsmmo_cli.tui.widgets.map_pane import MapPane
from artifactsmmo_cli.tui.sprites import (
    PLAYER_SPRITE, PLANNING_SPRITE, GATHER_SWING_FRAMES, FIGHT_SWING_FRAMES,
)
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.game_data import GameData


def _snap(**kw):
    base = dict(cycle_index=0, timestamp="t", character="c", x=0, y=0, level=1,
                xp=0, max_xp=1, hp=1, max_hp=1, gold=0, selected_goal="g",
                action="x", outcome="ok")
    base.update(kw)
    return CycleSnapshot(**base)


def _pane():
    return MapPane(GameData())


def test_idle_shows_player_sprite():
    p = _pane()
    p.snapshot = _snap(action_kind="rest")
    p._anim_start = 0.0
    assert p._player_sprite(now=1.0) is PLAYER_SPRITE


def test_planning_shows_bubble():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._anim_start = 0.0
    p._planning_active = True
    assert p._player_sprite(now=1.0) is PLANNING_SPRITE


def test_gather_picks_a_swing_frame():
    p = _pane()
    p.snapshot = _snap(action_kind="gather", cooldown_remaining=5.0)
    p._anim_start = 0.0
    assert p._player_sprite(now=0.5) in GATHER_SWING_FRAMES


def test_fight_picks_a_swing_frame():
    p = _pane()
    p.snapshot = _snap(action_kind="fight", cooldown_remaining=5.0)
    p._anim_start = 0.0
    assert p._player_sprite(now=0.5) in FIGHT_SWING_FRAMES


def test_update_snapshot_clears_planning_and_stamps_start(monkeypatch):
    p = _pane()
    p._planning_active = True
    monkeypatch.setattr("artifactsmmo_cli.tui.widgets.map_pane.time.monotonic", lambda: 42.0)
    p.update_snapshot(_snap(action_kind="gather", cooldown_remaining=5.0))
    assert p._planning_active is False
    assert p._anim_start == 42.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -v`
Expected: FAIL (`_player_sprite`/`_anim_start` missing).

- [ ] **Step 3: Implement the integration**

Edits in `map_pane.py`:

(a) Imports (top):
```python
import time
from artifactsmmo_cli.tui.sprites import (
    BLANK_SPRITE, FIGHT_SWING_FRAMES, GATHER_SWING_FRAMES, PLANNING_SPRITE,
    PLAYER_SPRITE, Sprite, SpriteCategory,
)
from artifactsmmo_cli.tui.swing_frames import Mode, current_mode, glide_index, swing_frame_index
```
Add constants near the existing ones:
```python
SWING_SWEEP_SECONDS = 0.8   # one chop/strike; loops over the cooldown
```

(b) `__init__` — add state (keep `_anim_frames`/`_anim_index` for glide positions):
```python
        self._anim_start = 0.0
        self._planning_active = False
```

(c) Replace `update_snapshot` (compute glide positions; stamp start; clear planning; no per-glide timer):
```python
    def update_snapshot(self, snap: CycleSnapshot) -> None:
        prior = self.snapshot
        self.snapshot = snap
        self._anim_start = time.monotonic()
        self._planning_active = False
        if prior is not None and (prior.x, prior.y) != (snap.x, snap.y):
            self._anim_frames = glide_path((prior.x, prior.y), (snap.x, snap.y), MAX_ANIM_STEPS)
        else:
            self._anim_frames = []
        self._anim_index = 0
        self.refresh()
```

(d) Persistent timer — replace `_stop_anim`/`_tick`/`on_unmount` with:
```python
    def on_mount(self) -> None:
        self._anim_timer = self.set_interval(ANIM_FRAME_SECONDS, self._tick)

    def _tick(self) -> None:
        if self._is_animating():
            self.refresh()

    def _is_animating(self) -> bool:
        if self._planning_active:
            return True
        snap = self.snapshot
        if snap is None:
            return False
        elapsed = time.monotonic() - self._anim_start
        return elapsed < snap.cooldown_remaining

    def on_unmount(self) -> None:
        if self._anim_timer is not None:
            self._anim_timer.stop()
            self._anim_timer = None
```
Keep `self._anim_timer: Timer | None = None` in `__init__`.

(e) `set_planning` (from Task 3 — ensure present):
```python
    def set_planning(self, active: bool) -> None:
        self._planning_active = active
        self.refresh()
```

(f) The frame selector + glide center, consumed by render:
```python
    def _player_sprite(self, now: float) -> Sprite:
        snap = self.snapshot
        if snap is None:
            return PLAYER_SPRITE
        elapsed = now - self._anim_start
        mode = current_mode(snap.action_kind, self._planning_active, elapsed, snap.cooldown_remaining)
        if mode is Mode.PLANNING:
            return PLANNING_SPRITE
        if mode is Mode.GATHER_SWING:
            return GATHER_SWING_FRAMES[swing_frame_index(elapsed, len(GATHER_SWING_FRAMES), SWING_SWEEP_SECONDS)]
        if mode is Mode.FIGHT_SWING:
            return FIGHT_SWING_FRAMES[swing_frame_index(elapsed, len(FIGHT_SWING_FRAMES), SWING_SWEEP_SECONDS)]
        return PLAYER_SPRITE

    def _glide_center(self, now: float) -> tuple[int, int] | None:
        if not self._anim_frames:
            return None
        snap = self.snapshot
        duration = snap.cooldown_remaining if snap is not None else 0.0
        idx = glide_index(now - self._anim_start, duration, len(self._anim_frames))
        return self._anim_frames[idx]
```

(g) `render` — use the time-based center; pass the player sprite through:
```python
    def render(self) -> Text:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting for first cycle...")
        width = self.size.width or FALLBACK_W
        height = self.size.height or FALLBACK_H
        now = time.monotonic()
        center = self._glide_center(now)
        return self._render_viewport(snap, width, height, center, self._player_sprite(now))
```

(h) Thread the player sprite into the viewport/tile selection:
```python
    def _tile_sprite_and_terrain(self, wx: int, wy: int, is_player: bool,
                                 player_sprite: Sprite) -> tuple[Sprite, str]:
        if is_player:
            return player_sprite, WALKABLE_COLOR
        content = self._tile_index.get((wx, wy))
        if content is None:
            terrain = WALKABLE_COLOR if (wx, wy) in self._known_tiles else UNMAPPED_COLOR
            return BLANK_SPRITE, terrain
        category, code = content
        return self._registry.sprite_for(code, category), WALKABLE_COLOR
```
Update `_render_viewport` signature to accept `player_sprite: Sprite` and pass it down:
```python
    def _render_viewport(self, snap, width, height, center=None, player_sprite=PLAYER_SPRITE):
        ...
                sprite, terrain = self._tile_sprite_and_terrain(wx, wy, is_player, player_sprite)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_tui/test_map_pane_animation.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full TUI suite**

Run: `uv run pytest tests/test_tui/ -q --no-cov`
Expected: PASS (existing map_pane tests still green; if a test asserted the old `_tile_sprite_and_terrain` arity or the per-glide timer, update it to the new signature/behavior, keeping its intent).

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/map_pane.py tests/test_tui/test_map_pane_animation.py
git commit -m "feat(tui): persistent timer + mode-driven player frames + cooldown-scaled glide"
```

---

## Task 7: Full gate + manual smoke

**Files:** none (verification only).

- [ ] **Step 1: Full suite with coverage**

Run: `uv run pytest -q`
Expected: PASS at the project's coverage gate. If new Textual-glue lines (timer wiring in `on_mount`/`_tick`) are genuinely untestable, add a written carve-out per the project's coverage policy and cite it in the commit.

- [ ] **Step 2: mypy + lint**

Run: `uv run mypy src/artifactsmmo_cli/tui src/artifactsmmo_cli/ai/action_kind.py`
Expected: no issues.

- [ ] **Step 3: Manual smoke (optional but recommended)**

Run the watch TUI against the live character and eyeball: movement glides and lands just before the next action; gathering shows the pickaxe chopping on the right; combat shows the sword on the left; a bubble appears top-right while the planner is deciding.
Run: `uv run artifactsmmo play Robby` (or the project's watch command).

- [ ] **Step 4: Commit any coverage carve-out / fixups**

```bash
git add -A
git commit -m "test(tui): coverage carve-out justification for Textual timer glue"
```

---

## Self-Review

**Spec coverage:**
- Feature 1 (move scaled to cooldown) → Task 4 `glide_index` + Task 6 `_glide_center`/`render`. ✓
- Feature 2 (gather swing CW) → Task 5 `GATHER_SWING_FRAMES` + Task 6 `_player_sprite`. ✓
- Feature 3 (combat swing CCW) → Task 5 `FIGHT_SWING_FRAMES` (mirrored) + Task 6. ✓
- Feature 4 (planning bubble) → Task 3 signal + Task 5 `PLANNING_SPRITE` + Task 6. ✓
- Structured snapshot fields → Task 2. ✓
- Persistent timer → Task 6. ✓
- Edge cases (no cooldown, elapsed past cooldown, single glide frame, degenerate sweep, headless no-op) → Task 4 tests + Task 3 `notify_planning` None-guard. ✓

**Type consistency:** `action_kind_of -> (str, str|None)` consumed in Task 2; `current_mode/swing_frame_index/glide_index` signatures identical across Tasks 4 and 6; `_player_sprite(now)`/`_glide_center(now)` and `_render_viewport(..., player_sprite)` consistent within Task 6; `ThreadSafeBridge(app, handler, planning_handler=...)` consistent across Tasks 3 and the play.py wiring.

**Placeholder scan:** none — every code step shows full code; sprite cells enumerated; clock tables concrete.

**Scope:** single subsystem (map TUI animation), one plan.
