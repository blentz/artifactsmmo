"""CurrencyTurnInGoal: buy the vendor item a fleet's dual-role currency pays
for, once `ai.currency_turnin.turn_in_ready_pure` and the per-cycle election
(Task 5, `GamePlayer._resolve_turn_in`) have named this character the buyer.

THE BUYER FUNDS ITSELF FIRST (fix-round-2, CRITICAL). `NpcBuyAction` pays the
currency out of INVENTORY, not the bank, and the buyer's own worn copies are
one `UnequipAction` away from inventory. So the chain is: unequip each worn
copy → withdraw only the REMAINDER the bank must supply → buy. The earlier
shape — always `Withdraw(currency x price)`, no unequip leg — livelocked the
buyer permanently whenever its own holdings were part of what made the fleet
ready: buyer wears 1, carries 1, bank holds 8, price 10 ⇒ `fleet_total` is 10
so this character WINS the election, then plans nothing forever because
`WithdrawItemAction.is_applicable` wants 10 in a bank that holds 8. That is
the most likely winner, not an edge case: the election's upgrade gate
(`GamePlayer._resolve_turn_in` rule 3) favours a character the item is an
upgrade for, and a medal-wearer is a natural winner.

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
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.currency_turnin import buyer_bank_draw_pure
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

    def _held(self, state: WorldState) -> int:
        """The buyer's OWN spendable units: carried plus worn. A worn copy
        counts because one `UnequipAction` moves it into inventory, which is
        where `NpcBuyAction` takes payment from — the same reason
        `dual_role_holdings` counts worn units as fleet currency."""
        return state.inventory.get(self._currency, 0) + len(self._worn_slots(state))

    def _worn_slots(self, state: WorldState) -> list[str]:
        return [slot for slot, code in state.equipment.items() if code == self._currency]

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Narrow to exactly the chain this goal can ever need: an Unequip for
        each of the buyer's own worn copies, the materialized bank withdraw
        sized to what those copies do NOT cover, and the one matching NpcBuy
        leaf. A wide pool is what makes this search expensive elsewhere in
        this repo (see the module docstrings this brief points at); this goal
        has no need of it.

        The Unequip legs are what make the plan REACHABLE rather than merely
        expressible: `UnequipAction.is_applicable` needs `inventory_free >= 1`,
        so the planner is free to order them before the withdraw fills the
        bag — and it must be handed both legs to have that choice at all.

        A zero-sized withdraw is omitted entirely: a buyer already carrying
        the whole price needs no bank leg, and `Withdraw(x0)` is a degenerate
        no-op the planner would have to step over.

        A withdraw is omitted for a SECOND reason too: no known bank tile. The
        earlier code read `bank_location_or_none or (0, 0)`, inventing map tile
        (0,0) as the bank — a fabricated game fact CLAUDE.md forbids ("use only
        API data or fail with an error") that would route a real Move to a tile
        the server never called a bank. The precedent for the honest shape is
        `ai/disposal_route.py` / `ai/bank_drain.py` / `ai/goals/sell_inventory.py`:
        no bank location, no bank leg — the buyer can still fund itself from
        its own worn and carried copies, and is simply un-plannable when those
        do not cover the price."""
        npc_buys = [a for a in actions
                   if isinstance(a, NpcBuyAction)
                   and a.npc_code == self._npc_code
                   and a.item_code == self._item_code]
        unequips = [a for a in actions
                   if isinstance(a, UnequipAction)
                   and state.equipment.get(a.slot) == self._currency]
        draw = buyer_bank_draw_pure(self._price, self._held(state))
        bank_location = game_data.bank_location_or_none
        if draw <= 0 or bank_location is None:
            return [*unequips, *npc_buys]
        withdraw = WithdrawItemAction(code=self._currency, quantity=draw,
                                      bank_location=bank_location)
        return [*unequips, withdraw, *npc_buys]

    def __repr__(self) -> str:
        return f"CurrencyTurnIn({self._item_code})"
