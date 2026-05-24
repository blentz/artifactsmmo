# TUI Live Cooldown Countdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the `StatusPane` cooldown readout tick down in real time (1s) instead of sitting frozen between AI cycles.

**Architecture:** Store a monotonic `_cooldown_expiry` set from each snapshot's fresh `cooldown_remaining`; a 1-second `set_interval` timer re-renders while a countdown is active; the Cooldown row reads a live `_cooldown_remaining()` shown as ceil-seconds. Only `StatusPane` changes.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff line-length 120, mypy --strict), Textual widget, Rich Table. Spec: `docs/superpowers/specs/2026-05-24-tui-live-cooldown-countdown-design.md`.

---

## File Structure

- `src/artifactsmmo_cli/tui/widgets/status_pane.py` — MODIFY: add `import math`/`import time`; `_cooldown_expiry` state; `_cooldown_remaining()` helper; `on_mount` timer + `_tick`; set expiry in `update_snapshot`; render the live value.
- `tests/test_tui/test_status_pane.py` — MODIFY: add countdown tests (monkeypatching `time.monotonic`); update the two ceil-seconds assertions.

The existing tests render `StatusPane()` directly (no Textual app), so the countdown logic must be exercised through the pure helpers/`render` with `time.monotonic` pinned — the timer (`on_mount`/`set_interval`) is thin glue not run in unit tests.

Reference — current relevant code in `status_pane.py`:
- `update_snapshot` (lines 55-57): calls `_track_eta`, sets `self.snapshot`.
- Cooldown render (lines 95-99): `if s.cooldown_remaining > 0: ... f"{s.cooldown_remaining:.1f}s" ... else "ready"`.
- `__init__` (50-53) sets `_eta_task`/`_eta_samples`.

---

### Task 1: Live countdown state, helper, timer, and render

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/status_pane.py`
- Test: `tests/test_tui/test_status_pane.py`

- [ ] **Step 1: Write the failing tests**

Add a new test class to `tests/test_tui/test_status_pane.py` (the file already has `_snap`, `_render`, `StatusPane` imported). Add `import time` and `import math` at the top of the test file if not present, and import nothing new from the widget (helpers are methods):

```python
class TestStatusPaneLiveCooldown:
    def test_update_snapshot_sets_expiry_from_remaining(self, monkeypatch):
        monkeypatch.setattr(time, "monotonic", lambda: 1000.0)
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=45.0))
        assert pane._cooldown_expiry == 1045.0

    def test_update_snapshot_zero_remaining_clears_expiry(self, monkeypatch):
        monkeypatch.setattr(time, "monotonic", lambda: 1000.0)
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=0.0))
        assert pane._cooldown_expiry is None

    def test_remaining_decreases_as_time_advances(self, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=45.0))
        clock["t"] = 1030.0                       # 30s elapsed
        assert pane._cooldown_remaining() == 15.0
        clock["t"] = 1100.0                       # past expiry
        assert pane._cooldown_remaining() == 0.0

    def test_remaining_zero_when_no_expiry(self):
        assert StatusPane()._cooldown_remaining() == 0.0

    def test_render_shows_live_countdown_not_frozen_snapshot(self, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=45.0))
        clock["t"] = 1020.5                       # 24.5s remaining -> ceil 25
        out = _render(pane)
        assert "25s" in out and "45" not in out   # live, not the frozen 45

    def test_render_ready_when_countdown_elapsed(self, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=5.0))
        clock["t"] = 1010.0                       # well past expiry
        assert "ready" in _render(pane)

    def test_tick_clears_expiry_once_elapsed(self, monkeypatch):
        clock = {"t": 1000.0}
        monkeypatch.setattr(time, "monotonic", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=5.0))
        clock["t"] = 1010.0
        pane._tick()
        assert pane._cooldown_expiry is None       # stops ticking after the final frame
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_tui/test_status_pane.py::TestStatusPaneLiveCooldown -v`
Expected: FAIL — `AttributeError: 'StatusPane' object has no attribute '_cooldown_expiry'` / `_cooldown_remaining` / `_tick`.

- [ ] **Step 3: Add imports + state**

In `status_pane.py`, add to the top imports (after `from datetime import datetime`):

```python
import math
import time
```

In `__init__` (after `self._eta_samples: list[tuple[float, int]] = []`), add:

```python
        self._cooldown_expiry: float | None = None
```

- [ ] **Step 4: Set expiry in `update_snapshot` + add helper, timer, tick**

Replace `update_snapshot` with:

```python
    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._track_eta(snap)
        self._cooldown_expiry = (
            time.monotonic() + snap.cooldown_remaining
            if snap.cooldown_remaining > 0 else None
        )
        self.snapshot = snap
```

Add these methods (e.g. after `update_snapshot`):

```python
    def on_mount(self) -> None:
        """Tick once a second so the cooldown counts down between AI cycles."""
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._cooldown_expiry is not None:
            self.refresh()
            if self._cooldown_remaining() <= 0.0:
                self._cooldown_expiry = None   # render the final 'ready' frame, then stop

    def _cooldown_remaining(self) -> float:
        if self._cooldown_expiry is None:
            return 0.0
        return max(0.0, self._cooldown_expiry - time.monotonic())
```

- [ ] **Step 5: Render the live value**

In `_render_status`, replace the cooldown block (currently lines ~95-99):

```python
        if s.cooldown_remaining > 0:
            cd_color = "yellow" if s.cooldown_remaining < 10 else "red"
            t.add_row("Cooldown", f"[{cd_color}]{s.cooldown_remaining:.1f}s[/{cd_color}]")
        else:
            t.add_row("Cooldown", "[green]ready[/green]")
