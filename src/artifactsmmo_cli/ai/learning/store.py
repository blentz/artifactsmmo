"""SQLModel-backed learning store for autoregressive GOAP planning."""

import json
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
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
from artifactsmmo_cli.ai.learning.recovery_attribution import (
    attribute_forced_recovery,
)
from artifactsmmo_cli.ai.learning.schema_init import exclusive_schema_lock
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


def grind_action_prefix(skill: str) -> str:
    """The `action_repr` prefix every `LevelSkill` cycle for `skill` carries.

    `LevelSkill.__repr__` renders `LevelSkill({skill}->{target_level})`, so the
    TARGET is the only part that varies. Matching on the prefix therefore counts a
    `->5` grind and a `->10` grind as the same evidence about how fast this
    character gains xp in this skill, which is what they are; matching the exact
    string would silently drop half the observations."""
    return f"LevelSkill({skill}->"


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


MIN_DROP_KILLS = 50
"""Kills of one monster required before its OBSERVED drop rate replaces the
static API table.

Below this the estimate is noise, and noise here is expensive because it feeds a
cost the planner ranks on. Measured 2026-08-08: at n=199 `green_slime/apple`
read 0.60x its static rate — comfortably inside sampling error for p=0.083, and
taken literally a 40% price rise on every recipe using apples. At n>=700 the
observed rates sat within ~3% of static.

50 is a floor on ARRIVING at a usable number, not a claim that 50 is precise;
the fallback below it is the static table, which the same measurement shows is
close to right."""


