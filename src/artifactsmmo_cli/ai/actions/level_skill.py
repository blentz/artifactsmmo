"""LevelSkill: a GOAP action that raises a crafting skill to `target_level`.

The GOAP planner treats skill levels as immutable during search, so
CraftAction's skill gate (skill_level < crafting_level -> not applicable) is
otherwise unsatisfiable in-search — an under-skill craft cannot be planned.
LevelSkill's `apply` OPTIMISTICALLY sets the skill to `target_level` (the whole
grind assumed complete, the FightAction optimistic-apply idiom), so a downstream
CraftAction(target) becomes applicable in the SIMULATED plan; the player expands
the action into an incremental grind at execution (Phase 3) and PlanCache replan
reconciles the optimism with reality.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState

PER_LEVEL_COST = 50.0
"""No-curve fallback cost per skill level (~10 grind crafts at 5s each). Keeps
cost strictly positive and monotone in the level gap when SkillXpCurve has no
observations yet."""

PER_CRAFT_COST = 5.0
"""Seconds per grind craft, matching CraftAction.cost's 5.0/quantity base."""

AVG_XP_PER_CRAFT = 20
"""Conservative XP granted per grind craft when converting a curve XP estimate
into a craft-cycle count. Refined by observation; never a hardcoded curve."""


@dataclass
class LevelSkill(Action):
    """Raise `skill` to `target_level`. Optimistic apply; player-expanded at execution."""

    tags: ClassVar[frozenset[str]] = frozenset({"skill_grind"})
    """Admits this action into GatherMaterialsGoal.relevant_actions' search
    space (tag-based so the goal need not import LevelSkill). New tag in the
    base.py vocabulary."""

    skill: str
    target_level: int
    xp_curve: SkillXpCurve | None = field(default=None, repr=False, compare=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.skills.get(self.skill, 1) >= self.target_level:
            return False
        # A skill is grindable from here via EITHER a craftable in-skill rung
        # (skill_grind_target) OR — for a gather skill (alchemy/mining/woodcutting
        # /fishing, whose gather skill name is reused as the tier-1 craft skill) —
        # a gatherable resource usable now (best_gather_resource_drop): gathering
        # it grants skill xp. Without the gather arm an under-skill gather-skill
        # craft (e.g. small_health_potion at alchemy 1, whose lowest craftable
        # rung is level 5) could never grind and was an unplannable residual.
        current = state.skills.get(self.skill, 1)
        return (skill_grind_target(self.skill, state, game_data) is not None
                or best_gather_resource_drop(self.skill, current, game_data)
                is not None)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_skills = dict(state.skills)
        new_skills[self.skill] = self.target_level
        return dataclasses.replace(state, skills=new_skills)

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        current = state.skills.get(self.skill, 1)
        gap = max(0, self.target_level - current)
        curve = self.xp_curve
        if curve is not None and curve.observed:
            total_xp = curve.total_xp_to_reach(current, self.target_level)
            cycles = max(gap, -(-total_xp // AVG_XP_PER_CRAFT))  # ceil-div
            return cycles * PER_CRAFT_COST
        return gap * PER_LEVEL_COST

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        raise RuntimeError(
            "LevelSkill is expanded by the player skill-grind hook (Phase 3); "
            "it must not be executed directly."
        )

    def __repr__(self) -> str:
        return f"LevelSkill({self.skill}->{self.target_level})"
