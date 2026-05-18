"""LevelSkillGoal: grind a crafting skill up to unlock a gated upgrade.

Active when a known craftable upgrade requires `target_level` in a given
skill that Robby has not yet reached, AND the gap is small enough that
grinding through it is reasonable. Drives the planner to craft items in
that skill family until the skill levels up.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.bank import DepositAllAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


MAX_SKILL_GAP = 5
"""Don't fire if the level gap exceeds this — too long a grind for one
strategic pivot; better to attempt the current task and let level-ups
trickle in naturally."""

PRIORITY_WHEN_FIRING = 55.0
"""Beats FarmItems(35)/UpgradeEquipment(35-50) so the loop diverts to
skill grinding when an upgrade is gated. Loses to LowYieldCancelGoal(70)
so we still cancel a bad task first."""


class LevelSkillGoal(Goal):
    """Level a specific skill to `target_level` by crafting items in its family."""

    def __init__(self, skill_name: str, target_level: int) -> None:
        self._skill_name = skill_name
        self._target_level = target_level

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return self.priority(state, game_data, history)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        current = state.skills.get(self._skill_name, 0)
        gap = self._target_level - current
        if gap <= 0 or gap > MAX_SKILL_GAP:
            return 0.0
        # Don't fire if no craftable item in this skill family exists at the
        # character's current skill level (no way to make progress).
        if not self._has_craftable_in_skill(state, game_data):
            return 0.0
        return PRIORITY_WHEN_FIRING

    def is_satisfied(self, state: WorldState) -> bool:
        return state.skills.get(self._skill_name, 0) >= self._target_level

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"skills": {self._skill_name: self._target_level}}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """Craft anything in this skill family + supporting Gather/Rest/Deposit."""
        result: list[Action] = []
        for action in actions:
            if isinstance(action, RestAction):
                result.append(action)
            elif isinstance(action, DepositAllAction):
                result.append(action)
            elif isinstance(action, GatherAction):
                # All gathers are fair game; they replenish materials for crafting.
                result.append(action)
            elif isinstance(action, CraftAction):
                stats = game_data.item_stats(action.code)
                if stats is not None and stats.crafting_skill == self._skill_name:
                    result.append(action)
        return result

    @property
    def max_depth(self) -> int:
        # Crafts can need deep recipe chains; budget matches GatherMaterials.
        return 100

    def _has_craftable_in_skill(self, state: WorldState, game_data: GameData) -> bool:
        """True if any recipe in this skill family is craftable at current skill."""
        current = state.skills.get(self._skill_name, 0)
        for item_code, _recipe in game_data._crafting_recipes.items():
            stats = game_data.item_stats(item_code)
            if stats is None or stats.crafting_skill != self._skill_name:
                continue
            if stats.crafting_level <= current:
                return True
        return False

    def __repr__(self) -> str:
        return f"LevelSkill({self._skill_name}->{self._target_level})"
