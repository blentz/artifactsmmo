"""TaskCancelGoal: cancel any task that is infeasible for the character."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import PIVOT, task_decision
from artifactsmmo_cli.ai.world_state import WorldState


class TaskCancelGoal(Goal):
    """Cancel the current task when it is infeasible for the character.

    Fires for ANY task type (fight or non-fight): a monster task whose target is
    well above the character's level, or an items task whose target item needs a
    crafting skill level the character has not reached. Low priority (12) so the
    bot attempts feasible tasks first and only cancels as an escape.
    """

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 12.0 if task_decision(state, game_data, history) == PIVOT else 0.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": None, "task_total": 0}

    def __repr__(self) -> str:
        return "TaskCancel"
