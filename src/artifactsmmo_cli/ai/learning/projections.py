"""Phase G-B projections: throughput/yield estimates over the LearningStore.

Pure functions over recent Cycle history. Return None (or a low-sample
sentinel) when there's not enough data; callers must check and fall back to
hardcoded defaults during warm-up.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §2.
"""

import json
import statistics

from pydantic import BaseModel, Field

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


WARMUP_MIN_SAMPLES = 10
"""Minimum cycles for a projection to be considered trustworthy.

Below this, projection functions return None. Callers should fall back to
hardcoded defaults (existing goal priorities) when None is returned.
"""

TASKS_COIN_CODE = "tasks_coin"


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
    if not rows:
        return None
    # rows are newest-first; reverse to chronological for delta detection.
    chrono = list(reversed(rows))

    intervals: list[int] = []
    last_progress_at: int | None = None
    prev_progress: int | None = None
    for cycle in chrono:
        if prev_progress is not None and cycle.task_progress is not None:
            if cycle.task_progress > prev_progress:
                if last_progress_at is not None:
                    intervals.append(cycle.cycle_index - last_progress_at)
                last_progress_at = cycle.cycle_index
        prev_progress = cycle.task_progress

    # Also include cycles_to_satisfy events as 1-cycle progress markers.
    for cycle in chrono:
        if cycle.cycles_to_satisfy is not None and cycle.cycles_to_satisfy > 0:
            intervals.append(cycle.cycles_to_satisfy)

    if len(intervals) < WARMUP_MIN_SAMPLES:
        return None
    return statistics.median(intervals)


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
