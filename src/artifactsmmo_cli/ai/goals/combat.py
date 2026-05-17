"""Combat goals: monster farming and task completion."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
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
        if history is None:
            return base
        fight_repr = f"Fight({self.monster_code})"
        observed_xp = history.action_effect(fight_repr, "delta_xp", window=50)
        if observed_xp is None:
            return base
        xp_multiplier = min(2.0, max(0.5, observed_xp / 10.0))
        return base * xp_multiplier

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
            elif isinstance(action, (RestAction, UseConsumableAction)):
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
    """Complete the current character task (monster kills, gathering, or crafting)."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if not state.task_code or state.task_total == 0:
            return 0.0
        progress_fraction = state.task_progress / state.task_total
        return 50.0 + progress_fraction * 40.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.task_progress >= state.task_total and state.task_total > 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": state.task_total}

    def __repr__(self) -> str:
        return "CompleteTask"
