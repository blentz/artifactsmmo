"""SQLModel-backed learning store for autoregressive GOAP planning."""

import json
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

from sqlalchemy import func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, col, create_engine, select

from artifactsmmo_cli.ai.learning.models import (
    Blocker,
    CombatLoadoutOutcome,
    CraftYieldObservation,
    Cycle,
    LearnedSetting,
    LoadoutProfileObservation,
    PlanBodyLog,
    PlanBodyLogBase,
    PlanCommitment,
    PlanCommitmentBase,
    Session,
    SkillXpObservation,
    TaskRewardObservation,
)
from artifactsmmo_cli.ai.learning.store_warmup_core import (
    WARMUP_MIN_SAMPLES,
    warmup_gated_median,
    warmup_gated_success_rate,
)
from artifactsmmo_cli.ai.learning.types import ActionStats, GoalStats

_T = TypeVar("_T")


@dataclass(frozen=True)
class CombatLoadoutOutcomeRow:
    """Decoupled pure-data row returned by LearningStore.combat_loadout_outcomes().

    Callers see parsed Python types (loadout as dict, bools as bool) and never
    the SQLModel table row or raw JSON. Pure data; exempt from one-class-per-file.
    """

    character: str
    task_key: str
    loadout: dict[str, str]
    predicted_win: bool
    actual_win: bool


def _parse_skill_xp_value(raw: str | None, skill: str) -> int:
    """Extract one skill's per-cycle xp delta from a stored JSON row.

    Returns 0 when the row is None, malformed JSON, not a dict, or holds a
    non-numeric value for `skill`. Mirrors `projections._parse_skill_xp`'s
    tolerance so a single bad row never crashes the average.
    """
    if raw is None:
        return 0
    try:
        delta = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
    if not isinstance(delta, dict):
        return 0
    try:
        return int(delta.get(skill, 0))
    except (TypeError, ValueError):
        return 0


