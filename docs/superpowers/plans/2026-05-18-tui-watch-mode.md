# TUI Watch Mode for `play` Command — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a live TUI to the `play` command so a human can watch a character play in real time. Four-pane Textual layout: character status, NetHack-inspired map, inventory, scrolling log of decisions. Reads bot state directly (in-process), no file polling.

**Architecture:** Textual app runs in the main thread. `GamePlayer.run()` runs in a worker thread. Bot exposes a `cycle_observer` callable invoked at the end of every cycle with `(state, decision_context)`. TUI subscribes; updates widgets via `App.call_from_thread()` to stay thread-safe.

**Spec:** None — design discussed inline. Single-char focus, static map viewport, snapshot-style state delivery via observer (no file IO), default TTY colors.

**Tech Stack:** Python 3.13, uv, Textual (>=0.50), Rich (transitive). New CLI flag `--tui` on existing `play` command.

---

## File Structure

### New files
```
src/artifactsmmo_cli/tui/
├── __init__.py
├── app.py                       # Textual App subclass with 4-pane layout
├── widgets/
│   ├── __init__.py
│   ├── status_pane.py           # HP/XP/level/gold/current goal/path
│   ├── inventory_pane.py        # item codes + qty (sorted desc), equipped slots
│   ├── map_pane.py              # NetHack-style viewport centered on @
│   └── log_pane.py              # scrolling decision log
├── observer.py                  # CycleObserver protocol + ThreadSafeBridge
└── glyphs.py                    # entity→glyph mapping table
```

### Modified files
```
src/artifactsmmo_cli/ai/player.py     # add cycle_observer hook + call site
src/artifactsmmo_cli/commands/play.py # add --tui flag, spawn worker thread + TUI
pyproject.toml                         # add textual dependency
```

---

## Task T-1: Bot-side observer hook

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Modify: `tests/test_ai/test_player.py` (one new test)

GamePlayer gets an optional `cycle_observer: Callable[[CycleSnapshot], None] | None` constructor argument. At the end of each cycle (after `_emit_trace`), invoke it with a frozen snapshot.

**`CycleSnapshot` pydantic model** (lives in `src/artifactsmmo_cli/ai/cycle_snapshot.py`):

```python
from pydantic import BaseModel, Field

class GoalRankEntry(BaseModel):
    goal: str
    priority: float

class CycleSnapshot(BaseModel):
    """Frozen per-cycle state + decision context the TUI consumes."""
    cycle_index: int
    timestamp: str               # ISO-8601 UTC
    character: str
    # State
    x: int
    y: int
    level: int
    xp: int
    max_xp: int
    hp: int
    max_hp: int
    gold: int
    inventory: dict[str, int]
    inventory_max: int
    equipment: dict[str, str | None]
    skills: dict[str, int]
    skill_xp: dict[str, int]
    task_code: str | None
    task_type: str | None
    task_progress: int
    task_total: int
    # Decision
    selected_goal: str
    action: str
    outcome: str
    goal_rank: list[GoalRankEntry] = Field(default_factory=list)
    path_next_action: str | None = None
    projected_cycles_to_max: float | None = None
    max_level: int = 0
    remaining_levels: int = 0
```

- [ ] **Step 1: Write the failing test**

```python
def test_cycle_observer_invoked_with_snapshot():
    calls = []
    player = GamePlayer(character="hero",
                         cycle_observer=lambda snap: calls.append(snap))
    # ... drive one cycle ...
    assert len(calls) == 1
    assert calls[0].character == "hero"
    assert calls[0].cycle_index == 0
```

- [ ] **Step 2: Add to `GamePlayer.__init__`**

```python
def __init__(self, ..., cycle_observer: Callable[[CycleSnapshot], None] | None = None):
    ...
    self._cycle_observer = cycle_observer
```

- [ ] **Step 3: Build + invoke snapshot at end of cycle**

After `_emit_trace(...)` in both branches (success and no_plan), add:

