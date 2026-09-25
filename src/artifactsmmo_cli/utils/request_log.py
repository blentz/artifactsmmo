"""RequestLog: the fleet's shared record of rate-limited requests, in SQLite.

ArtifactsMMO applies its rate limits PER IP, so every `play --all` child draws
from one budget. A per-process history can only police a static slice of that
budget; this log lets every child see every sibling's requests, so the fleet as
a whole is held to the real limit and an idle child's share is usable by a busy
one.
"""

import sqlite3
from collections.abc import Mapping, Sequence

BUSY_TIMEOUT_SECONDS = 30.0
"""How long a connection waits for a sibling's write lock before SQLite raises.
Each transaction here is a handful of indexed statements, so a sibling holds the
lock for milliseconds; the timeout only has to outlast a burst of them."""


def longest_wait(history: Sequence[float], now: float, windows: Mapping[float, int]) -> float:
    """Seconds until every window has room for one more request. 0.0 when a
    request may go now. `history` is ascending request timestamps."""
    wait = 0.0
    for span, limit in windows.items():
        recent = [t for t in history if now - t < span]
        if len(recent) >= limit:
            # The oldest request inside this window must age out of it.
            wait = max(wait, recent[-limit] + span - now)
    return wait


class RequestLog:
    """Timestamps of recent requests per bucket, shared through one SQLite file.

    Timestamps come from the caller's clock, which must be WALL time: the log
    outlives processes AND reboots (it sits in the persistent learning DB).
    `time.monotonic` restarts at zero on boot, and live 2026-09-25 that left
    every stored entry in the future, counted in every window forever, and
    blocked the whole fleet in `_initialize`. A timestamp later than `now`
    cannot be a real past request (the clock went backwards), so it is dropped
    with the expired ones."""

    def __init__(self, db_path: str) -> None:
        # isolation_level=None: this class issues its own BEGIN IMMEDIATE, which
        # takes the write lock BEFORE the window count. The count and the insert
        # therefore see the same history, even with siblings racing.
        self._conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS,
                                     isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS rate_requests (bucket TEXT NOT NULL, ts REAL NOT NULL)")
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS ix_rate_requests_bucket_ts ON rate_requests (bucket, ts)")

    def try_record(self, bucket: str, now: float, windows: Mapping[float, int]) -> float:
        """Record one request at `now` and return 0.0 if every window has room.
        Otherwise record nothing and return the seconds to wait."""
        longest = max(windows, default=0.0)
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            self._conn.execute(
                "DELETE FROM rate_requests WHERE bucket = ? AND (ts <= ? OR ts > ?)",
                (bucket, now - longest, now))
            history = [row[0] for row in self._conn.execute(
                "SELECT ts FROM rate_requests WHERE bucket = ? ORDER BY ts", (bucket,))]
            wait = longest_wait(history, now, windows)
            if wait <= 0.0:
                self._conn.execute(
                    "INSERT INTO rate_requests (bucket, ts) VALUES (?, ?)", (bucket, now))
        finally:
            # COMMIT on the error path too: a failed statement must not leave
            # the write lock held and stall every sibling.
            self._conn.execute("COMMIT")
        return wait

    def close(self) -> None:
        self._conn.close()
