# Autoregressive Planning Implementation Plan

> **Status: COMPLETED** (2026-05-17). All six sub-phases (F-A through F-F) merged to `main`. Plan checkboxes left as-is for historical reference; see the live `main` branch for the implemented form. Real-play follow-on work (planner state-key, FarmItems horizon, etc.) is documented in the GOAP Robustness Layer plan's "Post-merge fixes" section since those bugs lived in the GOAP layer, not the learning layer.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add SQLModel-backed learning store so GOAP actions and goals consult observed history (action cost, success rate, observed effects, goal effectiveness) when computing cost and value, enabling within-session adaptation.

**Architecture:** New `src/artifactsmmo_cli/ai/learning/` package: SQLModel `Cycle` + `Session` storage models, `LearningStore` wrapping a SQLAlchemy engine with WAL pragmas, query methods that fall back to defaults until sample warmup is reached. `Action.cost` / `Goal.value` / `GOAPPlanner.plan` add `history: LearningStore | None = None` parameter (backward compatible). Selected hot-path actions/goals (`FightAction`, `GatherAction`, `MoveAction`, `FarmMonsterGoal`, `GatherMaterialsGoal`) consult the store; rest ignore it. Player wiring writes one `Cycle` row per loop iteration, tracking goal first-selected to compute cycles-to-satisfy.

**Tech Stack:** Python 3.13, uv, SQLModel (>=0.0.14) pulling SQLAlchemy 2.x + Pydantic 2 transitively, pytest + pytest-cov, mypy, Typer (CLI).

**Spec:** `docs/superpowers/specs/2026-05-17-autoregressive-planning-design.md`

---

## File Structure

### New files
```
src/artifactsmmo_cli/ai/learning/
├── __init__.py
├── models.py        # Cycle, Session SQLModel classes
├── types.py         # ActionStats, GoalStats Pydantic models
└── store.py         # LearningStore class

tests/test_ai/
├── test_learning_models.py
├── test_learning_store.py
├── test_player_learning.py
└── test_cli_learn.py
```

### Modified files
- `pyproject.toml` — add `sqlmodel>=0.0.14`
- `src/artifactsmmo_cli/ai/actions/base.py` — `Action.cost` signature
- `src/artifactsmmo_cli/ai/goals/base.py` — `Goal.value` + `Goal.priority` signatures
- `src/artifactsmmo_cli/ai/planner.py` — `GOAPPlanner.plan` signature
- `src/artifactsmmo_cli/ai/player.py` — accept `history`, compute deltas, record cycles
- `src/artifactsmmo_cli/commands/play.py` — `--learn` / `--learn-db` flags
- Every `actions/*.py` subclass — append `history` parameter to `cost()`
- Every `goals/*.py` subclass — append `history` parameter to `value()` / `priority()`
- Five subclasses opt in to actually consult `history`

---

# Phase F-A — SQLModel storage

**Validation gate:** model unit tests green; mypy clean.

---

## Task F-A1: Add sqlmodel dependency + create package

**Files:**
- Modify: `pyproject.toml`
- Create: `src/artifactsmmo_cli/ai/learning/__init__.py`

- [ ] **Step 1: Add the dependency**

```bash
uv add sqlmodel
```

Expected: `pyproject.toml` updated; `uv.lock` regenerated.

- [ ] **Step 2: Create the package skeleton**

```bash
mkdir -p src/artifactsmmo_cli/ai/learning
touch src/artifactsmmo_cli/ai/learning/__init__.py
```

- [ ] **Step 3: Verify install**

```bash
uv run python -c "import sqlmodel; print(sqlmodel.__version__)"
```

Expected: version >=0.0.14 printed.

- [ ] **Step 4: Verify no regression**

```bash
uv run pytest tests/test_ai/ -q --tb=no 2>&1 | tail -3
```

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock src/artifactsmmo_cli/ai/learning/__init__.py
git commit -m "feat(ai): add sqlmodel dependency and learning package skeleton"
```

---

## Task F-A2: Create Cycle SQLModel

**Files:**
- Create: `src/artifactsmmo_cli/ai/learning/models.py`
- Create: `tests/test_ai/test_learning_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_learning_models.py`:

```python
"""Tests for SQLModel storage models."""

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.learning.models import Cycle


class TestCycle:
    def test_minimal_construction_with_required_fields(self):
        c = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="session-1",
            cycle_index=0,
            character="testchar",
            outcome="ok",
        )
        assert c.session_id == "session-1"
        assert c.outcome == "ok"
        assert c.bank_accessible is True
        assert c.actual_cooldown_seconds is None

    def test_validation_rejects_non_numeric_cooldown(self):
        with pytest.raises(ValidationError):
            Cycle(
                ts="2026-05-17T00:00:00+00:00",
                session_id="session-1",
                cycle_index=0,
                character="testchar",
                outcome="ok",
                actual_cooldown_seconds="not a number",  # type: ignore[arg-type]
            )

    def test_all_optional_state_fields_accept_none(self):
        c = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="session-1",
            cycle_index=0,
            character="testchar",
            outcome="no_plan",
            x=None, y=None, hp=None, gold=None, level=None,
        )
        assert c.x is None
        assert c.gold is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_ai/test_learning_models.py -v
```

Expected: collection error.

- [ ] **Step 3: Implement Cycle model**

Create `src/artifactsmmo_cli/ai/learning/models.py`:

```python
"""SQLModel definitions for the GOAP learning store.

Each model is simultaneously a Pydantic model (validation at construction)
and a SQLAlchemy ORM row (persistence).
"""

from sqlmodel import Field, SQLModel


class Cycle(SQLModel, table=True):
    """One row per player-loop cycle."""

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
    outcome: str

    # Cost & planner
    predicted_cost: float | None = None
    actual_cooldown_seconds: float | None = None
    planner_nodes: int | None = None
    planner_depth: int | None = None
    planner_timed_out: bool | None = None
    plan_len: int | None = None

    # Effects (state delta from previous cycle)
    delta_gold: int | None = None
    delta_xp: int | None = None
    delta_hp: int | None = None
    delta_inv_used: int | None = None
    drops_json: str | None = None

    # Goal completion tracking
    cycles_to_satisfy: int | None = None
```

- [ ] **Step 4: Run tests to verify pass**

```bash
uv run pytest tests/test_ai/test_learning_models.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py tests/test_ai/test_learning_models.py
git commit -m "feat(ai): add Cycle SQLModel for per-cycle observation storage"
```

---

## Task F-A3: Add Session SQLModel

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py`
- Modify: `tests/test_ai/test_learning_models.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_learning_models.py`:

```python
from artifactsmmo_cli.ai.learning.models import Session


class TestSession:
    def test_minimal_construction(self):
        s = Session(
            session_id="session-1",
            started_at="2026-05-17T00:00:00+00:00",
            character="testchar",
        )
        assert s.session_id == "session-1"
        assert s.cycle_count == 0
        assert s.ended_at is None
        assert s.exit_reason is None

    def test_with_exit_reason(self):
        s = Session(
            session_id="session-1",
            started_at="2026-05-17T00:00:00+00:00",
            character="testchar",
            ended_at="2026-05-17T01:00:00+00:00",
            cycle_count=42,
            exit_reason="normal",
        )
        assert s.cycle_count == 42
        assert s.exit_reason == "normal"
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_models.py::TestSession -v
```

Expected: collection error (Session not defined).

- [ ] **Step 3: Add Session to models.py**

Append to `src/artifactsmmo_cli/ai/learning/models.py`:

```python
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

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_models.py -v
```

Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py tests/test_ai/test_learning_models.py
git commit -m "feat(ai): add Session SQLModel for player.run() invocations"
```

---

## Task F-A4: Add ActionStats and GoalStats Pydantic types

**Files:**
- Create: `src/artifactsmmo_cli/ai/learning/types.py`
- Modify: `tests/test_ai/test_learning_models.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_learning_models.py`:

```python
from artifactsmmo_cli.ai.learning.types import ActionStats, GoalStats


