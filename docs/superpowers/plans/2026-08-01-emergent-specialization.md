# Emergent Specialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the characters of a `play --all` run take exclusive named roles, publish what they need to a shared board, and produce for each other through the bank, so duplicated gathering stops burning the per-IP rate budget.

**Architecture:** Coordination rides the `learning.db` SQLite file every child already opens (`--learn-db`, WAL). A new `CoordinationStore` owns two new tables and is the only place in the codebase that reads without a `character` filter. A character claims a role under a UNIQUE-constrained lease with a TTL heartbeat, publishes its unmet closure demand each cycle, and serves the top unmet sibling demand through a new `SupplyBankGoal`. A fifth ranking factor, `role_alignment`, then biases which gear chain a role-holder pursues.

**Tech Stack:** Python 3.13, `uv`, SQLModel/SQLAlchemy over SQLite (WAL), pytest, Lean 4 (`formal/`), mypy, ruff.

## Global Constraints

Copied from `AGENTS.md`/`CLAUDE.md`; every task's requirements implicitly include these.

- ALWAYS prefix Python commands with `uv run` (e.g. `uv run pytest`, `uv run mypy`).
- DO NOT use inline imports. All imports at the top of the file.
- ONE CLASS PER FILE for behavioral classes. Cohesive groups of pure data/schema/enum declarations may share a module (this is why both new SQLModel tables go in the existing `ai/learning/models.py`).
- NEVER use `if TYPE_CHECKING`.
- NEVER use triple-dot relative imports. Absolute imports only.
- **NEVER catch `Exception`.** Catch the specific class only (`SQLAlchemyError`, `IntegrityError`).
- Multiple levels of error handling is always a bug — each failure is handled at exactly one level.
- Use only API data or fail with an error. No invented defaults.
- All tests live in `tests/`. Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- DO NOT create multiple implementations. Fix in place.

**Constants fixed by the spec** (use these exact values):

- `LEASE_TTL_SECONDS = 600`
- `ROLE_MIN_HOLD_CYCLES = 100`
- `ROLE_SWITCH_MARGIN = Fraction(2)`
- `DEMAND_TTL_SECONDS = 600`
- `SUPPLY_PRIORITY_FLOOR = 30.0`, `SUPPLY_PRIORITY_CEILING = 50.0`

