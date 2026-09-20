"""CompleteTaskGoal: turn in the current task at the taskmaster once finished."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
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

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Drop `TaskCancelAction`. THE TURN-IN IS THE ONLY ROUTE THIS GOAL
        MEANS, and nothing else in the goal says so.

        `desired_state` asks for the ABSENCE of a task, and a cancel clears
        `task_code`/`task_progress`/`task_total` exactly as a turn-in does. The
        two `cost()` bodies are the same `distance_cost_pure(1.0, dist)` to the
        same `taskmaster_location`, so the planner faced an exact tie between a
        reward and a forfeit with nothing in the target to break it.

        Live HAL, 2026-09-19T18:10:10Z: a `skeleton` task reached 362/362 at
        18:07:10, and three minutes later the store recorded
        `selected_goal=CompleteTask`, `action_repr=TaskCancel`. A day of
        grinding forfeited, and a `tasks_coin` spent to forfeit it.

        Filtered HERE rather than priced, because the cancel is not a worse way
        to finish a task -- it is a different decision entirely, and the goal
        that owns it is `TaskCancelGoal` (which fires on a task the character
        cannot progress). Making the turn-in merely CHEAPER would leave the
        cancel reachable whenever the arithmetic shifted; making it
        unreachable from this goal states the intent. The action itself is
        untouched, so the abandon route stays alive for its own goal.
        """
        return [a for a in actions if not isinstance(a, TaskCancelAction)]

    def __repr__(self) -> str:
        return "CompleteTask"