class TestActionStats:
    def test_construction_and_immutability(self):
        s = ActionStats(
            action_repr="Fight(yellow_slime)",
            sample_count=10,
            median_cost_seconds=12.3,
            success_rate=0.9,
            median_delta_xp=15.0,
            median_delta_gold=0.0,
        )
        assert s.action_repr == "Fight(yellow_slime)"
        with pytest.raises(ValidationError):
            s.action_repr = "changed"  # type: ignore[misc]


class TestGoalStats:
    def test_construction(self):
        s = GoalStats(
            goal_repr="FarmMonster(yellow_slime)",
            sample_count=3,
            avg_cycles_to_satisfy=12.5,
            satisfaction_rate=0.66,
        )
        assert s.sample_count == 3
        assert s.avg_cycles_to_satisfy == 12.5

    def test_avg_cycles_can_be_none(self):
        s = GoalStats(
            goal_repr="X",
            sample_count=0,
            avg_cycles_to_satisfy=None,
            satisfaction_rate=0.0,
        )
        assert s.avg_cycles_to_satisfy is None
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_models.py::TestActionStats tests/test_ai/test_learning_models.py::TestGoalStats -v
```

Expected: collection error.

- [ ] **Step 3: Implement types**

Create `src/artifactsmmo_cli/ai/learning/types.py`:

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

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_models.py -v
```

Expected: 8 tests pass total.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/types.py tests/test_ai/test_learning_models.py
git commit -m "feat(ai): add ActionStats and GoalStats Pydantic query-result models"
```

---

### Phase F-A Validation Gate

```bash
uv run pytest tests/test_ai/test_learning_models.py -q
uv run mypy src/artifactsmmo_cli/ai/learning/
```

Expected: all green; mypy clean.

---

# Phase F-B — LearningStore core

**Validation gate:** in-memory SQLite round-trip; WAL pragma applied; error tolerance verified.

---

## Task F-B1: LearningStore __init__ + schema creation + pragmas

**Files:**
- Create: `src/artifactsmmo_cli/ai/learning/store.py`
- Create: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_learning_store.py`:

```python
"""Tests for LearningStore."""

import os
import tempfile

import pytest
from sqlalchemy import text
from sqlmodel import Session as SqlSession

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.learning.store import LearningStore


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


class TestLearningStoreInit:
    def test_creates_db_file(self, tmp_db_path):
        os.unlink(tmp_db_path)
        assert not os.path.exists(tmp_db_path)
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        assert os.path.exists(tmp_db_path)
        store.close()

    def test_creates_tables(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        with SqlSession(store._engine) as s:
            result = s.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )).all()
        store.close()
        names = {row[0] for row in result}
        assert "cycles" in names
        assert "sessions" in names

    def test_wal_journal_mode_enabled(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        with store._engine.connect() as conn:
            mode = conn.execute(text("PRAGMA journal_mode")).scalar()
        store.close()
        assert mode == "wal"

    def test_idempotent_init(self, tmp_db_path):
        store1 = LearningStore(db_path=tmp_db_path, character="testchar")
        store1.close()
        store2 = LearningStore(db_path=tmp_db_path, character="testchar")
        store2.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py -v
```

Expected: collection error (LearningStore not defined).

- [ ] **Step 3: Create store skeleton**

Create `src/artifactsmmo_cli/ai/learning/store.py`:

```python
"""SQLModel-backed learning store for autoregressive GOAP planning."""

from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from artifactsmmo_cli.ai.learning.models import Cycle, Session


class LearningStore:
    """Event log + queryable learned stats. Best-effort: errors degrade to defaults."""

    def __init__(self, db_path: str, character: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)

        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()

        self._character = character
        self._session_id: str | None = None

    def close(self) -> None:
        self._engine.dispose()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestLearningStoreInit -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): LearningStore __init__ with schema creation and WAL pragmas"
```

---

## Task F-B2: start_session / end_session

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_learning_store.py`:

```python
class TestSessionLifecycle:
    def test_start_session_returns_id_and_inserts_row(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        session_id = store.start_session()
        assert session_id.startswith("session-")

        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT session_id, character, exit_reason FROM sessions")).all()
        store.close()
        assert len(rows) == 1
        assert rows[0][0] == session_id
        assert rows[0][1] == "testchar"
        assert rows[0][2] is None

    def test_end_session_records_exit_reason(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        session_id = store.start_session()
        store.end_session(exit_reason="keyboard_interrupt")
        with SqlSession(store._engine) as s:
            rows = s.execute(text(
                "SELECT exit_reason, ended_at FROM sessions WHERE session_id=:sid"
            ), {"sid": session_id}).all()
        store.close()
        assert rows[0][0] == "keyboard_interrupt"
        assert rows[0][1] is not None

    def test_end_session_without_start_is_noop(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.end_session()
        store.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestSessionLifecycle -v
```

Expected: FAIL (methods missing).

- [ ] **Step 3: Implement**

In `src/artifactsmmo_cli/ai/learning/store.py`, add imports + methods:

```python
from datetime import datetime, timezone

from sqlmodel import Session as SqlSession
```

Add methods to `LearningStore`:

```python
    def start_session(self) -> str:
        """Begin a new session; insert Session row, return session_id."""
        self._session_id = datetime.now(tz=timezone.utc).strftime("session-%Y%m%d-%H%M%S-%f")
        with SqlSession(self._engine) as s:
            s.add(Session(
                session_id=self._session_id,
                started_at=datetime.now(tz=timezone.utc).isoformat(),
                character=self._character,
            ))
            s.commit()
        return self._session_id

    def end_session(self, exit_reason: str = "normal") -> None:
        """Mark current session ended. No-op if no session was started."""
        if self._session_id is None:
            return
        with SqlSession(self._engine) as s:
            row = s.get(Session, self._session_id)
            if row is not None:
                row.ended_at = datetime.now(tz=timezone.utc).isoformat()
                row.exit_reason = exit_reason
                s.add(row)
                s.commit()
        self._session_id = None
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -v
```

Expected: 7 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): LearningStore.start_session and end_session lifecycle"
```

---

## Task F-B3: record_cycle with SQLAlchemyError handling

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_learning_store.py`:

```python
class TestRecordCycle:
    def test_round_trip(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="overridden",
            cycle_index=0,
            character="overridden",
            outcome="ok",
            action_repr="Fight(yellow_slime)",
            actual_cooldown_seconds=12.5,
        )
        store.record_cycle(cycle)

        with SqlSession(store._engine) as s:
            rows = s.execute(text(
                "SELECT action_repr, actual_cooldown_seconds, session_id, character FROM cycles"
            )).all()
        store.close()
        assert len(rows) == 1
        assert rows[0][0] == "Fight(yellow_slime)"
        assert rows[0][1] == 12.5

    def test_record_cycle_overrides_session_id_and_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="actual_char")
        session_id = store.start_session()
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="wrong",
            cycle_index=0,
            character="wrong",
            outcome="ok",
        )
        store.record_cycle(cycle)
        with SqlSession(store._engine) as s:
            rows = s.execute(text("SELECT session_id, character FROM cycles")).all()
        store.close()
        assert rows[0][0] == session_id
        assert rows[0][1] == "actual_char"

    def test_record_cycle_swallows_sqlalchemy_error(self, tmp_db_path, monkeypatch):
        from sqlalchemy.exc import SQLAlchemyError

        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()

        def boom(self, instance):
            raise SQLAlchemyError("simulated DB failure")

        monkeypatch.setattr(SqlSession, "add", boom)
        cycle = Cycle(
            ts="2026-05-17T00:00:00+00:00",
            session_id="x", cycle_index=0, character="testchar", outcome="ok",
        )
        store.record_cycle(cycle)
        store.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestRecordCycle -v
```

Expected: FAIL.

- [ ] **Step 3: Implement record_cycle**

Add import:

```python
from sqlalchemy.exc import SQLAlchemyError
```

Add method to `LearningStore`:

```python
    def record_cycle(self, cycle: Cycle) -> None:
        """Insert one validated Cycle row. Best-effort: SQLAlchemyError caught, never raised."""
        if self._session_id is None:
            return
        cycle.session_id = self._session_id
        cycle.character = self._character
        try:
            with SqlSession(self._engine) as s:
                s.add(cycle)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_cycle failed: {e}")
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -v
```

Expected: 10 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): LearningStore.record_cycle with SQLAlchemyError tolerance"
```

---

## Task F-B4: Re-export LearningStore from package

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/__init__.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_learning_store.py`:

```python
def test_package_reexport():
    from artifactsmmo_cli.ai.learning import LearningStore as RootImport
    from artifactsmmo_cli.ai.learning.store import LearningStore as ModuleImport
    assert RootImport is ModuleImport
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::test_package_reexport -v
```

Expected: FAIL.

- [ ] **Step 3: Add re-export**

Replace `src/artifactsmmo_cli/ai/learning/__init__.py` with:

```python
"""GOAP learning store: SQLModel-backed event log + queryable stats."""

from artifactsmmo_cli.ai.learning.store import LearningStore

__all__ = ["LearningStore"]
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -q
```

Expected: 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/__init__.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): re-export LearningStore from learning package"
```

---

### Phase F-B Validation Gate

```bash
uv run pytest tests/test_ai/test_learning_store.py tests/test_ai/test_learning_models.py -q
uv run mypy src/artifactsmmo_cli/ai/learning/
```

---

# Phase F-C — Query methods

**Validation gate:** all query methods covered by unit tests against synthetic event histories.

---

## Task F-C1: action_cost query

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ai/test_learning_store.py`:

```python
def _insert_cycles(store, action_repr, cooldowns, outcomes=None):
    """Helper: insert N cycles with given cooldowns and outcomes."""
    outcomes = outcomes or ["ok"] * len(cooldowns)
    for i, (cd, oc) in enumerate(zip(cooldowns, outcomes)):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome=oc,
            action_repr=action_repr,
            actual_cooldown_seconds=cd,
        ))


