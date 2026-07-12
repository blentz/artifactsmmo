"""ReachSkillGoal: reach `target_level` in one skill via the planner-native
LevelSkill action.

A THIN goal (P3a Task 2): where the retired LevelSkillGoal drove an in-search
craft/gather grind, this goal simply admits the `LevelSkill(skill, target_level)`
action — whose optimistic `apply` sets the skill to `target_level` in the
simulated plan — and lets the planner sequence it. The PURSUE_TASK skill-grind
branch of the strategy driver constructs this instead of LevelSkillGoal, which
P3b retires.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Inlined from LevelSkillGoal.PRIORITY_WHEN_FIRING (level_skill.py:32) so arbiter
# ordering is UNCHANGED when the PURSUE_TASK skill grind routes here instead:
# beats FarmItems(35)/UpgradeEquipment(35-50), loses to LowYieldCancelGoal(70).
PRIORITY_WHEN_FIRING = 55.0


class ReachSkillGoal(Goal):
    """Reach `target_level` in `skill_name` by aiming the LevelSkill action."""

    def __init__(self, skill_name: str, target_level: int) -> None:
        self._skill_name = skill_name
        self._target_level = target_level

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
        """The `"skill_grind"`-tagged actions (LevelSkill) whose skill matches
        this goal's target. Duck-typed (no LevelSkill import): this goal targets
        exactly ONE skill, so a plain skill-name match suffices — no (skill,level)
        gating set is needed."""
        return [action for action in actions
                if "skill_grind" in action.tags
                and getattr(action, "skill", None) == self._skill_name]

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
