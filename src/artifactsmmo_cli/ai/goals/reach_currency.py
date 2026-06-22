"""ReachCurrencyGoal: complete tasks until a currency (e.g. tasks_coin) reaches
a target, to fund a task-currency purchase (jasper_crystal @ tasks_trader).

max_depth is bounded by funding_cycles_pure (proved sufficient in
Formal.Liveness.CurrencyFunding.fundingCycles_sufficient), so the GOAP search has
enough depth to assemble the accept→progress→complete loop without the budget
timeout that pegged the planner before this capability existed."""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

ACTIONS_PER_CYCLE = 3   # accept + one progress action + complete
PRIORITY_WHEN_NEEDED = 1.0  # placeholder ranking; demand routing is C4


class ReachCurrencyGoal(Goal):
    """Drive the task loop until `currency` count reaches `target`."""

    def __init__(self, currency: str, target: int) -> None:
        self._currency = currency
        self._target = target

    def _on_hand(self, state: WorldState) -> int:
        bank = state.bank_items or {}
        return state.inventory.get(self._currency, 0) + bank.get(self._currency, 0)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_NEEDED

    def is_satisfied(self, state: WorldState) -> bool:
        return self._on_hand(state) >= self._target

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {self._currency: self._target}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [a for a in actions
                if isinstance(a, (AcceptTaskAction, CompleteTaskAction,
                                  FightAction, CraftAction))]

    @property
    def max_depth(self) -> int:
        """Conservative WORST CASE: on_hand=0 and the minimum possible floor=1 give
        the MOST cycles (== target), so this depth is always enough for any
        actual on_hand>=0 / floor>=1 (Formal...fundingCycles_sufficient). `max_depth`
        is a PROPERTY (Goal.max_depth) — no state/gd available, hence the static
        worst case. funding_cycles_pure is the LIVE proved-core caller."""
        cycles = funding_cycles_pure(0, self._target, 1)
        return max(ACTIONS_PER_CYCLE, cycles * ACTIONS_PER_CYCLE)

    def __repr__(self) -> str:
        return f"ReachCurrency({self._currency}, {self._target})"
