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


@contextmanager
def exclusive_schema_lock(engine: Engine) -> Iterator[Connection]:
    """Yield a connection holding SQLite's EXCLUSIVE write lock, committed on
    a clean exit.

    `BEGIN EXCLUSIVE` takes the lock IMMEDIATELY (unlike the default deferred
    begin, which takes it at the first write — far too late, since the probe
    that decides whether to write happens before that). A sibling process
    executing the same statement gets SQLITE_BUSY and pysqlite's busy handler
    retries it until the lock frees; first-open schema work on an empty file
    costs milliseconds, so the queue drains well inside the default five-second
    busy timeout.

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