class LearningStore:
    # How much raw stream to read to fill a window of ONE goal's cycles. Attribution
    # needs each recovery cycle's predecessor, so the query can no longer filter by
    # goal -- which means a goal that is sparse in recent history can UNDER-FILL its
    # window. Measured at a factor of 3: HAL's green_slime rate fell from 200 samples
    # to 152, not because the evidence aged out but because the read stopped early.
    # Ten keeps a bounded read while leaving a goal that ran a tenth of the time its
    # full window. The window's meaning does shift from "the last N cycles OF THIS
    # GOAL, however long ago" to "this goal's cycles within the recent stream", and
    # that is a real change: evidence from far enough back now falls out entirely.
    _RECOVERY_STREAM_FACTOR = 10

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
        # Schema creation AND the column migrations below run under SQLite's
        # exclusive writer lock, because each is a probe-then-create pair that
        # is not atomic across PROCESSES. `play --all --learn` hands every
        # child the SAME learning DB path, and they open it within about a
        # second of each other — the exposure that killed a child on the
        # coordination DB ("table role_leases already exists"). Before
        # `play --all` existed, exactly one process ever opened this file, so
        # an unlocked `create_all` was safe for as long as it shipped; the
        # multi-character supervisor is what made it reachable. See
        # `schema_init`.
        with exclusive_schema_lock(self._engine) as conn:
            SQLModel.metadata.create_all(conn)
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
            # Harness-migration column (2026-08-15): cycles gains the skill
            # levels held BEFORE the action. NULLABLE with no DEFAULT -- the
            # rows already in the wild were written without levels, and
            # back-filling 0 or today's level would hand a replay a fabricated
            # observation. A consumer excludes NULL rather than defaulting it.
            if cols and "skill_levels_json" not in cols:
                conn.exec_driver_sql("ALTER TABLE cycles ADD COLUMN skill_levels_json TEXT")
            # Craft-xp numerator migration (2026-08-15): craft_yield gains the
            # skill level its xp was measured at. NULLABLE with no DEFAULT --
            # the rows already in the wild were measured at a level nobody
            # recorded, and back-filling them with 0 or with today's level
            # would hand a per-skill xp fit a fabricated observation. A
            # consumer excludes NULL rather than defaulting it.
            yield_cols = {row[1]
                          for row in conn.exec_driver_sql("PRAGMA table_info(craft_yield)")}
            if yield_cols and "skill_level" not in yield_cols:
                conn.exec_driver_sql("ALTER TABLE craft_yield ADD COLUMN skill_level INTEGER")

        # PRAGMAs go on their OWN connection, after the lock is released:
        # SQLite refuses a journal_mode change inside a transaction.
        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
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
        win_count / goal_avg_cycles_to_satisfy) for the duration of one READ-ONLY
        decision episode. Safe because the DB is not written inside one — that is
        the whole condition, and it holds for the strategy decision exactly as it
        does for the planner search nested within it. Reentrant: a nested enter
        reuses the outer cache; the original cache is restored on exit.

        The player opens it around the WHOLE `StrategyEngine.decide` (not just the
        planner) because the unified objective runs one `cheapest_path_to_level`
        walk per candidate and each walk asks `is_winnable` about every monster at
        or above a level — ~3.6k reads per walk uncached."""
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
        """Return up to `window` most recent Cycle rows for this goal, NEWEST FIRST,
        including the recovery cycles the goal's own fighting forced.

        RECOVERY IS A DIFFERENT GOAL, AND THAT MADE THE RATE A DIFFERENT UNIT. The
        arbiter preempts a grind with `RestoreHP` when hit points fall, so every Rest
        the combat loop forces is filed under `RestoreHP` and NOT under the grind that
        caused it. Measured on 36455 live cycles: `GrindCharacterXP(green_slime)` is
        100.0% FightAction and 0% Rest, while `RestoreHP` holds 5668 Rests.

        So a rate averaged over the goal's own rows alone is XP per FIGHT, while the
        predicted branch it is compared against is XP per LOOP ACTION (S-023) -- and a
        monster with observations outranked one without by the whole loop factor,
        about 2.4x at live per-kill costs. That is the same defect as the seconds-vs-
        cycles bug this branch already had once, one order of magnitude smaller and
        therefore harder to see.

        ATTRIBUTION IS TEMPORAL, and it is the only thing the data supports: a
        recovery cycle belongs to the goal that ran immediately before it. The damage
        that forced the Rest came from the fight that preceded it, and cycles carry a
        monotonic id, so "the goal of the previous cycle" is computable and needs no
        new column. A recovery preceded by nothing, or by another recovery, walks back
        to the last non-recovery goal; recoveries at the very start of the window have
        nothing to attach to and are dropped rather than guessed at.
        """
        try:
            with SqlSession(self._engine) as s:
                # Read the raw stream, not a filtered slice: attribution needs each
                # recovery cycle's PREDECESSOR, which a `where goal = x` filter has
                # already discarded. The window is widened because the stream now
                # includes cycles that will be attributed elsewhere.
                stmt = (
                    select(Cycle)
                    .where(col(Cycle.character) == self._character)
                    .order_by(col(Cycle.id).desc())
                    .limit(window * self._RECOVERY_STREAM_FACTOR)
                )
                stream = list(s.exec(stmt))
        except SQLAlchemyError:
            return []
        return attribute_forced_recovery(stream, goal_repr, window)

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


    def observed_drop_rate(self, monster_code: str, item_code: str,
                           window: int = 2000,
                           min_kills: int = MIN_DROP_KILLS) -> float | None:
        """Units of `item_code` obtained per kill of `monster_code`, MEASURED.

        Replaces the static API drop table wherever there is enough evidence,
        and deliberately carries the character's PROSPECTING effect with it: the
        server applies prospecting when it rolls the drop, so an observation is
        already the post-bonus rate. That is why `acquisition_cost` applies its
        prospecting relief ONLY on the static fallback — applying both would
        count the bonus twice.

        Measured 2026-08-08 over 4,000+ recorded kills, observed vs API static:
        `chicken/raw_chicken` 48.3% vs 50.0%, `red_slime/red_slimeball` 9.6% vs
        10.0%, `chicken/egg` 8.6% vs 8.3% — the table is accurate to ~3% on large
        samples. The exceptions are the ones that matter: `chicken/feather` 14.8%
        vs 12.5% (1.18x) and `sheep/wool` 11.8% vs 8.3% (1.42x), both saying the
        drop route is CHEAPER than the static model priced it.

        Scoped to this store's character, because prospecting is per-character
        and is baked into the number.

        `None` below `min_kills`, where the estimate is noise: at n=199
        `green_slime/apple` read 0.60x of its static rate, which is inside
        ordinary sampling error for p=0.083 and would otherwise be taken as a
        40% price rise."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.drops_json)
                    .where(col(Cycle.character) == self._character)
                    .where(col(Cycle.action_repr) == f"Fight({monster_code})")
                    .order_by(col(Cycle.id).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if len(rows) < min_kills:
                return None
            total = 0
            for raw in rows:
                if not raw:
                    continue
                try:
                    drops = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                if isinstance(drops, dict):
                    value = drops.get(item_code, 0)
                    if isinstance(value, int):
                        total += max(0, value)
            return float(total) / len(rows)
        except SQLAlchemyError:
            return None

    def skill_xp_per_cycle_all(self, skill: str,
                               window: int = WINDOW_RECENT) -> float | None:
        """UNCONDITIONAL mean per-cycle XP gain for `skill`: total gain divided by
        EVERY cycle in the window, not only the ones that gained.

        The distinction is not academic. `skill_xp_per_cycle` above averages only
        cycles with a positive delta, so when one cycle in forty pays 54 xp and
        the other thirty-nine pay nothing, it reports **54** while the character
        is really earning **1.3** per cycle. Measured live on R2D2, 2026-08-08:
        207 `LevelSkill(weaponcrafting->10)` actions over 4.5 hours moved
        weaponcrafting xp 343 -> 613 and the level not at all, while
        `skill_xp_per_cycle` said 54.0 — a 41x over-estimate.

        A grind priced with the conditional mean is priced 41x too cheap, and
        `J` will commit to it: `greater_wooden_staff` showed `acquire_cost=68`
        for a weaponcrafting 6->10 grind that is in truth thousands of actions.
        Anything asking "how many cycles will this grind take" wants THIS
        function; the conditional mean answers "how much do I get when I get
        any", which is a different question.

        Returns None when the window holds no cycles at all. A cycle with no
        entry for `skill`, or a malformed row, counts as a ZERO gain rather than
        being skipped — that is precisely the population the conditional mean
        drops."""
        try:
            with SqlSession(self._engine) as s:
                stmt = (
                    select(Cycle.delta_skill_xp_json)
                    .where(col(Cycle.character) == self._character)
                    .order_by(col(Cycle.id).desc())
                    .limit(window)
                )
                rows = list(s.exec(stmt))
            if not rows:
                return None
            total = sum(max(0, _parse_skill_xp_value(raw, skill)) for raw in rows)
            return float(total) / len(rows)
        except SQLAlchemyError:
            return None

    def skill_grind_rate(self, skill: str,
                         window: int = WINDOW_RECENT) -> float | None:
        """Mean per-cycle XP gain for `skill` over the most recent `window` cycles
        THIS CHARACTER SPENT GRINDING IT.

        The difference from `skill_xp_per_cycle_all` is WHERE THE LIMIT FALLS.
        That method limits to the last `window` cycles and then measures one skill
        inside them, so a character doing anything else reads 0.0 — measured
        2026-08-17 on the live DB, all five characters read exactly 0.0 for all
        four crafting skills, which made `acquisition_cost._gated_craft_option`
        decline every skill-gated craft and price every iron-tier item at
        `UNOBTAINABLE_PER_UNIT`. That is an absorbing state: the price forbids the
        grind and the absent grind keeps the price. Here the limit falls on rows
        that already matched the grind's `action_repr`, so the sample IS the
        grind's own cycles and a grind in progress feeds the estimate that prices
        it.

        THE ZERO-XP CYCLES INSIDE THE GRIND STAY IN THE DENOMINATOR, and that is
        the safety property. A grind is mostly gathering: over 3,658 live
        `LevelSkill(gearcrafting->10)` cycles, 136 were a craft paying 53-131 xp
        and 3,112 were 30-second gathers paying nothing. `skill_xp_per_cycle`
        above drops those gathers and so reported 54.0 against a true 1.08 — the
        50x under-pricing that committed R2D2 to 207 `LevelSkill` actions over 4.5
        hours for +270 skill xp and zero character xp (2026-08-08). This estimator
        reports 1.59-4.92 on the same live data.
        `TestSkillGrindRate.test_the_conditional_mean_and_the_grind_rate_must_differ`
        pins the two apart on one fixture.

        Returns None when this character has no recorded grind cycles for the
        skill — IGNORANCE, on which the caller may fall back to
        `fleet_skill_grind_rate`. Returns 0.0 when the grind ran and gained
        nothing — EVIDENCE, on which the caller must decline. Those are different
        answers and a caller must not conflate them.
        """
        return self._grind_rate(skill, window, character=self._character)

    def fleet_skill_grind_rate(self, skill: str,
                               window: int = WINDOW_RECENT) -> float | None:
        """`skill_grind_rate` pooled over EVERY character in the store.

        A character that has never ground a skill has no evidence of its own, but
        a sibling that has is evidence about the same server, the same recipes and
        the same workshops. The fallback is deliberately ONE-WAY: a character with
        its own observations always uses them, however unflattering, because its
        gear and level are baked into them.
        """
        return self._grind_rate(skill, window, character=None)

    def fleet_supply_request_cycles(self) -> float | None:
        """Median producer cycles ONE fleet supply request has historically cost,
        or None when the fleet has never served one.

        This is the price of the `sibling:` unlock in `acquisition_cost` — what a
        character pays, in fleet cycles, to have a sibling make something it
        cannot make itself. It is MEASURED rather than chosen: the alternative
        was a constant, and a modelling constant nothing pins is proof-inert
        however green the gate (`feedback_gate_green_does_not_pin_a_constant`).

        Read off `SupplyBank(<item>x<qty>)` goal cycles, grouped per
        (request, producer) pair — the same shape `_grind_rate` reads
        `LevelSkill(<skill>-><level>)` cycles. Measured 2026-08-20 over 172 pairs:
        median 15 cycles per request, mean 19, max 239 — against ~413 cycles for a
        character to grind gearcrafting 9->10 itself. That ratio is the whole
        argument for the route.

        MEDIAN, not mean: the distribution has a long tail (one 239-cycle request
        against a median of 15) and a mean would let a single pathological request
        price every future one.

        The coordination tables are UPSERTED rather than append-only, so the
        requester's IDLE WAIT between publishing a demand and the units landing
        cannot be recovered from the store and is NOT included here. That is a
        declared gap, not a forgotten one: this number is the fleet's PRODUCTION
        cost, and it understates the requester's wall-clock latency.
        """
        try:
            with SqlSession(self._engine) as s:
                rows = list(s.exec(
                    select(Cycle.selected_goal, Cycle.character)
                    .where(col(Cycle.selected_goal).contains("SupplyBank("))))
        except SQLAlchemyError:
            return None
        # The key type admits a None goal rather than guarding against one:
        # `contains` cannot match NULL, so the query already excludes it, and a
        # guard here would be a branch no schema state can reach.
        # `cycles.character` is NOT NULL, so the producer half is always present.
        per_pair: dict[tuple[str | None, str], int] = {}
        for goal, character in rows:
            per_pair[(goal, character)] = per_pair.get((goal, character), 0) + 1
        if not per_pair:
            return None
        return float(median(sorted(per_pair.values())))

    def _grind_rate(self, skill: str, window: int,
                    character: str | None) -> float | None:
        """Shared body of the two grind-rate estimators — ONE query, so the
        per-character and fleet answers cannot drift into disagreeing about what a
        grind cycle is."""
        prefix = grind_action_prefix(skill)
        try:
            with SqlSession(self._engine) as s:
                stmt = select(Cycle.delta_skill_xp_json).where(
                    col(Cycle.action_repr).startswith(prefix, autoescape=True))
                if character is not None:
                    stmt = stmt.where(col(Cycle.character) == character)
                stmt = stmt.order_by(col(Cycle.id).desc()).limit(window)
                rows = list(s.exec(stmt))
            if not rows:
                return None
            total = sum(max(0, _parse_skill_xp_value(raw, skill)) for raw in rows)
            return float(total) / len(rows)
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
        winnability inference needs the unsmoothed count.

        SEARCH-CACHED (2026-08-07), like its sibling `action_cost`. This is the
        hottest read in the codebase and it was the only one of its family issuing
        a fresh SELECT every call: `is_winnable` -> `_won_at_or_above_level` walks
        every monster at or above a level, so one `cheapest_path_to_level` walk
        fired **3,617** queries and took ~400ms, of which ~95% was SQLite. The
        tally is a read-only count over history the planner does not write during a
        search — exactly the invariant `search_cache` documents — so the memo is
        sound for the same reason `action_cost`'s is. Outside a search the cache is
        None and every call still hits the DB."""
        return self._cached(("win_count", action_repr),
                            lambda: self._win_count_uncached(action_repr))

    def _win_count_uncached(self, action_repr: str) -> int:
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

    def record_craft_yield(self, item_code: str, quantity: int, xp: int,
                           skill_level: int | None = None) -> None:
        """Upsert observed (quantity, xp, skill_level) for (character,
        item_code). Last write wins, INCLUDING the level.

        `skill_level` is the crafting skill's level at the moment `xp` was
        paid. It defaults to None so every existing caller keeps working, and
        None reads back as "unknown" rather than as a level — see
        `CraftYieldObservation.skill_level`.

        The whole row is overwritten together on purpose. Carrying a stale
        level past a fresh xp would attribute the new figure to the level the
        character had the FIRST time it crafted the item, which is worse than
        having no level at all.
        """
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
                    existing.skill_level = skill_level
                    s.add(existing)
                else:
                    s.add(CraftYieldObservation(
                        character=self._character,
                        item_code=item_code,
                        quantity=quantity,
                        xp=xp,
                        skill_level=skill_level,
                    ))
                s.commit()
        except SQLAlchemyError as e:
            print(f"[learning] record_craft_yield failed: {e}")

    def observed_craft_xp(self, item_code: str) -> tuple[int, int, int | None] | None:
        """Observed (xp, quantity, skill_level) for (character, item_code), or
        None when the item has never been crafted by this character.

        XP FIRST, unlike `observed_craft_yield`'s (quantity, xp): that function
        exists to ground-truth `CraftSchema.quantity` for the planner, and this
        one exists to feed a per-skill XP fit. Ordering each tuple by what its
        caller actually wants keeps a caller from silently reading the wrong
        member of a same-shaped pair.

        `skill_level` is None for a row recorded before the column existed or
        by a caller that could not resolve the skill. A fit must EXCLUDE those
        rows rather than substitute a level for them.
        """
        try:
            with SqlSession(self._engine) as s:
                stmt = select(CraftYieldObservation).where(
                    CraftYieldObservation.character == self._character,
                    CraftYieldObservation.item_code == item_code,
                )
                row = s.exec(stmt).first()
                if row is None:
                    return None
                return (row.xp, row.quantity, row.skill_level)
        except SQLAlchemyError:
            return None

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
