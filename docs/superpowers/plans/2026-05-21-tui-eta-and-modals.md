# TUI ETA + Character/Log Modals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a task-completion ETA to the status pane, and full-screen `c` (character detail) and `l` (debug log) modals to the watch TUI.

**Architecture:** Pure helpers (`task_eta_seconds`/`format_eta`, `build_character_detail`, `build_debug_log_line`) hold the logic and are unit-tested directly. Two `Screen` subclasses provide the modals; `WatchApp` gains key bindings, a latest-snapshot ref, a capped recent-snapshot deque, and modal push/pop wiring. Screens verified with Textual's `App.run_test()`.

**Tech Stack:** Python 3.13, `uv`, pytest, Textual (Screen/run_test), Rich.

---

## File Structure
- Modify `src/artifactsmmo_cli/tui/widgets/status_pane.py` — ETA samples + row + pure `task_eta_seconds`, `format_eta`, `_epoch`.
- Create `src/artifactsmmo_cli/tui/screens/__init__.py`.
- Create `src/artifactsmmo_cli/tui/screens/character_screen.py` — `CharacterScreen` + `build_character_detail`.
- Create `src/artifactsmmo_cli/tui/screens/log_screen.py` — `LogScreen` + `build_debug_log_line`.
- Modify `src/artifactsmmo_cli/tui/app.py` — bindings, snapshot buffer, modal actions, dispatch.
- Tests under `tests/test_tui/`.

All test files reuse the existing `_snap(**overrides)` builder pattern (see `tests/test_tui/test_status_pane.py` and `test_app.py`).

---

## Task 1: Task ETA helpers + status row

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/status_pane.py`
- Test: `tests/test_tui/test_status_pane.py`

- [ ] **Step 1: Write failing tests for the pure helpers**

Add to `tests/test_tui/test_status_pane.py`:

```python
from artifactsmmo_cli.tui.widgets.status_pane import (
    StatusPane, task_eta_seconds, format_eta,
)


class TestTaskEta:
    def test_none_with_fewer_than_two_samples(self):
        assert task_eta_seconds([], remaining=5) is None
        assert task_eta_seconds([(0.0, 0)], remaining=5) is None

    def test_none_when_no_time_span(self):
        assert task_eta_seconds([(10.0, 0), (10.0, 2)], remaining=5) is None

    def test_none_when_rate_not_positive(self):
        assert task_eta_seconds([(0.0, 3), (60.0, 3)], remaining=5) is None  # no progress
        assert task_eta_seconds([(0.0, 5), (60.0, 3)], remaining=5) is None  # went down

    def test_steady_progress(self):
        # 2 progress over 60s = 0.0333/s; remaining 4 -> 120s
        assert task_eta_seconds([(0.0, 0), (60.0, 2)], remaining=4) == 120.0

    def test_format_eta_sub_minute(self):
        assert format_eta(45.0) == "~45s"

    def test_format_eta_minutes(self):
        assert format_eta(250.0) == "~4m 10s"
```

- [ ] **Step 2: Run, confirm FAIL** — `uv run pytest tests/test_tui/test_status_pane.py -k "TaskEta" -v` → ImportError.

- [ ] **Step 3: Implement the helpers**

In `src/artifactsmmo_cli/tui/widgets/status_pane.py`, add at module level (top imports: `from datetime import datetime`):

```python
ETA_WINDOW = 20
"""Number of recent (time, progress) samples used to estimate task ETA."""


def _epoch(timestamp: str) -> float:
    """ISO-8601 (UTC, possibly trailing 'Z') -> epoch seconds."""
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp()


def task_eta_seconds(samples: list[tuple[float, int]], remaining: int) -> float | None:
    """Estimate seconds to finish `remaining` task units from (time, progress)
    samples. None when there is too little data or no positive progress rate."""
    if len(samples) < 2:
        return None
    t0, p0 = samples[0]
    t1, p1 = samples[-1]
    span = t1 - t0
    gained = p1 - p0
    if span <= 0 or gained <= 0:
        return None
    rate = gained / span
    return remaining / rate


def format_eta(seconds: float) -> str:
    """Human ETA: '~45s' under a minute, else '~Xm Ys'."""
    total = int(seconds)
    if total < 60:
        return f"~{total}s"
    return f"~{total // 60}m {total % 60}s"
```

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_tui/test_status_pane.py -k "TaskEta" -v`.

