"""ReachSkillGoal: reach `target_level` in one skill.

Served by decomposition (`craft_plan_gen._decompose_grind`, Phase 2d-a): one
grind cycle's committed legs, ending in the leg that earns the skill's XP. It
admits no actions to the search (Phase 2d-b2): the `LevelSkill` macro it used
to admit left the action pool, and a grind is not a search problem.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Inlined from LevelSkillGoal.PRIORITY_WHEN_FIRING (level_skill.py:32) so arbiter
# ordering is UNCHANGED when the PURSUE_TASK skill grind routes here instead:
# beats FarmItems(35)/UpgradeEquipment(35-50), stays under 70.
PRIORITY_WHEN_FIRING = 55.0


class ReachSkillGoal(Goal):
    """Reach `target_level` in `skill_name` (served by its grind's decomposition)."""

    def __init__(self, skill_name: str, target_level: int) -> None:
        self._skill_name = skill_name
        self._target_level = target_level

    @property
    def skill(self) -> str:
        return self._skill_name

    @property
    def target_level(self) -> int:
        return self._target_level

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_FIRING

    def is_satisfied(self, state: WorldState) -> bool:
        return state.skills.get(self._skill_name, 1) >= self._target_level

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"skills": {self._skill_name: self._target_level}}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """None: the grind is decomposition's (module docstring). When it
        declines, the search has nothing to try and gives up at once instead
        of exploring the whole pool."""
        return []

    @property
    def max_depth(self) -> int:
        # Mirrors LevelSkillGoal.max_depth (level_skill.py:167-169).
        return 100

    def serialize(self) -> dict[str, object]:
        return {"type": "ReachSkillGoal",
                "skill_name": self._skill_name,
                "target_level": self._target_level}

    def __repr__(self) -> str:
        return f"ReachSkill({self._skill_name}->{self._target_level})"
