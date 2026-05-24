# TUI Live Cooldown Countdown

Date: 2026-05-24
Status: Draft (for review)

Make the `StatusPane` cooldown readout tick down in real time instead of sitting
frozen between cycles.

## Problem

`StatusPane` renders `Cooldown {s.cooldown_remaining:.1f}s` straight from the
latest `CycleSnapshot`. A snapshot is pushed only once per AI cycle, and a cycle
blocks on the game's action cooldown (often 60s+). So the displayed value is the
remaining-at-snapshot-time and stays **frozen** for the whole cooldown — it only
jumps when the next cycle starts. The user wants a live countdown.

## Design

Drive the cooldown row from an absolute expiry recomputed by a repeating timer,
decoupled from cycle cadence. Only `StatusPane` changes; no snapshot-model,
observer, or app changes.

### State

`StatusPane` gains:
- `self._cooldown_expiry: float | None = None` — a `time.monotonic()` instant when
  the cooldown ends, or `None` when not on cooldown.

`update_snapshot(snap)` sets it from the fresh snapshot value:
```python
    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self._track_eta(snap)
        self._cooldown_expiry = (
            time.monotonic() + snap.cooldown_remaining
            if snap.cooldown_remaining > 0 else None
        )
        self.snapshot = snap
```
`monotonic()` is used (not wall clock) so the countdown is immune to system clock
changes; `cooldown_remaining` is fresh at snapshot receipt, so `now + remaining`
is an accurate expiry.

### Remaining helper

```python
    def _cooldown_remaining(self) -> float:
        if self._cooldown_expiry is None:
            return 0.0
        return max(0.0, self._cooldown_expiry - time.monotonic())
```

### Timer

Started once when the widget mounts (Textual runtime); ticks every second and
refreshes only while a countdown is active, so an idle/ready pane does no work:
```python
    def on_mount(self) -> None:
        self.set_interval(1.0, self._tick)

    def _tick(self) -> None:
        if self._cooldown_expiry is not None:
            self.refresh()
            if self._cooldown_remaining() <= 0.0:
                self._cooldown_expiry = None   # final "ready" frame, then stop ticking
```
The `set_interval` handle is fire-and-forget (lives for the widget's lifetime).

### Render

The Cooldown row reads the live remaining and shows whole seconds via `ceil`
(reads "time left", reaches `ready` exactly at 0). Colours unchanged:
```python
        remaining = self._cooldown_remaining()
        if remaining > 0:
            cd_color = "yellow" if remaining < 10 else "red"
            t.add_row("Cooldown", f"[{cd_color}]{math.ceil(remaining)}s[/{cd_color}]")
        else:
            t.add_row("Cooldown", "[green]ready[/green]")
```
(`import math`, `import time` at top. The `.1f` fractional display is dropped in
favour of whole seconds per the 1s-tick decision.)

## Error handling

- No snapshot yet → `render` still returns `Text("Waiting...")` (unchanged); the
  timer may fire first but `_cooldown_expiry is None` → no refresh, no error.
- A new snapshot mid-countdown resets `_cooldown_expiry` (new cooldown or `None`).
- Pure logic; no API, no `except Exception`.

## Testing

Per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.
Existing tests render `StatusPane` without a Textual app, so the countdown logic
is unit-tested through the pure helpers (monkeypatch `time.monotonic`); the timer
is thin glue.

- **`update_snapshot` sets expiry:** `cooldown_remaining=45` with `monotonic`
  pinned → `_cooldown_expiry == pinned + 45`; `cooldown_remaining=0` → `None`.
- **`_cooldown_remaining`:** advancing `monotonic` partway → remaining decreases;
  past expiry → clamps to `0.0`; `None` expiry → `0.0`.
- **Render live countdown:** with expiry set and `monotonic` advanced, the
  rendered Cooldown row shows the ceil-seconds value (e.g. `"45s"`), and shows
  `ready` once remaining hits 0 — proving render reads the live helper, not the
  frozen `snap.cooldown_remaining`.
- **Colour thresholds:** remaining `< 10` → yellow, `>= 10` → red, `0` → green
  `ready` (assert via a colour Console or the markup string).
- **`_tick` clears expiry at 0:** after `monotonic` passes expiry, one `_tick`
  call refreshes and sets `_cooldown_expiry = None` (so ticking stops).
- Existing StatusPane tests (HP/XP/task/goal rows) stay green. The two
  `TestStatusPaneCooldown` value assertions are updated for ceil-seconds:
  `test_cooldown_shows_seconds_when_positive` `"5.5s"` → `"6s"` (ceil of the
  just-under-5.5 live remaining), `test_cooldown_high_value` `"15.0s"` → `"15s"`.
  `test_cooldown_ready_when_zero` (`"ready"`) is unaffected. To keep these
  deterministic despite the `monotonic()`-based live remaining, pin
  `time.monotonic` in the cooldown tests.

## Files

- Modify `src/artifactsmmo_cli/tui/widgets/status_pane.py` — `_cooldown_expiry`
  state, `_cooldown_remaining` helper, `on_mount` timer, `_tick`, render change;
  add `import math`, `import time`.
- Modify `tests/test_tui/test_status_pane.py` — countdown tests + update any
  `"45.0s"` expectation to `"45s"`.

## Out of scope

- Live-ticking the task ETA or any other row.
- Sub-second precision (1s tick chosen).
- Changes to `CycleSnapshot`, the observer, or the AI loop.