- [ ] **Step 5: Write failing tests for the ETA row**

```python
class TestStatusEtaRow:
    def test_eta_dash_before_enough_samples(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="t", task_type="items",
                                   task_progress=0, task_total=10,
                                   timestamp="2026-05-21T12:00:00Z"))
        assert "ETA" in _render(pane)
        assert "—" in _render(pane)

    def test_eta_shows_estimate_with_progress(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="t", task_type="items",
                                   task_progress=0, task_total=10,
                                   timestamp="2026-05-21T12:00:00Z"))
        pane.update_snapshot(_snap(task_code="t", task_type="items",
                                   task_progress=2, task_total=10,
                                   timestamp="2026-05-21T12:01:00Z"))
        out = _render(pane)
        assert "ETA" in out and "~" in out and "m" in out  # 8 remaining at 2/60s

    def test_eta_resets_on_task_change(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="a", task_total=5, task_progress=1,
                                   timestamp="2026-05-21T12:00:00Z"))
        pane.update_snapshot(_snap(task_code="b", task_total=5, task_progress=0,
                                   timestamp="2026-05-21T12:00:30Z"))
        # only 1 sample for task b -> dash
        assert "—" in _render(pane)

    def test_no_eta_row_without_task(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code=None))
        assert "ETA" not in _render(pane)
```

- [ ] **Step 6: Run, confirm FAIL** — the new pane tests fail (no ETA row / no sample tracking yet).

- [ ] **Step 7: Implement sample tracking + the row**

