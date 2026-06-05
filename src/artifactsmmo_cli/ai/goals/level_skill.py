"""LevelSkillGoal: grind a crafting skill up to unlock a gated upgrade.

Active when a known craftable upgrade requires `target_level` in a given
skill that Robby has not yet reached, AND the gap is small enough that
grinding through it is reasonable. Drives the planner to craft items in
that skill family until the skill levels up.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

MAX_SKILL_GAP = 5
"""Don't fire if the level gap exceeds this — too long a grind for one
strategic pivot; better to attempt the current task and let level-ups
trickle in naturally."""

# Beats FarmItems(35)/UpgradeEquipment(35-50); loses to LowYieldCancelGoal(70).
# Inlined from retired priorities.py (LEVEL_SKILL = 55.0).
PRIORITY_WHEN_FIRING = 55.0
"""Beats FarmItems(35)/UpgradeEquipment(35-50) so the loop diverts to
skill grinding when an upgrade is gated. Loses to LowYieldCancelGoal(70)
so we still cancel a bad task first."""


class LevelSkillGoal(Goal):
    """Level a specific skill to `target_level` by crafting items in its family."""

    def __init__(self, skill_name: str, target_level: int, initial_skill_xp: int = 0,
                 xp_curve: SkillXpCurve | None = None) -> None:
        self._skill_name = skill_name
        self._target_level = target_level
        self._initial_skill_xp = initial_skill_xp
        # SkillXpCurve maps current skill_level -> XP needed to advance. Empty
        # curve (no observations) means the planner has no learned XP-to-next-
        # level estimate; projection-based satisfaction is disabled in that
        # case and the goal falls back to the skills-level snapshot check.
        self._xp_curve = xp_curve if xp_curve is not None else SkillXpCurve()

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        current = state.skills.get(self._skill_name, 0)
        gap = self._target_level - current
        # NOTE: the strategy driver bounds target_level to current+LEVEL_LOOKAHEAD,
        # so with MAX_SKILL_GAP=5 this guard stays inert for the objective-step
        # path (gap <= 3). The "don't grind too far" intent is handled by the
        # bounded target + per-cycle replan. The guard still protects any other
        # (small-gap) caller.
        if gap <= 0 or gap > MAX_SKILL_GAP:
            return 0.0
        # Don't fire if no craftable item in this skill family exists at the
        # character's current skill level (no way to make progress).
        if not self._has_craftable_in_skill(state, game_data):
            return 0.0
        return PRIORITY_WHEN_FIRING

    def is_satisfied(self, state: WorldState) -> bool:
        # Two satisfaction paths:
        #   (1) Server-snapshot path: skills[skill] already at/above target.
        #       This is the post-API truth (skills only advances after a real
        #       API call refreshes the snapshot via from_character_schema).
        #   (2) Planner-projection path: the per-plan-path
        #       `projected_skill_xp_delta` accumulator (mutated by Gather/Craft
        #       .apply, NOT a baseline field) has pushed
        #       `state.skill_xp + projected_delta` past the XP threshold needed
        #       to reach `target_level`. The threshold is `required_xp` from
        #       the learned SkillXpCurve at the goal's current observed level;
        #       with no observations (default empty curve) projection-based
        #       satisfaction is disabled (the curve returns 0, which we treat
        #       as "no estimate" — only path (1) applies).
        if state.skills.get(self._skill_name, 0) >= self._target_level:
            return True
        current_level = state.skills.get(self._skill_name, 0)
        required = self._xp_curve.required_xp(current_level)
        if required <= 0:
            return False
        current_xp = state.skill_xp.get(self._skill_name, 0)
        projected = state.projected_skill_xp_delta.get(self._skill_name, 0)
        return current_xp + projected >= required

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"skills": {self._skill_name: self._target_level}}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """Craft anything in this skill family + supporting Gather / Rest /
        Deposit / Withdraw. Withdraw is included so the planner can pull
        already-banked recipe inputs instead of re-gathering them — closes
        the same regrind regression seen in PursueTaskGoal."""
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags:
                result.append(action)
            elif "withdraw" in action.tags:
                # Any banked material may be a recipe input for a craft in
                # this skill family; let the planner figure out which.
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
