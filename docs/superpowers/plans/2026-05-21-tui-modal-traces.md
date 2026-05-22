# TUI Modal Trace Detail + Formatting Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline) — the schema change threads through player→snapshot→screens, so tasks are tightly coupled; do not parallelize.

**Goal:** The `l` log modal shows full per-cycle planner trace detail (the data `_emit_trace` writes to `traces.jsonl`), and both the `c` and `l` modals stop truncating/clipping their content.

**Architecture:** Extend `CycleSnapshot` with the planner-trace fields it currently lacks (`planner_nodes/depth/timed_out`, `plan_len`, `goals_tried`, `suppressed_goals`, `path_blocked`). Build `planner_stats` once at each decision site in `player.py` and pass the same dict to both `_emit_trace` and `_notify_observer`, so the TUI pipeline carries trace-complete data with no file coupling and no `--trace` dependency. Rewrite `build_debug_log_line` to render a multi-line trace block, and add scroll/wrap containers so neither modal clips.

**Tech Stack:** Python 3.13, `uv`, pytest, pydantic, Rich/Textual.

---

## File Structure
- Modify `src/artifactsmmo_cli/ai/cycle_snapshot.py` — add `GoalAttempt` model + new `CycleSnapshot` fields.
- Modify `src/artifactsmmo_cli/ai/player.py` — build `planner_stats` once per site; pass to `_notify_observer`; populate new snapshot fields.
- Modify `src/artifactsmmo_cli/tui/screens/log_screen.py` — multi-line trace renderer; `RichLog(wrap=True)`.
- Modify `src/artifactsmmo_cli/tui/screens/character_screen.py` — `VerticalScroll` container.
- Modify tests under `tests/` accordingly.

---

## Task 1: Extend CycleSnapshot with planner-trace fields

**Files:** Modify `src/artifactsmmo_cli/ai/cycle_snapshot.py`; Test `tests/test_ai/test_cycle_snapshot.py` (or existing snapshot test).

- Add `GoalAttempt(BaseModel)`: `goal: str`, `nodes: int = 0`, `depth: int = 0`, `timed_out: bool = False`, `plan_len: int = 0`.
- Add to `CycleSnapshot`: `planner_nodes: int = 0`, `planner_depth: int = 0`, `planner_timed_out: bool = False`, `plan_len: int = 0`, `goals_tried: list[GoalAttempt] = Field(default_factory=list)`, `suppressed_goals: list[str] = Field(default_factory=list)`, `path_blocked: bool = False`.
- Test: a snapshot built with these fields round-trips; defaults apply when omitted.

## Task 2: Thread planner_stats into _notify_observer

**Files:** Modify `src/artifactsmmo_cli/ai/player.py`; Test `tests/test_ai/` player/observer test.

- At both decision sites (no_plan ~305-318, success ~399-416): build `planner_stats = {...}` once into a local; pass to `_emit_trace(planner_stats=planner_stats)` and to `_notify_observer(..., planner_stats=planner_stats)`.
- `_notify_observer` gains a `planner_stats: dict[str, object]` param. Populate snapshot:
  - `planner_nodes=int(planner_stats["nodes"])`, `planner_depth=int(planner_stats["depth"])`, `planner_timed_out=bool(planner_stats["timed_out"])`, `plan_len=int(planner_stats["plan_len"])`.
  - `goals_tried=[GoalAttempt(goal=str(g["goal"]), nodes=int(g["nodes"]), depth=int(g["depth"]), timed_out=bool(g["timed_out"]), plan_len=int(g["plan_len"])) for g in planner_stats["goals_tried"]]`.
  - `suppressed_goals=list(self._suppressed_goals.keys())`.
  - `path_blocked=bool(planner_stats.get("path_blocked", False))`.
- Test: drive a cycle with a stub observer; assert the captured snapshot carries the planner internals + goals_tried + suppressed_goals.

## Task 3: Rewrite the log trace renderer + wrap

**Files:** Modify `src/artifactsmmo_cli/tui/screens/log_screen.py`; Test `tests/test_tui/test_log_screen.py`.

- `build_debug_log_line(snap) -> str` (rename keeps callers): emit a multi-line Rich-markup trace block:
  - header: `ts c{cycle}  goal  action  outcome`
  - `  planner: nodes=N depth=D plan_len=L timed_out=yes/no  path next=… blocked=… proj=…`
  - `  goals tried: G(n=…/d=…/len=… [TIMEOUT])  …`
  - `  goal rank: g=p  …` (priority>0)
  - `  suppressed: …` (only when non-empty)
- `RichLog(wrap=True, …)` so long lines wrap instead of clipping.
- Tests: block contains nodes/depth/plan_len, each goals_tried goal, the rank entries, suppressed line when present and absent when empty.

## Task 4: CharacterScreen scroll container

**Files:** Modify `src/artifactsmmo_cli/tui/screens/character_screen.py`; Test `tests/test_tui/test_character_screen.py`.

- Wrap the detail `Static` in `VerticalScroll` so a tall character sheet scrolls instead of clipping. `compose` yields `VerticalScroll(Static(..., id="char-detail"))`; `update_snapshot` still targets `#char-detail`.
- Test: screen still mounts via `run_test()`, `#char-detail` query still resolves, re-render on new snapshot works.

## Task 5: Full verification
- `uv run pytest -q` → 0 failures, 0 skipped.
- `uv run pytest --cov` on changed files → 100%.
- `uv run ruff check` + `uv run mypy` on changed files → clean.

---

## Self-review notes
- Snapshot fields all have defaults → existing snapshot constructions (tests, map_pane) keep working.
- `planner_stats` built once per site removes the divergence risk between trace and snapshot.
- `goals_tried` dict shape (goal/nodes/depth/timed_out/plan_len) matches `_select_goal`'s `attempt()`.