In `StatusPane`, track samples in `update_snapshot` and add the row in `_render_status`. Add an `__init__` (StatusPane currently has none — Static's default):

```python
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._eta_task: str | None = None
        self._eta_samples: list[tuple[float, int]] = []

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._track_eta(snap)
        self.snapshot = snap

    def _track_eta(self, snap: CycleSnapshot) -> None:
        if not snap.task_code:
            self._eta_task = None
            self._eta_samples = []
            return
        if snap.task_code != self._eta_task:
            self._eta_task = snap.task_code
            self._eta_samples = []
        self._eta_samples.append((_epoch(snap.timestamp), snap.task_progress))
        if len(self._eta_samples) > ETA_WINDOW:
            self._eta_samples = self._eta_samples[-ETA_WINDOW:]
```

In `_render_status`, right after the existing Task row, add (only when a task is active):

```python
        if s.task_code:
            remaining = max(0, s.task_total - s.task_progress)
            eta = task_eta_seconds(self._eta_samples, remaining)
            t.add_row("ETA", format_eta(eta) if eta is not None else "[dim]—[/dim]")
```

(Keep the existing `update_snapshot` body's `self.snapshot = snap` — it now lives after `_track_eta`.)

- [ ] **Step 8: Run, confirm PASS** — `uv run pytest tests/test_tui/test_status_pane.py -q`.

- [ ] **Step 9: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/status_pane.py tests/test_tui/test_status_pane.py
git commit -m "feat(tui): task-completion ETA in the status pane"
```

---

## Task 2: CharacterScreen modal + detail builder

**Files:**
- Create: `src/artifactsmmo_cli/tui/screens/__init__.py` (empty)
- Create: `src/artifactsmmo_cli/tui/screens/character_screen.py`
- Test: `tests/test_tui/test_character_screen.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tui/test_character_screen.py`:

```python
from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.screens.character_screen import build_character_detail


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=3, y=4, level=5, xp=120, max_xp=500, hp=80, max_hp=150, gold=42,
        selected_goal="g", action="a", outcome="ok",
        skills={"mining": 10, "alchemy": 1}, skill_xp={"mining": 50, "alchemy": 5},
        equipment={"weapon_slot": "copper_axe", "shield_slot": None},
        task_code="small_health_potion", task_type="items",
        task_progress=2, task_total=29,
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def test_detail_includes_vitals_and_task():
    out = _text(build_character_detail(_snap()))
    assert "hero" in out and "L5" in out
    assert "80/150" in out          # hp
    assert "42" in out              # gold
    assert "(3,4)" in out
    assert "small_health_potion" in out and "2/29" in out


def test_detail_lists_all_skills_with_level_and_xp():
    out = _text(build_character_detail(_snap()))
    assert "mining" in out and "10" in out and "50" in out
    assert "alchemy" in out

def test_detail_lists_equipment_slots():
    out = _text(build_character_detail(_snap()))
    assert "weapon_slot" in out and "copper_axe" in out
    assert "shield_slot" in out and "—" in out   # empty slot

def test_detail_no_task():
    out = _text(build_character_detail(_snap(task_code=None)))
    assert "none" in out.lower()
```

- [ ] **Step 2: Run, confirm FAIL** — ModuleNotFoundError.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/tui/screens/__init__.py` (empty file).

Create `src/artifactsmmo_cli/tui/screens/character_screen.py`:

```python
"""Full-screen character detail modal (toggled with 'c')."""

from rich.console import RenderableType
from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_character_detail(snap: CycleSnapshot) -> RenderableType:
    """Full character detail from a snapshot: vitals, all skills (level + xp),
    every equipment slot, and the current task. Combat stats are not in the
    snapshot and are intentionally omitted."""
    t = Table(box=None, padding=(0, 2), show_header=False, title=f"{snap.character}  L{snap.level}")
    t.add_column("k", style="dim")
    t.add_column("v")
    t.add_row("HP", f"{snap.hp}/{snap.max_hp}")
    t.add_row("XP", f"{snap.xp}/{snap.max_xp}")
    t.add_row("Gold", str(snap.gold))
    t.add_row("Pos", f"({snap.x},{snap.y})")
    if snap.task_code:
        t.add_row("Task", f"{snap.task_code}  {snap.task_progress}/{snap.task_total}")
    else:
        t.add_row("Task", "none")
    t.add_row("", "")
    for skill in sorted(snap.skills):
        xp = snap.skill_xp.get(skill, 0)
        t.add_row(skill, f"L{snap.skills[skill]}   xp {xp}")
    t.add_row("", "")
    for slot in sorted(snap.equipment):
        t.add_row(slot, snap.equipment[slot] or "—")
    return t


class CharacterScreen(Screen):
    """Modal full-screen character detail. Dismiss with 'c' or Escape."""

    BINDINGS = [("escape", "dismiss", "Back"), ("c", "dismiss", "Back")]

    def __init__(self, snapshot: CycleSnapshot, **kwargs) -> None:
        super().__init__(**kwargs)
        self._snapshot = snapshot

    def compose(self) -> ComposeResult:
        yield Static(build_character_detail(self._snapshot), id="char-detail")

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._snapshot = snap
        self.query_one("#char-detail", Static).update(build_character_detail(snap))
```

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_tui/test_character_screen.py -v`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/__init__.py src/artifactsmmo_cli/tui/screens/character_screen.py tests/test_tui/test_character_screen.py
git commit -m "feat(tui): CharacterScreen full-detail modal"
```

---

## Task 3: LogScreen modal + debug log builder

**Files:**
- Create: `src/artifactsmmo_cli/tui/screens/log_screen.py`
- Test: `tests/test_tui/test_log_screen.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_tui/test_log_screen.py`:

```python
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, GoalRankEntry
from artifactsmmo_cli.tui.screens.log_screen import build_debug_log_line


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=7, timestamp="2026-05-21T12:34:56Z", character="hero",
        x=3, y=4, level=5, xp=0, max_xp=100, hp=80, max_hp=150, gold=0,
        selected_goal="FarmItems", action="Craft(potion)", outcome="ok",
        task_code="potion", task_type="items", task_progress=2, task_total=29,
        cooldown_remaining=4.5, path_next_action="green_slime",
        projected_cycles_to_max=1234.0,
        goal_rank=[GoalRankEntry(goal="FarmItems", priority=75.0),
                   GoalRankEntry(goal="TaskCancel", priority=0.0)],
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def test_debug_line_has_core_fields():
    line = build_debug_log_line(_snap())
    assert "12:34:56" in line and "c  7" in line.replace(" ", " ")  # cycle index present
    assert "FarmItems" in line and "Craft(potion)" in line and "ok" in line

def test_debug_line_has_debug_detail():
    line = build_debug_log_line(_snap())
    assert "2/29" in line              # task progress
    assert "80/150" in line            # hp
    assert "4.5" in line               # cooldown
    assert "(3,4)" in line             # position
    assert "green_slime" in line       # path next
    assert "1234" in line              # projected cycles

def test_debug_line_includes_full_goal_rank():
    line = build_debug_log_line(_snap())
    # full ranking (priority > 0): FarmItems shown; zero-priority omitted
    assert "FarmItems" in line and "75" in line
    assert "TaskCancel" not in line    # priority 0 filtered
```

(Adjust the `"c  7"` assertion to match the exact format you emit; assert the cycle number appears.)

- [ ] **Step 2: Run, confirm FAIL** — ModuleNotFoundError.

- [ ] **Step 3: Implement**

Create `src/artifactsmmo_cli/tui/screens/log_screen.py`:

```python
"""Full-screen debug-level game log modal (toggled with 'l')."""

from collections.abc import Iterable

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def build_debug_log_line(snap: CycleSnapshot) -> str:
    """Rich-markup debug record for one cycle: the compact decision line plus
    task progress, vitals, cooldown, position, path-next, projected cycles, and
    the full goal-rank ranking (priority > 0)."""
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    outcome_color = {"ok": "green", "no_plan": "yellow"}.get(snap.outcome, "red")
    ranks = "  ".join(
        f"{gr.goal}={gr.priority:.0f}" for gr in snap.goal_rank if gr.priority > 0
    )
    task = f"{snap.task_progress}/{snap.task_total}" if snap.task_code else "-"
    proj = f"{snap.projected_cycles_to_max:.0f}" if snap.projected_cycles_to_max is not None else "?"
    return (
        f"[dim]{ts}[/dim] c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal}[/cyan] {snap.action} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}] "
        f"| task {task} hp {snap.hp}/{snap.max_hp} cd {snap.cooldown_remaining:.1f} "
        f"pos ({snap.x},{snap.y}) next {snap.path_next_action or '?'} proj {proj} "
        f"| {ranks}"
    )


class LogScreen(Screen):
    """Modal full-screen debug log. Dismiss with 'l' or Escape."""

    BINDINGS = [("escape", "dismiss", "Back"), ("l", "dismiss", "Back")]

    def __init__(self, history: Iterable[CycleSnapshot], **kwargs) -> None:
        super().__init__(**kwargs)
        self._history = list(history)

    def compose(self) -> ComposeResult:
        log = RichLog(wrap=False, markup=True, auto_scroll=True, id="debug-log")
        yield log

    def on_mount(self) -> None:
        log = self.query_one("#debug-log", RichLog)
        for snap in self._history:
            log.write(build_debug_log_line(snap))

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.query_one("#debug-log", RichLog).write(build_debug_log_line(snap))
```

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_tui/test_log_screen.py -v`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/screens/log_screen.py tests/test_tui/test_log_screen.py
git commit -m "feat(tui): LogScreen debug-level log modal"
```

---

## Task 4: Wire bindings, snapshot buffer, and modal toggles into WatchApp

**Files:**
- Modify: `src/artifactsmmo_cli/tui/app.py`
- Test: `tests/test_tui/test_app.py`

- [ ] **Step 1: Write failing tests (Textual `run_test`)**

Add to `tests/test_tui/test_app.py`:

```python
import pytest
from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.log_screen import LogScreen


class TestWatchAppBuffers:
    def test_update_stores_last_and_recent(self):
        app = _make_app()
        # exercise the pure storage method without a running app loop
        app._store_snapshot(_snap(cycle_index=1))
        app._store_snapshot(_snap(cycle_index=2))
        assert app._last_snapshot.cycle_index == 2
        assert len(app._recent_snapshots) == 2

    def test_recent_snapshots_capped(self):
        app = _make_app()
        for i in range(app.LOG_BUFFER + 50):
            app._store_snapshot(_snap(cycle_index=i))
        assert len(app._recent_snapshots) == app.LOG_BUFFER


class TestWatchAppModals:
    @pytest.mark.asyncio
    async def test_c_toggles_character_screen(self):
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap())
            await pilot.press("c")
            assert isinstance(app.screen, CharacterScreen)
            await pilot.press("c")
            assert not isinstance(app.screen, CharacterScreen)

    @pytest.mark.asyncio
    async def test_l_toggles_log_screen(self):
        app = _make_app()
        async with app.run_test() as pilot:
            app.update_snapshot(_snap())
            await pilot.press("l")
            assert isinstance(app.screen, LogScreen)
            await pilot.press("escape")
            assert not isinstance(app.screen, LogScreen)
```

(`asyncio_mode = "auto"` is already set in pyproject per existing app tests; the `@pytest.mark.asyncio` is harmless/optional — match how `test_app.py`'s existing `run_test` tests are marked.)

- [ ] **Step 2: Run, confirm FAIL** — no `_store_snapshot`/`LOG_BUFFER`/bindings yet.

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/tui/app.py`:

Add imports:
```python
from collections import deque

from artifactsmmo_cli.tui.screens.character_screen import CharacterScreen
from artifactsmmo_cli.tui.screens.log_screen import LogScreen
```

Class changes:
```python
    LOG_BUFFER = 500

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("c", "toggle_character", "Character"),
        ("l", "toggle_log", "Log"),
    ]

    def __init__(self, character: str, game_data: GameData, **kwargs) -> None:
        super().__init__(**kwargs)
        self._character = character
        self._game_data = game_data
        self.title = f"artifactsmmo watch: {character}"
        self._last_snapshot: CycleSnapshot | None = None
        self._recent_snapshots: deque[CycleSnapshot] = deque(maxlen=self.LOG_BUFFER)

    def _store_snapshot(self, snap: CycleSnapshot) -> None:
        self._last_snapshot = snap
        self._recent_snapshots.append(snap)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._store_snapshot(snap)
        self.query_one("#status", StatusPane).update_snapshot(snap)
        self.query_one("#map", MapPane).update_snapshot(snap)
        self.query_one("#inv", InventoryPane).update_snapshot(snap)
        self.query_one("#log", LogPane).update_snapshot(snap)
        top = self.screen
        if isinstance(top, (CharacterScreen, LogScreen)):
            top.update_snapshot(snap)

    def action_toggle_character(self) -> None:
        if isinstance(self.screen, CharacterScreen):
            self.pop_screen()
        elif self._last_snapshot is not None:
            self.push_screen(CharacterScreen(self._last_snapshot))

    def action_toggle_log(self) -> None:
        if isinstance(self.screen, LogScreen):
            self.pop_screen()
        else:
            self.push_screen(LogScreen(self._recent_snapshots))
```

(`deque` passed to `LogScreen(history=...)` is iterable — its `__init__` does `list(history)`.)

- [ ] **Step 4: Run, confirm PASS** — `uv run pytest tests/test_tui/test_app.py -q`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/tui/app.py tests/test_tui/test_app.py
git commit -m "feat(tui): c/l bindings, snapshot buffer, modal push/pop wiring"
```

---

## Task 5: Verification

**Files:** none.

- [ ] **Step 1:** `uv run pytest -q` — all pass, 0 skipped.
- [ ] **Step 2:** Coverage:
  `uv run pytest --cov=artifactsmmo_cli.tui.widgets.status_pane --cov=artifactsmmo_cli.tui.screens.character_screen --cov=artifactsmmo_cli.tui.screens.log_screen --cov=artifactsmmo_cli.tui.app --cov-report=term-missing -q` — 100% on the new/changed modules; add focused tests for any missed branch (e.g. `task_eta_seconds` rate-zero, `_track_eta` no-task reset, `action_toggle_character` with no snapshot).
- [ ] **Step 3:** `uv run ruff check <changed files>` clean; `uv run mypy src/artifactsmmo_cli/tui` — no new errors vs main.
- [ ] **Step 4:** Commit any coverage/lint fixes.

```bash
git add -A
git commit -m "test(tui): close coverage gaps for ETA + modals"
```

---

## Self-review notes
- Spec coverage: ETA samples + pure helpers + row (Task 1); CharacterScreen + builder, full skills/equipment/vitals/task (Task 2); LogScreen + debug builder with full goal_rank (Task 3); app bindings + buffer + modal wiring + live refresh (Task 4); verification incl. coverage (Task 5). All spec sections mapped.
- Type consistency: `task_eta_seconds(samples, remaining)`, `format_eta(seconds)`, `build_character_detail(snap)`, `build_debug_log_line(snap)`, `_store_snapshot`, `LOG_BUFFER`, `ETA_WINDOW` used identically across tasks; screens take `(snapshot)` / `(history)` and expose `update_snapshot`.
- Placeholder check: the only fuzzy assertion is the LogScreen `"c  7"` cycle-number check — Task 3 Step 1 explicitly tells the implementer to match the emitted format and just assert the cycle number appears. Everything else is concrete.
- Combat stats excluded from the character view per spec (not in snapshot).
