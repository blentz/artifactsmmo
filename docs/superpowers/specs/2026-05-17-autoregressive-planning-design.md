# Autoregressive Planning — Design Spec

**Date:** 2026-05-17
**Status:** Draft (pending review)
**Predecessor:** `docs/superpowers/specs/2026-05-15-goap-robustness-layer-design.md` (Phase F was named there as future work; this spec realises it)

## Overview

Add per-cycle observation capture and learned-stat feedback so the GOAP planner adapts to real-world outcomes. SQLModel-backed SQLite store (`LearningStore`) records every cycle. Actions and goals consult the store at planning time for learned cost, success rate, observed effects, and goal-effectiveness modifiers. Real-time write per cycle, real-time read per planning round. JSONL trace retained alongside as a forensic log.

The current GOAP planner is memoryless: `Action.cost()` returns a static formula (`2.0 + distance`), `Goal.value()` ignores historical effectiveness. Real-play with Robby surfaced two consequences: the bot can pursue actions that have empirically been slow/failing, and goals can stay high-priority despite being unproductive in practice. This spec closes that gap.

## Context

### Existing groundwork (laid by the robustness-layer spec)

- `Action.cost(state, game_data)` / `Goal.value(state, game_data)` signatures already accept `state` and `game_data` — adding `history: LearningStore | None = None` is non-breaking.
- The JSONL tracer (`Tracer` ABC, `FileTracer`) captures `(state, goals, selected_goal, action, next_state, outcome, planner_stats)` per cycle. That data structure informed this schema.
- `StuckDetector.CycleRecord` is the in-process version of the same idea for short-term recovery; the autoregressive store is the durable, long-horizon version.

### Live trace shape (sampled from Robby 2026-05-17)

```json
{
  "ts": "2026-05-17T00:29:58.110560+00:00",
  "cycle": 0,
  "state": {"x": 2, "y": 0, "hp": 130, "max_hp": 130, "gold": 53, "level": 3,
            "inventory_used": 90, "inventory_max": 104, "bank_accessible": true,
            "task_code": null, "task_type": null, "task_progress": 0, "task_total": 0},
  "cooldown_remaining_at_cycle_start": 29.746447,
  "selected_goal": "GatherMaterials(copper_boots)",
  "planner": {"nodes": 225, "depth": 18, "timed_out": false, "plan_len": 18},
  "action": "Gather(copper_rocks)",
  "outcome": "ok",
  "recovery": null,
  "suppressed_goals": []
}
```

State-delta between consecutive trace rows yields per-action observed effects (inventory drops, gold gained, xp gained, hp delta) for free.

## Goals & Non-goals

### Goals
- Capture per-cycle data into a SQLite event log (SQLModel, validated at construction).
- Provide queryable learned stats — action cost, success rate, observed effect, goal-effectiveness — over a configurable recency window.
- Feed learned stats into `Action.cost()` and `Goal.value()` so the planner adapts within a single session.
- Backward compatible: `history=None` keeps v1 behaviour.
- "Data integrity" enforced via Pydantic validation at the SQLModel boundary.
- All imports top-of-file. No `TYPE_CHECKING`, no string forward refs, no lazy imports.

### Non-goals
- Online learning beyond per-cycle aggregation (no gradient descent, no model training, no neural nets).
- Schema migration tooling (Alembic) — additive `create_all` only in v1.
- Cross-character learning blending (per-character rows; no global model that mixes).
- Replacement of the JSONL tracer — both formats kept; serve different audiences.
- Modification of `WorldState`, `apply()` (must stay pure for A*), `is_satisfied`, `desired_state`, `relevant_actions`, or the stuck-state detector.

## Architecture

```
                   ┌────────────────────────────────────────┐
                   │            GamePlayer.run()            │
                   │  (per cycle)                           │
                   └────────────────────────────────────────┘
                                    │
                ┌───────────────────┼───────────────────────────┐
                │                   │                           │
                ▼                   ▼                           ▼
       build_actions/goals     planner.plan()             action.execute()
       (consults history)     (consults history)          (returns new_state)
                │                   │                           │
                └───────────────────┴────────┐                  │
                                             │                  │
                                             ▼                  ▼
                         LearningStore.record_cycle(Cycle(...))
                                             │
                                             ▼
                                  ┌──────────────────┐    ┌──────────────┐
                                  │   learning.db    │    │ traces.jsonl │
                                  │  (sqlmodel/sqlite│    │ (forensic)   │
                                  └──────────────────┘    └──────────────┘
```

