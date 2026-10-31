"""Phase G-B projections: throughput/yield estimates over the LearningStore.

Pure functions over recent Cycle history. Return None (or a low-sample
sentinel) when there's not enough data; callers must check and fall back to
hardcoded defaults during warm-up.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §2.
"""

import json

from pydantic import BaseModel, Field

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE

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
