"""TaskCancelGoal: cancel a task whose monster target is above the character's reach."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState


class TaskCancelGoal(Goal):
    """Cancel the current task when the target monster is too strong to kill.

    Only applies to monster tasks. Triggers at low priority (12) so the bot
    attempts the task first and cancels as a last resort when stuck.
    """

    def value(self, state: WorldState, game_data: GameData) -> float:
        if not self._task_is_too_hard(state, game_data):
            return 0.0
        return 12.0

    def is_satisfied(self, state: WorldState) -> bool:
        return not state.task_code or state.task_total == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_code": None, "task_total": 0}

    def _task_is_too_hard(self, state: WorldState, game_data: GameData) -> bool:
        if state.task_type != "monsters" or not state.task_code:
            return False
        monster_level = game_data.monster_level(state.task_code)
        return monster_level > 0 and monster_level > state.level + 2

    def __repr__(self) -> str:
        return "TaskCancel"
