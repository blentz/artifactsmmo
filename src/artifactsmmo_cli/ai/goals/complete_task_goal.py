"""CompleteTaskGoal: turn in the current task at the taskmaster once finished."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


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