class TestActionCost:
    def test_returns_default_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0])
        assert store.action_cost("Fight(x)", default=99.0) == 99.0
        store.close()

    def test_returns_median_when_at_least_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0, 11.0, 12.0, 13.0, 14.0])
        assert store.action_cost("Fight(x)", default=99.0) == 12.0
        store.close()

    def test_filters_by_action_repr(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 5)
        _insert_cycles(store, "Fight(y)", [20.0] * 5)
        assert store.action_cost("Fight(x)", default=99.0) == 10.0
        assert store.action_cost("Fight(y)", default=99.0) == 20.0
        store.close()

    def test_ignores_failed_actions(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)",
                       cooldowns=[10.0, 10.0, 10.0, 99.0, 99.0],
                       outcomes=["ok", "ok", "ok", "error:HTTP_497", "error:HTTP_497"])
        assert store.action_cost("Fight(x)", default=42.0) == 42.0
        store.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestActionCost -v
```

Expected: FAIL.

- [ ] **Step 3: Implement action_cost**

Add imports to `src/artifactsmmo_cli/ai/learning/store.py`:

```python
import statistics

from sqlmodel import select
```

Add method to `LearningStore`:

```python
    def action_cost(self, action_repr: str, default: float, window: int = 50) -> float:
        """Median actual_cooldown_seconds over last `window` ok cycles, or default if < 5 samples."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.actual_cooldown_seconds)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                        Cycle.outcome == "ok",
                        Cycle.actual_cooldown_seconds.is_not(None),
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if len(rows) < 5:
                return default
            return statistics.median(rows)
        except SQLAlchemyError:
            return default
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -q
```

Expected: 15 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): LearningStore.action_cost query (median cooldown over recent window)"
```

---

## Task F-C2: success_rate query

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ai/test_learning_store.py`:

```python
class TestSuccessRate:
    def test_returns_1_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 3, outcomes=["error:X"] * 3)
        assert store.success_rate("Fight(x)") == 1.0
        store.close()

    def test_all_ok_returns_1(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 10, outcomes=["ok"] * 10)
        assert store.success_rate("Fight(x)") == 1.0
        store.close()

    def test_all_error_returns_0(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 10, outcomes=["error:X"] * 10)
        assert store.success_rate("Fight(x)") == 0.0
        store.close()

    def test_mixed_returns_fraction(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 10,
                       outcomes=["ok"] * 7 + ["error:X"] * 3)
        assert store.success_rate("Fight(x)") == 0.7
        store.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestSuccessRate -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Add method to `LearningStore`:

```python
    def success_rate(self, action_repr: str, window: int = 50) -> float:
        """Fraction of last `window` cycles with outcome=='ok'. 1.0 if < 5 samples."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.outcome)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                outcomes = list(s.exec(stmt))
            if len(outcomes) < 5:
                return 1.0
            return sum(1 for o in outcomes if o == "ok") / len(outcomes)
        except SQLAlchemyError:
            return 1.0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -q
```

Expected: 19 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): LearningStore.success_rate query"
```

---

## Task F-C3: action_effect query

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ai/test_learning_store.py`:

```python
def _insert_cycles_with_deltas(store, action_repr, deltas):
    for i, d in enumerate(deltas):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome="ok",
            action_repr=action_repr,
            delta_xp=d.get("delta_xp"),
            delta_gold=d.get("delta_gold"),
            delta_hp=d.get("delta_hp"),
            delta_inv_used=d.get("delta_inv_used"),
        ))


class TestActionEffect:
    def test_returns_none_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "Fight(x)", [{"delta_xp": 10}] * 3)
        assert store.action_effect("Fight(x)", "delta_xp") is None
        store.close()

    def test_returns_median_delta_xp(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "Fight(x)",
            [{"delta_xp": v} for v in [10, 12, 14, 16, 18]])
        assert store.action_effect("Fight(x)", "delta_xp") == 14.0
        store.close()

    def test_returns_median_delta_gold(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "Sell(x)",
            [{"delta_gold": v} for v in [5, 5, 10, 10, 10]])
        assert store.action_effect("Sell(x)", "delta_gold") == 10.0
        store.close()

    def test_unknown_field_returns_none(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles_with_deltas(store, "X", [{"delta_xp": 10}] * 5)
        assert store.action_effect("X", "nonexistent_field") is None
        store.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestActionEffect -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Add method + allowed-field constant to `LearningStore`:

```python
    _ALLOWED_EFFECT_FIELDS = ("delta_gold", "delta_xp", "delta_hp", "delta_inv_used")

    def action_effect(self, action_repr: str, field: str, window: int = 50) -> float | None:
        """Median of `field` over recent ok cycles. Allowed fields: delta_gold/delta_xp/delta_hp/delta_inv_used."""
        if field not in self._ALLOWED_EFFECT_FIELDS:
            return None
        col = getattr(Cycle, field)
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(col)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                        Cycle.outcome == "ok",
                        col.is_not(None),
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if len(rows) < 5:
                return None
            return statistics.median(rows)
        except SQLAlchemyError:
            return None
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -q
```

Expected: 23 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): LearningStore.action_effect query (median state delta per action)"
```

---

## Task F-C4: goal_avg_cycles_to_satisfy query + sample_count

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ai/test_learning_store.py`:

