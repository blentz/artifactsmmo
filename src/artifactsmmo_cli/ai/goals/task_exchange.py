"""TaskExchangeGoal: exchange ONE batch of task coins at the taskmaster."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


def tasks_coin_total(state: WorldState) -> int:
    """Inventory + bank tasks_coin total (bank-unknown counts as zero)."""
    bank = state.bank_items or {}
    return state.inventory.get(TASKS_COIN_CODE, 0) + bank.get(TASKS_COIN_CODE, 0)


class TaskExchangeGoal(Goal):
    """Exchange task coins when at least one full batch can be spent.

    ONE-batch semantics: the goal captures the inventory+bank coin total at
    construction and is satisfied as soon as that total has dropped by at
    least one batch (`min_coins`) — i.e. after a single executed exchange.
    The pre-fix "drain ALL coins" reading (`total < min_coins`) made the
    minimum plan ~`total/min_coins` exchanges long, which exceeded max_depth
    and produced a guaranteed planner timeout storm whenever coins
    accumulated (and the exchange never executed, so the real cost was never
    learned). One batch matches the formal cycle model
    (formal/Formal/Liveness/CycleStep.lean: one `.taskExchange` per cycle)
    and Formal.Phase10GoalLattices.taskExchangeSatisfied.

    The per-exchange coin cost is not exposed as API data, so the player
    learns it empirically (HTTP 478 failures / success coin deltas) and
    injects the current minimum here; the goal never hardcodes the cost.
    """

    def __init__(self, min_coins: int = 1, *, initial_total: int) -> None:
        self._min_coins = min_coins
        self._initial_total = initial_total

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return 22.0

    def is_satisfied(self, state: WorldState) -> bool:
        # Satisfied once one batch has been spent from the construction-time
        # total. The threshold clamps at 0 (Nat subtraction in the Lean model:
        # Formal.Phase10GoalLattices.taskExchangeSatisfied), so a goal
        # constructed below one batch is satisfied only at zero coins.
        return tasks_coin_total(state) <= max(0, self._initial_total - self._min_coins)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        # After ONE exchange, the inventory pool drops by one batch.
        target = max(0, state.inventory.get(TASKS_COIN_CODE, 0) - self._min_coins)
        return {"inventory": {TASKS_COIN_CODE: target}}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData
    ) -> list[Action]:
        """Scope to the exchange itself, tasks_coin withdraws (bank-held
        coins must pass through inventory), and DepositAll (the exchange
        needs >= 1 free slot for the reward). Everything else — every
        gather/craft/fight in the game — cannot move the coin total and
        only widens the search, which is what let the pre-fix goal burn a
        full planning budget even while unplannable."""
        return [
            action for action in actions
            if (
                isinstance(action, TaskExchangeAction)
                or (isinstance(action, WithdrawItemAction) and action.code == TASKS_COIN_CODE)
                or isinstance(action, DepositAllAction)
            )
        ]

    def __repr__(self) -> str:
        return "TaskExchange"