```python
if self._cycle_observer is not None:
    snap = CycleSnapshot(
        cycle_index=self._cycle_counter,
        timestamp=datetime.now(tz=timezone.utc).isoformat(),
        character=self.character,
        x=self.state.x, y=self.state.y,
        level=self.state.level, xp=self.state.xp, max_xp=self.state.max_xp,
        hp=self.state.hp, max_hp=self.state.max_hp,
        gold=self.state.gold,
        inventory=dict(self.state.inventory),
        inventory_max=self.state.inventory_max,
        equipment=dict(self.state.equipment),
        skills=dict(self.state.skills),
        skill_xp=dict(self.state.skill_xp),
        task_code=self.state.task_code,
        task_type=self.state.task_type,
        task_progress=self.state.task_progress,
        task_total=self.state.task_total,
        selected_goal=repr(selected_goal) if selected_goal else "<none>",
        action=repr(action) if action else "<no_plan>",
        outcome=outcome,
        goal_rank=[GoalRankEntry(goal=e["goal"], priority=e["priority"]) for e in goal_rank_trace],
        path_next_action=plan.next_action_monster if (plan := self._last_path_plan) else None,
        projected_cycles_to_max=(self._last_path_plan.total_cycles
                                  if self._last_path_plan and self._last_path_plan.total_cycles != float("inf")
                                  else None),
        max_level=self.game_data.max_character_level if self.game_data else 0,
        remaining_levels=max(0, (self.game_data.max_character_level if self.game_data else 0) - self.state.level),
    )
    self._cycle_observer(snap)
```

- [ ] **Step 4: Tests pass.** Commit.

---

## Task T-2: Add `textual` dependency

- [ ] `uv add textual`
- [ ] Verify it installs cleanly. Commit lockfile + pyproject.

---

## Task T-3: Glyph mapping module

**Files:** `src/artifactsmmo_cli/tui/glyphs.py`

NetHack-faithful entity→glyph table:

```python
"""Map (x,y) tile content → single character + color for the map pane."""

PLAYER_GLYPH = "@"
PLAYER_COLOR = "yellow"

CONTENT_GLYPHS = {
    "monster":    ("M", "red"),
    "resource_woodcutting": ("T", "green"),
    "resource_mining":      ("*", "yellow"),
    "resource_fishing":     ("~", "blue"),
    "resource_alchemy":     ("%", "magenta"),
    "bank":       ("$", "yellow"),
    "tasks_master": ("?", "cyan"),
    "npc":        ("!", "cyan"),
    "workshop":   ("W", "white"),
    "transition": (">", "magenta"),
}

UNMAPPED_GLYPH = " "
WALKABLE_GLYPH = "·"
```

- [ ] Pure data file, no logic. Tests assert table has expected keys.
- [ ] Commit.

---

## Task T-4: Map pane widget

**Files:** `src/artifactsmmo_cli/tui/widgets/map_pane.py`

```python
class MapPane(Static):
    """Static-viewport NetHack-style map centered on player."""

    VIEWPORT_W = 41   # odd so player is centered
    VIEWPORT_H = 21

    def __init__(self, game_data: GameData, **kwargs):
        super().__init__(**kwargs)
        self._game_data = game_data
        self._snap: CycleSnapshot | None = None

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snap = snap
        self.refresh()

    def render(self) -> RenderableType:
        if self._snap is None:
            return "Waiting for first cycle..."
        return self._render_viewport(self._snap)

    def _render_viewport(self, snap: CycleSnapshot) -> str:
        # Center on (snap.x, snap.y); render VIEWPORT_W x VIEWPORT_H grid.
        # Use Rich Text for per-cell color.
        ...
```

Resolution: a Rich `Text` per row, joined with newlines. Each cell consults:
- player position → PLAYER_GLYPH
- game_data._monster_locations (any monster at (x,y))
- game_data._resource_locations + resource skill (woodcutting/mining/etc)
- game_data._npc_locations, _bank_location, _taskmaster_location
- game_data._transition_tiles

- [ ] Test: synthetic GameData + snapshot → assert specific glyphs at specific viewport cells.
- [ ] Commit.

---

## Task T-5: Status / Inventory / Log panes

**Files:**
- `src/artifactsmmo_cli/tui/widgets/status_pane.py`
- `src/artifactsmmo_cli/tui/widgets/inventory_pane.py`
- `src/artifactsmmo_cli/tui/widgets/log_pane.py`

### StatusPane