```python
def _insert_goal_satisfactions(store, goal_repr, cycle_deltas):
    for i, cd in enumerate(cycle_deltas):
        store.record_cycle(Cycle(
            ts=f"2026-05-17T00:00:{i:02d}+00:00",
            session_id="x", cycle_index=i, character="x", outcome="ok",
            selected_goal=goal_repr,
            cycles_to_satisfy=cd,
        ))


class TestGoalAvgCyclesToSatisfy:
    def test_returns_none_when_fewer_than_5_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_goal_satisfactions(store, "FarmMonster(x)", [3, 5, 7])
        assert store.goal_avg_cycles_to_satisfy("FarmMonster(x)") is None
        store.close()

    def test_returns_median_when_enough_samples(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_goal_satisfactions(store, "FarmMonster(x)", [4, 5, 6, 7, 8])
        assert store.goal_avg_cycles_to_satisfy("FarmMonster(x)") == 6.0
        store.close()


class TestSampleCount:
    def test_returns_zero_for_unknown_action(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        assert store.sample_count("Nothing(x)") == 0
        store.close()

    def test_counts_only_matching_action_and_character(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        _insert_cycles(store, "Fight(x)", [10.0] * 7)
        _insert_cycles(store, "Fight(y)", [10.0] * 3)
        assert store.sample_count("Fight(x)") == 7
        assert store.sample_count("Fight(y)") == 3
        store.close()
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestGoalAvgCyclesToSatisfy tests/test_ai/test_learning_store.py::TestSampleCount -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Add methods to `LearningStore`:

```python
    def goal_avg_cycles_to_satisfy(self, goal_repr: str, window: int = 20) -> float | None:
        """Median cycles-to-satisfy over last `window` completions. None if < 5 samples."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.cycles_to_satisfy)
                    .where(
                        Cycle.character == self._character,
                        Cycle.selected_goal == goal_repr,
                        Cycle.cycles_to_satisfy.is_not(None),
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if len(rows) < 5:
                return None
            return statistics.median(rows)
        except SQLAlchemyError:
            return None

    def sample_count(self, action_repr: str) -> int:
        """Number of cycles recorded for this action_repr and the store's character."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.id)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                    )
                )
                return len(list(s.exec(stmt)))
        except SQLAlchemyError:
            return 0
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -q
```

Expected: 27 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): goal_avg_cycles_to_satisfy and sample_count queries"
```

---

## Task F-C5: action_stats and goal_stats rollups

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/store.py`
- Modify: `tests/test_ai/test_learning_store.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_ai/test_learning_store.py`:

```python
class TestStatsRollups:
    def test_action_stats_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        stats = store.action_stats("Nothing(x)")
        store.close()
        assert stats.action_repr == "Nothing(x)"
        assert stats.sample_count == 0
        assert stats.median_cost_seconds is None
        assert stats.success_rate == 1.0

    def test_action_stats_populated(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        store.start_session()
        for i in range(10):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T01:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(x)", actual_cooldown_seconds=12.0,
                delta_xp=10, delta_gold=0,
            ))
        stats = store.action_stats("Fight(x)")
        store.close()
        assert stats.sample_count == 10
        assert stats.median_cost_seconds == 12.0
        assert stats.success_rate == 1.0
        assert stats.median_delta_xp == 10.0


