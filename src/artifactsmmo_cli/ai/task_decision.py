"""Decide whether to skill up to complete the active task, or pivot away.

Value-per-cycle: estimate cycles to reach the gating skill level and produce the
task, value the (learned) reward over those cycles, and compare to a baseline
alternative value-per-cycle. Low confidence (unobserved skill gap or no reward
history) biases toward pivoting — don't commit to a long grind on a rough guess.
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


def task_decision(state: WorldState, game_data: GameData,
                  history: LearningStore | None) -> str:
    req = task_requirement(state, game_data)
    if req is None:
        return PURSUE  # already feasible
    if req.skill == "combat" or history is None:
        return PIVOT  # combat-gated: no skill-grind path here
    curve = SkillXpCurve(observed=history.skill_max_xp_observations(req.skill))
    if not curve.is_confident(req.current_level, req.required_level):
        return PIVOT
    skill_cycles = curve.cycles_to_level(req.current_level, req.required_level,
                                         DEFAULT_SKILL_XP_PER_CYCLE)
    # task_requirement returns None when task_total == 0, so total_cycles >= 1 here
    # (skill_cycles >= 0 + task_total >= 1) — no divide-by-zero guard needed.
    total_cycles = skill_cycles + float(state.task_total)
    reward = history.mean_task_reward_value(default=DEFAULT_TASK_REWARD_VALUE)
    skill_up_vpc = reward / total_cycles
    return PURSUE if skill_up_vpc >= DEFAULT_COIN_VALUE_GOLD else PIVOT