### New modules

- `src/artifactsmmo_cli/ai/learning/__init__.py` — re-exports `LearningStore` for `from artifactsmmo_cli.ai.learning import LearningStore`.
- `src/artifactsmmo_cli/ai/learning/models.py` — `Cycle`, `Session` SQLModel classes (one role: ORM + Pydantic in one definition).
- `src/artifactsmmo_cli/ai/learning/types.py` — `ActionStats`, `GoalStats` Pydantic `BaseModel`s for query results.
- `src/artifactsmmo_cli/ai/learning/store.py` — `LearningStore` class wrapping SQLModel engine + sessionmaker.

Splitting by file respects one-class-per-file from CLAUDE.md.

### Modified modules

- `src/artifactsmmo_cli/ai/actions/base.py` — `Action.cost` adds `history: LearningStore | None = None` (real top-of-file import).
- `src/artifactsmmo_cli/ai/goals/base.py` — `Goal.value` and `Goal.priority` add `history`.
- `src/artifactsmmo_cli/ai/planner.py` — `GOAPPlanner.plan` adds `history`; threads through to `action.cost` and `goal.value`.
- `src/artifactsmmo_cli/ai/player.py` — accepts `history: LearningStore | None`; computes deltas; calls `store.record_cycle()` per cycle.
- `src/artifactsmmo_cli/commands/play.py` — adds `--learn` / `--learn-db` flags.
- Every existing `Action` and `Goal` subclass — mechanically add `history: LearningStore | None = None` parameter to override-points so the ABC signature stays consistent (most ignore the parameter).
- Selected action/goal subclasses (`FightAction`, `GatherAction`, `MoveAction`, `FarmMonsterGoal`, `GatherMaterialsGoal`) — actually consult `history`.

### Import-cycle audit

Dependency edges added:
- `learning/models.py` → `sqlmodel` only.
- `learning/types.py` → `pydantic` only.
- `learning/store.py` → `learning.models`, `learning.types`, `sqlmodel`. No `actions/`, `goals/`, `game_data`, `world_state`.
- `actions/base.py` → `learning.store` (new).
- `goals/base.py` → `learning.store` (new).
- `planner.py` → `learning.store` (new).
- `player.py` → `learning.store` (new).

`learning/*` depends on nothing in `ai/`. One-way edge. No cycles. All imports real top-of-file imports — no `TYPE_CHECKING`, no string forward refs, no lazy imports.

### New dependency

`sqlmodel>=0.0.14` (transitively pulls `sqlalchemy>=2.0` and `pydantic>=2`). Add via `uv add sqlmodel`.

## Storage models

### `learning/models.py`

```python
"""SQLModel definitions for the GOAP learning store.

Each model is simultaneously a Pydantic model (validation at construction)
and a SQLAlchemy ORM row (persistence). One definition, two roles.
"""

from sqlmodel import Field, SQLModel


class Cycle(SQLModel, table=True):
    """One row per player-loop cycle: state snapshot + goal/action + outcome + effects."""

    __tablename__ = "cycles"

    id: int | None = Field(default=None, primary_key=True)

    ts: str = Field(index=True)
    session_id: str = Field(index=True)
    cycle_index: int
    character: str = Field(index=True)

    # State snapshot
    x: int | None = None
    y: int | None = None
    hp: int | None = None
    max_hp: int | None = None
    gold: int | None = None
    level: int | None = None
    xp: int | None = None
    inventory_used: int | None = None
    inventory_max: int | None = None
    bank_accessible: bool = True
    task_code: str | None = None
    task_type: str | None = None
    task_progress: int | None = None
    task_total: int | None = None

    # Goal + action
    selected_goal: str | None = Field(default=None, index=True)
    action_repr: str | None = Field(default=None, index=True)
    action_class: str | None = None
    outcome: str                                                  # "ok" | "no_plan" | "error:..."

    # Cost & planner
    predicted_cost: float | None = None
    actual_cooldown_seconds: float | None = None
    planner_nodes: int | None = None
    planner_depth: int | None = None
    planner_timed_out: bool | None = None
    plan_len: int | None = None

    # Effects (state delta from previous cycle in same session)
    delta_gold: int | None = None
    delta_xp: int | None = None
    delta_hp: int | None = None
    delta_inv_used: int | None = None
    drops_json: str | None = None                                 # {item_code: qty}

    # Goal completion tracking
    cycles_to_satisfy: int | None = None                          # set on the cycle a goal transitions to satisfied


class Session(SQLModel, table=True):
    """One row per GamePlayer.run() invocation."""

    __tablename__ = "sessions"

    session_id: str = Field(primary_key=True)
    started_at: str
    character: str = Field(index=True)
    ended_at: str | None = None
    cycle_count: int = 0
    exit_reason: str | None = None
```