class TestGoalStatsRollup:
    def test_goal_stats_empty(self, tmp_db_path):
        store = LearningStore(db_path=tmp_db_path, character="testchar")
        stats = store.goal_stats("Nothing")
        store.close()
        assert stats.sample_count == 0
        assert stats.avg_cycles_to_satisfy is None
        assert stats.satisfaction_rate == 0.0
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_learning_store.py::TestStatsRollups tests/test_ai/test_learning_store.py::TestGoalStatsRollup -v
```

Expected: FAIL.

- [ ] **Step 3: Implement**

Add import:

```python
from artifactsmmo_cli.ai.learning.types import ActionStats, GoalStats
```

Add methods to `LearningStore`:

```python
    def action_stats(self, action_repr: str, window: int = 50) -> ActionStats:
        """Return one Pydantic-validated rollup for one action."""
        n = self.sample_count(action_repr)
        return ActionStats(
            action_repr=action_repr,
            sample_count=n,
            median_cost_seconds=(self.action_cost(action_repr, default=-1.0, window=window)
                                  if n >= 5 else None),
            success_rate=self.success_rate(action_repr, window=window),
            median_delta_xp=self.action_effect(action_repr, "delta_xp", window=window),
            median_delta_gold=self.action_effect(action_repr, "delta_gold", window=window),
        )

    def goal_stats(self, goal_repr: str, window: int = 20) -> GoalStats:
        """Return one Pydantic-validated rollup for one goal."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.cycles_to_satisfy)
                    .where(
                        Cycle.character == self._character,
                        Cycle.selected_goal == goal_repr,
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            sample_count = len(rows)
            satisfied = [r for r in rows if r is not None]
            sat_rate = (len(satisfied) / sample_count) if sample_count else 0.0
            avg = statistics.median(satisfied) if len(satisfied) >= 5 else None
            return GoalStats(
                goal_repr=goal_repr,
                sample_count=sample_count,
                avg_cycles_to_satisfy=avg,
                satisfaction_rate=sat_rate,
            )
        except SQLAlchemyError:
            return GoalStats(
                goal_repr=goal_repr,
                sample_count=0,
                avg_cycles_to_satisfy=None,
                satisfaction_rate=0.0,
            )
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_learning_store.py -q
```

Expected: 30 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/store.py tests/test_ai/test_learning_store.py
git commit -m "feat(ai): action_stats and goal_stats Pydantic rollups"
```

---

### Phase F-C Validation Gate

```bash
uv run pytest tests/test_ai/test_learning_store.py tests/test_ai/test_learning_models.py -q
uv run mypy src/artifactsmmo_cli/ai/learning/
```

---

# Phase F-D — Signature additions

**Validation gate:** AI test suite unchanged count; mypy clean.

---

## Task F-D1: Add history parameter to Action.cost ABC + all subclasses

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/base.py`
- Modify: every `src/artifactsmmo_cli/ai/actions/*.py` subclass

- [ ] **Step 1: Update the ABC**

In `src/artifactsmmo_cli/ai/actions/base.py`, add import at top:

```python
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Update the `cost` abstractmethod:

```python
    @abstractmethod
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        """Estimated seconds. Optional `history` lets subclasses consult learned stats."""
```

- [ ] **Step 2: Update every concrete subclass's cost method**

Files to update: `bank.py`, `bank_expansion.py`, `bank_gold.py`, `claim.py`, `combat.py`, `consumable.py`, `crafting.py`, `delete.py`, `equipment.py`, `gathering.py`, `movement.py`, `movement_semantic.py`, `npc.py`, `npc_sell.py`, `recycle.py`, `rest.py`, `task.py`, `task_trade.py`, `transition.py`.

For each, add `LearningStore` import at top:

```python
from artifactsmmo_cli.ai.learning.store import LearningStore
```

And append the parameter to the `cost` signature:

```python
    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        # ... existing body unchanged
```

- [ ] **Step 3: Run AI tests to confirm no regression**

```bash
uv run pytest tests/test_ai/ -q --tb=no 2>&1 | tail -3
```

Expected: same test count; no failures.

- [ ] **Step 4: Mypy check**

```bash
uv run mypy src/artifactsmmo_cli/ai/actions/ 2>&1 | tail -5
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/
git commit -m "refactor(ai): add history parameter to Action.cost ABC and subclasses"
```

---

## Task F-D2: Add history parameter to Goal.value + Goal.priority ABC and subclasses

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/base.py`
- Modify: every `src/artifactsmmo_cli/ai/goals/*.py` subclass

- [ ] **Step 1: Update the ABC**

In `src/artifactsmmo_cli/ai/goals/base.py`, add import:

```python
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Update `value` and `priority`:

```python
    @abstractmethod
    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        """Urgency score. Higher = more urgent."""

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        """Goal selection weight. Defaults to value()."""
        return self.value(state, game_data, history)
```

- [ ] **Step 2: Update every concrete goal subclass**

Files to update: `claim_pending.py`, `combat.py`, `expand_bank.py`, `farm_items.py`, `gathering.py`, `progression.py`, `sell_inventory.py`, `survival.py`, `task_cancel.py`, `task_exchange.py`, `unlock_bank.py`.

For each, add the import and update `value` (and `priority` where overridden) signatures.

- [ ] **Step 3: Run AI tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no 2>&1 | tail -3
```

Expected: no regression.

- [ ] **Step 4: Mypy check**

```bash
uv run mypy src/artifactsmmo_cli/ai/goals/ 2>&1 | tail -5
```

Expected: clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/
git commit -m "refactor(ai): add history parameter to Goal.value/priority ABC and subclasses"
```

---

## Task F-D3: Add history to GOAPPlanner.plan and thread through

**Files:**
- Modify: `src/artifactsmmo_cli/ai/planner.py`
- Modify: `tests/test_ai/test_planner.py`

- [ ] **Step 1: Write a regression test**

Append to `tests/test_ai/test_planner.py`:

```python
def test_plan_accepts_history_parameter():
    """GOAPPlanner.plan should accept history (and ignore None gracefully)."""
    from artifactsmmo_cli.ai.actions.rest import RestAction
    from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
    from artifactsmmo_cli.ai.planner import GOAPPlanner
    from tests.test_ai.fixtures import make_state

    planner = GOAPPlanner()
    state = make_state(hp=50, max_hp=100)
    goal = RestoreHPGoal()
    actions = [RestAction()]
    plan = planner.plan(state, goal, actions, GameData(), history=None)
    assert plan == [RestAction()]
```

NOTE: hoist `GameData` to top of `test_planner.py` per CLAUDE.md.

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_planner.py::test_plan_accepts_history_parameter -v
```

Expected: FAIL.

- [ ] **Step 3: Update planner.py**

Add import at top:

```python
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Update `plan` signature and pass `history` to cost/value calls:

```python
    def plan(
        self,
        state: WorldState,
        goal: Goal,
        actions: list[Action],
        game_data: GameData,
        history: LearningStore | None = None,
    ) -> list[Action]:
        max_depth = goal.max_depth
        deadline = time.monotonic() + _SEARCH_BUDGET_SECONDS
        stats = PlanStats()

        h0 = goal.value(state, game_data, history)
        heap: list[_Node] = [_Node(f_score=h0, depth=0, state=state, plan=[], g_score=0.0)]
        visited: set[tuple[object, ...]] = set()
        relevant = goal.relevant_actions(actions, state, game_data)

        while heap:
            if time.monotonic() >= deadline:
                stats.timed_out = True
                break

            node = heapq.heappop(heap)

            key = _state_key(node.state)
            if key in visited:
                continue
            visited.add(key)
            stats.nodes_explored += 1
            if node.depth > stats.max_depth_reached:
                stats.max_depth_reached = node.depth

            if goal.is_satisfied(node.state):
                self.last_stats = stats
                return node.plan

            if node.depth >= max_depth:
                continue

            for action in relevant:
                if not action.is_applicable(node.state, game_data):
                    continue

                next_state = action.apply(node.state, game_data)
                g = node.g_score + action.cost(node.state, game_data, history)
                h = goal.value(next_state, game_data, history)
                heapq.heappush(
                    heap,
                    _Node(
                        f_score=g + h,
                        depth=node.depth + 1,
                        state=next_state,
                        plan=node.plan + [action],
                        g_score=g,
                    ),
                )

        self.last_stats = stats
        return []
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_planner.py tests/test_ai/test_player_run.py -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/planner.py tests/test_ai/test_planner.py
git commit -m "refactor(ai): GOAPPlanner.plan threads history through to cost/value calls"
```

---

### Phase F-D Validation Gate

```bash
uv run pytest tests/test_ai/ -q --tb=no
uv run mypy src/artifactsmmo_cli/ai/
```

---

# Phase F-E — Opt-in integrations

Five subclasses opt in. Each follows the same pattern: keep static formula as fallback; if `history` provided, query learned cost/effect; for actions, apply success-rate penalty.

---

## Task F-E1: FightAction.cost consults history

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/combat.py`
- Modify: `tests/test_ai/test_actions.py`

- [ ] **Step 1: Write failing test**

First, hoist these imports to top of `tests/test_ai/test_actions.py`:

```python
import os
import tempfile
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Append:

```python
def test_fight_action_cost_uses_history_when_provided():
    """When LearningStore has >=5 samples, FightAction.cost returns the learned median."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(yellow_slime)", actual_cooldown_seconds=25.0,
            ))
        action = FightAction(monster_code="yellow_slime", locations=frozenset({(1, 1)}))
        state = make_state(x=1, y=1, hp=100, max_hp=100)
        gd = GameData()
        # Confirm action.__repr__ matches "Fight(yellow_slime)" before relying on the test
        assert repr(action) == "Fight(yellow_slime)"
        assert action.cost(state, gd, history=store) == 25.0
        static_cost = action.cost(state, gd, history=None)
        assert static_cost != 25.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_fight_action_cost_penalises_low_success_rate():
    """Action with low success rate gets cost / success_rate penalty."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(z)", actual_cooldown_seconds=10.0,
            ))
        for i in range(5, 10):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="error:X",
                action_repr="Fight(z)", actual_cooldown_seconds=99.0,
            ))
        action = FightAction(monster_code="z", locations=frozenset({(1, 1)}))
        state = make_state(x=1, y=1, hp=100, max_hp=100)
        # Expected: 10.0 / 0.5 = 20.0
        assert action.cost(state, GameData(), history=store) == 20.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_actions.py::test_fight_action_cost_uses_history_when_provided tests/test_ai/test_actions.py::test_fight_action_cost_penalises_low_success_rate -v
```

Expected: FAIL.

- [ ] **Step 3: Update FightAction.cost**

In `src/artifactsmmo_cli/ai/actions/combat.py`, replace `FightAction.cost` body. Read the current static formula first to preserve it; then add learned-cost branch:

```python
def cost(self, state: WorldState, game_data: GameData,
         history: LearningStore | None = None) -> float:
    # ... compute `static` using the existing formula ...
    if history is None:
        return static
    learned = history.action_cost(repr(self), default=static, window=50)
    rate = history.success_rate(repr(self), window=50)
    if rate < 0.95:
        return learned / max(rate, 0.1)
    return learned
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: no regression + 2 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/combat.py tests/test_ai/test_actions.py
git commit -m "feat(ai): FightAction.cost consults LearningStore for learned cost + success penalty"
```

---

## Task F-E2: GatherAction.cost consults history

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/gathering.py`
- Modify: `tests/test_ai/test_actions.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_actions.py`:

```python
def test_gather_action_cost_uses_history_when_provided():
    from artifactsmmo_cli.ai.actions.gathering import GatherAction

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        action = GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 2)}))
        repr_str = repr(action)
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr=repr_str, actual_cooldown_seconds=18.0,
            ))
        state = make_state(x=2, y=2, hp=100, max_hp=100, inventory={}, inventory_max=20)
        assert action.cost(state, GameData(), history=store) == 18.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)
```

NOTE: hoist `GatherAction` to top of test file.

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_actions.py::test_gather_action_cost_uses_history_when_provided -v
```

Expected: FAIL.

- [ ] **Step 3: Update GatherAction.cost**

In `src/artifactsmmo_cli/ai/actions/gathering.py`, replace the `cost` body — preserve the existing static formula, then:

```python
def cost(self, state: WorldState, game_data: GameData,
         history: LearningStore | None = None) -> float:
    # ... existing static formula ...
    if history is None:
        return static
    learned = history.action_cost(repr(self), default=static, window=50)
    rate = history.success_rate(repr(self), window=50)
    if rate < 0.95:
        return learned / max(rate, 0.1)
    return learned
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: no regression + new test passes.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/gathering.py tests/test_ai/test_actions.py
git commit -m "feat(ai): GatherAction.cost consults LearningStore"
```

---

## Task F-E3: MoveAction.cost consults history

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/movement.py`
- Modify: `tests/test_ai/test_actions.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_actions.py`:

```python
def test_move_action_cost_uses_history_when_provided():
    from artifactsmmo_cli.ai.actions.movement import MoveAction

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        action = MoveAction(x=3, y=4)
        repr_str = repr(action)
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr=repr_str, actual_cooldown_seconds=8.0,
            ))
        state = make_state(x=0, y=0)
        assert action.cost(state, GameData(), history=store) == 8.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_actions.py::test_move_action_cost_uses_history_when_provided -v
```

Expected: FAIL.

- [ ] **Step 3: Update MoveAction.cost**

In `src/artifactsmmo_cli/ai/actions/movement.py`, replace `cost` body — preserve the existing static formula, then:

```python
def cost(self, state: WorldState, game_data: GameData,
         history: LearningStore | None = None) -> float:
    # ... existing static formula ...
    if history is None:
        return static
    learned = history.action_cost(repr(self), default=static, window=50)
    rate = history.success_rate(repr(self), window=50)
    if rate < 0.95:
        return learned / max(rate, 0.1)
    return learned
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: green + new test passes.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/actions/movement.py tests/test_ai/test_actions.py
git commit -m "feat(ai): MoveAction.cost consults LearningStore"
```

---

## Task F-E4: FarmMonsterGoal.value consults history

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/combat.py`
- Modify: `tests/test_ai/test_goals.py`

- [ ] **Step 1: Write failing test**

Hoist imports to top of `tests/test_ai/test_goals.py`:

```python
import os
import tempfile
from artifactsmmo_cli.ai.goals.combat import FarmMonsterGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Append:

```python
def test_farm_monster_goal_value_amplifies_on_high_xp_yield():
    """When Fight(monster) has observed high delta_xp, goal.value scales up."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                action_repr="Fight(yellow_slime)", delta_xp=20,
            ))
        goal = FarmMonsterGoal(monster_code="yellow_slime", initial_xp=0)
        gd = make_game_data()
        gd._monster_level = {"yellow_slime": 1}
        state = make_state(xp=50, max_xp=100, level=5)
        base = goal.value(state, gd, history=None)
        with_hist = goal.value(state, gd, history=store)
        # base = 30 + (50/100)*20 = 40
        # multiplier = min(2.0, max(0.5, 20/10)) = 2.0 → with_hist = 80
        assert base == 40.0
        assert with_hist == 80.0
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_farm_monster_goal_value_unchanged_when_history_none():
    gd = make_game_data()
    gd._monster_level = {"x": 1}
    state = make_state(xp=50, max_xp=100, level=5)
    goal = FarmMonsterGoal(monster_code="x", initial_xp=0)
    assert goal.value(state, gd) == goal.value(state, gd, history=None)
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_goals.py::test_farm_monster_goal_value_amplifies_on_high_xp_yield tests/test_ai/test_goals.py::test_farm_monster_goal_value_unchanged_when_history_none -v
```

Expected: FAIL.

- [ ] **Step 3: Update FarmMonsterGoal.value**

In `src/artifactsmmo_cli/ai/goals/combat.py`:

```python
def value(self, state: WorldState, game_data: GameData,
          history: LearningStore | None = None) -> float:
    monster_level = game_data.monster_level(self.monster_code)
    if monster_level > 0 and best_equipped_level(state, game_data) < monster_level - 1:
        return 0.0
    if state.max_xp == 0:
        return 30.0
    xp_fraction = state.xp / state.max_xp
    base = 30.0 + xp_fraction * 20.0

    if history is None:
        return base
    fight_repr = f"Fight({self.monster_code})"
    observed_xp = history.action_effect(fight_repr, "delta_xp", window=50)
    if observed_xp is None:
        return base
    xp_multiplier = min(2.0, max(0.5, observed_xp / 10.0))
    return base * xp_multiplier
