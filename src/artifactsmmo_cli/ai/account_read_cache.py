"""AccountReadCache: one fleet-wide copy of each account-scoped API read.

`/my/grandexchange/orders`, `/my/bank` + `/my/bank/items` and
`/my/pending_items` return the same answer to every character on the account,
and they all bill the ACCOUNT rate bucket, the tightest one the API declares.
Read per character, per cycle, they cost the fleet five times what the
information is worth; live 2026-09-25, the per-cycle GE-order poll alone
parked three children in `_acquire_account` for 18 minutes.

Entries live in a table of the shared coordination DB, so a read by any child
serves every sibling until it goes stale.
"""

import sqlite3
import time
from collections.abc import Callable

from artifactsmmo_cli.utils.request_log import BUSY_TIMEOUT_SECONDS

KEYS = ("ge_open_orders", "bank", "pending_items")
"""Every key this cache holds. The TTL divides the idle budget between them."""

IDLE_SHARE = 0.5
"""Fraction of the account bucket that idle (unforced) refreshes may spend,
across all keys together. The rest is left for forced reads: the fresh fetch a
character makes right after it changes the resource itself."""


class AccountReadCache:
    """Fleet-shared, TTL'd cache of account-scoped reads, keyed by resource.

    TTL IS DERIVED FROM THE BUDGET, not picked. Each key's share of the idle
    budget is `IDLE_SHARE / len(KEYS)` of the account bucket's sustainable
    rate. A key whose fetch costs `cost` requests therefore may refresh once
    every `cost * len(KEYS) * account_interval / IDLE_SHARE` seconds. `cost` is
    what the key's last fetch actually spent, so a bank that grows a second
    page gets a longer TTL on its own.

    SINGLE-FLIGHT. A stale lookup hands the caller a refresh lease and returns
    None ("you fetch"). While that lease runs, siblings are served the stale
    payload instead of fetching too. A cold key (never fetched) has nothing
    stale to serve, so concurrent cold lookups may each fetch once.
    """

    def __init__(self, db_path: str, owner: str, account_interval: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._owner = owner
        self._interval = account_interval
        self._clock = clock
        # isolation_level=None + explicit BEGIN IMMEDIATE: `lookup` reads the
        # row and takes the lease in one write-locked transaction, so two
        # siblings cannot both see "stale, nobody refreshing" and both fetch.
        self._conn = sqlite3.connect(db_path, timeout=BUSY_TIMEOUT_SECONDS,
                                     isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS account_reads ("
            "key TEXT PRIMARY KEY, payload TEXT, fetched_at REAL, cost INTEGER,"
            " refreshing_until REAL, refresher TEXT)")

    def ttl(self, cost: int) -> float:
        """Seconds a payload that took `cost` requests to fetch stays fresh."""
        return cost * len(KEYS) * self._interval / IDLE_SHARE

    def lookup(self, key: str) -> str | None:
        """The payload to use, or None when THIS caller must fetch and
        `publish`. A None also hands this caller the refresh lease."""
        self._check(key)
        now = self._clock()
        self._conn.execute("BEGIN IMMEDIATE")
        try:
            row = self._conn.execute(
                "SELECT payload, fetched_at, cost, refreshing_until, refresher "
                "FROM account_reads WHERE key = ?", (key,)).fetchone()
            if row is not None and row[0] is not None:
                payload, fetched_at, cost, refreshing_until, refresher = row
                if now - fetched_at < self.ttl(cost):
                    return str(payload)
                if (refreshing_until is not None and refreshing_until > now
                        and refresher != self._owner):
                    return str(payload)
            # The lease lasts one TTL of the last known cost: long enough to
            # cover a fetch that waits on the account governor, and a crashed
            # refresher delays the next refresh by at most that much.
            lease_cost = row[2] if row is not None and row[2] is not None else 1
            self._conn.execute(
                "INSERT INTO account_reads (key, refreshing_until, refresher) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET refreshing_until = excluded.refreshing_until,"
                " refresher = excluded.refresher",
                (key, now + self.ttl(lease_cost), self._owner))
            return None
        finally:
            self._conn.execute("COMMIT")

    def publish(self, key: str, payload: str, cost: int) -> None:
        """Store a fresh fetch that cost `cost` requests, and end any lease."""
        self._check(key)
        self._conn.execute(
            "INSERT INTO account_reads (key, payload, fetched_at, cost, refreshing_until, refresher) "
            "VALUES (?, ?, ?, ?, NULL, NULL) "
            "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload,"
            " fetched_at = excluded.fetched_at, cost = excluded.cost,"
            " refreshing_until = NULL, refresher = NULL",
            (key, payload, self._clock(), cost))

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _check(key: str) -> None:
        if key not in KEYS:
            raise ValueError(f"unknown account read {key!r}; known: {KEYS}")
