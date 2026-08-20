"""The first-open schema lock's busy timeout is DECLARED, not inherited.

`exclusive_schema_lock` serializes five `play --all` children behind SQLite's
writer lock, and the losers rely on pysqlite's busy handler to retry until the
winner commits. The module reasoned about "the default five-second busy timeout"
while nothing set, stated or tested it — so it was a library default the design
depended on and never owned.

It broke on a gate run (2026-08-20) under `pytest -n auto`:

    sqlite3.OperationalError: database is locked
    FAILED test_concurrent_first_open_of_a_new_learning_db_creates_the_schema_once

These tests pin the fix at the level that actually matters — the timeout a real
connection reports — rather than asserting that a constant equals itself.
"""

import tempfile
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session as SqlSession

from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.schema_init import (
    SCHEMA_LOCK_TIMEOUT_SECONDS,
    schema_lock_connect_args,
)
from artifactsmmo_cli.ai.learning.store import LearningStore


def _busy_timeout_ms(engine) -> int:  # type: ignore[no-untyped-def]
    with SqlSession(engine) as s:
        return int(s.execute(text("PRAGMA busy_timeout")).scalar())


def test_learning_store_connections_carry_the_declared_timeout(tmp_path: Path) -> None:
    """A real connection must REPORT the timeout, not merely be constructed with
    a kwarg — the failure mode was a default nobody noticed was in force."""
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="HAL")
    try:
        assert _busy_timeout_ms(store._engine) == SCHEMA_LOCK_TIMEOUT_SECONDS * 1000
    finally:
        store.close()


def test_coordination_store_connections_carry_the_declared_timeout(
        tmp_path: Path) -> None:
    """Both stores share the lock, so both must share the timeout. A store that
    built its engine without `schema_lock_connect_args` would silently drop back
    to pysqlite's five seconds and re-open the defect for everyone racing it."""
    store = CoordinationStore(db_path=str(tmp_path / "c.db"), character="HAL")
    try:
        assert _busy_timeout_ms(store._engine) == SCHEMA_LOCK_TIMEOUT_SECONDS * 1000
    finally:
        store.close()


def test_the_declared_timeout_beats_pysqlites_silent_default() -> None:
    """The whole point is headroom over the inherited 5s. Pinning the INEQUALITY
    rather than the number keeps this from being a test that a constant equals
    itself: raising the ceiling stays legal, quietly falling back does not.
    """
    assert schema_lock_connect_args() == {"timeout": float(SCHEMA_LOCK_TIMEOUT_SECONDS)}
    assert SCHEMA_LOCK_TIMEOUT_SECONDS > 5


def test_a_store_built_without_the_helper_would_get_the_old_default() -> None:
    """The counterfactual that makes the two tests above load-bearing.

    Without this, "the timeout is 30000" reads as a property of SQLite rather
    than of our engine construction, and deleting `connect_args` from a store
    would leave those assertions looking like they still tested something.
    """
    from sqlalchemy import create_engine

    with tempfile.TemporaryDirectory() as d:
        bare = create_engine(f"sqlite:///{Path(d) / 'bare.db'}")
        try:
            assert _busy_timeout_ms(bare) == 5000, (
                "pysqlite's default changed; SCHEMA_LOCK_TIMEOUT_SECONDS' "
                "rationale needs re-reading")
        finally:
            bare.dispose()