**Spec corrections** (already applied to the spec file in the same commit as this plan — noted here because the spec's own wording is what an implementer would otherwise search for):

- The spec calls the ranking function `weighted_candidates`. It does not exist. The real functions are `_scaled_weights`, `focus_aging_pick` and `focus_aging_order` in `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py`.
- The spec says the Lean `MeansKind` list goes "17 -> 18". The Python `MeansKind` enum has **15** variants and becomes **16**. The Lean `Formal.Liveness.MeansKind` inductive is the *combined* guard + collect + objective + discretionary ladder, not a mirror of the Python enum; its `allInLadderOrder` gains one entry. The "17-element" figure is a stale comment in the `ProductionLadder.lean` header.

## File Structure

**Created:**

| path | responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/learning/coordination_store.py` | `CoordinationStore` — the only cross-character reader. Claim/renew/release leases; publish/read demand. |
| `src/artifactsmmo_cli/ai/role_catalog.py` | `Role` dataclass + `ROLE_CATALOG` + `validate_catalog`. Skills drawn from `skill_classes` derived sets. |
| `src/artifactsmmo_cli/ai/role_selection.py` | Pure: `decide_role` -> keep / claim / release. Owns dwell, margin, release-on-idle. |
| `src/artifactsmmo_cli/ai/role_alignment.py` | Pure: `role_alignment_map` -> `{(slot, code): Fraction}`. |
| `src/artifactsmmo_cli/ai/goals/supply_bank.py` | `SupplyBankGoal`. |
| `tests/test_ai/test_coordination_store.py` | Store unit + real multi-process race test. |
| `tests/test_ai/test_role_catalog.py` | Catalog validation. |
| `tests/test_ai/test_role_selection.py` | Hysteresis logic. |
| `tests/test_ai/test_role_alignment.py` | Alignment multipliers + inert sentinel. |
| `tests/test_ai/test_supply_bank_goal.py` | Goal behaviour + priority band. |

**Modified:**

| path | change |
|---|---|
| `src/artifactsmmo_cli/ai/learning/models.py` | Add `RoleLease`, `MaterialDemand` tables. |
| `src/artifactsmmo_cli/ai/tiers/means.py` | Append `MeansKind.SUPPLY_BANK`; slot into `DISCRETIONARY_ORDER`; add `_fires` branch. |
| `src/artifactsmmo_cli/ai/tiers/decide_key.py` | Add `_MEANS_REPR[MeansKind.SUPPLY_BANK]`. |
| `src/artifactsmmo_cli/ai/strategy_driver.py` | Add `map_means` branch. |
| `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py` | Add `_NO_ROLE` and the fifth factor to `_scaled_weights` / `focus_aging_pick` / `focus_aging_order`. |
| `src/artifactsmmo_cli/ai/tiers/progression_tree.py` | Build the role map; thread it; extend the fast-path inertness guard. |
| `src/artifactsmmo_cli/ai/player.py` | Construct `CoordinationStore`; per-cycle coordination block. |
| `src/artifactsmmo_cli/ai/cycle_snapshot.py` | Add `role` and `served_demand` trace fields. |
| `formal/Formal/Liveness/MeansKind.lean` | Add `supplyBank`; extend `allInLadderOrder`. |
| `formal/Formal/Liveness/ProductionLadder.lean` | Add `supplyBankFires`; re-discharge ladder proofs; fix the stale "17-element" header. |
| `formal/Formal/DecideKey.lean` | Add `goalReprOfMeans .supplyBank`. |
| `formal/diff/test_decide_key_diff.py` | Add to `_MEANS_INDEX`. |
| `tests/test_ai/test_decide_key.py` | Covered by the existing all-variants round-trip; no edit expected — verify. |
| `docs/superpowers/specs/2026-07-31-emergent-specialization-design.md` | Append the measured before/after duplicate-gather numbers (Task 14). |

**Phase boundaries.** Tasks 1-12 deliver throughput and are independently shippable: characters take roles, publish demand, supply each other, and Task 12 proves on a live run that they actually did. Tasks 13-14 add the `role_alignment` ranking factor. Stop after Task 12 and ship if you want the throughput win before the ranking change.

---

### Task 1: Coordination tables

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/models.py` (append after `LearnedSetting`, ~line 158)
- Test: `tests/test_ai/test_coordination_store.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `RoleLease(role: str, character: str, claimed_at: str, expires_at: str)` and `MaterialDemand(character: str, item_code: str, quantity: int, expires_at: str)`, both SQLModel tables with `id: int | None` primary keys. `RoleLease.role` is UNIQUE.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_coordination_store.py
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine

from artifactsmmo_cli.ai.learning.models import MaterialDemand, RoleLease


@pytest.fixture(name="engine")
def _engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coord.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def test_role_is_unique(engine) -> None:
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="HAL",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        s.add(RoleLease(role="miner", character="C3P0",
                        claimed_at="2026-08-01T00:00:00+00:00",
                        expires_at="2026-08-01T00:10:00+00:00"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_material_demand_roundtrip(engine) -> None:
    with SqlSession(engine) as s:
        s.add(MaterialDemand(character="HAL", item_code="copper_bar", quantity=6,
                             expires_at="2026-08-01T00:10:00+00:00"))
        s.commit()
    with SqlSession(engine) as s:
        row = s.query(MaterialDemand).one()
        assert (row.character, row.item_code, row.quantity) == ("HAL", "copper_bar", 6)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: FAIL with `ImportError: cannot import name 'RoleLease'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/learning/models.py — append after LearnedSetting


class RoleLease(SQLModel, table=True):
    """Exclusive claim on a specialization role, held by one character at a
    time. `role` is UNIQUE, so a concurrent double-claim raises IntegrityError
    in exactly one place (CoordinationStore.claim) and the loser re-reads —
    which doubles as the cold-start allocator (no tiebreak rule needed).

    `expires_at` is the single liveness rule in the coordination system: a row
    is real if unexpired. A crashed child stops renewing and its lease
    evaporates without supervisor involvement."""

    __tablename__ = "role_leases"

    id: int | None = Field(default=None, primary_key=True)
    role: str = Field(index=True, unique=True)
    character: str = Field(index=True)
    claimed_at: str
    expires_at: str


class MaterialDemand(SQLModel, table=True):
    """One character's declared unmet need for one item. Upsert key is
    (character, item_code). Carries the same `expires_at` liveness rule as
    RoleLease so a dead character's demand stops being served on the same
    clock that frees its role."""

    __tablename__ = "material_demand"

    id: int | None = Field(default=None, primary_key=True)
    character: str = Field(index=True)
    item_code: str = Field(index=True)
    quantity: int
    expires_at: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/models.py tests/test_ai/test_coordination_store.py
git commit -m "feat(learning): add RoleLease and MaterialDemand coordination tables"
```

---

### Task 2: CoordinationStore lease lifecycle

**Files:**
- Create: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py` (extend)

**Interfaces:**
- Consumes: `RoleLease` from Task 1.
- Produces:
  - `CoordinationStore(db_path: str, character: str)`
  - `claim(role: str, now: datetime) -> bool` — True if this character now holds `role`
  - `renew(role: str, now: datetime) -> None`
  - `release(role: str) -> None`
  - `live_leases(now: datetime) -> dict[str, str]` — `{role: character}` for unexpired rows only
  - `close() -> None`
  - module constant `LEASE_TTL_SECONDS = 600`

`now` is a parameter on every method rather than read from the clock inside, so TTL tests inject time instead of sleeping.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_coordination_store.py — append
from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.learning.coordination_store import (
    LEASE_TTL_SECONDS,
    CoordinationStore,
)

_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_claim_succeeds_then_blocks_other_character(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        assert hal.claim("miner", _T0) is True
        assert c3po.claim("miner", _T0) is False
        assert hal.live_leases(_T0) == {"miner": "HAL"}
    finally:
        hal.close()
        c3po.close()


def test_expired_lease_is_not_live_and_can_be_reclaimed(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.live_leases(later) == {}
        assert c3po.claim("miner", later) is True
        assert c3po.live_leases(later) == {"miner": "C3P0"}
    finally:
        hal.close()
        c3po.close()


def test_renew_extends_expiry(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    mid = _T0 + timedelta(seconds=LEASE_TTL_SECONDS - 1)
    later = _T0 + timedelta(seconds=LEASE_TTL_SECONDS + 1)
    try:
        assert hal.claim("miner", _T0) is True
        hal.renew("miner", mid)
        assert hal.live_leases(later) == {"miner": "HAL"}
    finally:
        hal.close()


def test_release_frees_the_role(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        hal.release("miner")
        assert hal.live_leases(_T0) == {}
    finally:
        hal.close()


def test_reclaiming_own_live_lease_is_idempotent(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    try:
        assert hal.claim("miner", _T0) is True
        assert hal.claim("miner", _T0) is True
    finally:
        hal.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.learning.coordination_store'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/learning/coordination_store.py
"""Cross-character coordination over the shared learning DB.

`LearningStore` is single-character by construction: every read filters
`character == self._character`, and that invariant is load-bearing (learned
action costs and success rates must not blend across characters at different
levels with different gear). This class is the ONLY place in the codebase that
queries the coordination tables without a character filter, so the
"reads siblings" surface stays auditable in one file.

Opens the SAME sqlite file `LearningStore` does (children all receive one
`--learn-db` path from `MultiRun._child_argv`), with the same WAL settings.

Every method takes `now` rather than reading the clock, so TTL behaviour is
tested by injecting time instead of sleeping.

Best-effort, matching `LearningStore`'s contract: a `SQLAlchemyError` degrades
to the empty view (no siblings), which is present-day single-character
behaviour. Handled here and NOT re-handled upstream.
"""

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine, select

from artifactsmmo_cli.ai.learning.models import RoleLease

LEASE_TTL_SECONDS = 600
"""Seconds a lease survives without renewal. Renewed every cycle, so this only
has to exceed the longest LEGITIMATE gap between cycles — not the action
cooldown, but a capped Retry-After backoff or a long planner search. Ten
minutes clears both, and costs at most ten minutes of an unworked role against
sessions that run for hours."""


class CoordinationStore:
    """Lease + demand board over the shared learning DB. Cross-character reads
    live here and nowhere else."""

    def __init__(self, db_path: str, character: str) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)
        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()
        self._character = character

    @property
    def character(self) -> str:
        return self._character

    def _expiry(self, now: datetime) -> str:
        return (now + timedelta(seconds=LEASE_TTL_SECONDS)).isoformat()

    def claim(self, role: str, now: datetime) -> bool:
        """Take `role` if it is unheld or its lease has expired.

        Returns True when this character holds it afterwards. The UNIQUE
        constraint on `role` resolves the concurrent-claim race: the loser
        takes IntegrityError HERE, returns False, and picks another role next
        cycle. This is also the cold-start allocator — five children that all
        pick the same top-demand role serialize into distinct roles over
        successive rounds, so no tiebreak rule is needed."""
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(select(RoleLease).where(RoleLease.role == role)).first()
                if row is not None:
                    if row.character != self._character and row.expires_at > stamp:
                        return False
                    row.character = self._character
                    row.claimed_at = stamp
                    row.expires_at = self._expiry(now)
                    s.add(row)
                else:
                    s.add(RoleLease(role=role, character=self._character,
                                    claimed_at=stamp, expires_at=self._expiry(now)))
                s.commit()
                return True
        except IntegrityError:
            return False
        except SQLAlchemyError as e:
            print(f"[coordination] claim failed: {e}")
            return False

    def renew(self, role: str, now: datetime) -> None:
        """Extend this character's lease on `role`. No-op if it holds none."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(RoleLease).where(
                        RoleLease.role == role,
                        RoleLease.character == self._character,
                    )
                ).first()
                if row is None:
                    return
                row.expires_at = self._expiry(now)
                s.add(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] renew failed: {e}")

    def release(self, role: str) -> None:
        """Drop this character's lease on `role`. No-op if it holds none."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(RoleLease).where(
                        RoleLease.role == role,
                        RoleLease.character == self._character,
                    )
                ).first()
                if row is None:
                    return
                s.delete(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] release failed: {e}")

    def live_leases(self, now: datetime) -> dict[str, str]:
        """`{role: character}` over UNEXPIRED leases only, across ALL
        characters. One of the two deliberately unfiltered reads."""
        stamp = now.isoformat()
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(select(RoleLease).where(RoleLease.expires_at > stamp)).all()
                return {r.role: r.character for r in rows}
        except SQLAlchemyError as e:
            print(f"[coordination] live_leases failed: {e}")
            return {}

    def close(self) -> None:
        self._engine.dispose()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/coordination_store.py tests/test_ai/test_coordination_store.py
git commit -m "feat(learning): add CoordinationStore lease lifecycle with TTL"
```

---

### Task 3: Multi-process claim race

The claim race is the one behaviour that mocks cannot verify. `CharacterSupervisor` is already tested over a real subprocess; this follows that precedent with real processes against one temp DB.

**Files:**
- Test: `tests/test_ai/test_coordination_store.py` (extend)

**Interfaces:**
- Consumes: `CoordinationStore.claim` from Task 2.
- Produces: nothing new.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_coordination_store.py — append
import multiprocessing


def _claim_worker(db_path: str, character: str, role: str, out: object) -> None:
    """Module-level so it is picklable by multiprocessing's spawn start method."""
    store = CoordinationStore(db_path=db_path, character=character)
    try:
        out.put((character, store.claim(role, _T0)))
    finally:
        store.close()


def test_exactly_one_process_wins_a_contested_role(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    seed = CoordinationStore(db_path=db, character="seed")
    seed.close()  # create the schema before the children race on it

    ctx = multiprocessing.get_context("spawn")
    queue = ctx.Queue()
    names = ["HAL", "C3P0", "R2D2", "Robby", "KITT"]
    procs = [ctx.Process(target=_claim_worker, args=(db, n, "miner", queue)) for n in names]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
        assert p.exitcode == 0

    results = dict(queue.get() for _ in names)
    winners = [n for n, won in results.items() if won]
    assert len(winners) == 1

    check = CoordinationStore(db_path=db, character="observer")
    try:
        assert check.live_leases(_T0) == {"miner": winners[0]}
    finally:
        check.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_coordination_store.py::test_exactly_one_process_wins_a_contested_role -v`
Expected: FAIL — without a busy timeout, concurrent writers raise `sqlite3.OperationalError: database is locked` and at least one child exits non-zero.

- [ ] **Step 3: Write minimal implementation**

Add a busy timeout so a contending writer waits for the write lock instead of erroring out. In `CoordinationStore.__init__`, replace the `create_engine` line:

```python
        self._engine = create_engine(
            f"sqlite:///{db_path}",
            connect_args={"timeout": 30},
        )
```

and add to the PRAGMA block, after `synchronous`:

```python
            conn.execute(text("PRAGMA busy_timeout=30000"))
```

Document why, above `__init__`'s PRAGMA block:

```python
        # busy_timeout: five children claim concurrently on startup. Without it
        # a contending writer raises OperationalError("database is locked")
        # rather than waiting for the write lock, which would turn the
        # cold-start allocator into a crash. 30s >> the sub-millisecond
        # transactions this store issues.
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/coordination_store.py tests/test_ai/test_coordination_store.py
git commit -m "test(learning): prove exactly one process wins a contested role"
```

---

### Task 4: Demand board

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/coordination_store.py`
- Test: `tests/test_ai/test_coordination_store.py` (extend)

**Interfaces:**
- Consumes: `MaterialDemand` (Task 1), `CoordinationStore` (Task 2).
- Produces:
  - `publish_demand(demand: Mapping[str, int], now: datetime) -> None` — replaces this character's rows wholesale
  - `sibling_demand(now: datetime) -> dict[str, int]` — unexpired demand summed by item, EXCLUDING this character
  - module constant `DEMAND_TTL_SECONDS = 600`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_coordination_store.py — append
from artifactsmmo_cli.ai.learning.coordination_store import DEMAND_TTL_SECONDS


def test_sibling_demand_sums_across_characters_and_excludes_self(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        hal.publish_demand({"copper_bar": 6, "ash_plank": 2}, _T0)
        c3po.publish_demand({"copper_bar": 4}, _T0)
        assert hal.sibling_demand(_T0) == {"copper_bar": 4}
        assert c3po.sibling_demand(_T0) == {"copper_bar": 6, "ash_plank": 2}
    finally:
        hal.close()
        c3po.close()


def test_publish_demand_replaces_prior_rows(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": 6, "ash_plank": 2}, _T0)
        hal.publish_demand({"copper_bar": 1}, _T0)
        assert obs.sibling_demand(_T0) == {"copper_bar": 1}
    finally:
        hal.close()
        obs.close()


def test_expired_demand_is_not_served(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    later = _T0 + timedelta(seconds=DEMAND_TTL_SECONDS + 1)
    try:
        hal.publish_demand({"copper_bar": 6}, _T0)
        assert obs.sibling_demand(later) == {}
    finally:
        hal.close()
        obs.close()


def test_empty_demand_clears_the_board(tmp_path: Path) -> None:
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    obs = CoordinationStore(db_path=db, character="observer")
    try:
        hal.publish_demand({"copper_bar": 6}, _T0)
        hal.publish_demand({}, _T0)
        assert obs.sibling_demand(_T0) == {}
    finally:
        hal.close()
        obs.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: FAIL with `ImportError: cannot import name 'DEMAND_TTL_SECONDS'`

- [ ] **Step 3: Write minimal implementation**

Add the import of `MaterialDemand` and `Mapping` at the top of `coordination_store.py`:

```python
from collections.abc import Mapping
```

and extend the models import:

```python
from artifactsmmo_cli.ai.learning.models import MaterialDemand, RoleLease
```

Add the constant beside `LEASE_TTL_SECONDS`:

```python
DEMAND_TTL_SECONDS = 600
"""Seconds a published demand row survives without republication. Same clock as
LEASE_TTL_SECONDS on purpose: a crashed character's demand stops being served
at the same moment its role frees up, so there is exactly ONE liveness rule in
the coordination system."""
```

Add the methods to `CoordinationStore`:

```python
    def _demand_expiry(self, now: datetime) -> str:
        return (now + timedelta(seconds=DEMAND_TTL_SECONDS)).isoformat()

    def publish_demand(self, demand: Mapping[str, int], now: datetime) -> None:
        """Replace this character's demand rows wholesale.

        Replace rather than merge: demand is a snapshot of what is unmet RIGHT
        NOW, so an item that dropped off the closure must stop being served
        immediately. Merging would leave satisfied demand on the board until
        its TTL, and siblings would keep producing into a bank nobody drains."""
        expiry = self._demand_expiry(now)
        try:
            with SqlSession(self._engine) as s:
                stale = s.exec(
                    select(MaterialDemand).where(
                        MaterialDemand.character == self._character
                    )
                ).all()
                for row in stale:
                    s.delete(row)
                for item_code, quantity in demand.items():
                    if quantity > 0:
                        s.add(MaterialDemand(character=self._character,
                                             item_code=item_code,
                                             quantity=quantity,
                                             expires_at=expiry))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[coordination] publish_demand failed: {e}")

    def sibling_demand(self, now: datetime) -> dict[str, int]:
        """Unexpired demand summed by item across every OTHER character. The
        second of the two deliberately unfiltered reads."""
        stamp = now.isoformat()
        totals: dict[str, int] = {}
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(
                    select(MaterialDemand).where(
                        MaterialDemand.expires_at > stamp,
                        MaterialDemand.character != self._character,
                    )
                ).all()
        except SQLAlchemyError as e:
            print(f"[coordination] sibling_demand failed: {e}")
            return {}
        for row in rows:
            totals[row.item_code] = totals.get(row.item_code, 0) + row.quantity
        return totals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_coordination_store.py -v`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/learning/coordination_store.py tests/test_ai/test_coordination_store.py
git commit -m "feat(learning): add the cross-character material demand board"
```

---

### Task 5: Role catalog

**Files:**
- Create: `src/artifactsmmo_cli/ai/role_catalog.py`
- Test: `tests/test_ai/test_role_catalog.py`

**Interfaces:**
- Consumes: `GATHER_SKILLS`, `COMBAT_CRAFT_SKILLS`, `CONSUMABLE_CRAFT_SKILLS` from `ai/tiers/skill_classes.py`.
- Produces:
  - `Role` frozen dataclass with `name: str`, `gather: str | None`, `craft: str`
  - `ROLE_CATALOG: tuple[Role, ...]`
  - `validate_catalog(catalog: tuple[Role, ...]) -> None` — raises `ValueError` on a skill outside the API-derived sets
  - `role_skills(role: Role) -> frozenset[str]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_role_catalog.py
import pytest

from artifactsmmo_cli.ai.role_catalog import (
    ROLE_CATALOG,
    Role,
    role_skills,
    validate_catalog,
)
from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)


def test_shipped_catalog_validates() -> None:
    validate_catalog(ROLE_CATALOG)


def test_catalog_covers_every_api_skill_exactly_once() -> None:
    every = GATHER_SKILLS | COMBAT_CRAFT_SKILLS | CONSUMABLE_CRAFT_SKILLS
    owned: list[str] = []
    for role in ROLE_CATALOG:
        owned.extend(sorted(role_skills(role)))
    assert set(owned) == every
    assert len(owned) == len(set(owned)), "a skill is owned by two roles"


def test_role_names_are_unique() -> None:
    names = [r.name for r in ROLE_CATALOG]
    assert len(names) == len(set(names))


def test_unknown_gather_skill_is_rejected() -> None:
    bad = (Role(name="ghost", gather="mythweaving", craft="weaponcrafting"),)
    with pytest.raises(ValueError, match="mythweaving"):
        validate_catalog(bad)


def test_unknown_craft_skill_is_rejected() -> None:
    bad = (Role(name="ghost", gather="mining", craft="mythsmithing"),)
    with pytest.raises(ValueError, match="mythsmithing"):
        validate_catalog(bad)


def test_gatherless_role_is_allowed() -> None:
    validate_catalog((Role(name="jeweler", gather=None, craft="jewelrycrafting"),))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_role_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.role_catalog'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/role_catalog.py
"""Named specialization roles.

A role is a STRATEGY declaration, the same category of thing as
`loadout_profiles` — not a classification derived from API data, so the
"generic over API taxonomy, never hardcoded" rule (which governs item keep/junk
classification) does not apply. What DOES apply is that a role must not name a
skill the server lacks: `validate_catalog` checks every declared skill against
the api-client-derived sets in `tiers/skill_classes.py` and raises rather than
silently no-opping, per "use only API data or fail with an error".

`skill_classes` derives GATHER_SKILLS / COMBAT_CRAFT_SKILLS /
CONSUMABLE_CRAFT_SKILLS from the `CraftSkill` / `GatheringSkill` enums by set
algebra over a single policy seed, specifically so they cannot drift from the
schema. This module's only hand-authored content is the PAIRING of those
skills into roles.

Verified against the api-client enums 2026-08-01:
  GatheringSkill = {alchemy, fishing, mining, woodcutting}
  CraftSkill     = {alchemy, cooking, gearcrafting, jewelrycrafting, mining,
                    weaponcrafting, woodcutting}
so GATHER_SKILLS = {fishing, mining, woodcutting} (alchemy both gathers and
brews and is valued as consumable-craft), COMBAT_CRAFT_SKILLS =
{gearcrafting, jewelrycrafting, weaponcrafting}, CONSUMABLE_CRAFT_SKILLS =
{alchemy, cooking}.

`mining` and `woodcutting` appear in BOTH enums — they cover extraction and the
first processing step alike — so `miner` owning `mining` covers ore through
bar, and `logger` owning `woodcutting` covers log through plank.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)


@dataclass(frozen=True)
class Role:
    """One specialization. `gather` is None for a pure-consumer role. Pure data;
    exempt from one-class-per-file."""

    name: str
    gather: str | None
    craft: str


ROLE_CATALOG: tuple[Role, ...] = (
    Role(name="miner", gather="mining", craft="weaponcrafting"),
    Role(name="logger", gather="woodcutting", craft="gearcrafting"),
    Role(name="fisher", gather="fishing", craft="cooking"),
    # No gather skill: a pure consumer of banked bars. This role is the
    # clearest single signal that collusion is working — it CANNOT progress
    # without a sibling's deposit.
    Role(name="jeweler", gather=None, craft="jewelrycrafting"),
    Role(name="alchemist", gather="alchemy", craft="alchemy"),
)
"""Five roles covering all eight API skills, each owned exactly once."""


def role_skills(role: Role) -> frozenset[str]:
    """Every skill this role owns. `gather == craft` (alchemist) collapses."""
    if role.gather is None:
        return frozenset({role.craft})
    return frozenset({role.gather, role.craft})


def validate_catalog(catalog: tuple[Role, ...]) -> None:
    """Raise ValueError if any role names a skill outside the API-derived sets."""
    valid_gather = GATHER_SKILLS | CONSUMABLE_CRAFT_SKILLS
    valid_craft = COMBAT_CRAFT_SKILLS | CONSUMABLE_CRAFT_SKILLS | GATHER_SKILLS
    for role in catalog:
        if role.gather is not None and role.gather not in valid_gather:
            raise ValueError(
                f"Role {role.name!r} declares gather skill {role.gather!r}, "
                f"which is not an API gathering skill: {sorted(valid_gather)}"
            )
        if role.craft not in valid_craft:
            raise ValueError(
                f"Role {role.name!r} declares craft skill {role.craft!r}, "
                f"which is not an API craft skill: {sorted(valid_craft)}"
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_role_catalog.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/role_catalog.py tests/test_ai/test_role_catalog.py
git commit -m "feat(ai): add the API-validated specialization role catalog"
```

---

### Task 6: Role selection hysteresis

The whole correctness of the design lives in this pure function. Every hysteresis rule from the spec is here and nowhere else.

**Files:**
- Create: `src/artifactsmmo_cli/ai/role_selection.py`
- Test: `tests/test_ai/test_role_selection.py`

**Interfaces:**
- Consumes: `Role`, `ROLE_CATALOG`, `role_skills` (Task 5).
- Produces:
  - `RoleDecision` frozen dataclass: `keep: str | None`, `claim: str | None`, `release: str | None` (exactly one is non-None)
  - `decide_role(current, held_cycles, live_leases, demand_by_role, character, catalog) -> RoleDecision`
  - constants `ROLE_MIN_HOLD_CYCLES = 100`, `ROLE_SWITCH_MARGIN = Fraction(2)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_role_selection.py
from fractions import Fraction

from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import (
    ROLE_MIN_HOLD_CYCLES,
    ROLE_SWITCH_MARGIN,
    decide_role,
)

_ME = "HAL"


def _decide(current, held_cycles, leases, demand):
    return decide_role(current=current, held_cycles=held_cycles,
                       live_leases=leases, demand_by_role=demand,
                       character=_ME, catalog=ROLE_CATALOG)


def test_claims_highest_demand_role_when_holding_none() -> None:
    d = _decide(None, 0, {}, {"miner": 10, "logger": 3})
    assert (d.claim, d.keep, d.release) == ("miner", None, None)


def test_skips_roles_held_by_a_sibling() -> None:
    d = _decide(None, 0, {"miner": "C3P0"}, {"miner": 10, "logger": 3})
    assert d.claim == "logger"


def test_claims_nothing_when_every_role_is_leased() -> None:
    leases = {r.name: "C3P0" for r in ROLE_CATALOG}
    d = _decide(None, 0, leases, {"miner": 10})
    assert (d.claim, d.keep, d.release) == (None, None, None)


def test_claims_an_unleased_role_even_with_zero_demand() -> None:
    d = _decide(None, 0, {}, {})
    assert d.claim is not None


def test_keeps_current_role_before_min_hold_even_if_another_is_better() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES - 1, {"logger": _ME},
                {"logger": 1, "miner": 100})
    assert d.keep == "logger"


def test_switches_after_min_hold_when_margin_is_cleared() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME},
                {"logger": 1, "miner": 100})
    assert d.release == "logger"


def test_holds_when_margin_is_not_cleared() -> None:
    # miner is better but not MARGIN times better.
    demand = {"logger": 10, "miner": int(10 * ROLE_SWITCH_MARGIN) - 1}
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, demand)
    assert d.keep == "logger"


def test_releases_on_idle_after_min_hold_with_no_better_alternative() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, {})
    assert d.release == "logger"


def test_idle_role_is_kept_before_min_hold() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES - 1, {"logger": _ME}, {})
    assert d.keep == "logger"


def test_reclaims_when_our_lease_vanished() -> None:
    # TTL expired mid-session while we still believed we held it.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES + 5, {}, {"logger": 5})
    assert d.claim == "logger"


def test_margin_is_exactly_two() -> None:
    assert ROLE_SWITCH_MARGIN == Fraction(2)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_role_selection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.role_selection'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/role_selection.py
"""Pure hysteresis core for role claim/hold/release.

Three parameters, each defending a different failure:

  * ROLE_MIN_HOLD_CYCLES — thrash between two near-equal roles. Sized from the
    2026-07-31 traces: characters ran 519-587 cycles per session and the copper
    phase alone was ~300 gathers, so a dwell shorter than a production run
    means switching mid-supply-chain and stranding half-made goods in a bag.
  * ROLE_SWITCH_MARGIN — oscillation from noise on the demand board. A RATIO,
    not an absolute delta: demand magnitudes span orders (progression_tree_core
    documents a live gain ratio of 18100:2000), so any fixed threshold is
    either always or never met.
  * release-on-idle — the hole where a character that finishes its role keeps
    renewing a lease nobody needs. Because it renews, the TTL never fires and
    the role stays locked for the whole session.

Pure: no I/O, no clock, no classes beyond the frozen result record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.role_catalog import Role

ROLE_MIN_HOLD_CYCLES = 100
"""Cycles a role must be held before it may be voluntarily released."""

ROLE_SWITCH_MARGIN = Fraction(2)
"""A rival role must carry this multiple of the current role's unmet demand."""


@dataclass(frozen=True)
class RoleDecision:
    """Exactly one field is non-None, or all three are None (nothing to do).
    Pure data; exempt from one-class-per-file."""

    keep: str | None = None
    claim: str | None = None
    release: str | None = None


def _best_free_role(live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                    character: str, catalog: tuple[Role, ...]) -> tuple[str | None, int]:
    """Highest-demand role not leased by SOMEONE ELSE, with its demand.

    Ties are resolved by catalog order — a declared, semantic order, never a
    repr or alphabetical sort. Ties are also harmless: the UNIQUE constraint on
    RoleLease.role serializes concurrent claimants regardless."""
    best: str | None = None
    best_demand = -1
    for role in catalog:
        holder = live_leases.get(role.name)
        if holder is not None and holder != character:
            continue
        demand = demand_by_role.get(role.name, 0)
        if demand > best_demand:
            best, best_demand = role.name, demand
    return best, max(best_demand, 0)


def decide_role(current: str | None, held_cycles: int,
                live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                character: str, catalog: tuple[Role, ...]) -> RoleDecision:
    """Decide whether to keep, claim, or release a role this cycle."""
    if current is None:
        best, _ = _best_free_role(live_leases, demand_by_role, character, catalog)
        return RoleDecision(claim=best) if best is not None else RoleDecision()

    if live_leases.get(current) != character:
        # Our lease lapsed (TTL expired during a stall) or a sibling took it.
        # Re-claim rather than assume we still hold it.
        return RoleDecision(claim=current)

    if held_cycles < ROLE_MIN_HOLD_CYCLES:
        return RoleDecision(keep=current)

    own_demand = demand_by_role.get(current, 0)
    if own_demand <= 0:
        return RoleDecision(release=current)

    rival_best = -1
    for role in catalog:
        if role.name == current:
            continue
        holder = live_leases.get(role.name)
        if holder is not None and holder != character:
            continue
        rival_best = max(rival_best, demand_by_role.get(role.name, 0))

    if rival_best >= own_demand * ROLE_SWITCH_MARGIN:
        return RoleDecision(release=current)
    return RoleDecision(keep=current)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_role_selection.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/role_selection.py tests/test_ai/test_role_selection.py
git commit -m "feat(ai): add role selection hysteresis with dwell, margin and idle release"
```

---

### Task 7: Map sibling demand onto roles

`decide_role` takes demand keyed by ROLE, but `CoordinationStore.sibling_demand` returns demand keyed by ITEM. This task builds the bridge, and it is the piece that makes a role mean something concrete.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/role_selection.py`
- Test: `tests/test_ai/test_role_selection.py` (extend)

**Interfaces:**
- Consumes: `Role`, `role_skills` (Task 5); `GameData.get_item` for an item's producing skill.
- Produces: `demand_by_role(item_demand: Mapping[str, int], skill_of_item: Mapping[str, str | None], catalog: tuple[Role, ...]) -> dict[str, int]`

`skill_of_item` is passed in rather than derived, keeping this module pure and free of `GameData`. The caller (Task 9) builds it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_role_selection.py — append
from artifactsmmo_cli.ai.role_selection import demand_by_role


def test_demand_routes_to_the_role_owning_the_producing_skill() -> None:
    item_demand = {"copper_bar": 6, "ash_plank": 4}
    skill_of_item = {"copper_bar": "mining", "ash_plank": "woodcutting"}
    got = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)
    assert got["miner"] == 6
    assert got["logger"] == 4


def test_demand_for_an_unowned_skill_is_dropped() -> None:
    got = demand_by_role({"mystery": 5}, {"mystery": None}, ROLE_CATALOG)
    assert sum(got.values()) == 0


def test_demand_sums_when_two_items_share_a_role() -> None:
    item_demand = {"copper_bar": 6, "iron_bar": 3}
    skill_of_item = {"copper_bar": "mining", "iron_bar": "mining"}
    assert demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)["miner"] == 9


def test_every_role_appears_even_with_no_demand() -> None:
    got = demand_by_role({}, {}, ROLE_CATALOG)
    assert set(got) == {r.name for r in ROLE_CATALOG}
    assert set(got.values()) == {0}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_role_selection.py -v`
Expected: FAIL with `ImportError: cannot import name 'demand_by_role'`

- [ ] **Step 3: Write minimal implementation**

Add `role_skills` to the existing `role_catalog` import at the top of `role_selection.py`:

```python
from artifactsmmo_cli.ai.role_catalog import Role, role_skills
```

Append:

```python
def demand_by_role(item_demand: Mapping[str, int],
                   skill_of_item: Mapping[str, str | None],
                   catalog: tuple[Role, ...]) -> dict[str, int]:
    """Aggregate item-keyed demand into role-keyed demand.

    `skill_of_item` maps an item code to the skill that PRODUCES it (its craft
    skill, or its gathering skill for a raw resource), or None when the API
    exposes no producing skill — in which case no role owns it and the demand
    is dropped rather than assigned to an arbitrary role.

    Passed in rather than derived from GameData so this module stays pure and
    testable without a game-data fixture."""
    totals = {role.name: 0 for role in catalog}
    owner: dict[str, str] = {}
    for role in catalog:
        for skill in role_skills(role):
            owner[skill] = role.name
    for item_code, quantity in item_demand.items():
        skill = skill_of_item.get(item_code)
        if skill is None:
            continue
        role_name = owner.get(skill)
        if role_name is None:
            continue
        totals[role_name] += quantity
    return totals
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_role_selection.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/role_selection.py tests/test_ai/test_role_selection.py
git commit -m "feat(ai): route item-keyed sibling demand onto roles by producing skill"
```

---

### Task 8: SupplyBankGoal

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/supply_bank.py`
- Test: `tests/test_ai/test_supply_bank_goal.py`

**Interfaces:**
- Consumes: `Goal` ABC, `clamp_into_band`.
- Produces: `SupplyBankGoal(item_code: str, quantity: int, demand: int)` with the standard `Goal` API; constants `SUPPLY_PRIORITY_FLOOR = 30.0`, `SUPPLY_PRIORITY_CEILING = 50.0`, `SUPPLY_DEMAND_GAIN = 1.0`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_supply_bank_goal.py
from artifactsmmo_cli.ai.goals.supply_bank import (
    SUPPLY_PRIORITY_CEILING,
    SUPPLY_PRIORITY_FLOOR,
    SupplyBankGoal,
)
from artifactsmmo_cli.ai.world_state import WorldState


def _state(bank: dict[str, int] | None) -> WorldState:
    return WorldState.create(x=0, y=0, hp=100, max_hp=100, level=5, xp=0, max_xp=100,
                             gold=0, inventory={}, inventory_max=100,
                             bank_items=bank, bank_gold=0)


def test_unsatisfied_when_bank_lacks_the_target(game_data) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state({})) is False


def test_satisfied_when_bank_holds_the_target(game_data) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state({"copper_bar": 6})) is True


def test_unvisited_bank_is_not_satisfied(game_data) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.is_satisfied(_state(None)) is False


def test_desired_state_targets_banked_quantity(game_data) -> None:
    goal = SupplyBankGoal(item_code="copper_bar", quantity=6, demand=6)
    assert goal.desired_state(_state({}), game_data) == {"banked": {"copper_bar": 6}}


def test_priority_stays_inside_the_band(game_data) -> None:
    low = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=0)
    high = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=100_000)
    assert low.value(_state({}), game_data) == SUPPLY_PRIORITY_FLOOR
    assert high.value(_state({}), game_data) == SUPPLY_PRIORITY_CEILING


def test_priority_rises_with_demand(game_data) -> None:
    small = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=2)
    large = SupplyBankGoal(item_code="copper_bar", quantity=1, demand=8)
    assert large.value(_state({}), game_data) > small.value(_state({}), game_data)


def test_ceiling_stays_below_the_survival_floor() -> None:
    assert SUPPLY_PRIORITY_CEILING < 70.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_supply_bank_goal.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.goals.supply_bank'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/artifactsmmo_cli/ai/goals/supply_bank.py
"""Produce a material a SIBLING needs and bank it.

This is the goal that turns the demand board into actual production. Without
it, bank-first sourcing changes nothing: each character gathers exactly what
its own plan demands, crafts it, and leaves the bank empty, so a consumer
preferring WITHDRAW still finds nothing there.

`desired_state` targets BANKED quantity, not held quantity — the distinction
that keeps sibling demand from being consumed by the producer's own craft. That
separation is the whole reason this is a distinct goal rather than an inflation
of the character's own closure demand.

Priority is the clamped demand lift, the same construction `scalar_priority`
and `grind_character_xp` use: the band ceiling sits below the survival floor of
70, so a supply goal can NEVER outrank a survival guard by construction rather
than by tuning.
"""

from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.world_state import WorldState

SUPPLY_PRIORITY_FLOOR = 30.0
"""Minimum priority when active. Matches GrindCharacterXpGoal's floor so a
zero-demand supply goal never outranks ordinary progression."""

SUPPLY_PRIORITY_CEILING = 50.0
"""Upper bound. Stays under ReachSkillGoal (55) and the survival floor (70).
Deliberately overlaps GrindCharacterXpGoal's [30, 45] band so heavy sibling
demand CAN outrank marginal char-xp grinding, but never a skill gate."""

SUPPLY_DEMAND_GAIN = 1.0
"""Priority points per unit of unmet sibling demand."""


class SupplyBankGoal(Goal):
    """Bank `quantity` of `item_code` for the siblings that asked for it."""

    def __init__(self, item_code: str, quantity: int, demand: int) -> None:
        self._item_code = item_code
        self._quantity = quantity
        self._demand = demand

    def __repr__(self) -> str:
        return f"SupplyBank({self._item_code}x{self._quantity})"

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        bonus = Fraction(self._demand) * Fraction(SUPPLY_DEMAND_GAIN)
        clamped = clamp_into_band(Fraction(SUPPLY_PRIORITY_FLOOR),
                                  Fraction(SUPPLY_PRIORITY_CEILING), bonus)
        return float(clamped)

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items
        if bank is None:
            return False
        return bank.get(self._item_code, 0) >= self._quantity

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"banked": {self._item_code: self._quantity}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_supply_bank_goal.py -v`
Expected: 7 passed

Note: if `WorldState.create` rejects these kwargs or the `game_data` fixture is not available in `tests/test_ai/`, read `tests/test_ai/conftest.py` and the `WorldState.create` signature at `src/artifactsmmo_cli/ai/world_state.py:223` and adapt the helper — do not invent defaults.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/goals/supply_bank.py tests/test_ai/test_supply_bank_goal.py
git commit -m "feat(goals): add SupplyBankGoal targeting BANKED quantity for siblings"
```

---

### Task 9: MeansKind.SUPPLY_BANK — Python lockstep

Three Python sites must move together. The enum comment at `means.py:60` records why new variants are appended LAST: the DecideKey oracle's index dispatch and the diff test's `_MEANS_INDEX` depend on stable ordinals.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py`
- Modify: `src/artifactsmmo_cli/ai/tiers/decide_key.py`
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py`
- Test: `tests/test_ai/test_decide_key.py` (verify existing all-variants coverage catches it)

**Interfaces:**
- Consumes: `SupplyBankGoal` (Task 8), `SelectionContext`.
- Produces: `MeansKind.SUPPLY_BANK`; `map_means` returns a `SupplyBankGoal` for it.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_decide_key.py — append
from artifactsmmo_cli.ai.tiers.decide_key import _MEANS_REPR
from artifactsmmo_cli.ai.tiers.means import DISCRETIONARY_ORDER, MeansKind


def test_supply_bank_is_the_last_enum_variant() -> None:
    assert list(MeansKind)[-1] is MeansKind.SUPPLY_BANK


def test_supply_bank_has_a_dispatch_repr() -> None:
    assert _MEANS_REPR[MeansKind.SUPPLY_BANK] == "SupplyBank"


def test_supply_bank_sits_between_consumables_and_idle_selling() -> None:
    order = list(DISCRETIONARY_ORDER)
    assert (order.index(MeansKind.MAINTAIN_CONSUMABLES)
            < order.index(MeansKind.SUPPLY_BANK)
            < order.index(MeansKind.SELL_IDLE))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_decide_key.py -v`
Expected: FAIL with `AttributeError: SUPPLY_BANK`

- [ ] **Step 3: Write minimal implementation**

In `src/artifactsmmo_cli/ai/tiers/means.py`, append to the enum (after `GE_BID`, keeping the append-LAST rule):

```python
    SUPPLY_BANK = "supply_bank"  # 2026-08-01: produce a material a SIBLING needs.
```

Insert into `DISCRETIONARY_ORDER` between `MAINTAIN_CONSUMABLES` and `SELL_IDLE`:

```python
    MeansKind.MAINTAIN_CONSUMABLES,  # prep heals for combat before idle housekeeping
    # Supplying a sibling a material it actually declared beats every idle
    # housekeeping means (sell/recycle/expand/drain), because it converts this
    # character's cycle into progress for a DIFFERENT character. It sits below
    # combat prep and the task means, which serve this character's own
    # committed objective.
    MeansKind.SUPPLY_BANK,
    MeansKind.SELL_IDLE,
```

Add the `_fires` branch (place it next to the other discretionary branches):

```python
    if kind is MeansKind.SUPPLY_BANK:
        # ctx.supply_target is None whenever there is no live sibling demand
        # this character's role can serve — which is every cycle of a
        # single-character run, so this means is inert without `--all`.
        return ctx.supply_target is not None
```

Add the field to `SelectionContext` in `src/artifactsmmo_cli/ai/tiers/guards.py` (find the dataclass and append, with a default so every existing construction site keeps working):

```python
    supply_target: tuple[str, int, int] | None = None
    """(item_code, quantity, demand) this character should produce for a
    sibling this cycle, or None when nothing is servable. Populated by the
    player's per-cycle coordination block; None on every single-character run."""
```

In `src/artifactsmmo_cli/ai/tiers/decide_key.py`, add to `_MEANS_REPR`:

```python
    MeansKind.SUPPLY_BANK: "SupplyBank",
```

In `src/artifactsmmo_cli/ai/strategy_driver.py`, add the import at the top:

```python
from artifactsmmo_cli.ai.goals.supply_bank import SupplyBankGoal
```

and the `map_means` branch (before the final `raise`):

```python
    if kind is MeansKind.SUPPLY_BANK:
        assert ctx.supply_target is not None  # _fires guarantees a target
        item_code, quantity, demand = ctx.supply_target
        return SupplyBankGoal(item_code=item_code, quantity=quantity, demand=demand)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_decide_key.py tests/test_ai/ -x -q`
Expected: PASS. The existing `test_decide_key.py` round-trip over every variant now also covers `SUPPLY_BANK`.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/means.py src/artifactsmmo_cli/ai/tiers/decide_key.py \
        src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/strategy_driver.py \
        tests/test_ai/test_decide_key.py
git commit -m "feat(tiers): add MeansKind.SUPPLY_BANK and its dispatch"
```

---

### Task 10: MeansKind.SUPPLY_BANK — Lean lockstep

The Lean side is compiler-enforced: `goalReprOfMeans` is a total match, so the build FAILS until the variant is handled. That is the mechanism keeping the model from drifting, and it means this task cannot be skipped or half-done.

**Files:**
- Modify: `formal/Formal/Liveness/MeansKind.lean`
- Modify: `formal/Formal/Liveness/ProductionLadder.lean`
- Modify: `formal/Formal/DecideKey.lean`
- Modify: `formal/diff/test_decide_key_diff.py`

**Interfaces:**
- Consumes: `MeansKind.SUPPLY_BANK` (Task 9).
- Produces: Lean `.supplyBank` variant present in `allInLadderOrder` at the position matching `DISCRETIONARY_ORDER`.

- [ ] **Step 1: Run the build to see it fail**

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: PASS (Lean does not yet know about the Python variant). Then run the diff test:

Run: `uv run pytest formal/diff/test_decide_key_diff.py -v`
Expected: FAIL on `assert set(_MEANS_INDEX.keys()) == set(MeansKind)` — the Python enum gained a variant the Lean index does not have.

- [ ] **Step 2: Add the Lean variant**

In `formal/Formal/Liveness/MeansKind.lean`, add to the inductive, positioned with the other discretionary means (after `maintainConsumables`, mirroring `DISCRETIONARY_ORDER`):

```lean
  | supplyBank          -- SUPPLY_BANK,        means.py (2026-08-01): produce a
                        -- material a SIBLING declared on the demand board.
                        -- Fires iff a supply target is present.
```

Find `allInLadderOrder` and insert `.supplyBank` between `.maintainConsumables` and `.sellIdle`, matching the Python `DISCRETIONARY_ORDER` exactly.

- [ ] **Step 3: Add the fires predicate and re-discharge the ladder**

In `formal/Formal/Liveness/ProductionLadder.lean`, add the predicate near the other discretionary ones:

```lean
/-- SUPPLY_BANK. Mirrors `means.py::_fires(SUPPLY_BANK, …)`: fires exactly when
    a supply target is present, i.e. some unexpired sibling demand is servable
    by this character's role. Modelled as an opaque State field because the
    target is computed from the coordination DB, which this model does not
    reproduce — the same honest-disclosure treatment `objectiveStep` gets. -/
def supplyBankFires (s : State) : Bool := s.supplyTargetPresent
```

Add `supplyTargetPresent : Bool` to the `State` structure in the same file, and extend the ladder's `fires` dispatch with the `.supplyBank => supplyBankFires s` case. Add `supplyBank` to the honest-disclosure list in the header comment alongside `objectiveStep`.

While in this file, fix the stale header: the walk is over `allInLadderOrder`, whose length is the sum of `GUARD_ORDER`, `COLLECT_REWARD_ORDER`, `[.objectiveStep]` and `DISCRETIONARY_ORDER` — replace the "17-element MeansKind list" phrasing with the accurate description rather than an element count that has already drifted once.

- [ ] **Step 4: Add the repr and rebuild**

In `formal/Formal/DecideKey.lean`, add to `goalReprOfMeans`:

```lean
  | .supplyBank      => "SupplyBank"
```

Run: `cd formal && lake build 2>&1 | tail -20`
Expected: PASS with no `sorry` and no non-exhaustive-match errors. If a liveness theorem now fails, discharge it — do not weaken the statement.

- [ ] **Step 5: Update the diff index and verify**

In `formal/diff/test_decide_key_diff.py`, add to `_MEANS_INDEX` with the ordinal matching the Lean inductive's constructor position.

Run: `uv run pytest formal/diff/test_decide_key_diff.py -v`
Expected: PASS

- [ ] **Step 6: Check axioms and commit**

Run: `cd formal && lake env lean --run Formal/Audit.lean 2>&1 | tail -20`
Expected: no new axioms, no `sorry`.

```bash
git add formal/
git commit -m "feat(formal): add supplyBank to the means ladder and DecideKey"
```

---

### Task 11: Wire coordination into the player loop

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py` (constructor; run loop beside `self._gear_latch.update(...)` at ~line 928)
- Modify: `src/artifactsmmo_cli/ai/cycle_snapshot.py`
- Test: `tests/test_ai/test_player_coordination.py`

**Interfaces:**
- Consumes: `CoordinationStore` (Tasks 2, 4), `decide_role` / `demand_by_role` (Tasks 6, 7), `ROLE_CATALOG` (Task 5).
- Produces: `GamePlayer._coordination`, `GamePlayer._role`, `GamePlayer._role_held_cycles`; `CycleSnapshot.role` and `CycleSnapshot.supply_target`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_player_coordination.py
from datetime import datetime, timezone

from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import decide_role, demand_by_role

_T0 = datetime(2026, 8, 1, tzinfo=timezone.utc)


def test_two_stores_converge_on_distinct_roles(tmp_path) -> None:
    """The cold-start allocator: both characters want the same top-demand role,
    the UNIQUE constraint serializes them, and they end up on different roles."""
    db = str(tmp_path / "coord.db")
    hal = CoordinationStore(db_path=db, character="HAL")
    c3po = CoordinationStore(db_path=db, character="C3P0")
    try:
        hal.publish_demand({"copper_bar": 10}, _T0)
        c3po.publish_demand({"ash_plank": 4}, _T0)
        skills = {"copper_bar": "mining", "ash_plank": "woodcutting"}

        held: dict[str, str] = {}
        for store in (hal, c3po):
            by_role = demand_by_role(store.sibling_demand(_T0), skills, ROLE_CATALOG)
            decision = decide_role(current=held.get(store.character), held_cycles=0,
                                   live_leases=store.live_leases(_T0),
                                   demand_by_role=by_role,
                                   character=store.character, catalog=ROLE_CATALOG)
            assert decision.claim is not None
            assert store.claim(decision.claim, _T0) is True
            held[store.character] = decision.claim

        assert held["HAL"] != held["C3P0"]
        assert hal.live_leases(_T0) == {held["HAL"]: "HAL", held["C3P0"]: "C3P0"}
    finally:
        hal.close()
        c3po.close()
```

- [ ] **Step 2: Run test to verify it fails or passes**

Run: `uv run pytest tests/test_ai/test_player_coordination.py -v`
Expected: PASS — this test exercises only Tasks 2-7 and is the integration check that they compose. If it fails, the defect is in `decide_role` or `demand_by_role`, not in the wiring below.

- [ ] **Step 3: Add the snapshot fields**

In `src/artifactsmmo_cli/ai/cycle_snapshot.py`, add beside the existing `aged_pick` field:

```python
    role: str | None = None
    """The specialization role this character held this cycle, or None when it
    holds none (every cycle of a single-character run)."""

    supply_target: str | None = None
    """`repr` of the sibling demand being served this cycle, or None. This is
    the trace field that proves collusion actually fired."""
```

- [ ] **Step 4: Wire the player**

In `GamePlayer.__init__`, add beside the learning-store construction:

```python
        self._coordination: CoordinationStore | None = None
        self._role: str | None = None
        self._role_held_cycles: int = 0
```

Add a setter so `play.py` can inject the store (mirroring how the learning store is threaded):

```python
    def set_coordination_store(self, store: "CoordinationStore | None") -> None:
        """Attach the cross-character coordination store. None (the default)
        disables coordination entirely, which is the single-character path."""
        self._coordination = store
```

Add the per-cycle block in `run()`, immediately AFTER `self._gear_latch.update(...)` and BEFORE `self._arbiter.set_cycle(...)`:

```python
                # Coordination: renew our lease, publish what we still need,
                # and re-decide our role. All local SQLite against the shared
                # learning DB — zero API calls, so this costs nothing from the
                # per-IP rate budget that actually binds this bot.
                self._update_coordination(state, game_data)
```

and the method itself:

```python
    def _update_coordination(self, state: WorldState, game_data: GameData) -> None:
        """Renew, publish, and re-decide this character's role for one cycle.

        No-op when no coordination store is attached, which is every
        single-character run."""
        if self._coordination is None:
            return
        now = datetime.now(tz=timezone.utc)
        if self._role is not None:
            self._coordination.renew(self._role, now)
        self._coordination.publish_demand(self._own_unmet_demand(state, game_data), now)

        item_demand = self._coordination.sibling_demand(now)
        skill_of_item = {code: game_data.producing_skill(code) for code in item_demand}
        by_role = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)
        decision = decide_role(current=self._role, held_cycles=self._role_held_cycles,
                               live_leases=self._coordination.live_leases(now),
                               demand_by_role=by_role,
                               character=self._coordination.character,
                               catalog=ROLE_CATALOG)
        if decision.release is not None:
            self._coordination.release(decision.release)
            self._role = None
            self._role_held_cycles = 0
        elif decision.claim is not None:
            if self._coordination.claim(decision.claim, now):
                self._role = decision.claim
                self._role_held_cycles = 0
        elif decision.keep is not None:
            self._role_held_cycles += 1
```

`_own_unmet_demand` and `GameData.producing_skill` are the two helpers this needs. Implement `_own_unmet_demand` by reusing the closure-demand function `task_reservation` already calls:

```python
    def _own_unmet_demand(self, state: WorldState, game_data: GameData) -> dict[str, int]:
        """This character's unmet closure demand for its chosen root, minus what
        it already holds. Reuses `_closure_demand` — the same function
        `task_reservation` uses — rather than computing demand a second way."""
        root = self._last_decide_crafting_target
        if root is None:
            return {}
        demand = _closure_demand({root: 1}, game_data.recipes)
        return {code: qty - state.inventory.get(code, 0)
                for code, qty in demand.items()
                if qty - state.inventory.get(code, 0) > 0}
```

Before writing `GameData.producing_skill`, grep for an existing accessor — `recipe_catalog.py` and `item_catalog.py` already index recipes by skill, and duplicating that lookup would violate the DRY constraint. If one exists, call it; if not, add it to `game_data.py` returning the item's craft skill, falling back to its gathering skill, and `None` when the API exposes neither.

- [ ] **Step 5: Construct the store in the play command**

In `src/artifactsmmo_cli/commands/play.py`, beside the existing `LearningStore` construction at line 125, build the coordination store on the SAME `db_path` and attach it. Guard it on the multi-character path only — a single-character run must stay bit-identical, so attach only when `--emit-events` is set (the flag `MultiRun._child_argv` always passes to children).

- [ ] **Step 6: Run the full AI suite and commit**

Run: `uv run pytest tests/test_ai/ -q`
Expected: all pass, no new failures.

```bash
git add src/artifactsmmo_cli/ai/player.py src/artifactsmmo_cli/ai/cycle_snapshot.py \
        src/artifactsmmo_cli/commands/play.py tests/test_ai/test_player_coordination.py
git commit -m "feat(ai): wire per-cycle role coordination into the player loop"
```

---

### Task 12: Runtime activation proof

Green tests do not prove active. This project has shipped several gate-green epics that never fired in production, so this task is a gate, not a formality.

**Files:**
- Create: `scripts/verify_collusion.py`
- Test: none (this is an analysis script over real run artifacts)

**Interfaces:**
- Consumes: `play-trace-*.jsonl` files and `~/.cache/artifactsmmo/learning.db`.
- Produces: a pass/fail report on the three activation criteria.

- [ ] **Step 1: Write the verification script**

```python
# scripts/verify_collusion.py
"""Prove that cross-character collusion actually fired on a live run.

Green tests do not prove runtime activation. Three criteria, all of which must
hold on a real `play --all` run before the epic is done:

  1. at least one character held a role
  2. SupplyBankGoal was actually selected at least once
  3. a Withdraw succeeded against stock a DIFFERENT character deposited

Criterion 3 is the one that proves collusion rather than mere divergence.

Usage: uv run python scripts/verify_collusion.py <trace-glob>
"""

import collections
import glob
import json
import os
import re
import sys


def main(pattern: str) -> int:
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"FAIL: no trace files matched {pattern!r}")
        return 1

    roles_held: set[str] = set()
    supply_selected = 0
    deposits: dict[str, set[str]] = collections.defaultdict(set)
    cross_withdraws: list[tuple[str, str]] = []

    records = []
    for path in files:
        match = re.match(r"play-trace-(.+?)-\d{8}-", os.path.basename(path))
        if match is None:
            continue
        character = match.group(1)
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            record["_character"] = character
            records.append(record)
    records.sort(key=lambda r: r["ts"])

    for record in records:
        character = record["_character"]
        if record.get("role"):
            roles_held.add(f"{character}:{record['role']}")
        if "SupplyBank" in (record.get("selected_goal") or ""):
            supply_selected += 1
        action = record.get("action") or ""
        if record.get("outcome") != "ok":
            continue
        deposit = re.match(r"Deposit\w*\((\w+)", action)
        if deposit:
            deposits[deposit.group(1)].add(character)
        withdraw = re.match(r"Withdraw\((\w+)", action)
        if withdraw:
            item = withdraw.group(1)
            others = deposits.get(item, set()) - {character}
            if others:
                cross_withdraws.append((character, item))

    checks = [
        ("a character held a role", bool(roles_held), sorted(roles_held)[:5]),
        ("SupplyBankGoal was selected", supply_selected > 0, supply_selected),
        ("a sibling-deposited item was withdrawn", bool(cross_withdraws),
         cross_withdraws[:5]),
    ]
    failed = 0
    for label, ok, detail in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {label} -- {detail}")
        failed += 0 if ok else 1
    return 1 if failed else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
```

- [ ] **Step 2: Run a live multi-character session**

Run: `uv run artifactsmmo play --all --learn --trace`
Let it run long enough for a character to exceed `ROLE_MIN_HOLD_CYCLES` (100 cycles) and for at least one supply cycle to complete. Stop it cleanly.

- [ ] **Step 3: Verify all three criteria**

Run: `uv run python scripts/verify_collusion.py 'play-trace-*.jsonl'`
Expected: three PASS lines, exit 0.

If criterion 3 fails while 1 and 2 pass, the epic is INERT: characters diverged but never actually consumed each other's output. Do not proceed — diagnose why `WITHDRAW` is not winning in `obtain_sources`.

- [ ] **Step 4: Commit**

```bash
git add scripts/verify_collusion.py
git commit -m "test(scripts): add the three-criterion collusion activation check"
```

---

### Task 13: role_alignment ranking factor

Phase 2 begins here. Tasks 1-12 are shippable without this.

The factor mirrors `achievability` exactly: same `(slot, code)` key, same empty-map sentinel, same four threading sites. Landing it inert first and activating separately is the discipline that caught the synergy epic running with weighting off.

**Files:**
- Create: `src/artifactsmmo_cli/ai/role_alignment.py`
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree_core.py` (`_scaled_weights` at line 222, `focus_aging_pick` at 247, `focus_aging_order` at 292)
- Test: `tests/test_ai/test_role_alignment.py`

**Interfaces:**
- Consumes: `Role`, `role_skills` (Task 5); `GearCandidate`.
- Produces: `role_alignment_pure(owned_skills: frozenset[str], candidate_skill: str | None) -> Fraction`; `_NO_ROLE: Mapping[tuple[str, str], Fraction]` in `progression_tree_core.py`; constants `ALIGNED = Fraction(1)`, `MISALIGNED = Fraction(1, 2)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_role_alignment.py
from fractions import Fraction

from artifactsmmo_cli.ai.role_alignment import ALIGNED, MISALIGNED, role_alignment_pure


def test_candidate_in_our_skills_is_unpenalised() -> None:
    assert role_alignment_pure(frozenset({"mining", "weaponcrafting"}),
                               "weaponcrafting") == ALIGNED


def test_candidate_outside_our_skills_is_damped() -> None:
    assert role_alignment_pure(frozenset({"mining", "weaponcrafting"}),
                               "gearcrafting") == MISALIGNED


def test_unknown_producing_skill_is_unpenalised() -> None:
    """No signal must never become a penalty — the no-invented-data rule."""
    assert role_alignment_pure(frozenset({"mining"}), None) == ALIGNED


def test_no_role_is_identity() -> None:
    assert role_alignment_pure(frozenset(), "weaponcrafting") == ALIGNED


def test_damping_never_reorders_below_zero() -> None:
    assert MISALIGNED > 0
    assert MISALIGNED < ALIGNED
    assert isinstance(MISALIGNED, Fraction)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_role_alignment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'artifactsmmo_cli.ai.role_alignment'`

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/role_alignment.py
"""Fifth ranking factor: damp gear chains outside this character's role.

`_scaled_weights` composes gain * falloff * synergy * achievability. This adds
role alignment as a fifth multiplier on the SAME (slot, code) key, so a
role-holder prefers the chain its own skills already serve.

DAMP, never boost: an aligned candidate keeps its weight exactly (Fraction(1)),
and a misaligned one is halved. That way a character with NO role — the
single-character path, or a roster larger than the catalog — sees every
multiplier at 1 and the weight is byte-identical to the four-factor value.

An unknown producing skill reads as ALIGNED, not MISALIGNED: no signal must
never become a penalty, per "use only API data or fail with an error" — we do
not know the chain is wrong, so we do not act as if it is.
"""

from fractions import Fraction

ALIGNED = Fraction(1)
"""No signal, or the candidate's skill is one this role owns."""

MISALIGNED = Fraction(1, 2)
"""The candidate's chain belongs to another role. Halved rather than zeroed:
a role-holder must still be ABLE to pursue an off-role chain when nothing else
is available, or a jeweler with no banked bars would have no plan at all."""


def role_alignment_pure(owned_skills: frozenset[str],
                        candidate_skill: str | None) -> Fraction:
    """Multiplier for one gear candidate given the skills this role owns."""
    if not owned_skills:
        return ALIGNED
    if candidate_skill is None:
        return ALIGNED
    return ALIGNED if candidate_skill in owned_skills else MISALIGNED
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_ai/test_role_alignment.py -v`
Expected: 5 passed

- [ ] **Step 5: Thread the factor inert through the tree core**

In `progression_tree_core.py`, add the sentinel beside `_NO_ACHIEVABILITY`:

```python
_NO_ROLE: Mapping[tuple[str, str], Fraction] = MappingProxyType({})
"""The empty role map — 'no role signal'. A missing `(slot, code)` entry reads
as `Fraction(1)`, so this sentinel is byte-identical to the pre-role weight
`gain * falloff * synergy * achievability`. Sibling of `_NO_SYNERGY` /
`_NO_ACHIEVABILITY`; the default for every role-aware function so the whole
plumbing lands inert before real values arrive, and the one-line kill switch if
a live trace goes wrong."""
```

Add `role: Mapping[tuple[str, str], Fraction] = _NO_ROLE` as the last parameter of `_scaled_weights`, `focus_aging_pick` and `focus_aging_order`, forward it through both call sites inside `focus_aging_order`, and extend the product in `_scaled_weights`:

```python
    return [(c.slot, c.gain * falloff(focus.get((c.slot, c.code), 0))
             * synergy.get((c.slot, c.code), Fraction(1))
             * achievability.get((c.slot, c.code), Fraction(1))
             * role.get((c.slot, c.code), Fraction(1)))
            for c in candidates]
```

Also extend `focus_aging_pick`'s fast-path guard so a pick steered by role goes through the aging interleave, exactly as the synergy and achievability clauses do.

- [ ] **Step 6: Prove it landed inert**

```python
# tests/test_ai/test_role_alignment.py — append
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    _NO_ROLE,
    _scaled_weights,
    focus_aging_order,
    focus_aging_pick,
)