```

The `fight_repr` MUST match `FightAction.__repr__()` exactly. Confirm by reading `FightAction.__repr__` in `actions/combat.py`. If it differs, adjust.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/combat.py tests/test_ai/test_goals.py
git commit -m "feat(ai): FarmMonsterGoal.value modulates by observed Fight delta_xp"
```

---

## Task F-E5: GatherMaterialsGoal.value consults history

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py`
- Modify: `tests/test_ai/test_goals.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_goals.py`:

```python
def test_gather_materials_goal_unchanged_when_history_none():
    from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
    goal = GatherMaterialsGoal(target_item="copper_boots", needed={"copper_ore": 60})
    state = make_state(inventory={}, inventory_max=104, bank_items={})
    gd = make_game_data()
    assert goal.value(state, gd) == goal.value(state, gd, history=None)


def test_gather_materials_goal_value_penalty_when_slow_to_satisfy():
    """When goal historically takes many cycles to satisfy, value is scaled down."""
    from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    try:
        store = LearningStore(db_path=path, character="testchar")
        store.start_session()
        for i in range(5):
            store.record_cycle(Cycle(
                ts=f"2026-05-17T00:00:{i:02d}+00:00",
                session_id="x", cycle_index=i, character="x", outcome="ok",
                selected_goal="GatherMaterials(copper_boots)",
                cycles_to_satisfy=50,
            ))
        goal = GatherMaterialsGoal(target_item="copper_boots", needed={"copper_ore": 60})
        state = make_state(inventory={}, inventory_max=104, bank_items={})
        gd = make_game_data()
        base = goal.value(state, gd, history=None)
        with_hist = goal.value(state, gd, history=store)
        assert with_hist < base  # penalty applied
        store.close()
    finally:
        if os.path.exists(path):
            os.unlink(path)
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_goals.py::test_gather_materials_goal_value_penalty_when_slow_to_satisfy tests/test_ai/test_goals.py::test_gather_materials_goal_unchanged_when_history_none -v
```

Expected: FAIL.

- [ ] **Step 3: Update GatherMaterialsGoal.value**

In `src/artifactsmmo_cli/ai/goals/gathering.py`:

```python
def value(self, state: WorldState, game_data: GameData,
          history: LearningStore | None = None) -> float:
    base = self._compute_base_value(state, game_data)
    if history is None:
        return base
    avg_cycles = history.goal_avg_cycles_to_satisfy(repr(self), window=20)
    if avg_cycles is None or avg_cycles == 0:
        return base
    efficiency = min(1.0, 5.0 / avg_cycles)
    return base * efficiency

def _compute_base_value(self, state: WorldState, game_data: GameData) -> float:
    # ... move the existing body of value() here verbatim
```

The refactor preserves the existing `value()` body — just moved into `_compute_base_value` and called from the new `value()`.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/gathering.py tests/test_ai/test_goals.py
git commit -m "feat(ai): GatherMaterialsGoal.value applies cycles-to-satisfy efficiency modifier"
```

---

### Phase F-E Validation Gate

```bash
uv run pytest tests/test_ai/ -q --tb=no
uv run mypy src/artifactsmmo_cli/ai/
```

---

# Phase F-F — Player wiring + CLI

---

## Task F-F1: GamePlayer accepts history parameter

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Modify: `tests/test_ai/test_player.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_player.py`:

