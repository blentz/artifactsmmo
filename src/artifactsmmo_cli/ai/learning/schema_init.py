"""Cross-process-safe first-open schema work for the shared SQLite file.

`play --all` spawns one child process per character within about a second of
each other, and every child opens the SAME SQLite file — the coordination DB
(`CoordinationStore`), which is the learning DB itself when `--learn` is on
(`LearningStore`). Both constructors do first-open schema work of the form
"probe what exists, then create what does not":

* `SQLModel.metadata.create_all` reflects the table names, then issues a
  `CREATE TABLE` for each one it did not see;
* `LearningStore`'s column migrations read `PRAGMA table_info(cycles)`, then
  `ALTER TABLE` for each column they did not see.

Neither pair is atomic with respect to another PROCESS. pysqlite runs DDL in
autocommit (since Python 3.6 a `CREATE TABLE` no longer opens an implicit
transaction), so five siblings all probe an empty file, all decide to create,
and the losers of the race raise. That is not hypothetical: a live `play --all`
run killed a child with

    OperationalError: (sqlite3.OperationalError) table role_leases already
    exists  [SQL: CREATE TABLE role_leases (...)]

This module fixes the race rather than absorbing it: `exclusive_schema_lock`
serializes the whole probe-and-create sequence behind SQLite's own writer lock,
so a loser blocks until the winner commits and then PROBES AGAIN — seeing the
finished schema and issuing no DDL at all. Nothing is caught, so a genuinely
broken database still raises exactly as loudly as before.

It lives in its own module because BOTH stores need it and there must be one
implementation of the locking discipline, not one per store.
"""

import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine
from sqlalchemy.exc import OperationalError

#: Seconds a process waits for the first-open schema lock before giving up.
#:
#: pysqlite's own default is 5, and this module USED to depend on it silently —
#: the docstring below reasoned that the queue "drains well inside the default
#: five-second busy timeout" while nothing in the codebase set, stated or tested
#: it. That assumption is load-dependent and it broke: a gate run on 2026-08-20
#: killed a child with `sqlite3.OperationalError: database is locked` under
#: `pytest -n auto`, seventeen workers doing real SQLite I/O at once.
#:
#: The window is worse than the old docstring implied, for a reason worth
#: stating: both stores enable `journal_mode=WAL` only AFTER this lock (a
#: journal-mode change is illegal inside a transaction), so the five-way
#: first-open race runs in ROLLBACK-JOURNAL mode, where a writer excludes every
#: reader.
#:
#: 30 seconds is not "absorbing" the error. The lock is held for milliseconds on
#: an idle machine, so a higher ceiling costs a healthy run exactly nothing and
#: only spends time that would otherwise have been a crash. A genuinely stuck
#: database still raises, just as loudly, 30 seconds later.
SCHEMA_LOCK_TIMEOUT_SECONDS = 30


def schema_lock_connect_args() -> dict[str, float]:
    """`create_engine(..., connect_args=...)` for a store sharing the schema lock.

    Exists so the timeout is set in ONE place for both stores. A store that
    builds its engine without it silently gets pysqlite's 5-second default and
    the first-open race becomes load-sensitive again — the defect
    `SCHEMA_LOCK_TIMEOUT_SECONDS` documents.
    """
    return {"timeout": float(SCHEMA_LOCK_TIMEOUT_SECONDS)}


@contextmanager
def exclusive_schema_lock(engine: Engine) -> Iterator[Connection]:
    """Yield a connection holding SQLite's EXCLUSIVE write lock, committed on
    a clean exit.

    `BEGIN EXCLUSIVE` takes the lock IMMEDIATELY (unlike the default deferred
    begin, which takes it at the first write — far too late, since the probe
    that decides whether to write happens before that). A sibling process
    executing the same statement gets SQLITE_BUSY and pysqlite's busy handler
    retries it until the lock frees. Callers MUST build their engine with
    `schema_lock_connect_args()`, so that handler has
    `SCHEMA_LOCK_TIMEOUT_SECONDS` rather than pysqlite's undeclared five-second
    default — see that constant for the gate run where five was not enough.

    The body must therefore contain BOTH halves of every check-then-create
    pair. Splitting them across two locks would be no better than no lock at
    all.

    `PRAGMA journal_mode` must NOT be set in here: SQLite refuses a journal-mode
    change inside a transaction. Callers set their PRAGMAs on a separate
    connection after this block.

    If the body raises, `commit()` is skipped and the connection context
    manager rolls back and closes; the exception propagates untouched. This
    module never handles a database error — the stores' own `SQLAlchemyError`
    handling is the single level, and adding a second one here would hide a
    corrupt database behind a silent retry.
    """
    with engine.connect() as conn:
        conn.exec_driver_sql("BEGIN EXCLUSIVE")
        yield conn
        conn.commit()


#: Seconds ONE `PRAGMA journal_mode=WAL` attempt is given before it is retried.
#:
#: Deliberately short, because the connection's 30-second busy timeout does NOT
#: protect this statement and a long attempt therefore buys nothing. Measured on
#: this machine (sqlite 3.50.4): with `connect(timeout=30)` in force, one
#: connection converting a rollback-journal file while 24 ordinary
#: `BEGIN EXCLUSIVE` writers queued on it was refused with
#: `database is locked` after 1.03 SECONDS — 29 of its 30 seconds unspent —
#: while every one of those 24 writers went on to succeed, the last at 3.33s.
#: Repeated at a 10-second timeout it gave up at 2.13s. The busy handler is
#: invoked (a single static reader does make it wait the whole timeout), but
#: under a queue of writers the conversion abandons almost at once, so the
#: retry has to be OURS.
WAL_ATTEMPT_TIMEOUT_SECONDS = 1.0

