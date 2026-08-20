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

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Connection, Engine

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