```

with:

```python
        remaining = self._cooldown_remaining()
        if remaining > 0:
            cd_color = "yellow" if remaining < 10 else "red"
            t.add_row("Cooldown", f"[{cd_color}]{math.ceil(remaining)}s[/{cd_color}]")
        else:
            t.add_row("Cooldown", "[green]ready[/green]")
```

(`_render_status` takes `s` for the other rows; the cooldown row now uses `self._cooldown_remaining()` instead of `s.cooldown_remaining`.)

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_status_pane.py::TestStatusPaneLiveCooldown -v`
Expected: PASS (7 tests).
Then `uv run ruff check src/artifactsmmo_cli/tui/widgets/status_pane.py tests/test_tui/test_status_pane.py && uv run mypy src/artifactsmmo_cli/tui/widgets/status_pane.py` — clean.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/tui/widgets/status_pane.py tests/test_tui/test_status_pane.py
git commit -m "feat(tui): live cooldown countdown in StatusPane

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Update the existing cooldown assertions for ceil-seconds

**Files:**
- Modify: `tests/test_tui/test_status_pane.py`

The render now uses `math.ceil(self._cooldown_remaining())`, and `_cooldown_remaining()` reads `time.monotonic()`, so the existing `TestStatusPaneCooldown` value assertions (`"5.5s"`, `"15.0s"`) are stale and non-deterministic. Pin the clock and update to ceil-seconds.

- [ ] **Step 1: Run the existing cooldown tests to see them fail**

Run: `uv run pytest tests/test_tui/test_status_pane.py::TestStatusPaneCooldown -v`
Expected: FAIL — `test_cooldown_shows_seconds_when_positive` (no `"5.5s"`) and `test_cooldown_high_value` (no `"15.0s"`); `test_cooldown_ready_when_zero` still passes.

- [ ] **Step 2: Update the two value assertions (pin the clock)**

Replace the `TestStatusPaneCooldown` body (lines ~93-107) with:

```python
class TestStatusPaneCooldown:
    def test_cooldown_ready_when_zero(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=0.0))
        assert "ready" in _render(pane)

    def test_cooldown_shows_seconds_when_positive(self, monkeypatch):
        monkeypatch.setattr(time, "monotonic", lambda: 500.0)
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=5.5))   # expiry 505.5; same instant -> 5.5 left
        assert "6s" in _render(pane)                          # ceil(5.5)

    def test_cooldown_high_value(self, monkeypatch):
        """Values >= 10 are colored red, still displays correctly."""
        monkeypatch.setattr(time, "monotonic", lambda: 500.0)
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=15.0))
        assert "15s" in _render(pane)                         # ceil(15.0)
```

(Pinning `time.monotonic` to a constant means `update_snapshot` and the render read the same instant, so remaining equals the snapshot value exactly — `ceil(5.5)=6`, `ceil(15.0)=15`. Ensure `import time` is at the top of the test file — added in Task 1.)

- [ ] **Step 3: Run to verify pass**

Run: `uv run pytest tests/test_tui/test_status_pane.py -v`
Expected: PASS (all StatusPane tests, including the updated cooldown ones).

- [ ] **Step 4: Commit**

```bash
git add tests/test_tui/test_status_pane.py
git commit -m "test(tui): update cooldown assertions for ceil-seconds countdown

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Full verification

**Files:** none

- [ ] **Step 1: Full suite** — `uv run pytest -q` → 0 failures, 0 errors, 0 skipped.
- [ ] **Step 2: Lint** — `uv run ruff check src tests` → clean.
- [ ] **Step 3: Type-check** — `uv run mypy src/artifactsmmo_cli/tui/widgets/status_pane.py` → no errors (and confirm no new errors vs the repo's pre-existing `mypy src` baseline).
- [ ] **Step 4: Coverage on changed code** — `uv run pytest tests/test_tui/test_status_pane.py --cov=artifactsmmo_cli.tui.widgets.status_pane --cov-report=term-missing -q` → the new `_cooldown_remaining`/`_tick`/expiry lines and the live render branch covered (the `on_mount`/`set_interval` glue line may be the only uncovered line, acceptable as thin Textual runtime glue — add a note if so, or cover via a Textual pilot if the suite already uses one).

---

## Self-Review

**Spec coverage:**
- `_cooldown_expiry` state + set in `update_snapshot` (monotonic + remaining; None when ≤0) → Task 1 Steps 3-4. ✓
- `_cooldown_remaining()` clamp-to-0 helper → Task 1 Step 4. ✓
- `on_mount` 1s timer + `_tick` refresh-while-active + clear-at-0 → Task 1 Step 4. ✓
- Render live ceil-seconds, colours unchanged, "ready" at 0 → Task 1 Step 5. ✓
- No snapshot → "Waiting..." unchanged (untouched code path). ✓
- Existing cooldown tests updated to ceil-seconds with pinned clock → Task 2. ✓
- Testing (0/0/0, 100% on changed, monkeypatch monotonic) → Tasks 1-3. ✓
- Out of scope (no snapshot/observer/AI changes, no ETA ticking, 1s only) — plan touches only `status_pane.py` + its test. ✓

**Placeholder scan:** none — every step has full code and exact commands.

**Type consistency:** `_cooldown_expiry: float | None`, `_cooldown_remaining() -> float`, `_tick()`/`on_mount()` consistent across Task 1 steps and the tests. Render uses `self._cooldown_remaining()` + `math.ceil`. Test helpers `_snap`/`_render` are the file's existing ones.
