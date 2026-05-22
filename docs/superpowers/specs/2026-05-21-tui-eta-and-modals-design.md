# TUI: task ETA + full-screen character / log modals

Date: 2026-05-21
Status: Approved (design)

## Goal

Three TUI watch-mode enhancements:
1. Show **estimated time to task completion** in the status pane.
2. Press **`c`** → full-screen **character detail** modal.
3. Press **`l`** → full-screen **debug-level game log** modal.

## Current state

`WatchApp` (tui/app.py) is a 2×2 grid of `StatusPane`, `MapPane`, `InventoryPane`,
`LogPane`; only `q` is bound. `CycleSnapshot` carries vitals, all 8 `skills` +
`skill_xp`, `equipment`, `task_code/type/progress/total`, `cooldown_remaining`,
`goal/action/outcome`, `goal_rank` (per-goal priorities), `path_next_action`,
`projected_cycles_to_max`, `timestamp` (ISO-8601 UTC). It does **not** carry
combat stats or per-skill `max_xp`.

## Feature 1 — Task ETA in StatusPane

A new "ETA" row, shown only when a task is active.

- **Rolling samples (TUI-side):** `StatusPane` keeps a bounded list of
  `(epoch_seconds, task_progress)` from the snapshots it receives (window
  `ETA_WINDOW = 20`). The clock is the snapshot's own `timestamp` (the bot's
  cycle time), parsed to epoch — deterministic and testable.
- **Reset** the samples when `task_code` changes (new task) or there is no task.
- **Pure computation** `task_eta_seconds(samples, remaining) -> float | None`:
  rate = `(progress_last - progress_first) / (t_last - t_first)`; returns
  `remaining / rate`. Returns `None` when there are `< 2` samples, the time
  span is `0`, or rate `<= 0` (no measurable progress yet).
- **Format** `format_eta(seconds) -> str`: `~{m}m {s}s` (or `~{s}s` under a
  minute); the row shows `—` when the estimate is `None`.

`epoch_seconds` parsing uses `datetime.fromisoformat` on `timestamp` (UTC). Both
helpers are module-level pure functions in `status_pane.py`.

## Feature 2 — `c`: CharacterScreen modal

`tui/screens/character_screen.py` — one `Screen` subclass.

- Pushed by the app's `c` binding; dismissed by `c` (toggle) or `Esc`.
- Renders **full character detail** from the latest snapshot via a pure builder
  `build_character_detail(snap) -> RenderableType`:
  - vitals: level, HP `hp/max_hp`, XP `xp/max_xp`, gold, position;
  - **all 8 skills**: name, level, current `skill_xp` (no max — not in snapshot);
  - **equipment**: every slot in `equipment`, item or `—`;
  - current task: `task_code  progress/total` (or "none").
  - Combat stats are intentionally excluded (not in the snapshot) — noted in
    the spec's Out of scope.
- Re-renders live: while open, `app.update_snapshot` refreshes it with the new
  snapshot.

## Feature 3 — `l`: LogScreen modal (debug-level)

`tui/screens/log_screen.py` — one `Screen` subclass wrapping a full-size
`RichLog`.

- Pushed by the app's `l` binding; dismissed by `l` (toggle) or `Esc`.
- **Debug-level** record per cycle via a pure builder
  `build_debug_log_line(snap) -> str` (Rich markup): timestamp, cycle, goal,
  action, outcome, **plus** `task progress`, `hp/max_hp`, `cooldown`,
  `pos (x,y)`, `path→next`, `proj cycles`, and the **full** `goal_rank`
  ranking (every goal with priority > 0, not just top 3).
- On open, seed from the app's recent-snapshot buffer (renders one debug line
  per stored snapshot); while open, append the live line each cycle.

## Supporting app changes (tui/app.py)

- `BINDINGS` adds `("c", "toggle_character", "Character")` and
  `("l", "toggle_log", "Log")` alongside `q`.
- Keep `self._last_snapshot: CycleSnapshot | None` and
  `self._recent_snapshots: deque[CycleSnapshot]` (maxlen `LOG_BUFFER = 500`).
- `update_snapshot` additionally: stores `_last_snapshot`, appends to
  `_recent_snapshots`, and — if the corresponding modal screen is on top —
  calls its update method with the snapshot.
- `action_toggle_character` / `action_toggle_log`: if the modal is already on
  the screen stack, `pop_screen`; else `push_screen` with the current
  snapshot/buffer. (Each screen also binds `Escape` → `dismiss`.)

## Testing

Success per project standard: 0 errors, 0 warnings, 0 skipped, 100% on changed code.

- `task_eta_seconds`: `< 2` samples → None; zero time span → None; non-increasing
  progress (rate ≤ 0) → None; steady progress → correct seconds (e.g. samples
  `(0,0),(60,2)` with remaining `4` → `120.0`).
- `format_eta`: sub-minute (`~45s`), minutes+seconds (`~4m 10s`); None handled
  by the row (`—`).
- `StatusPane`: ETA row appears with a task + enough samples; `—` before that;
  samples reset on task change; no ETA row when no task.
- `build_character_detail`: contains each skill name+level, each equipment slot
  (item or `—`), vitals, task; with empty skills/equipment degrades gracefully.
- `build_debug_log_line`: contains the cycle's goal/action/outcome + task
  progress + hp + cooldown + the full goal_rank entries.
- `CharacterScreen` / `LogScreen` via Textual `App.run_test()`: `c`/`l` push,
  second press / `Esc` pops; LogScreen seeds from the buffer; both re-render on
  a new snapshot while open.
- `WatchApp`: `_recent_snapshots` capped at `LOG_BUFFER`; `update_snapshot`
  stores `_last_snapshot`; bindings present.

## Files

- `src/artifactsmmo_cli/tui/widgets/status_pane.py` — ETA samples + row;
  `task_eta_seconds`, `format_eta`, epoch parse (module-level).
- `src/artifactsmmo_cli/tui/screens/__init__.py` (new package).
- `src/artifactsmmo_cli/tui/screens/character_screen.py` (new) +
  `build_character_detail`.
- `src/artifactsmmo_cli/tui/screens/log_screen.py` (new) +
  `build_debug_log_line`.
- `src/artifactsmmo_cli/tui/app.py` — bindings, snapshot buffer, modal wiring.
- Tests under `tests/test_tui/`.

## Out of scope
- Combat stats / per-skill max_xp in the character view (not in CycleSnapshot;
  would require extending the snapshot + player).
- Persisting the log across runs; tailing the bot's stdout/log file (the TUI is
  snapshot-driven).
- Changes to map/inventory panes.
