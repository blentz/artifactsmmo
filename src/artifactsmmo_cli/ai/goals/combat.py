"""Combat goals: monster farming and task completion."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.dynamic_priority import learned_priority_bonus
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


def best_equipped_level(state: WorldState, game_data: GameData) -> int:
    """Highest item level across all equipped slots, or 0 if nothing is equipped."""
    best = 0
    for code in state.equipment.values():
        if code:
            stats = game_data.item_stats(code)
            if stats and stats.level > best:
                best = stats.level
    return best


class FarmMonsterGoal(Goal):
    """Farm monsters for XP and drops. Satisfied when XP increases from baseline."""

    def __init__(self, monster_code: str, initial_xp: int = 0) -> None:
        self.monster_code = monster_code
        self._initial_xp = initial_xp

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        monster_level = game_data.monster_level(self.monster_code)
        if monster_level > 0 and best_equipped_level(state, game_data) < monster_level - 1:
            return 0.0  # under-equipped — block combat, let upgrade goal take over
        if state.max_xp == 0:
            base = 30.0
        else:
            xp_fraction = state.xp / state.max_xp
            base = 30.0 + xp_fraction * 20.0
        # G-F: layer the scalar-yield bonus on top of the existing
        # XP-fraction base. Replaces the old delta_xp-only multiplier — the
        # scalarizer already weights character XP correctly (level + 1).
        bonus = learned_priority_bonus(repr(self), state, game_data, history)
        return base + bonus

    def is_satisfied(self, state: WorldState) -> bool:
        return state.xp > self._initial_xp

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"xp": self._initial_xp + 10}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        """Restrict planner to Fight on THIS monster plus HP recovery options.

        Without this filter the planner sees every FightAction and may pick a
        cheaper-cost different monster, defeating the purpose of a per-monster goal.
        """
        result: list[Action] = []
        for action in actions:
            if isinstance(action, FightAction) and action.monster_code == self.monster_code:
                result.append(action)
            elif "recovery" in action.tags:
                result.append(action)
            elif "equip" in action.tags and getattr(action, "target_monster_code", None) == self.monster_code:
                result.append(action)
        return result

    def __repr__(self) -> str:
        return f"FarmMonster({self.monster_code})"


class AcceptTaskGoal(Goal):
    """Accept a new task when the character has none."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 20.0

    def is_satisfied(self, state: WorldState) -> bool:
        return bool(state.task_code)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": "__pending__"}

    def __repr__(self) -> str:
        return "AcceptTask"


class CompleteTaskGoal(Goal):
    """Turn in the current task at the taskmaster once it's fully progressed.

    Satisfied when the character has no active task (the post-turn-in state).
    Value is only positive when a finished-but-not-turned-in task is held;
    otherwise this goal stays out of the way.
    """

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        if not state.task_code or state.task_total == 0:
            return 0.0
        if state.task_progress < state.task_total:
            return 0.0
        # Task is full; turning it in is the next move.
        return 90.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": ""}

    def __repr__(self) -> str:
        return "CompleteTask"