class LearningStore:
    """Event log + queryable learned stats. Best-effort: errors degrade to defaults."""

    # Default lookback window over recent action cycles (cost/success/effect stats).
    WINDOW_ACTION = 50
    # Default lookback window over recent goal completions (cycles-to-satisfy stats).
    WINDOW_GOAL = 20
    # Default lookback window over recent cycles for trend queries (goal history, skill XP).
    WINDOW_RECENT = 100

    def __init__(self, db_path: str, character: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{db_path}")
        # Dispose the engine's pooled SQLite connection when this store is
        # garbage-collected, so callers that forget close() don't leak a
        # connection (raises ResourceWarning). Bound to the engine, not self.
        self._finalizer = weakref.finalize(self, self._engine.dispose)
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
            # Consumable batch-cook migration (2026-07-05): the column shipped
            # in the model without a matching one-shot ALTER, so pre-existing
            # DBs failed EVERY record_cycle INSERT ("table cycles has no
            # column named consumables_expended_json") — learning silently
            # dead since the batch-cook merge on old caches.
            if cols and "consumables_expended_json" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cycles ADD COLUMN consumables_expended_json TEXT NOT NULL DEFAULT '{}'"
                )
            conn.commit()

        self._character = character
        self._session_id: str | None = None
        self._session_row_written: bool = False
        self._search_cache: dict[tuple[object, ...], object] | None = None

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

    @contextmanager
    def search_cache(self) -> Iterator[None]:
        """Memoize learned-stat queries (action_cost median / success_rate /
        goal_avg_cycles_to_satisfy) for the duration of one planner search. Safe
        because the DB is not written during planning. Reentrant: a nested
        enter reuses the outer cache; the original cache is restored on exit."""
        prev = self._search_cache
        if prev is None:
            self._search_cache = {}
        try:
            yield
        finally:
            self._search_cache = prev

    def _cached(self, key: tuple[object, ...], compute: Callable[[], _T]) -> _T:
        if self._search_cache is None:
            return compute()
        if key not in self._search_cache:
            self._search_cache[key] = compute()
        return self._search_cache[key]  # type: ignore[return-value]

    def action_cost(self, action_repr: str, default: float, window: int = WINDOW_ACTION) -> float:
        """Median actual_cooldown_seconds over last `window` ok cycles, or default if < 5 samples."""
        median = self._cached(
            ("action_cost", action_repr, window),
            lambda: self._action_cost_median(action_repr, window),
        )
        return median if median is not None else default

    def _action_cost_median(self, action_repr: str, window: int) -> float | None:
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
            return warmup_gated_median(non_null)
        except SQLAlchemyError:
            return None

    def action_class_cost(self, action_class: str, default: float,
                          window: int = WINDOW_ACTION) -> float:
        """Median actual_cooldown_seconds over the last `window` ok cycles of a
        given ACTION TYPE (e.g. "FightAction", "MovementAction",
        "DepositAllAction"), or `default` if < 5 samples.

        Per-action-TYPE cooldown is what the #16 strategic_value weights consume:
        the cooldown-seconds-saved commensuration reads the learned typical fight
        / move / deposit cooldown from gameplay rather than assuming a static
        figure (no fight-cooldown formula exists in the API). Companion to
        `action_cost`, which keys on the specific `action_repr`."""
        median = self._cached(
            ("action_class_cost", action_class, window),
            lambda: self._action_class_cost_median(action_class, window),
        )
        return median if median is not None else default

    def _action_class_cost_median(self, action_class: str, window: int) -> float | None:
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.actual_cooldown_seconds)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_class == action_class,
                        Cycle.outcome == "ok",
                        col(Cycle.actual_cooldown_seconds).is_not(None),
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            non_null = [r for r in rows if r is not None]
            return warmup_gated_median(non_null)
        except SQLAlchemyError:
            return None

    def action_class_fraction(self, action_class: str,
                              window: int = WINDOW_ACTION) -> float:
        """Fraction of the last `window` ok cycles whose `action_class` matches —
        the observed ACTION-MIX frequency. 0.0 when no ok cycles are recorded.

        #16 strategic_value frequency-weighting: a wisdom point helps on every
        FIGHT cycle, a bag on every BANK-TRIP cycle, so their cooldown-seconds-
        saved rates must be weighted by HOW OFTEN each action type actually runs.
        That frequency is learned here from the action mix rather than derived
        from an (untracked) char-level xp curve."""
        return self._cached(
            ("action_class_fraction", action_class, window),
            lambda: self._action_class_fraction_uncached(action_class, window),
        )

    def _action_class_fraction_uncached(self, action_class: str, window: int) -> float:
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.action_class)
                    .where(
                        Cycle.character == self._character,
                        Cycle.outcome == "ok",
                        col(Cycle.action_class).is_not(None),
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if not rows:
                return 0.0
            match = sum(1 for r in rows if r == action_class)
            return match / len(rows)
        except SQLAlchemyError:
            return 0.0

    def success_rate(self, action_repr: str, window: int = WINDOW_ACTION) -> float:
        """Fraction of last `window` cycles with outcome=='ok'. 1.0 if < 5 samples."""
        return self._cached(
            ("success_rate", action_repr, window),
            lambda: self._success_rate_uncached(action_repr, window),
        )

    def _success_rate_uncached(self, action_repr: str, window: int) -> float:
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
            return warmup_gated_success_rate(outcomes)
        except SQLAlchemyError:
            return 1.0

    def hp_healed_per_fight(self, monster_code: str,
                            restore_of: Callable[[str], int],
                            window: int = WINDOW_ACTION) -> float | None:
        """Mean HP-healed per WON Fight(monster) over the last `window`; None below
        WARMUP_MIN_SAMPLES. hp_healed per row = sum(qty * restore_of(code)) over the
        cycle's consumables_expended_json (empty -> 0). `restore_of` supplies the
        per-code restore so the store stays GameData-free."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.consumables_expended_json)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == f"Fight({monster_code})",
                        Cycle.outcome == "ok",
                    )
                    .order_by(col(Cycle.ts).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
        except SQLAlchemyError:
            return None
        if len(rows) < WARMUP_MIN_SAMPLES:
            return None
        healed: list[float] = []
        for raw in rows:
            consumed = json.loads(raw) if raw else {}
            healed.append(float(sum(qty * restore_of(code) for code, qty in consumed.items())))
        return sum(healed) / len(healed)

    _ALLOWED_EFFECT_FIELDS = ("delta_gold", "delta_xp", "delta_hp", "delta_inv_used")

    def action_effect(self, action_repr: str, field: str, window: int = WINDOW_ACTION) -> float | None:
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
            return warmup_gated_median(non_null)
        except SQLAlchemyError:
            return None

    def goal_avg_cycles_to_satisfy(self, goal_repr: str, window: int = WINDOW_GOAL) -> float | None:
        """Median cycles-to-satisfy over last `window` completions. None if < 5 samples."""
        return self._cached(
            ("goal_avg", goal_repr, window),
            lambda: self._goal_avg_cycles_uncached(goal_repr, window),
        )

    def _goal_avg_cycles_uncached(self, goal_repr: str, window: int) -> float | None:
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
            return warmup_gated_median(non_null)
        except SQLAlchemyError:
            return None

    def recent_goal_cycles(self, goal_repr: str, window: int = WINDOW_RECENT) -> list[Cycle]:
        """Return up to `window` most recent Cycle rows where selected_goal=goal_repr
        for the store's character. Newest first.

        Phase G-B projections aggregate over these rows in pure Python so the
        scoring math stays testable with synthetic Cycle lists.
        """
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle)
                    .where(
                        col(Cycle.character) == self._character,
                        col(Cycle.selected_goal) == goal_repr,
                    )
                    .order_by(col(Cycle.id).desc())
                    .limit(window)
                )
                return list(s.exec(stmt))
        except SQLAlchemyError:
            return []

    def recent_selected_goals(self, window: int) -> list[str]:
        """Return up to `window` most recent non-None Cycle.selected_goal values for
        this character, newest first.  Used by loadout_profiles._recent_task_keys to
        parse combat/gather keys from recent activity without filtering by a specific
        goal repr."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.selected_goal)
                    .where(
                        col(Cycle.character) == self._character,
                        col(Cycle.selected_goal).is_not(None),
                    )
                    .order_by(col(Cycle.id).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            return [r for r in rows if r is not None]
        except SQLAlchemyError:
            return []

    def skill_xp_per_cycle(self, skill: str, window: int = WINDOW_RECENT) -> float | None:
        """Mean positive per-cycle XP gain for `skill` over the most recent `window` cycles.

        Only cycles with a positive delta for the given skill are included.
        Returns None when no such data exists (caller falls back to a default).
        Malformed `delta_skill_xp_json` rows are skipped (matching the guard in
        `projections._parse_skill_xp`) so they do not crash the average.
        """
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.delta_skill_xp_json)
                    .where(col(Cycle.character) == self._character)
                    .order_by(col(Cycle.id).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            values: list[int] = []
            for raw in rows:
                xp = _parse_skill_xp_value(raw, skill)
                if xp > 0:
                    values.append(xp)
            if not values:
                return None
            return float(sum(values)) / len(values)
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

    def win_count(self, action_repr: str) -> int:
        """Number of cycles with outcome=='ok' recorded for this action_repr. The raw
        (NOT warmup-gated) success tally — `success_rate` returns 1.0 below 5 samples,
        so it cannot distinguish a single win from a single loss; the monotonic-win
        winnability inference needs the unsmoothed count."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.id)
                    .where(
                        Cycle.character == self._character,
                        Cycle.action_repr == action_repr,
                        Cycle.outcome == "ok",
                    )
                )
                return len(list(s.exec(stmt)))
        except SQLAlchemyError:
            return 0

    def action_stats(self, action_repr: str, window: int = WINDOW_ACTION) -> ActionStats:
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

    def goal_stats(self, goal_repr: str, window: int = WINDOW_GOAL) -> GoalStats:
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
            avg = warmup_gated_median(satisfied)
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

    def set_blocker(self, blocker_code: str, unlock_monster: str | None,
                     required_level: int) -> None:
        """Upsert a learned blocker for this character. Persists across sessions."""
        try:
            with SqlSession(self._engine) as s:
                existing = s.get(Blocker, blocker_code)
                if existing is not None and existing.character == self._character:
                    existing.unlock_monster = unlock_monster
                    existing.required_level = required_level
                    existing.discovered_at = datetime.now(tz=timezone.utc).isoformat()
                    s.add(existing)
                else:
                    s.add(Blocker(
                        blocker_code=blocker_code,
                        character=self._character,
                        unlock_monster=unlock_monster,
                        required_level=required_level,
                        discovered_at=datetime.now(tz=timezone.utc).isoformat(),
                    ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] set_blocker failed: {e}")

    def get_blocker(self, blocker_code: str) -> Blocker | None:
        """Return the persisted blocker for this character, or None."""
        try:
            with SqlSession(self._engine) as s:
                b = s.get(Blocker, blocker_code)
                if b is not None and b.character == self._character:
                    return b
                return None
        except SQLAlchemyError:
            return None

    def delete_blocker(self, blocker_code: str) -> None:
        """Remove a persisted blocker for this character (e.g. a stale bank lock
        recorded against a gated bank when an open bank is actually available)."""
        try:
            with SqlSession(self._engine) as s:
                b = s.get(Blocker, blocker_code)
                if b is not None and b.character == self._character:
                    s.delete(b)
                    s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] delete_blocker failed: {e}")

    def record_skill_max_xp(self, skill: str, level: int, max_xp: int) -> None:
        """Upsert observed max_xp for (self._character, skill, level). Last write wins."""
        try:
            with SqlSession(self._engine) as s:
                stmt = select(SkillXpObservation).where(
                    SkillXpObservation.character == self._character,
                    SkillXpObservation.skill == skill,
                    SkillXpObservation.level == level,
                )
                existing = s.exec(stmt).first()
                if existing is not None:
                    existing.max_xp = max_xp
                    s.add(existing)
                else:
                    s.add(SkillXpObservation(
                        character=self._character,
                        skill=skill,
                        level=level,
                        max_xp=max_xp,
                    ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_skill_max_xp failed: {e}")

    def skill_max_xp_observations(self, skill: str) -> dict[int, int]:
        """Return {level: max_xp} for all observed (self._character, skill) rows."""
        try:
            with SqlSession(self._engine) as s:
                stmt = select(SkillXpObservation).where(
                    SkillXpObservation.character == self._character,
                    SkillXpObservation.skill == skill,
                )
                rows = list(s.exec(stmt))
            return {row.level: row.max_xp for row in rows}
        except SQLAlchemyError:
            return {}

    def record_craft_yield(self, item_code: str, quantity: int, xp: int) -> None:
        """Upsert observed (quantity, xp) for (character, item_code). Last write wins."""
        try:
            with SqlSession(self._engine) as s:
                stmt = select(CraftYieldObservation).where(
                    CraftYieldObservation.character == self._character,
                    CraftYieldObservation.item_code == item_code,
                )
                existing = s.exec(stmt).first()
                if existing is not None:
                    existing.quantity = quantity
                    existing.xp = xp
                    s.add(existing)
                else:
                    s.add(CraftYieldObservation(
                        character=self._character,
                        item_code=item_code,
                        quantity=quantity,
                        xp=xp,
                    ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_craft_yield failed: {e}")

    def observed_craft_yield(self, item_code: str) -> tuple[int, int] | None:
        """Observed (quantity, xp) for (character, item_code), or None."""
        try:
            with SqlSession(self._engine) as s:
                stmt = select(CraftYieldObservation).where(
                    CraftYieldObservation.character == self._character,
                    CraftYieldObservation.item_code == item_code,
                )
                row = s.exec(stmt).first()
            return (row.quantity, row.xp) if row is not None else None
        except SQLAlchemyError:
            return None

    def record_loadout_profile(self, task_key: str, loadout: dict[str, str]) -> None:
        """Upsert the loadout for (character, task_key). Last write wins. Best-effort."""
        try:
            with SqlSession(self._engine) as s:
                stmt = select(LoadoutProfileObservation).where(
                    LoadoutProfileObservation.character == self._character,
                    LoadoutProfileObservation.task_key == task_key,
                )
                existing = s.exec(stmt).first()
                encoded = json.dumps(loadout, sort_keys=True)
                if existing is not None:
                    existing.loadout = encoded
                    s.add(existing)
                else:
                    s.add(LoadoutProfileObservation(
                        character=self._character, task_key=task_key, loadout=encoded))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_loadout_profile failed: {e}")

    def loadout_profiles(self) -> dict[str, dict[str, str]]:
        """All stored {task_key: {slot: code}} for this character. Best-effort ({} on error)."""
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(select(LoadoutProfileObservation).where(
                    LoadoutProfileObservation.character == self._character)).all()
            return {r.task_key: json.loads(r.loadout) for r in rows}
        except SQLAlchemyError:
            return {}

    def record_task_reward_value(self, value: float) -> None:
        """Append one completed-task reward observation for this character."""
        try:
            with SqlSession(self._engine) as s:
                s.add(TaskRewardObservation(character=self._character, value=value))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_task_reward_value failed: {e}")

    def _task_reward_values(self) -> list[float]:
        """Return all recorded task reward values for this character."""
        try:
            with SqlSession(self._engine) as s:
                stmt = select(TaskRewardObservation).where(
                    TaskRewardObservation.character == self._character,
                )
                rows = list(s.exec(stmt))
            return [row.value for row in rows]
        except SQLAlchemyError:
            return []

    def task_reward_sample_count(self) -> int:
        """Number of completed-task reward observations for this character."""
        return len(self._task_reward_values())

    def mean_task_reward_value(self, default: float) -> float:
        """Mean reward value over all observations, or `default` if none recorded."""
        vals = self._task_reward_values()
        return sum(vals) / len(vals) if vals else default

    def record_combat_outcome(self, task_key: str, loadout: dict[str, str],
                              predicted_win: bool, actual_win: bool) -> None:
        """Append one fight outcome row. APPEND (calibration history); NOT upsert.
        Best-effort: SQLAlchemyError is caught and printed; never raised."""
        try:
            with SqlSession(self._engine) as s:
                s.add(CombatLoadoutOutcome(
                    character=self._character,
                    task_key=task_key,
                    loadout=json.dumps(loadout, sort_keys=True),
                    predicted_win=predicted_win,
                    actual_win=actual_win,
                ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_combat_outcome failed: {e}")

    def combat_loadout_outcomes(self) -> list[CombatLoadoutOutcomeRow]:
        """All recorded fight outcome rows for this character, insertion order.
        Best-effort: returns [] on SQLAlchemyError."""
        try:
            with SqlSession(self._engine) as s:
                rows = s.exec(select(CombatLoadoutOutcome).where(
                    CombatLoadoutOutcome.character == self._character)).all()
            return [
                CombatLoadoutOutcomeRow(
                    character=r.character,
                    task_key=r.task_key,
                    loadout=json.loads(r.loadout),
                    predicted_win=r.predicted_win,
                    actual_win=r.actual_win,
                )
                for r in rows
            ]
        except SQLAlchemyError:
            return []

    def close(self) -> None:
        self._engine.dispose()


    def get_learned_int(self, key: str, default: int) -> int:
        """Read a per-character int setting (e.g. `task_exchange_min_coins`).
        Returns `default` when the row is missing or any DB error fires —
        keeps the player loop alive on degraded storage."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(LearnedSetting).where(
                        LearnedSetting.character == self._character,
                        LearnedSetting.key == key,
                    )
                ).first()
                return int(row.value) if row is not None else default
        except SQLAlchemyError:
            return default

    def set_learned_int(self, key: str, value: int) -> None:
        """Upsert a per-character int setting. Persists across sessions so
        repeated re-discovery (e.g. the taskmaster's exchange cost via HTTP
        478 climbs) only pays its discovery rejections once per character."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(LearnedSetting).where(
                        LearnedSetting.character == self._character,
                        LearnedSetting.key == key,
                    )
                ).first()
                if row is not None:
                    row.value = int(value)
                    s.add(row)
                else:
                    s.add(LearnedSetting(
                        character=self._character, key=key, value=int(value),
                    ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] set_learned_int({key}) failed: {e}")

    def record_plan_body(self, goal_repr: str, head_action_repr: str,
                         body: list[str]) -> None:
        """Append a computed plan body. Best-effort; degraded storage must not
        kill the player loop."""
        try:
            with SqlSession(self._engine) as s:
                s.add(PlanBodyLog(
                    character=self._character,
                    session_id=self._session_id or "no-session",
                    ts=datetime.now(tz=timezone.utc).isoformat(),
                    goal_repr=goal_repr,
                    head_action_repr=head_action_repr,
                    body_json=json.dumps(body),
                ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_plan_body failed: {e}")

    def plan_bodies_for_goal(self, goal_repr: str) -> list[PlanBodyLogBase]:
        """All logged plan bodies for a goal repr (Phase-2 macro detector input)."""
        try:
            with SqlSession(self._engine) as s:
                return list(s.exec(
                    select(PlanBodyLog).where(
                        PlanBodyLog.character == self._character,
                        PlanBodyLog.goal_repr == goal_repr,
                    )
                ).all())
        except SQLAlchemyError:
            return []

    def save_plan_commitment(self, goal_repr: str, goal_json: str,
                             plan_reprs: list[str], cursor: int,
                             crafting_target: str | None,
                             latch_active: bool) -> None:
        """Upsert the single live commitment row for this character."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(PlanCommitment).where(
                        PlanCommitment.character == self._character)
                ).first()
                ts = datetime.now(tz=timezone.utc).isoformat()
                if row is not None:
                    row.goal_repr = goal_repr
                    row.goal_json = goal_json
                    row.plan_json = json.dumps(plan_reprs)
                    row.cursor = cursor
                    row.crafting_target = crafting_target
                    row.latch_active = latch_active
                    row.replanned_ts = ts
                    s.add(row)
                else:
                    s.add(PlanCommitment(
                        character=self._character, goal_repr=goal_repr,
                        goal_json=goal_json,
                        plan_json=json.dumps(plan_reprs), cursor=cursor,
                        crafting_target=crafting_target, latch_active=latch_active,
                        replanned_ts=ts,
                    ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] save_plan_commitment failed: {e}")

    def load_plan_commitment(self) -> PlanCommitmentBase | None:
        """Read the live commitment row, or None when absent / on DB error."""
        try:
            with SqlSession(self._engine) as s:
                return s.exec(
                    select(PlanCommitment).where(
                        PlanCommitment.character == self._character)
                ).first()
        except SQLAlchemyError:
            return None

    def update_commitment_cursor(self, cursor: int) -> None:
        """Advance the persisted cursor on the single live commitment row.
        No-op when no commitment row exists yet (or on DB error)."""
        try:
            with SqlSession(self._engine) as s:
                row = s.exec(
                    select(PlanCommitment).where(
                        PlanCommitment.character == self._character)
                ).first()
                if row is None:
                    return
                row.cursor = cursor
                s.add(row)
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] update_commitment_cursor failed: {e}")