Renders:
- `L{level}  HP:[bar]  XP:[bar] {xp}/{max_xp}  Gold: {gold}`
- `Goal: {selected_goal} ({priority})`
- `Path → L{max_level}: {projected_cycles_to_max} cyc, next={path_next_action}`
- `Task: {task_code} {task_progress}/{task_total}` (or "no task")
- HP bar red below 25%

### InventoryPane

Renders a sorted (desc by qty) list of items. Each line: `{qty:>4}  {code}`. Header line: `Inventory {used}/{max}`. Highlight equipped slots in a second sub-table.

### LogPane

Append-only log of `[hh:mm:ss] cycle={n} goal={g} action={a} outcome={o}`. Auto-scroll to bottom. Color outcome (ok=green, error*=red, no_plan=yellow). Use `RichLog` (Textual's built-in) — handles wrapping + scrollback.

- [ ] Each widget has its own `update_snapshot(snap)` method.
- [ ] Tests for each (snapshot → expected lines).
- [ ] Commit.

---

## Task T-6: App + observer bridge + CLI integration

**Files:**
- `src/artifactsmmo_cli/tui/app.py`
- `src/artifactsmmo_cli/tui/observer.py`
- `src/artifactsmmo_cli/commands/play.py` (modify)

### Observer bridge

```python
# observer.py
class ThreadSafeBridge:
    """Bot worker thread → main UI thread. Bot calls `notify(snap)`;
    bridge schedules `app.call_from_thread(handler, snap)`."""

    def __init__(self, app: App, handler: Callable[[CycleSnapshot], None]):
        self._app = app
        self._handler = handler

    def notify(self, snap: CycleSnapshot) -> None:
        self._app.call_from_thread(self._handler, snap)
```

### App

```python
# app.py
class WatchApp(App):
    """Textual watch-mode app. Lays out the four panes."""

    CSS = """..."""  # grid layout

    def __init__(self, character: str, game_data: GameData, **kw):
        super().__init__(**kw)
        self._character = character
        self._game_data = game_data

    def compose(self) -> ComposeResult:
        yield Header()
        with Grid(id="root"):
            yield StatusPane(id="status")
            yield MapPane(self._game_data, id="map")
            yield InventoryPane(id="inv")
            yield LogPane(id="log")
        yield Footer()

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        """Called from main thread via ThreadSafeBridge."""
        self.query_one("#status", StatusPane).update_snapshot(snap)
        self.query_one("#map", MapPane).update_snapshot(snap)
        self.query_one("#inv", InventoryPane).update_snapshot(snap)
        self.query_one("#log", LogPane).update_snapshot(snap)
```

### CLI

```python
# commands/play.py
def play(
    character: str,
    learn: bool = typer.Option(False, "--learn"),
    learn_db: Path | None = typer.Option(None, "--learn-db"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    tui: bool = typer.Option(False, "--tui", help="Watch the character via a TUI"),
):
    ...
    if tui:
        _play_with_tui(player, client)
    else:
        player.run(client)

def _play_with_tui(player: GamePlayer, client: AuthenticatedClient):
    import threading
    from artifactsmmo_cli.tui.app import WatchApp
    from artifactsmmo_cli.tui.observer import ThreadSafeBridge

    # Game_data must be loaded before app starts so the map can render.
    player.game_data = GameData.load(client)
    app = WatchApp(character=player.character, game_data=player.game_data)
    bridge = ThreadSafeBridge(app, app.update_snapshot)
    player.set_cycle_observer(bridge.notify)

    bot_thread = threading.Thread(target=player.run, args=(client,), daemon=True)

    def on_mount() -> None:
        bot_thread.start()
    app.on_mount = on_mount  # or use App.on_mount hook

    app.run()
    # When user quits the TUI, the daemon thread is killed with the process.
```

- [ ] Tests: smoke-test `WatchApp` with fake snapshots; assert layout renders.
- [ ] Manual: `uv run artifactsmmo play Robby --tui` opens the TUI, shows live updates.
- [ ] Commit.

---

## Final validation

- [ ] Full test suite: `uv run pytest -q`
- [ ] Manual: run `uv run artifactsmmo play Robby --tui --learn --learn-db ...`. Verify all four panes populate as cycles tick. Quit cleanly (q or Ctrl+C).
- [ ] Doc: update `README` / `docs/PLAN_artifactsmmo_cli.md` to mention `--tui`.