### `learning/types.py`

```python
"""Pydantic models for data returned by LearningStore queries (not persisted)."""

from pydantic import BaseModel, ConfigDict


class ActionStats(BaseModel):
    """Aggregated statistics for one action_repr."""

    model_config = ConfigDict(frozen=True)

    action_repr: str
    sample_count: int
    median_cost_seconds: float | None
    success_rate: float
    median_delta_xp: float | None
    median_delta_gold: float | None


class GoalStats(BaseModel):
    """Aggregated statistics for one goal_repr."""

    model_config = ConfigDict(frozen=True)

    goal_repr: str
    sample_count: int
    avg_cycles_to_satisfy: float | None
    satisfaction_rate: float
```

## LearningStore API

### `learning/store.py`

```python
"""SQLModel-backed learning store for autoregressive GOAP planning."""

import json
import statistics
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession, SQLModel, create_engine, select

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.learning.types import ActionStats, GoalStats


class LearningStore:
    """Event log + queryable learned stats. Best-effort: errors degrade to defaults, never raise into the player loop."""

    def __init__(self, db_path: str, character: str) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)
        # WAL for concurrent reads + serial writes; NORMAL sync for throughput.
        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()
        self._character = character
        self._session_id: str | None = None

    def start_session(self) -> str: ...
    def end_session(self, exit_reason: str = "normal") -> None: ...
    def record_cycle(self, cycle: Cycle) -> None: ...

    # Query methods — fall back to supplied default until sample_count >= 5
    def action_cost(self, action_repr: str, default: float, window: int = 50) -> float: ...
    def success_rate(self, action_repr: str, window: int = 50) -> float: ...
    def goal_avg_cycles_to_satisfy(self, goal_repr: str, window: int = 20) -> float | None: ...
    def action_effect(self, action_repr: str, field: str, window: int = 50) -> float | None: ...

    def action_stats(self, action_repr: str, window: int = 50) -> ActionStats: ...
    def goal_stats(self, goal_repr: str, window: int = 20) -> GoalStats: ...
    def sample_count(self, action_repr: str) -> int: ...

    def close(self) -> None:
        self._engine.dispose()
```

## Integration into Action/Goal/Planner

### Signature additions

```python
# actions/base.py
from artifactsmmo_cli.ai.learning.store import LearningStore   # top-level import; no cycle

class Action(ABC):
    @abstractmethod
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float: ...
```

```python
# goals/base.py
from artifactsmmo_cli.ai.learning.store import LearningStore

class Goal(ABC):
    @abstractmethod
    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float: ...

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        return self.value(state, game_data, history)
```

```python
# planner.py
from artifactsmmo_cli.ai.learning.store import LearningStore

class GOAPPlanner:
    def plan(self, state: WorldState, goal: Goal, actions: list[Action],
             game_data: GameData, history: LearningStore | None = None) -> list[Action]:
        ...
        g = node.g_score + action.cost(node.state, game_data, history)
        h = goal.value(next_state, game_data, history)
        ...
```