```python
def test_game_player_accepts_history_kwarg():
    """GamePlayer must accept history: LearningStore | None."""
    from artifactsmmo_cli.ai.player import GamePlayer
    player = GamePlayer(character="testchar", history=None)
    assert player.history is None


def test_game_player_default_history_is_none():
    from artifactsmmo_cli.ai.player import GamePlayer
    player = GamePlayer(character="testchar")
    assert player.history is None
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_player.py::test_game_player_accepts_history_kwarg tests/test_ai/test_player.py::test_game_player_default_history_is_none -v
```

Expected: FAIL.

- [ ] **Step 3: Update GamePlayer**

In `src/artifactsmmo_cli/ai/player.py`, add import:

```python
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Update `__init__`:

```python
def __init__(
    self,
    character: str,
    verbose: bool = False,
    dry_run: bool = False,
    tracer: Tracer | None = None,
    history: LearningStore | None = None,
) -> None:
    # ... existing assignments unchanged ...
    self.history = history
```

Update goal selection / planner-call sites in `run()` to pass `self.history`:

```python
goals.sort(
    key=lambda g: g.priority(self.state, self.game_data, self.history),
    reverse=True,
)
for goal in goals:
    if goal.priority(self.state, self.game_data, self.history) <= 0:
        break
    plan = self.planner.plan(self.state, goal, actions, self.game_data, self.history)
```

Also update any verbose-output blocks that call `g.priority(self.state, self.game_data)` to include `self.history`.

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_player.py tests/test_ai/test_player_run.py -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(ai): GamePlayer accepts history parameter and threads through to goals/planner"
```

---

## Task F-F2: Compute deltas and record_cycle helper

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Create: `tests/test_ai/test_player_learning.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_player_learning.py`:

```python
"""Integration: GamePlayer + LearningStore."""

import os
import tempfile

import pytest
from sqlmodel import Session as SqlSession, select

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_player_records_cycle_with_deltas(tmp_db_path):
    store = LearningStore(db_path=tmp_db_path, character="testchar")
    store.start_session()

    player = GamePlayer(character="testchar", history=store)
    player.game_data = GameData()
    prev_state = make_state(gold=50, xp=100, hp=80, inventory_used=10)
    new_state = make_state(gold=55, xp=110, hp=85, inventory_used=12)
    player._record_learning_cycle(
        prev_state=prev_state,
        new_state=new_state,
        action_repr="Fight(yellow_slime)",
        action_class="FightAction",
        outcome="ok",
        selected_goal="FarmMonster(yellow_slime)",
        predicted_cost=10.0,
        actual_cooldown_seconds=11.5,
        planner_nodes=5, planner_depth=2,
        planner_timed_out=False, plan_len=1,
    )

    with SqlSession(store._engine) as s:
        rows = list(s.exec(select(Cycle)))
    store.close()

    assert len(rows) == 1
    r = rows[0]
    assert r.action_repr == "Fight(yellow_slime)"
    assert r.outcome == "ok"
    assert r.delta_gold == 5
    assert r.delta_xp == 10
    assert r.delta_hp == 5
    assert r.delta_inv_used == 2
    assert r.actual_cooldown_seconds == 11.5


def test_player_no_history_does_not_write(tmp_db_path):
    player = GamePlayer(character="testchar", history=None)
    player.game_data = GameData()
    player._record_learning_cycle(
        prev_state=make_state(),
        new_state=make_state(),
        action_repr="X", action_class="X", outcome="ok",
        selected_goal="G", predicted_cost=0.0, actual_cooldown_seconds=0.0,
        planner_nodes=0, planner_depth=0, planner_timed_out=False, plan_len=0,
    )
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_player_learning.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implement helper**

In `src/artifactsmmo_cli/ai/player.py`, add imports (hoist `json` to top, ensure `datetime`/`timezone` already imported):

```python
import json
from artifactsmmo_cli.ai.learning.models import Cycle
```

Add method to `GamePlayer`:

```python
    def _record_learning_cycle(
        self,
        prev_state: WorldState,
        new_state: WorldState,
        action_repr: str,
        action_class: str,
        outcome: str,
        selected_goal: str,
        predicted_cost: float,
        actual_cooldown_seconds: float,
        planner_nodes: int,
        planner_depth: int,
        planner_timed_out: bool,
        plan_len: int,
        cycles_to_satisfy: int | None = None,
    ) -> None:
        """Build a Cycle row and persist via LearningStore. No-op when history is None."""
        if self.history is None:
            return
        drops = self._compute_drops(prev_state, new_state)
        cycle = Cycle(
            ts=datetime.now(tz=timezone.utc).isoformat(),
            session_id="placeholder",
            cycle_index=getattr(self, "_cycle_counter", 0),
            character=self.character,
            x=new_state.x, y=new_state.y,
            hp=new_state.hp, max_hp=new_state.max_hp,
            gold=new_state.gold, level=new_state.level, xp=new_state.xp,
            inventory_used=new_state.inventory_used,
            inventory_max=new_state.inventory_max,
            bank_accessible=self._bank_accessible,
            task_code=new_state.task_code, task_type=new_state.task_type,
            task_progress=new_state.task_progress, task_total=new_state.task_total,
            selected_goal=selected_goal,
            action_repr=action_repr,
            action_class=action_class,
            outcome=outcome,
            predicted_cost=predicted_cost,
            actual_cooldown_seconds=actual_cooldown_seconds,
            planner_nodes=planner_nodes, planner_depth=planner_depth,
            planner_timed_out=planner_timed_out, plan_len=plan_len,
            delta_gold=new_state.gold - prev_state.gold,
            delta_xp=new_state.xp - prev_state.xp,
            delta_hp=new_state.hp - prev_state.hp,
            delta_inv_used=new_state.inventory_used - prev_state.inventory_used,
            drops_json=json.dumps(drops) if drops else None,
            cycles_to_satisfy=cycles_to_satisfy,
        )
        self.history.record_cycle(cycle)

    @staticmethod
    def _compute_drops(prev_state: WorldState, new_state: WorldState) -> dict[str, int]:
        """Items that appeared (positive deltas only)."""
        drops: dict[str, int] = {}
        for code, qty in new_state.inventory.items():
            prev_qty = prev_state.inventory.get(code, 0)
            if qty > prev_qty:
                drops[code] = qty - prev_qty
        return drops
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_player_learning.py -q
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_learning.py
git commit -m "feat(ai): GamePlayer._record_learning_cycle computes deltas and writes to LearningStore"
```

---

## Task F-F3: Wire _record_learning_cycle into run() main loop

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`

- [ ] **Step 1: Identify integration points**

The `run()` loop already records cycles to `StuckDetector` and emits trace records. Learning store call goes alongside. Two paths:

1. **Successful action path**: after `action.execute()`, before next iteration.
2. **No-plan path**: after the no-plan branch logs the cycle to detector/tracer.

For successful: capture `prev_state = self.state` BEFORE execute. After execute, compute `actual_cooldown_seconds = (new_state.cooldown_expires - now).total_seconds()`. Compute `predicted = action.cost(prev_state, self.game_data, self.history)`. Then call `_record_learning_cycle(...)`.

- [ ] **Step 2: Wire it in**

Read the current `run()` carefully. Find the existing `action.execute()` call site. Insert:

```python
            prev_state_for_learning = self.state
            new_state = ...  # result of action.execute / dry_run apply
            now = datetime.now(tz=timezone.utc)
            cooldown_remaining = 0.0
            if new_state.cooldown_expires is not None:
                cooldown_remaining = max(0.0, (new_state.cooldown_expires - now).total_seconds())
            predicted = action.cost(prev_state_for_learning, self.game_data, self.history)
            self._record_learning_cycle(
                prev_state=prev_state_for_learning,
                new_state=new_state,
                action_repr=repr(action),
                action_class=type(action).__name__,
                outcome="ok",
                selected_goal=repr(selected_goal),
                predicted_cost=predicted,
                actual_cooldown_seconds=cooldown_remaining,
                planner_nodes=self.planner.last_stats.nodes_explored,
                planner_depth=self.planner.last_stats.max_depth_reached,
                planner_timed_out=self.planner.last_stats.timed_out,
                plan_len=len(plan),
            )
            self.state = new_state
```

