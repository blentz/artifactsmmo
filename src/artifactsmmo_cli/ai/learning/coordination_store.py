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

import weakref
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


def _require_utc(now: datetime) -> None:
    """Guard the ONE invariant the whole TTL/liveness design rests on.

    Every liveness decision here (`claim`'s expiry check, `live_leases`'
    filter, `_expiry`'s stored value) compares `expires_at` and `stamp` as
    ISO 8601 STRINGS, lexicographically (`expires_at > stamp`), never as
    parsed datetimes. That comparison only agrees with true temporal order
    when every `now` that ever produced one of those strings is a UTC,
    timezone-aware datetime:

    - A naive datetime's `.isoformat()` carries no offset at all
      ("2026-08-01T00:00:00"), so it can't be compared against an aware
      string in any consistent way.
    - A non-UTC-but-aware datetime's `.isoformat()` sorts by its LOCAL
      wall-clock digits, not by the instant it names — e.g. an instant at
      "+05:00" prints an earlier-looking clock time than the same instant
      converted to UTC, so its string can sort as "older" than a genuinely
      earlier UTC timestamp. Mixing offsets would silently corrupt every
      lease's expiry comparison.

    Both failure modes are silent (no exception without this guard) and
    would corrupt every liveness decision in `CoordinationStore` — leases
    expiring early or never. This project's rule is to fail loudly on bad
    input rather than coerce it (e.g. assuming a naive datetime means UTC),
    so both cases raise `ValueError` naming the actual problem instead of
    being normalised.
    """
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError(
            f"CoordinationStore requires a timezone-aware UTC datetime; got a naive "
            f"datetime {now!r}. A naive datetime's isoformat() carries no offset, so "
            f"expires_at > stamp string comparisons cannot be trusted."
        )
    if now.utcoffset() != timedelta(0):
        raise ValueError(
            f"CoordinationStore requires a UTC datetime (offset +00:00); got {now!r} "
            f"with offset {now.utcoffset()}. A non-UTC offset's isoformat() sorts by "
            f"local wall-clock digits, not by the instant it names, which silently "
            f"corrupts the expires_at > stamp lexicographic comparison."
        )


class CoordinationStore:
    """Lease + demand board over the shared learning DB. Cross-character reads
    live here and nowhere else."""

    def __init__(self, db_path: str, character: str) -> None:
        self._engine = create_engine(f"sqlite:///{db_path}")
        # Dispose the engine's pooled SQLite connection when this store is
        # garbage-collected, so callers that forget close() don't leak a
        # connection (raises ResourceWarning). Bound to the engine, not self —
        # mirrors LearningStore.__init__.
        self._finalizer = weakref.finalize(self, self._engine.dispose)
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
        _require_utc(now)
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
        _require_utc(now)
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
        _require_utc(now)
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
