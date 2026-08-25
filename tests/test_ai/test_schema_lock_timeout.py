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

THE SAME TEST FAILED AGAIN, and the timeout was not the reason the second time.
The traceback landed on the journal-mode line, not the schema lock:

    sqlite3.OperationalError: database is locked
      File ".../ai/learning/store.py", line 225, in __init__   # journal_mode=WAL

That statement is the one thing in the constructor the declared timeout does not
cover. Measured here (sqlite 3.50.4), with `connect(timeout=30)` in force:

  * a single held READ lock refuses `PRAGMA journal_mode=WAL` for the whole
    timeout and then raises — while an ordinary `BEGIN IMMEDIATE` writer and
    `PRAGMA synchronous` sail straight through the same lock;
  * under a QUEUE of writers it is worse: the conversion was refused after
    1.03 SECONDS of its 30-second budget while all 24 competing writers
    succeeded, the last at 3.33s.

So the retry has to be ours, and `enable_wal` owns it for BOTH stores. The
tests below pin its three outcomes: a refusal is retried, the retry stops at the
budget rather than looping forever, and the short attempt timeout does not leak
into the pooled connection afterwards.
"""

import sqlite3
import tempfile
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session as SqlSession

from artifactsmmo_cli.ai.learning import schema_init
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.schema_init import (
    SCHEMA_LOCK_TIMEOUT_SECONDS,
    enable_wal,
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


# --- the journal-mode change: the statement the timeout does NOT cover -------


def _rollback_mode_db(path: Path) -> str:
    """A real file with a table, in ROLLBACK journal mode.

    Rollback mode is the whole point: converting rollback -> WAL is what needs
    an instant of exclusive access. A file already in WAL needs no conversion
    and cannot exhibit the defect.
    """
    db = str(path)
    seed = sqlite3.connect(db, isolation_level=None)
    seed.execute("CREATE TABLE t (x INTEGER)")
    assert seed.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    seed.close()
    return db


class _SiblingHoldingTheFile:
    """A sibling holding an ordinary read lock, for `hold_for` seconds.

    Its own thread, because a pysqlite connection may only be used from the
    thread that made it. This is the cheapest condition that refuses the
    conversion, and it is the real one: every child queueing for the exclusive
    schema lock takes a read lock on the way.
    """

    def __init__(self, db: str, hold_for: float) -> None:
        self._db, self._hold_for = db, hold_for
        self.holding = threading.Event()
        self._thread = threading.Thread(target=self._run)

    def _run(self) -> None:
        conn = sqlite3.connect(self._db, timeout=30.0, isolation_level=None)
        conn.execute("BEGIN")
        conn.execute("SELECT * FROM t").fetchall()
        self.holding.set()
        time.sleep(self._hold_for)
        conn.execute("ROLLBACK")
        conn.close()

    def __enter__(self) -> "_SiblingHoldingTheFile":
        self._thread.start()
        assert self.holding.wait(30), "the sibling never took its read lock"
        return self

    def __exit__(self, *exc: object) -> None:
        self._thread.join(timeout=60)


def _impatient_retries(monkeypatch: pytest.MonkeyPatch, budget: float) -> None:
    """Shrink the retry schedule so a test costs tenths of a second.

    The VALUES are not what these tests are about — the retry EXISTING is. The
    shipped values are pinned separately, below.
    """
    monkeypatch.setattr(schema_init, "WAL_ATTEMPT_TIMEOUT_SECONDS", 0.02)
    monkeypatch.setattr(schema_init, "WAL_RETRY_INITIAL_SECONDS", 0.01)
    monkeypatch.setattr(schema_init, "WAL_RETRY_MAX_SECONDS", 0.02)
    monkeypatch.setattr(schema_init, "WAL_TOTAL_BUDGET_SECONDS", budget)


def test_a_refused_conversion_is_retried_rather_than_killing_the_child(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE REGRESSION. A sibling holds the file for longer than one attempt, so
    the first attempt is genuinely refused; the store must still come up.

    This is the live `play --all --learn` path: five children are handed the
    same DB path, and a child that dies here is a character that never starts.
    Without the retry the first refusal propagates and the child is gone.
    """
    db = _rollback_mode_db(tmp_path / "race.db")
    _impatient_retries(monkeypatch, budget=30.0)
    engine = create_engine(f"sqlite:///{db}", connect_args=schema_lock_connect_args())
    try:
        # Held for far longer than one 0.02s attempt: the retry is load-bearing,
        # not a formality that a single lucky attempt would satisfy anyway.
        with _SiblingHoldingTheFile(db, hold_for=0.5):
            enable_wal(engine)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
    finally:
        engine.dispose()


