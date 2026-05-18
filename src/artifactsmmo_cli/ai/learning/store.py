"""SQLModel-backed learning store for autoregressive GOAP planning."""

import statistics
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, col, create_engine, select

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.learning.types import ActionStats, GoalStats


class LearningStore:
    """Event log + queryable learned stats. Best-effort: errors degrade to defaults."""

    def __init__(self, db_path: str, character: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)

        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            # Phase G-A migration: add delta_skill_xp_json to pre-existing
            # cycles tables. SQLModel.create_all only adds tables, not columns.
            # No Alembic in scope; one-shot ALTER is the simplest contract.
            cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(cycles)")}
            if cols and "delta_skill_xp_json" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cycles ADD COLUMN delta_skill_xp_json TEXT NOT NULL DEFAULT '{}'"
                )
            conn.commit()

        self._character = character
        self._session_id: str | None = None
        self._session_row_written: bool = False

    def start_session(self) -> str:
        """Allocate session_id. Actual Session row written lazily on first record_cycle."""
        self._session_id = datetime.now(tz=timezone.utc).strftime("session-%Y%m%d-%H%M%S-%f")
        self._session_row_written = False
        return self._session_id

    def _ensure_session_row(self) -> None:
        """Idempotent INSERT of the Session row before any Cycle row."""
        if self._session_row_written or self._session_id is None:
            return
        try:
            with SqlSession(self._engine) as s:
                s.add(Session(
                    session_id=self._session_id,
                    started_at=datetime.now(tz=timezone.utc).isoformat(),
                    character=self._character,
                ))
                s.commit()
            self._session_row_written = True
        except SQLAlchemyError as e:
            print(f"[learning] _ensure_session_row failed: {e}")

    def end_session(self, exit_reason: str = "normal") -> None:
        """Mark current session ended. No-op if no session was started or no cycle was recorded."""
        if self._session_id is None or not self._session_row_written:
            self._session_id = None
            return
        try:
            with SqlSession(self._engine) as s:
                row = s.get(Session, self._session_id)
                if row is not None:
                    n = s.exec(
                        select(func.count()).select_from(Cycle).where(Cycle.session_id == self._session_id)
                    ).one()
                    row.ended_at = datetime.now(tz=timezone.utc).isoformat()
                    row.exit_reason = exit_reason
                    row.cycle_count = int(n)
                    s.add(row)
                    s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] end_session failed: {e}")
        self._session_id = None

    def record_cycle(self, cycle: Cycle) -> None:
        """Insert one validated Cycle row. Best-effort: SQLAlchemyError caught, never raised."""
        if self._session_id is None:
            return
        self._ensure_session_row()
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
                        col(Cycle.actual_cooldown_seconds).is_not(None),
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            non_null = [r for r in rows if r is not None]
            if len(non_null) < 5:
                return default
            return statistics.median(non_null)
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
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                outcomes = list(s.exec(stmt))
            if len(outcomes) < 5:
                return 1.0
            return sum(1 for o in outcomes if o == "ok") / len(outcomes)
        except SQLAlchemyError:
            return 1.0

    _ALLOWED_EFFECT_FIELDS = ("delta_gold", "delta_xp", "delta_hp", "delta_inv_used")

    def action_effect(self, action_repr: str, field: str, window: int = 50) -> float | None:
        """Median of `field` over recent ok cycles. Allowed fields: delta_gold/delta_xp/delta_hp/delta_inv_used."""
        if field not in self._ALLOWED_EFFECT_FIELDS:
            return None
        field_col = getattr(Cycle, field)
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(field_col)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                        Cycle.outcome == "ok",
                        col(field_col).is_not(None),
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            non_null: list[float] = [float(r) for r in rows if r is not None]
            if len(non_null) < 5:
                return None
            return statistics.median(non_null)
        except SQLAlchemyError:
            return None

    def goal_avg_cycles_to_satisfy(self, goal_repr: str, window: int = 20) -> float | None:
        """Median cycles-to-satisfy over last `window` completions. None if < 5 samples."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.cycles_to_satisfy)
                    .where(
                        Cycle.character == self._character,
                        Cycle.selected_goal == goal_repr,
                        col(Cycle.cycles_to_satisfy).is_not(None),
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            non_null = [r for r in rows if r is not None]
            if len(non_null) < 5:
                return None
            return statistics.median(non_null)
        except SQLAlchemyError:
            return None

    def sample_count(self, action_repr: str) -> int:
        """Number of cycles recorded for this action_repr and the store's character."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.id)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                    )
                )
                return len(list(s.exec(stmt)))
        except SQLAlchemyError:
            return 0

    def action_stats(self, action_repr: str, window: int = 50) -> ActionStats:
        """Return one Pydantic-validated rollup for one action."""
        n = self.sample_count(action_repr)
        return ActionStats(
            action_repr=action_repr,
            sample_count=n,
            median_cost_seconds=(self.action_cost(action_repr, default=-1.0, window=window)
                                  if n >= 5 else None),
            success_rate=self.success_rate(action_repr, window=window),
            median_delta_xp=self.action_effect(action_repr, "delta_xp", window=window),
            median_delta_gold=self.action_effect(action_repr, "delta_gold", window=window),
        )

    def goal_stats(self, goal_repr: str, window: int = 20) -> GoalStats:
        """Return one Pydantic-validated rollup for one goal."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.cycles_to_satisfy)
                    .where(
                        Cycle.character == self._character,
                        Cycle.selected_goal == goal_repr,
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            sample_count = len(rows)
            satisfied = [r for r in rows if r is not None]
            sat_rate = (len(satisfied) / sample_count) if sample_count else 0.0
            avg = statistics.median(satisfied) if len(satisfied) >= 5 else None
            return GoalStats(
                goal_repr=goal_repr,
                sample_count=sample_count,
                avg_cycles_to_satisfy=avg,
                satisfaction_rate=sat_rate,
            )
        except SQLAlchemyError:
            return GoalStats(
                goal_repr=goal_repr,
                sample_count=0,
                avg_cycles_to_satisfy=None,
                satisfaction_rate=0.0,
            )

    def close(self) -> None:
        self._engine.dispose()
