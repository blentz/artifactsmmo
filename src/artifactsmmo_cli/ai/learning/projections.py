"""Phase G-B projections: throughput/yield estimates over the LearningStore.

Pure functions over recent Cycle history. Return None (or a low-sample
sentinel) when there's not enough data; callers must check and fall back to
hardcoded defaults during warm-up.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §2.
"""

import json

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.cycles_for_progress_core import (
    CycleRow,
    cycles_for_progress_pure,
)
from artifactsmmo_cli.ai.learning.low_yield_boundary import low_yield_fires_pure
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

WARMUP_MIN_SAMPLES = 10
"""Minimum cycles for a projection to be considered trustworthy.

Below this, projection functions return None. Callers should fall back to
hardcoded defaults (existing goal priorities) when None is returned.
"""


class Yield(BaseModel):
    """Average per-cycle yield while a goal was selected."""

    char_xp: float = 0.0
    """Average character-XP gained per cycle."""

    skill_xp: dict[str, float] = Field(default_factory=dict)
    """Per-skill average XP per cycle (sparse — only skills with non-zero deltas)."""

    gold: float = 0.0
    """Average gold delta per cycle."""

    tasks_coins: float = 0.0
    """Average tasks_coin gained per cycle (parsed from drops_json)."""

    sample_count: int = 0
    """Number of cycles aggregated. < WARMUP_MIN_SAMPLES => low confidence."""


class TaskProjection(BaseModel):
    """Projected completion of an in-flight items/monsters task."""

    cycles_remaining: float
    """Estimated cycles to take task_progress from current to task_total."""

    expected_char_xp: float
    """Total character XP expected over the remaining duration."""

    expected_gold: float
    """Total gold expected over the remaining duration (including completion bonus)."""

    expected_tasks_coins: float
    """Total tasks_coin expected (typically one batch on CompleteTask)."""

    confidence: float
    """0.0–1.0. 1.0 when sample size >= 3 * WARMUP_MIN_SAMPLES, scaled linearly below."""


def _parse_skill_xp(cycle: Cycle) -> dict[str, int]:
    """Parse delta_skill_xp_json from a Cycle row. Returns empty dict on bad data."""
    raw = cycle.delta_skill_xp_json or "{}"
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _parse_drops(cycle: Cycle) -> dict[str, int]:
    """Parse drops_json. Returns empty dict for missing/malformed data."""
    raw = cycle.drops_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def expected_yield_per_cycle(goal_repr: str, store: LearningStore, window: int = 100) -> Yield:
    """Average per-cycle reward while `goal_repr` was the selected goal.

    Returns an empty Yield (with sample_count=0) when there's no history. Callers
    can detect cold goals via `yield.sample_count < WARMUP_MIN_SAMPLES`.
    """
    rows = store.recent_goal_cycles(goal_repr, window=window)
    if not rows:
        return Yield()

    char_xp_total = 0
    gold_total = 0
    coins_total = 0
    skill_xp_totals: dict[str, int] = {}

    for cycle in rows:
        char_xp_total += cycle.delta_xp or 0
        gold_total += cycle.delta_gold or 0
        for skill, delta in _parse_skill_xp(cycle).items():
            skill_xp_totals[skill] = skill_xp_totals.get(skill, 0) + delta
        coins_total += _parse_drops(cycle).get(TASKS_COIN_CODE, 0)

    n = len(rows)
    return Yield(
        char_xp=char_xp_total / n,
        skill_xp={s: t / n for s, t in skill_xp_totals.items() if t != 0},
        gold=gold_total / n,
        tasks_coins=coins_total / n,
        sample_count=n,
    )


def cycles_for_progress(goal_repr: str, store: LearningStore, window: int = 100) -> float | None:
    """Median cycles between "progress events" while pursuing `goal_repr`.

    Progress event definitions:
      - FarmItems / CompleteTask-style goals: task_progress strictly increased
        between this cycle and the next.
      - Other goals: cycles_to_satisfy was recorded (goal reached desired state).

    Returns None when fewer than WARMUP_MIN_SAMPLES progress events observed,
    so callers fall back to defaults during warm-up.
    """
    rows = store.recent_goal_cycles(goal_repr, window=window)
    # Pure-core delegation. The two-append-loop semantics is intentional —
    # see `cycles_for_progress_core.py` header and the Lean proof
    # `Formal.CyclesForProgress.cyclesForProgressPure_eq_median_concat`.
    projected = [
        CycleRow(
            cycle_index=row.cycle_index,
            task_progress=row.task_progress,
            cycles_to_satisfy=row.cycles_to_satisfy,
        )
        for row in rows
    ]
    return cycles_for_progress_pure(projected, WARMUP_MIN_SAMPLES)


