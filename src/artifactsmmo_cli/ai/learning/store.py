"""SQLModel-backed learning store for autoregressive GOAP planning."""

import statistics
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine, select

from artifactsmmo_cli.ai.learning.models import Cycle, Session


class LearningStore:
    """Event log + queryable learned stats. Best-effort: errors degrade to defaults."""

    def __init__(self, db_path: str, character: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)

        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()

        self._character = character
        self._session_id: str | None = None

    def start_session(self) -> str:
        """Begin a new session; insert Session row, return session_id."""
        self._session_id = datetime.now(tz=timezone.utc).strftime("session-%Y%m%d-%H%M%S-%f")
        with SqlSession(self._engine) as s:
            s.add(Session(
                session_id=self._session_id,
                started_at=datetime.now(tz=timezone.utc).isoformat(),
                character=self._character,
            ))
            s.commit()
        return self._session_id

    def end_session(self, exit_reason: str = "normal") -> None:
        """Mark current session ended. No-op if no session was started."""
        if self._session_id is None:
            return
        with SqlSession(self._engine) as s:
            row = s.get(Session, self._session_id)
            if row is not None:
                row.ended_at = datetime.now(tz=timezone.utc).isoformat()
                row.exit_reason = exit_reason
                s.add(row)
                s.commit()
        self._session_id = None

    def record_cycle(self, cycle: Cycle) -> None:
        """Insert one validated Cycle row. Best-effort: SQLAlchemyError caught, never raised."""
        if self._session_id is None:
            return
        cycle.session_id = self._session_id
        cycle.character = self._character
        try:
            with SqlSession(self._engine) as s:
                s.add(cycle)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_cycle failed: {e}")

    def action_cost(self, action_repr: str, default: float, window: int = 50) -> float:
        """Median actual_cooldown_seconds over last `window` ok cycles, or default if < 5 samples."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.actual_cooldown_seconds)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                        Cycle.outcome == "ok",
                        Cycle.actual_cooldown_seconds.is_not(None),
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if len(rows) < 5:
                return default
            return statistics.median(rows)
        except SQLAlchemyError:
            return default

    def success_rate(self, action_repr: str, window: int = 50) -> float:
        """Fraction of last `window` cycles with outcome=='ok'. 1.0 if < 5 samples."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.outcome)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                    )
                    .order_by(Cycle.ts.desc())
                    .limit(window)
                )
                outcomes = list(s.exec(stmt))
            if len(outcomes) < 5:
                return 1.0
            return sum(1 for o in outcomes if o == "ok") / len(outcomes)
        except SQLAlchemyError:
            return 1.0

    def close(self) -> None:
        self._engine.dispose()
