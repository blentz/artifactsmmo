"""Decide whether to skill up to complete the active task, or pivot away.

Value-per-cycle: estimate cycles to reach the gating skill level and produce the
task, value the (learned) reward over those cycles, and compare to a confidence-
adjusted baseline value-per-cycle.

Confidence is used as a margin, not a gate: a fully-unobserved skill gap demands
4x the baseline value/cycle before committing to the grind; a fully-observed gap
demands exactly the baseline. This means PURSUE is reachable even with zero
observations as long as the expected value is high enough.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.scalarizer import DEFAULT_COIN_VALUE_GOLD
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_feasibility import task_requirement
from artifactsmmo_cli.ai.world_state import WorldState

PURSUE = "pursue"
PIVOT = "pivot"

DEFAULT_SKILL_XP_PER_CYCLE = 10.0
"""Fallback skill-XP gain rate per cycle before a rate has been learned."""

DEFAULT_TASK_REWARD_VALUE = 50.0
"""Fallback expected reward value before any task is completed (gold-equivalent)."""

LOW_CONFIDENCE_MARGIN = 3.0
"""Extra value-per-cycle multiplier applied when the skill gap is unobserved.

required_vpc = DEFAULT_COIN_VALUE_GOLD * (1.0 + LOW_CONFIDENCE_MARGIN * (1.0 - confidence))

A fully-unobserved gap (confidence=0) demands (1 + 3.0) = 4x the baseline before
committing to the grind. A fully-observed gap (confidence=1) demands exactly the
baseline. Intermediate confidence scales linearly between those extremes.
"""


def task_decision(state: WorldState, game_data: GameData,
                  history: LearningStore | None) -> str:
    req = task_requirement(state, game_data)
    if req is None:
        return PURSUE  # already feasible
    if req.skill == "combat" or history is None:
        return PIVOT  # combat-gated: no skill-grind path here
    curve = SkillXpCurve(observed=history.skill_max_xp_observations(req.skill))
    rate = history.skill_xp_per_cycle(req.skill) or DEFAULT_SKILL_XP_PER_CYCLE
    skill_cycles = curve.cycles_to_level(req.current_level, req.required_level, rate)
    # task_requirement returns None when task_total == 0, so total_cycles >= 1 here
    # (skill_cycles >= 0 + task_total >= 1) — no divide-by-zero guard needed.
    total_cycles = skill_cycles + float(state.task_total)
    reward = history.mean_task_reward_value(default=DEFAULT_TASK_REWARD_VALUE)
    skill_up_vpc = reward / total_cycles
    confidence = curve.confidence(req.current_level, req.required_level)
    required_vpc = DEFAULT_COIN_VALUE_GOLD * (1.0 + LOW_CONFIDENCE_MARGIN * (1.0 - confidence))
    return PURSUE if skill_up_vpc >= required_vpc else PIVOT
