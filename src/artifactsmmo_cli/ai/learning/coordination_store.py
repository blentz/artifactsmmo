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