For the no-plan path: similar but with `outcome="no_plan"`, `action_repr="<no_plan>"`, `prev_state=new_state=self.state`.

- [ ] **Step 3: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: green (existing tests don't pass a history; new code paths are no-op).

- [ ] **Step 4: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py
git commit -m "feat(ai): wire _record_learning_cycle into run() main loop"
```

---

## Task F-F4: Track goal first-selected for cycles_to_satisfy

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Modify: `tests/test_ai/test_player_learning.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_ai/test_player_learning.py`:

```python
def test_goal_cycles_to_satisfy_tracked():
    player = GamePlayer(character="testchar", history=None)
    player.game_data = GameData()
    player._note_goal_selection("G1", cycle_index=0)
    assert player._goal_first_selected_at == {"G1": 0}
    player._note_goal_selection("G1", cycle_index=1)
    assert player._goal_first_selected_at == {"G1": 0}
    cycles = player._compute_cycles_to_satisfy("G1", current_cycle=5)
    assert cycles == 5
    assert "G1" not in player._goal_first_selected_at
    player._note_goal_selection("G1", cycle_index=6)
    assert player._goal_first_selected_at["G1"] == 6
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_player_learning.py::test_goal_cycles_to_satisfy_tracked -v
```

Expected: FAIL.

- [ ] **Step 3: Implement helpers**

In `__init__`:

```python
        self._goal_first_selected_at: dict[str, int] = {}
```

Add methods:

```python
    def _note_goal_selection(self, goal_repr: str, cycle_index: int) -> None:
        """Record when a goal was first selected. Idempotent."""
        if goal_repr not in self._goal_first_selected_at:
            self._goal_first_selected_at[goal_repr] = cycle_index

    def _compute_cycles_to_satisfy(self, goal_repr: str, current_cycle: int) -> int | None:
        """Return cycles since first selection, then clear the entry. None if never selected."""
        first = self._goal_first_selected_at.pop(goal_repr, None)
        if first is None:
            return None
        return current_cycle - first
```

- [ ] **Step 4: Wire into run()**

After selecting a goal: `self._note_goal_selection(repr(selected_goal), cycle_index=self._cycle_counter)`.

In the successful-action path, extend the `_record_learning_cycle` call:

```python
            cycles_to_satisfy = None
            if selected_goal.is_satisfied(new_state):
                cycles_to_satisfy = self._compute_cycles_to_satisfy(repr(selected_goal), self._cycle_counter)
            self._record_learning_cycle(
                # ... existing args ...
                cycles_to_satisfy=cycles_to_satisfy,
            )
```

- [ ] **Step 5: Run tests**

```bash
uv run pytest tests/test_ai/ -q --tb=no
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player_learning.py
git commit -m "feat(ai): track goal first-selected timestamps for cycles_to_satisfy"
```

---

## Task F-F5: CLI --learn / --learn-db flags

**Files:**
- Modify: `src/artifactsmmo_cli/commands/play.py`
- Create: `tests/test_ai/test_cli_learn.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_ai/test_cli_learn.py`:

```python
"""End-to-end smoke for --learn flag plumbing."""

import subprocess


def test_default_learn_db_path_format():
    from artifactsmmo_cli.commands.play import default_learn_db_path
    path = default_learn_db_path()
    assert path.endswith("learning.db")
    assert "artifactsmmo" in path


def test_play_help_shows_learn_flags():
    result = subprocess.run(
        ["uv", "run", "artifactsmmo", "play", "play", "--help"],
        capture_output=True, text=True, timeout=30,
    )
    assert "--learn" in result.stdout
    assert "--learn-db" in result.stdout
```

- [ ] **Step 2: Verify fail**

```bash
uv run pytest tests/test_ai/test_cli_learn.py -v
```

Expected: FAIL.

- [ ] **Step 3: Add CLI flags**

In `src/artifactsmmo_cli/commands/play.py`:

Add imports at top:

```python
from pathlib import Path
from artifactsmmo_cli.ai.learning.store import LearningStore
```

Add helper:

```python
def default_learn_db_path() -> str:
    """Return ~/.cache/artifactsmmo/learning.db (parent dirs created on first use)."""
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")
```

Update `play` command — keep existing args, add `learn` and `learn_db`, wire `LearningStore` lifecycle:

```python
@app.command("play")
def play(
    character: str = typer.Argument(..., help="Character name to play"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    trace: bool = typer.Option(False, "--trace"),
    trace_file: str | None = typer.Option(None, "--trace-file"),
    learn: bool = typer.Option(False, "--learn",
                                help="Read/write learned stats to SQLite for autoregressive planning"),
    learn_db: str | None = typer.Option(None, "--learn-db",
                                         help="Learning DB path (default: ~/.cache/artifactsmmo/learning.db)"),
) -> None:
    """Run the autonomous GOAP AI player for one character."""
    # ... existing tracer setup ...

    store: LearningStore | None = None
    if learn:
        db_path = learn_db or default_learn_db_path()
        store = LearningStore(db_path=db_path, character=character)
        store.start_session()
        print(f"Learning enabled — DB at {db_path}")

    player = GamePlayer(
        character=character, verbose=verbose, dry_run=dry_run,
        tracer=tracer, history=store,
    )
    try:
        player.run()
    finally:
        if store is not None:
            store.end_session(exit_reason="normal")
            store.close()
```

- [ ] **Step 4: Run tests**

```bash
uv run pytest tests/test_ai/test_cli_learn.py -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/commands/play.py tests/test_ai/test_cli_learn.py
git commit -m "feat(cli): add --learn and --learn-db flags wired to LearningStore lifecycle"
```

---

### Phase F-F Validation Gate

```bash
uv run pytest tests/test_ai/ -q --tb=no
uv run mypy src/artifactsmmo_cli/ai/ src/artifactsmmo_cli/commands/
```

**Manual smoke:**

```bash
uv run artifactsmmo play play <character> --learn --learn-db /tmp/test_learn.db --dry-run --verbose 2>&1 | head -10
```

Then inspect the DB:

```bash
uv run python -c "
from sqlalchemy import create_engine
from sqlmodel import Session, select
from artifactsmmo_cli.ai.learning.models import Cycle, Session as SessRow
engine = create_engine('sqlite:////tmp/test_learn.db')
with Session(engine) as s:
    sessions = list(s.exec(select(SessRow)))
    cycles = list(s.exec(select(Cycle)))
    print(f'sessions: {len(sessions)}, cycles: {len(cycles)}')
    if cycles:
        c = cycles[0]
        print(f'first cycle: action={c.action_repr}, outcome={c.outcome}, delta_gold={c.delta_gold}')
"
```

Expected: `sessions: 1, cycles: N` with N > 0.

---

# Final Validation

After all phases:

- [ ] `uv run pytest -q` — full project suite green
- [ ] `uv run mypy src/artifactsmmo_cli/ai/ src/artifactsmmo_cli/ai/learning/` — clean
- [ ] `uv run pytest tests/test_ai/ --cov=src/artifactsmmo_cli/ai --cov-report=term -q | tail -3` — AI coverage ≥ 98%
- [ ] Manual `uv run artifactsmmo play play <char> --learn --learn-db /tmp/final.db --dry-run` — DB created, sessions + cycles populated, delta_* fields meaningful

After Robby runs with `--learn` for an extended session, autoregressive feedback surfaces: actions with poor empirical cost/success get penalised; goals with slow satisfaction get scaled down.