def test_the_short_attempt_timeout_does_not_leak_into_the_pooled_connection(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`PRAGMA busy_timeout` belongs to the CONNECTION, and `enable_wal` runs on
    a POOLED one. Leaving the short attempt timeout set would silently drop
    every later write on that connection from 30 seconds to a fraction of one —
    re-opening the very defect this module exists to close, and doing it only on
    the contended path where nobody would look.
    """
    db = _rollback_mode_db(tmp_path / "leak.db")
    _impatient_retries(monkeypatch, budget=30.0)
    engine = create_engine(f"sqlite:///{db}", connect_args=schema_lock_connect_args())
    try:
        with _SiblingHoldingTheFile(db, hold_for=0.5):
            enable_wal(engine)
        assert _busy_timeout_ms(engine) == SCHEMA_LOCK_TIMEOUT_SECONDS * 1000
    finally:
        engine.dispose()


def test_a_file_nobody_converts_within_the_budget_still_raises(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tolerating a LOST RACE is not tolerating a dead database.

    The retry is justified by "whichever sibling wins sets WAL for everyone". If
    no sibling ever wins, that justification is absent and the error is real, so
    it must surface — swallowing it would leave a store running on a file no
    sibling can write either.
    """
    db = _rollback_mode_db(tmp_path / "stuck.db")
    _impatient_retries(monkeypatch, budget=0.1)
    engine = create_engine(f"sqlite:///{db}", connect_args=schema_lock_connect_args())
    try:
        with _SiblingHoldingTheFile(db, hold_for=1.0), pytest.raises(OperationalError):
            enable_wal(engine)
    finally:
        engine.dispose()


def test_an_in_memory_store_opens_at_once_instead_of_waiting_to_be_shared() -> None:
    """`LearningStore(db_path=":memory:")` is what `play`, `plan` and
    `combat_deficit_report` build whenever learning is OFF — it is a production
    path, not a test convenience.

    An in-memory database has no file, so no sibling can open it, and SQLite
    answers 'memory' to a journal-mode change however often it is asked. Waiting
    for WAL there would hang every no-`--learn` command for the full budget and
    then kill it. The store must come up, immediately.
    """
    started = time.monotonic()
    store = LearningStore(db_path=":memory:", character="HAL")
    try:
        elapsed = time.monotonic() - started
        assert elapsed < 5.0, (
            f"opening an in-memory store took {elapsed:.1f}s — it is waiting for a "
            "WAL that an in-memory database can never have")
        with store._engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "memory"
    finally:
        store.close()


def test_the_backing_file_is_what_separates_shareable_from_private() -> None:
    """The discriminator itself, since the branch above hangs off it. A file DB
    reports its path; an in-memory one reports nothing, under either spelling."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "real.db"
        on_disk = create_engine(f"sqlite:///{path}",
                                connect_args=schema_lock_connect_args())
        anonymous = create_engine("sqlite://", connect_args=schema_lock_connect_args())
        named = create_engine("sqlite:///:memory:",
                              connect_args=schema_lock_connect_args())
        try:
            assert schema_init._backing_file(on_disk) == str(path)
            assert schema_init._backing_file(anonymous) == ""
            assert schema_init._backing_file(named) == ""
        finally:
            for e in (on_disk, anonymous, named):
                e.dispose()


def test_one_attempt_is_short_but_the_budget_is_the_declared_one(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The shipped schedule, pinned as an INEQUALITY so it stays a statement
    about the design rather than a constant equalling itself.

    A long single attempt is exactly what did not work: the conversion was
    refused 1.03s into a 30-second budget. Attempts must therefore be short
    enough to retry many times, while the TOTAL budget stays the same 30
    seconds the schema lock gets.
    """
    assert schema_init.WAL_ATTEMPT_TIMEOUT_SECONDS < SCHEMA_LOCK_TIMEOUT_SECONDS
    assert float(SCHEMA_LOCK_TIMEOUT_SECONDS) == schema_init.WAL_TOTAL_BUDGET_SECONDS
    assert (schema_init.WAL_TOTAL_BUDGET_SECONDS
            > 5 * schema_init.WAL_ATTEMPT_TIMEOUT_SECONDS), (
        "the budget must fit several attempts, or there is no retry to speak of")
    assert (schema_init.WAL_RETRY_INITIAL_SECONDS
            <= schema_init.WAL_RETRY_MAX_SECONDS)
