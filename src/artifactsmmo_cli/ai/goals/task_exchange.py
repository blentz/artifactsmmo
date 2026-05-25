"""TaskExchangeGoal: exchange task coins at the taskmaster for rewards."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


class TaskExchangeGoal(Goal):
    """Exchange task coins when at least one full batch can be spent.

    The per-exchange coin cost is not exposed as API data, so the player learns
    it empirically from HTTP 478 failures and injects the current minimum here;
    the goal never hardcodes the cost.
    """

    def __init__(self, min_coins: int = 1) -> None:
        self._min_coins = min_coins

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 22.0

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items or {}
        return state.inventory.get(TASKS_COIN_CODE, 0) + bank.get(TASKS_COIN_CODE, 0) < self._min_coins

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # After one exchange, inventory drops below the batch threshold.
        target = max(0, state.inventory.get(TASKS_COIN_CODE, 0) - self._min_coins)
        return {"inventory": {TASKS_COIN_CODE: target}}

    def __repr__(self) -> str:
        return "TaskExchange"