class PathSegment(BaseModel):
    """One grind-this-monster-until-level-up step in a path to max level."""

    from_level: int
    to_level: int
    monster_code: str
    estimated_cycles: float
    xp_per_cycle: float
    cycles_per_kill: float


class PathPlan(BaseModel):
    """Estimated cheapest path from current level to target level."""

    target_level: int
    total_cycles: float
    segments: list[PathSegment] = Field(default_factory=list)
    blocked: bool = False
    """True when no beatable monster exists at some intermediate level —
    the path cannot complete without unlocking new combat options."""

    @property
    def next_action_monster(self) -> str | None:
        """Monster code for the first segment, or None if the path is empty."""
        return self.segments[0].monster_code if self.segments else None


DEFAULT_FIGHT_CYCLES = 30.0
"""Fallback cycle cost per Fight when learning store has no observations.
~30s server cooldown is the typical post-fight cooldown."""

MIN_PATH_SUCCESS_RATE = 0.5
"""Minimum observed win-rate (with >= MIN_PATH_SAMPLES observations) for a
monster to remain in the path projection. Below threshold the monster is
skipped entirely — losing fights waste HP and drop net XP/cycle below
slower-but-survivable alternatives."""

MIN_PATH_SAMPLES = 5
"""Below this sample count the win-rate filter doesn't apply (the bot
hasn't had a fair chance to learn the monster yet)."""


def cheapest_path_to_level(
    target_level: int,
    state: WorldState,
    store: LearningStore,
    game_data: GameData,
) -> PathPlan:
    """Walk levels current → target picking the cheapest beatable monster
    at each step.

    XP per kill comes from the documented formula (`game_data.xp_per_kill`)
    — no magic guess. Cycle cost per kill comes from the learning store
    when observed; otherwise DEFAULT_FIGHT_CYCLES.

    Returns a PathPlan with `blocked=True` and `total_cycles=inf` when no
    beatable monster exists at some intermediate level.

    Known limits:
      - Assumes each level requires `state.max_xp` XP. We don't have the
        per-level XP curve from API; new char.max_xp could be discovered
        as the bot levels up and persisted in a follow-up.
      - Doesn't model gathering/crafting detours.
      - Doesn't account for HP recovery cycles, deaths, or cooldowns
        beyond what `action_cost` captures.
    """
    if state.level >= target_level:
        return PathPlan(target_level=target_level, total_cycles=0.0, segments=[])

    segments: list[PathSegment] = []
    sim_level = state.level
    xp_to_next = max(1, state.max_xp - state.xp)
    wisdom = state.wisdom

    while sim_level < target_level:
        # Beatable monsters at sim_level: FightAction.is_applicable allows
        # monster_level <= state.level + 1.
        beatable = [
            (code, lvl) for code, lvl in game_data.monster_levels.items()
            if 1 <= lvl <= sim_level + 1
        ]
        if not beatable:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)

        best_code: str | None = None
        best_xp_per_cycle = 0.0
        best_cost = DEFAULT_FIGHT_CYCLES
        for code, _lvl in beatable:
            fight_repr = f"Fight({code})"
            # Skip monsters with observed-low success_rate: losing fights waste
            # HP and produce zero XP net. Use the actual sample count from the
            # action stats (NOT goal cycles) so a few real losses count.
            samples = store.sample_count(fight_repr)
            if samples >= MIN_PATH_SAMPLES:
                rate = store.success_rate(fight_repr)
                if rate < MIN_PATH_SUCCESS_RATE:
                    continue
            observed = expected_yield_per_cycle(f"FarmMonster({code})", store)
            cost = store.action_cost(fight_repr, default=DEFAULT_FIGHT_CYCLES)
            if observed.sample_count > 0 and observed.char_xp > 0:
                xp_per_cycle = observed.char_xp
            else:
                # Documented formula. Yields exact XP-per-kill server-side.
                xp_per_kill = game_data.xp_per_kill(code, sim_level, wisdom=wisdom)
                xp_per_cycle = xp_per_kill / max(cost, 1.0)
            if xp_per_cycle > best_xp_per_cycle:
                best_code = code
                best_xp_per_cycle = xp_per_cycle
                best_cost = cost

        if best_code is None or best_xp_per_cycle <= 0:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)

        cycles_for_this_level = xp_to_next / best_xp_per_cycle
        segments.append(PathSegment(
            from_level=sim_level,
            to_level=sim_level + 1,
            monster_code=best_code,
            estimated_cycles=cycles_for_this_level,
            xp_per_cycle=best_xp_per_cycle,
            cycles_per_kill=best_cost,
        ))
        sim_level += 1
        xp_to_next = max(1, state.max_xp)

    total = sum(s.estimated_cycles for s in segments)
    return PathPlan(target_level=target_level, total_cycles=total, segments=segments)