def test_empty_role_map_is_byte_identical(gear_candidates) -> None:
    """The inert-landing proof: with _NO_ROLE the weights, pick and order are
    exactly what the four-factor composition produced."""
    focus: dict = {}
    seats: dict = {}
    assert (_scaled_weights(gear_candidates, focus)
            == _scaled_weights(gear_candidates, focus, role=_NO_ROLE))
    assert (focus_aging_pick(gear_candidates, focus, seats)
            is focus_aging_pick(gear_candidates, focus, seats, role=_NO_ROLE))
    assert (focus_aging_order(gear_candidates, focus, seats)
            == focus_aging_order(gear_candidates, focus, seats, role=_NO_ROLE))
```

Build the `gear_candidates` fixture from the `GearCandidate` dataclass at `progression_tree_core.py:158` — read its fields rather than guessing them.

Run: `uv run pytest tests/test_ai/test_role_alignment.py -v`
Expected: 6 passed

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/role_alignment.py \
        src/artifactsmmo_cli/ai/tiers/progression_tree_core.py \
        tests/test_ai/test_role_alignment.py
git commit -m "feat(tiers): add role_alignment as an inert fifth ranking factor"
```

---

### Task 14: Activate role_alignment and close out

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (mirror `_achievability_map` at line 339; callsites at 416-419; inertness guard at ~453)
- Modify: `docs/superpowers/specs/2026-07-31-emergent-specialization-design.md`

