"""CurrencyTurnInGoal: buy the vendor item a fleet's dual-role currency pays
for, once `ai.currency_turnin.turn_in_ready_pure` and the per-cycle election
(Task 5, `GamePlayer._resolve_turn_in`) have named this character the buyer.

`relevant_actions` MATERIALIZES its own `WithdrawItemAction` rather than
filtering one out of the ambient action pool: `build_actions` (factory.py)
only emits a Withdraw sized to the OBJECTIVE step's own crafting-closure
demand, and `price` medals is neither a recipe input nor the task's coin —
without a materialized withdraw this goal would be handed a pool with no way
to fund the purchase and could never plan. `NpcBuyAction` needs no such
treatment: `build_actions` already emits one x1 buy per (npc, item) pair in
`GameData.npc_stock` unconditionally (factory.py's "full vendor surface"
loop), so this goal only has to pick the one that matches. Same shape as
`ai/disposal_route.py`'s DEPOSIT arm, which materializes its own
`DepositItemAction` for exactly the same reason — a bank leg sized to a
decision the factory cannot anticipate."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

TURN_IN_PRIORITY = 95.0
"""Fixed urgency when unsatisfied. `select_pure` (arbiter_select.py) never
consults `value()` for a COLLECT_REWARD_ORDER candidate — the walk is purely
`COLLECT_REWARD_ORDER`'s declared order, which is what places this goal —
same as `SUPPLY_BANK` — above the objective step and below every guard. The
constant exists only because `Goal.value` is abstract; its magnitude carries
no selection meaning here."""


class CurrencyTurnInGoal(Goal):
    """Buy one `item_code` from `npc_code` for `price` units of `currency`.

    Satisfied by owning the item at all (bank OR bag) — a character that
    already banked its purchase (e.g. a re-plan after execution) must not
    re-buy a second copy."""

    def __init__(self, item_code: str, npc_code: str, price: int, currency: str) -> None:
        self._item_code = item_code
        self._npc_code = npc_code
        self._price = price
        self._currency = currency

    def _owned(self, state: WorldState) -> int:
        bank = state.bank_items or {}
        return state.inventory.get(self._item_code, 0) + bank.get(self._item_code, 0)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return TURN_IN_PRIORITY

    def is_satisfied(self, state: WorldState) -> bool:
        return self._owned(state) >= 1

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {self._item_code: 1}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Narrow to exactly the two-action chain this goal can ever need: the
        materialized currency withdraw and the one matching NpcBuy leaf. A
        wide pool is what makes this search expensive elsewhere in this repo
        (see the module docstrings this brief points at); this goal has no
        need of it."""
        npc_buys = [a for a in actions
                   if isinstance(a, NpcBuyAction)
                   and a.npc_code == self._npc_code
                   and a.item_code == self._item_code]
        bank_location = game_data.bank_location_or_none or (0, 0)
        withdraw = WithdrawItemAction(code=self._currency, quantity=self._price,
                                      bank_location=bank_location)
        return [withdraw, *npc_buys]

    def __repr__(self) -> str:
        return f"CurrencyTurnIn({self._item_code})"