def project_task_completion(
    state: WorldState, store: LearningStore, completion_bonus_gold: float = 150.0,
) -> TaskProjection | None:
    """Project remaining cycles and reward for the in-flight task.

    Requires `state.task_total > state.task_progress`. Returns None when there's
    no active task. Reward projections use FarmItems aggregates (the standard
    goal that drives task progression). `completion_bonus_gold` defaults to the
    typical observed CompleteTask payout (≈150 gold + 1 tasks_coin batch).
    """
    if state.task_total == 0 or state.task_progress >= state.task_total:
        return None

    remaining_progress = state.task_total - state.task_progress

    # Use the per-progress-event cadence; fall back to a conservative default.
    cycles_per_progress = cycles_for_progress("FarmItems", store) or 15.0
    cycles_remaining = remaining_progress * cycles_per_progress

    farm_yield = expected_yield_per_cycle("FarmItems", store)

    # Confidence ramps from 0 at zero samples to 1.0 at 3 * WARMUP_MIN_SAMPLES.
    confidence_cap = WARMUP_MIN_SAMPLES * 3
    confidence = min(1.0, farm_yield.sample_count / confidence_cap)

    return TaskProjection(
        cycles_remaining=cycles_remaining,
        expected_char_xp=farm_yield.char_xp * cycles_remaining,
        expected_gold=farm_yield.gold * cycles_remaining + completion_bonus_gold,
        # CompleteTask drops one tasks_coin batch (~3) on completion; that's
        # outside the per-cycle FarmItems yield so add it separately.
        expected_tasks_coins=farm_yield.tasks_coins * cycles_remaining + 3.0,
        confidence=confidence,
    )


LOW_YIELD_CONFIDENCE_THRESHOLD = 0.5
"""Don't cancel until projection confidence >= this. Below the threshold we
defer to existing hardcoded priorities and let the task run."""

LOW_YIELD_ALTERNATIVE_MARGIN = 1.5
"""Cancel only when the alternative's char-XP rate is at least this multiple
of the current task's rate. Higher = more conservative cancels."""


def _best_alternative_repr(history: LearningStore) -> str | None:
    """Find the FarmMonster repr with the most observed cycles.

    FarmMonster reprs are per-monster, e.g. "FarmMonster(chicken)". The
    canonical alternative for this comparison is whichever monster the
    bot has actually been farming.  None rows are skipped; returns None
    when no FarmMonster cycles exist or on DB error.
    """
    try:
        with Session(history._engine) as s:
            stmt = (
                select(Cycle.selected_goal)
                .where(
                    col(Cycle.character) == history._character,
                    col(Cycle.selected_goal).like("FarmMonster(%"),
                )
                .order_by(col(Cycle.id).desc())
                .limit(50)
            )
            rows = list(s.exec(stmt))
    except SQLAlchemyError:
        return None
    if not rows:
        return None
    counts: dict[str, int] = {}
    for r in rows:
        if r is not None:
            counts[r] = counts.get(r, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def low_yield_cancel_fires(state: WorldState, history: LearningStore | None) -> bool:
    """True when the held task should be cancelled for a clearly-better monster
    alternative. Single source of truth for both LowYieldCancelGoal and the
    strategy means predicate.

    Fires when: a task is held (task_code set AND task_total > 0), there is
    FarmItems yield history and a best FarmMonster alternative with samples, and
    either the current char-XP/cycle is 0 while the alternative is positive
    (zero fast-path), OR project_task_completion confidence >= 0.5 and the
    alternative rate >= current rate * 1.5.

    The pure decision boundary is delegated to `low_yield_fires_pure` in
    `low_yield_boundary.py`; this function is the impure shell that fetches
    the LearningStore aggregates.
    """
    if history is None or not state.task_code or state.task_total <= 0:
        return False

    farm_items_yield = expected_yield_per_cycle("FarmItems", history)
    if farm_items_yield.sample_count == 0:
        return False
    current_char_xp_per_cycle = farm_items_yield.char_xp

    alt_repr = _best_alternative_repr(history)
    if alt_repr is None:
        return False
    alt_yield = expected_yield_per_cycle(alt_repr, history)
    if alt_yield.sample_count == 0:
        return False
    alternative_char_xp_per_cycle = alt_yield.char_xp

    projection = project_task_completion(state, history)
    # Projection.None contributes confidence 0.0, which the pure boundary
    # rejects via the min_confidence gate UNLESS the zero-fast-path fires.
    confidence = projection.confidence if projection is not None else 0.0

    return low_yield_fires_pure(
        has_task=True,
        current_xp=current_char_xp_per_cycle,
        alt_xp=alternative_char_xp_per_cycle,
        confidence=confidence,
        farm_samples=farm_items_yield.sample_count,
        alt_samples=alt_yield.sample_count,
        margin=LOW_YIELD_ALTERNATIVE_MARGIN,
        min_confidence=LOW_YIELD_CONFIDENCE_THRESHOLD,
    )