**Interfaces:**
- Consumes: `role_alignment_pure` (Task 13), `GamePlayer._role` (Task 11).
- Produces: `_role_map(candidates, role_name, game_data) -> dict[tuple[str, str], Fraction]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_role_alignment.py — append
from artifactsmmo_cli.ai.tiers.progression_tree import _role_map


def test_role_map_is_empty_without_a_role(gear_candidates, game_data) -> None:
    assert _role_map(gear_candidates, None, game_data) == {}


def test_role_map_damps_off_role_candidates(gear_candidates, game_data) -> None:
    mapped = _role_map(gear_candidates, "miner", game_data)
    assert set(mapped.values()) <= {ALIGNED, MISALIGNED}
    assert all(isinstance(k, tuple) and len(k) == 2 for k in mapped)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_ai/test_role_alignment.py -v`
Expected: FAIL with `ImportError: cannot import name '_role_map'`

- [ ] **Step 3: Build and thread the map**

Add `_role_map` to `progression_tree.py` mirroring `_achievability_map`, returning `{}` when `role_name is None` so the no-role path produces the `_NO_ROLE` sentinel exactly. Look each candidate's producing skill up through the same `GameData` accessor Task 11 settled on. Thread the result into the `focus_aging_order` / `focus_aging_pick` calls at lines 418-419, and add a role clause to the fast-path inertness guard at ~line 453 alongside the synergy and achievability clauses.

