"""TaskExchangeGoal: exchange task coins at the taskmaster for rewards."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

_TASKS_COIN = "tasks_coin"


class TaskExchangeGoal(Goal):
    """Exchange task coins when any are held in inventory or bank."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 22.0

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items or {}
        return state.inventory.get(_TASKS_COIN, 0) + bank.get(_TASKS_COIN, 0) == 0

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {_TASKS_COIN: 0}}

    def __repr__(self) -> str:
        return "TaskExchange"
