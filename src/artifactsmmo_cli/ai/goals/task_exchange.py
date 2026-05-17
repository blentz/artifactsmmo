"""TaskExchangeGoal: exchange task coins at the taskmaster for rewards."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

_TASKS_COIN = "tasks_coin"
# API burns 3 coins per exchange; goal must not fire with fewer or TaskExchange
# loops on HTTP 478.
_EXCHANGE_COST = 3


class TaskExchangeGoal(Goal):
    """Exchange task coins when at least one full batch can be spent."""

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 22.0

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items or {}
        return state.inventory.get(_TASKS_COIN, 0) + bank.get(_TASKS_COIN, 0) < _EXCHANGE_COST

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # After one exchange, inventory drops below the batch threshold.
        target = max(0, state.inventory.get(_TASKS_COIN, 0) - _EXCHANGE_COST)
        return {"inventory": {_TASKS_COIN: target}}

    def __repr__(self) -> str:
        return "TaskExchange"