```python
# player.py
from artifactsmmo_cli.ai.learning.store import LearningStore

class GamePlayer:
    def __init__(self, character, verbose=False, dry_run=False,
                 tracer=None, history: LearningStore | None = None) -> None:
        ...
        self.history = history

    # In run():
    goals.sort(key=lambda g: g.priority(self.state, self.game_data, self.history), reverse=True)
    plan = self.planner.plan(self.state, goal, actions, self.game_data, self.history)
```

### Mechanical migration

Every existing `Action`/`Goal` subclass override gets `history: LearningStore | None = None` appended to the matching `cost`/`value` signature. Most subclasses ignore the parameter — only the opted-in subclasses below actually use it.

### Initial opt-ins

**Actions:** `FightAction`, `GatherAction`, `MoveAction`.

**Goals:** `FarmMonsterGoal`, `GatherMaterialsGoal`.

Rationale: combat and gathering dominate Robby's time and vary widely by target. Other actions (`RestAction`, `EquipAction`, etc.) have small, consistent cost — defer opt-in.

## The four learning targets

### Target 1 — Action cost (planner heuristic)

**Stored:** `cycles.actual_cooldown_seconds` per cycle. Computed in player loop as `(new_state.cooldown_expires - now).total_seconds()` after `action.execute()`.

**Aggregated:** median over last 50 events for `action_repr` where `outcome == "ok"`. Fallback: supplied default (static formula) when sample_count < 5.

**Applied:**

```python
def cost(self, state, game_data, history=None):
    static = 1.5 + dist
    if history is None:
        return static
    return history.action_cost(repr(self), default=static, window=50)
```

### Target 2 — Action success rate (cost penalty)

**Stored:** `cycles.outcome`.

**Aggregated:** `count(outcome=="ok") / count(*)` over last 50 events. Fallback: 1.0 when sample_count < 5.

**Applied:** wraps the cost output.

```python
def cost(self, state, game_data, history=None):
    static = 1.5 + dist
    if history is None:
        return static
    learned = history.action_cost(repr(self), default=static, window=50)
    rate = history.success_rate(repr(self), window=50)
    if rate < 0.95:
        return learned / max(rate, 0.1)        # rate=0.5 → 2x cost; rate=0.1 → 10x
    return learned
```

### Target 3 — Goal value (selection ordering)

**Stored:** derived — number of cycles between selecting a goal and seeing `is_satisfied(state)` become true. Implementation: a `cycles_to_satisfy` int column on the row where the goal transitions to satisfied (computed in player loop by remembering the cycle index when each goal was first selected and writing the delta when it satisfies).

**Aggregated:** median cycles-to-satisfy over last 20 goal completions. Fallback: None when sample_count < 5.

**Applied:** modulates the static value.

```python
def value(self, state, game_data, history=None):
    raw = ...static formula...
    if history is None:
        return raw
    avg_cycles = history.goal_avg_cycles_to_satisfy(repr(self), window=20)
    if avg_cycles is None or avg_cycles == 0:
        return raw
    efficiency = min(1.0, 5.0 / avg_cycles)    # 5 cycles "normal", 50 cycles 0.1x
    return raw * efficiency
```

### Target 4 — Action effects (state delta predictions)

**Stored:** `cycles.delta_gold`, `delta_xp`, `delta_hp`, `delta_inv_used`, `drops_json` per cycle. Computed in player loop as `new_state.<field> - prev_state.<field>`.

**Aggregated:** median of each delta field over last 50 events for `action_repr`.

**Applied:** consulted by **goals** (not by `apply()` — that stays pure). Example:

```python
# FarmMonsterGoal.value
def value(self, state, game_data, history=None):
    base = 30 + (state.xp / state.max_xp) * 20
    if history is None:
        return base
    fight_repr = f"Fight({self.monster_code})"
    observed_xp = history.action_effect(fight_repr, "delta_xp", window=50)
    if observed_xp is None:
        return base
    xp_multiplier = min(2.0, max(0.5, observed_xp / 10.0))
    return base * xp_multiplier
```

### Composition

All four stack:
- Goal selection — Targets 3 + 4.
- Planner A* search — Targets 1 + 2.

