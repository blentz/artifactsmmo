"""Decide whether the active task is feasible for the character right now.

Returns the gating skill requirement (or None when already feasible). Pure — no
API calls, no learning. Used by TaskCancelGoal, the LevelSkill prerequisite
wiring, and the cost-analysis decision.
"""

from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState

# A monster more than this many levels above the character is "too hard" — the
# existing TaskCancel rule, kept for parity.
MONSTER_LEVEL_MARGIN = 2


@dataclass(frozen=True)
class SkillRequirement:
    """A skill the character must raise to do the current task.

    For combat tasks `skill == "combat"` and the levels are character levels.
    """

    skill: str
    required_level: int
    current_level: int


def task_requirement(state: WorldState, game_data: GameData) -> SkillRequirement | None:
    """Gating requirement for the active task, or None if already feasible."""
    if not state.task_code or state.task_total == 0:
        return None
    if state.task_type == "monsters":
        monster_level = game_data.monster_level(state.task_code)
        if monster_level > 0 and monster_level > state.level + MONSTER_LEVEL_MARGIN:
            return SkillRequirement("combat", monster_level, state.level)
        return None
    if state.task_type == "items":
        return _item_skill_gap(state.task_code, state, game_data, seen=set())
    return None


def _item_skill_gap(item_code: str, state: WorldState, game_data: GameData,
                    seen: set[str]) -> SkillRequirement | None:
    """Largest unmet crafting-skill gap to produce item_code, recursing into
    craft ingredients. Returns the requirement with the highest required_level
    among unmet skills, or None if everything is within reach."""
    if item_code in seen:
        return None
    seen.add(item_code)
    worst: SkillRequirement | None = None
    stats = game_data.item_stats(item_code)
    if stats is not None and stats.crafting_skill:
        current = state.skills.get(stats.crafting_skill, 0)
        if current < stats.crafting_level:
            worst = SkillRequirement(stats.crafting_skill, stats.crafting_level, current)
    recipe = game_data.crafting_recipe(item_code) or {}
    for ingredient in recipe:
        sub = _item_skill_gap(ingredient, state, game_data, seen)
        if sub is not None and (worst is None or sub.required_level > worst.required_level):
            worst = sub
    return worst