Thread `self._role` from the player into whatever `SelectionContext` or `decide` argument `progression_tree` reads — follow how `crafting_target` is threaded through `_selection_context`.

- [ ] **Step 4: Run the full local gate**

Run: `bash formal/gate.sh > /tmp/gate.log 2>&1; echo "rc=${PIPESTATUS[0]}"; tail -20 /tmp/gate.log`
Expected: `rc=0`. Redirect rather than pipe — piping to `tail` reports tail's exit code and has masked a real `GATE FAIL` in this repo before.

- [ ] **Step 5: Re-run the activation proof**

Run: `uv run artifactsmmo play --all --learn --trace` for a fresh session, then:
Run: `uv run python scripts/verify_collusion.py 'play-trace-*.jsonl'`
Expected: three PASS lines.

Additionally confirm the fifth factor is live: at least one traced cycle must show a role-holder whose gear ranking differs from what the four-factor weight would have produced. If every `role_alignment` value is `Fraction(1)`, the factor is threaded but inert and the phase is not done.

- [ ] **Step 6: Record the measured outcome**

Re-run the baseline analysis from spec §2 and append the numbers to the spec's success-criteria section: duplicate gather count for a shared material, before and after. The baseline is 899 `copper_rocks` gathers across three characters with `Gather` at 62% of all actions. A run that shows no reduction means the roles diverged but the supply chain did not carry, which is a defect, not a tuning issue.