5-cycle warmup prevents spurious adjustments from tiny samples. 50-cycle window means recent behaviour dominates.

## Error handling, concurrency, lifecycle

### Best-effort discipline

The store must not break the player loop. Three failure modes:

| Failure | Handling |
|---|---|
| DB unreachable at startup | `__init__` creates parent dirs + DB file. If creation fails, raise — user passed `--learn`, must know |
| `record_cycle` write fails | Catch `SQLAlchemyError`, log warning once per session, continue. Cycle data lost; player keeps playing |
| Query fails during planning | Catch `SQLAlchemyError`, return supplied default. Degrades to v1 behaviour for that cycle |

**CLAUDE.md compliance:** catch `sqlalchemy.exc.SQLAlchemyError` (specific base), not bare `Exception`. Do NOT catch `pydantic.ValidationError` — validation failure = programming bug; fail loud.

### Concurrency

Single-process default. WAL mode enabled at engine creation handles concurrent reads + serial writes if multiple `artifactsmmo play <character>` invocations share a DB.

```python
with self._engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA synchronous=NORMAL"))
    conn.commit()
```

`synchronous=NORMAL` trades a tiny crash-recovery window for ~3× write throughput — appropriate for non-critical learning data.

### Lifecycle

1. **Startup** (in `commands/play.py` when `--learn`):
   - `store = LearningStore(db_path, character)` — creates DB, runs `SQLModel.metadata.create_all`.
   - `store.start_session()` — inserts `Session` row, captures session_id.
   - Pass `store` into `GamePlayer(..., history=store)`.

2. **Per cycle** (in `GamePlayer.run`):
   - Compute deltas from `prev_state` vs `new_state`.
   - Compute `drops_json` from inventory diff.
   - Construct `Cycle(...)` — Pydantic validates fields here.
   - Call `store.record_cycle(cycle)` — one INSERT, ~0.5ms.

3. **Shutdown** (always, in same `try/finally` that closes the tracer):
   - `store.end_session(exit_reason)` — `"normal"` | `"keyboard_interrupt"` | `"signal:<n>"`.
   - `store.close()`.

### Schema migration policy

v1: additive-only via `SQLModel.metadata.create_all`. New tables/columns appear on next startup; old data preserved; no destructive changes.

Add Alembic when first breaking change required.

### CLI integration

```python
@app.command("play")
def play(
    character: str = typer.Argument(...),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    trace: bool = typer.Option(False, "--trace"),
    trace_file: str | None = typer.Option(None, "--trace-file"),
    learn: bool = typer.Option(False, "--learn",
                                help="Read/write learned stats to SQLite for autoregressive planning"),
    learn_db: str | None = typer.Option(None, "--learn-db",
                                         help="Learning DB path (default: ~/.cache/artifactsmmo/learning.db)"),
) -> None:
    store: LearningStore | None = None
    if learn:
        db_path = learn_db or default_learn_db_path()
        store = LearningStore(db_path=db_path, character=character)
        store.start_session()
        print(f"Learning enabled — DB at {db_path}")

    player = GamePlayer(character=character, ..., history=store)
    try:
        player.run()
    finally:
        if store is not None:
            store.end_session(exit_reason="normal")
            store.close()
```

`default_learn_db_path()` returns `pathlib.Path.home() / ".cache" / "artifactsmmo" / "learning.db"` (parent dirs auto-created at first use).

## Testing strategy

### Layer 1 — `LearningStore` unit tests (`test_learning_store.py`)

In-memory SQLite via `create_engine("sqlite:///:memory:")`. Coverage:
- Schema creation idempotency.
- `record_cycle` round-trip.
- `action_cost` returns default when sample < 5; returns median when sample ≥ 5.
- `success_rate` boundary cases (all ok / all error / mixed).
- `goal_avg_cycles_to_satisfy` with synthesised satisfaction events.
- Pydantic validation: `Cycle(actual_cooldown_seconds="bad")` raises `ValidationError`.
- WAL pragma applied (verify via `PRAGMA journal_mode`).
- `record_cycle` swallows `SQLAlchemyError` (mock failing session).