#: Total wall clock spent getting the file into WAL before giving up.
#:
#: The same 30 seconds the schema lock gets, and for the same reason: on an idle
#: machine the whole thing is over in milliseconds, so the ceiling costs a
#: healthy run nothing and only spends time that would otherwise be a dead
#: character.
WAL_TOTAL_BUDGET_SECONDS = float(SCHEMA_LOCK_TIMEOUT_SECONDS)

#: Backoff between attempts: doubles, capped. Randomless on purpose — the
#: attempts are already staggered by the work each sibling does around them.
WAL_RETRY_INITIAL_SECONDS = 0.05
WAL_RETRY_MAX_SECONDS = 1.0


def _backing_file(engine: Engine) -> str:
    """The path SQLite itself reports for the `main` database, `''` for none.

    Asked of SQLite rather than parsed out of the engine URL, because the URL
    has several spellings for the same thing (`sqlite://`, `sqlite:///:memory:`)
    and the question being asked — is there a file for siblings to share? — is
    one SQLite answers directly.
    """
    with engine.connect() as conn:
        row = conn.exec_driver_sql("PRAGMA database_list").first()
        return str(row[2]) if row is not None else ""


def enable_wal(engine: Engine) -> None:
    """Put the shared file into WAL with `synchronous=NORMAL`, tolerating a lost
    race but not a database that never gets there.

    ONE implementation for both stores, because both open the same file and both
    were exposed identically.

    WHY THIS IS NOT A PLAIN `conn.execute("PRAGMA journal_mode=WAL")`
    ----------------------------------------------------------------
    Converting a rollback-journal file to WAL needs an instant in which no other
    connection holds any lock on it. `play --all` gives it the opposite: five
    children open the same path within about a second, and each one takes the
    exclusive schema lock on its way past. Two facts, both measured rather than
    read (sqlite 3.50.4):

    * The 30-second busy timeout does not save this statement. Under a queue of
      writers it was refused after 1.03s of a 30s budget while all 24 of those
      writers succeeded — see `WAL_ATTEMPT_TIMEOUT_SECONDS`. Everything else in
      the open sequence IS protected: an ordinary `BEGIN IMMEDIATE` writer and
      `PRAGMA synchronous` both go straight through a held read lock that
      refuses the journal-mode change outright.
    * Losing is harmless AS LONG AS SOMEBODY WINS. WAL is a persistent property
      of the FILE, so the first sibling to convert converts it for all of them,
      and a later attempt against an already-WAL file returns 'wal' instantly —
      it needs no exclusivity, because there is nothing left to convert. That
      makes the statement its own postcondition check, which matters: the QUERY
      form `PRAGMA journal_mode` is STALE on a connection opened before the
      conversion (measured: it still answered 'delete' after a sibling had
      converted), so confirming the outcome by reading it would raise on a file
      that is already correct.

    So each attempt runs under a SHORT busy timeout and the retry is ours. Only
    `OperationalError` is caught, and only around this one statement; a refusal
    is not a broken database, it is a sibling holding the file. The timeout is
    restored before the connection goes back to the pool, or every later write
    would silently inherit the short one
    (`test_learning_store_connections_carry_the_declared_timeout` pins that).

    Exhausting the budget still RAISES. A FILE nobody converted in 30 seconds is
    not a lost race, it is a database no sibling can write either. A database
    with no file behind it is a different thing entirely and returns at once —
    see `_backing_file`.
    """
    shared_file = _backing_file(engine)
    if not shared_file:
        # Nothing to share, so nothing to protect: an in-memory database is
        # private to this process, no sibling can open it, and SQLite will never
        # report anything but 'memory' for it however often it is asked. This is
        # not an exotic case — `play`, `plan` and `combat_deficit_report` all
        # build `LearningStore(db_path=":memory:")` whenever learning is off, so
        # treating a non-'wal' answer as failure here would take down every
        # command that runs WITHOUT `--learn`.
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
            conn.commit()
        return

    attempt_ms = int(WAL_ATTEMPT_TIMEOUT_SECONDS * 1000)
    declared_ms = SCHEMA_LOCK_TIMEOUT_SECONDS * 1000
    deadline = time.monotonic() + WAL_TOTAL_BUDGET_SECONDS
    delay = WAL_RETRY_INITIAL_SECONDS
    # What to raise if the budget runs out, replaced by the real refusal as soon
    # as there is one. The default covers the other way the postcondition can
    # fail: SQLite DECLINING the change by returning the unchanged mode instead
    # of raising, which must not become `raise None`.
    failure: OperationalError | RuntimeError = RuntimeError(
        f"could not put {shared_file} into WAL within {WAL_TOTAL_BUDGET_SECONDS}s: "
        f"SQLite declined the journal-mode change without reporting an error")

    while True:
        with engine.connect() as conn:
            conn.exec_driver_sql(f"PRAGMA busy_timeout={attempt_ms}")
            try:
                mode = conn.exec_driver_sql("PRAGMA journal_mode=WAL").scalar()
            except OperationalError as exc:
                # A sibling holds the file. Not an error yet — the next attempt
                # either wins it or finds the sibling has already converted it.
                conn.rollback()
                failure, mode = exc, None
            # Restored BEFORE the connection goes back to the pool, on every
            # path. `PRAGMA busy_timeout` is a property of the CONNECTION, not
            # of a transaction, so leaving the short one set here would hand the
            # short timeout to every later write the store makes on it.
            conn.exec_driver_sql(f"PRAGMA busy_timeout={declared_ms}")
            if mode == "wal":
                conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
                conn.commit()
                return

        if time.monotonic() >= deadline:
            raise failure
        time.sleep(delay)
        delay = min(delay * 2, WAL_RETRY_MAX_SECONDS)
