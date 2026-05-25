"""PursueTaskGoal: advance an items-type task by one unit via gather/craft -> TaskTrade.

The PURSUE actuator for items tasks. Re-plans each cycle (the arbiter executes
only plan[0]), so desired_state targets one more traded unit; satisfied the
moment progress advances or the task is full/gone, letting the arbiter re-decide
against fresh API-observed state.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Matches the retired FarmItems value (35) so task pursuit slots at the same
# weight as the behavior it restores.
PRIORITY_WHEN_FIRING = 35.0
"""Priority when an items task is being pursued. Mirrors retired FarmItems(35)."""


class PursueTaskGoal(Goal):
    """Drive gather/craft -> TaskTrade to advance an items-type task one unit."""

    def __init__(self, task_code: str, initial_progress: int) -> None:
        self._task_code = task_code
        self._initial_progress = initial_progress

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_FIRING

    def is_satisfied(self, state: WorldState) -> bool:
        if not state.task_code or state.task_total == 0:
            return True
        if state.task_progress >= state.task_total:
            return True
        return state.task_progress > self._initial_progress

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"task_progress": self._initial_progress + 1}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags:
                result.append(action)
            elif isinstance(action, (GatherAction, CraftAction, TaskTradeAction)):
                result.append(action)
        return result

    @property
    def max_depth(self) -> int:
        return 100

    def __repr__(self) -> str:
        return f"PursueTask({self._task_code})"