### Layer 2 — Model unit tests (`test_learning_models.py`)

Smoke tests confirming `Cycle` and `Session` instantiate correctly and reject malformed inputs. SQLModel's framework-level validation isn't our job — only column-level type sanity.

### Layer 3 — Integration tests (`test_player_learning.py`)

- `GamePlayer(..., history=store)` writes a `Cycle` per execution.
- After N synthesised cycles, `store.action_cost(repr(action))` returns learned median, not static default.
- Goal value modulation: synthetic delta_xp drives `FarmMonsterGoal.value` up/down.
- Backward compat: `history=None` produces identical behaviour to v1.

### Layer 4 — End-to-end CLI smoke (`test_cli_learn.py`)

`commands/play.py` with `--learn` and `--dry-run` against temp DB. Verify DB created, schema present, session inserted, closes cleanly.

### Out of scope
- Live convergence tests (run Robby for hours, inspect DB — empirical, not unit-testable).
- Multi-process WAL concurrency (SQLAlchemy's own coverage).
- Alembic migration tests (Alembic not yet in scope).

## Build order

Six phases.

| Phase | Scope | Estimate |
|---|---|---|
| **F-A** | `Cycle` + `Session` SQLModel + schema creation. Tests for model validation | ½ day |
| **F-B** | `LearningStore` class: `__init__`, `start_session`, `end_session`, `record_cycle`, `close`. WAL/sync pragmas. Round-trip + error-handling tests | 1 day |
| **F-C** | Query methods: `action_cost`, `success_rate`, `goal_avg_cycles_to_satisfy`, `action_effect`, `action_stats`, `goal_stats`, `sample_count`. Tests for each | 1 day |
| **F-D** | Signature additions: `history` param to `Action.cost`, `Goal.value`, `Goal.priority`, `GOAPPlanner.plan`. Mechanical pass over every subclass | ½ day |
| **F-E** | Opt-in integration: `FightAction.cost`, `GatherAction.cost`, `MoveAction.cost`, `FarmMonsterGoal.value`, `GatherMaterialsGoal.value`. Integration tests | 1 day |
| **F-F** | Player wiring + CLI: `GamePlayer(history=...)`, per-cycle delta compute, `store.record_cycle()`, `--learn` / `--learn-db` flags, `default_learn_db_path()`. E2E smoke | 1 day |

**Total: ~5 days focused work.**

Validation gate per phase:
- `uv run pytest tests/test_ai/ -q` — green.
- `uv run mypy src/artifactsmmo_cli/ai/ src/artifactsmmo_cli/ai/learning/` — clean.
- After F-F: `uv run artifactsmmo play <char> --learn --learn-db /tmp/test.db --dry-run` — DB created, schema correct, session populated.

### Order rationale

F-A first (everything depends on models). F-B next (store core). F-C before F-D (need query methods before wiring signatures that consume them). F-D before F-E (signature change is mechanical one-PR; F-E uses new signature). F-F last (user-facing wiring).

## Open design decisions (revisit during implementation)

1. **Goal cycles-to-satisfy capture mechanism** — easiest path is a `_pending_goal_selections: dict[str, int]` on `GamePlayer` tracking `repr(goal) → first_selected_cycle`; when `goal.is_satisfied()` becomes true, write the delta to the Cycle row and clear. Validate this is sufficient during F-E implementation.
2. **Drops-JSON format** — currently spec says `{item_code: qty}`. Could include `total_value_gold` derived from observed NPC sell prices. Defer until we have real drop data to look at.
3. **Recency-window tuning** — 50 events for actions, 20 for goal completions. May need adjustment after first multi-hour run with `--learn`. Constants live in `LearningStore.action_cost(window=50)` etc., easy to tune.
4. **Warmup threshold** — currently 5 samples. If learning kicks in too aggressively on noisy early data, raise to 10. Tuneable per query method.
5. **Multi-character DB layout** — current design is one DB with `character` column. If we ever want true per-character isolation (separate files), the `LearningStore(db_path, character)` API doesn't change — only `default_learn_db_path()` shifts to `~/.cache/artifactsmmo/<character>/learning.db`. Non-breaking.