- [ ] **Step 7: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/progression_tree.py \
        tests/test_ai/test_role_alignment.py \
        docs/superpowers/specs/2026-07-31-emergent-specialization-design.md
git commit -m "feat(tiers): activate role_alignment and record the measured outcome"
```

---

## Self-Review

**Spec coverage.** §1-2 evidence and success criteria → Task 12 (the three-criterion check) and Task 14 step 5. §3 existing facts → consumed throughout. §4 decisions → Tasks 4 (demand board), 5 (catalog), 2 (leases), 8+13 (the two seams). §5.1 tables → Task 1. §5.2 units → Tasks 2, 4, 5, 6, 7, 8, 13. §5.3 catalog → Task 5. §5.4 integration → Tasks 9, 13, 14. §5.5 rejected → not implemented, correctly. §6 data flow → Task 11. §7 hysteresis → Task 6; §7.1 race → Tasks 2-3; §7.2 degradation → Tasks 6, 13 (no-role identity). §8 error handling → Tasks 2, 4. §9 formal → Task 10. §10 testing → every task, plus Task 12.

**Known gaps this plan leaves.** Three, all deliberate and all flagged inline rather than silently assumed:

1. `GameData.producing_skill` may already exist under another name. Task 11 step 4 instructs a grep before writing it, because duplicating a recipe-to-skill lookup would violate DRY.
2. The `SupplyBankGoal` `desired_state` key `{"banked": ...}` must match what the planner and `DepositAction` actually consume. If no `banked` predicate exists, Task 8 needs a planner-side term — check `world_state.py` and the deposit action before implementing.
3. Task 10's Lean edits describe the required shape but cannot pin exact line numbers, because the ladder proofs will need re-discharging in whatever form the compiler demands.

**Placeholder scan.** No TBD/TODO. Every code step carries real code. The three items above are named uncertainties with a stated resolution procedure, not deferred work.

**Type consistency.** `CoordinationStore.claim/renew/release/live_leases/publish_demand/sibling_demand` are used with identical signatures in Tasks 2, 3, 4, 11 and 12. `decide_role` and `demand_by_role` keep the same keyword names in Tasks 6, 7 and 11. `RoleDecision.keep/claim/release` are consistent throughout. `role_alignment_pure`, `ALIGNED`, `MISALIGNED` and `_NO_ROLE` match across Tasks 13 and 14.
