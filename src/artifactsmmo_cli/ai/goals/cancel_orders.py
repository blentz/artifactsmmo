"""CancelOrdersGoal: cancel posted GE orders the bot needs undone now — on-need
(a SELL order whose item the active step needs back; a BUY order while gold is short)
plus TTL (any order aged past `TTL_CYCLES`).

Reactive guard goal (NOT an obtain-graph source): cancelling reverses an order's
escrow and REMOVES it from the open-order set, so a target that is cancelled is gone
from `cancel_targets` on the next evaluation — the firing signal falls false and the
guard cannot spin (fire-and-lose, exactly like DRAIN_BANK_JUNK / GE_BID). This is the
escape that underwrites the liveness guarantee that no posted order's capital is
locked forever.

FIRE-AND-LOSE HOLDS ONLY FOR A CANCEL THAT SUCCEEDS. A SELL cancel MINTS the
escrowed stack back into the bag, so a full bag refuses it (HTTP 497) and the
order stays open — it is a target again next cycle, and the guard re-picks the
same id. That is a spin, and it is not hypothetical: live 2026-09-09/10 it took
685 of 4465 cycles across five characters and drove Lor to `stuck_exit`.
`GeCancelOrderAction.is_applicable` now carries the slot+quantity room gate, so
an unreceivable cancel is never planned and the guard falls through to the next
rung instead of burning the cycle. The order is then held — NOT freed — until
DepositInventory / DiscardOverstock make room, which is the honest weakening of
the guarantee below: "no capital is locked forever" becomes "no capital is
locked forever, given the bag can receive it".
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.cancel_selection import cancel_targets
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

CANCEL_ORDERS_VALUE = 40.0
"""Guard-tier value: guards run on the fixed priority ladder (not by value), so this
is only read when a caller ranks the mapped goal directly. Positive-when-unsatisfied
is all that is required."""


class CancelOrdersGoal(Goal):
    """Cancel every order `cancel_selection.cancel_targets` reports.

    Each target order id becomes one `GeCancelOrderAction`; the least-cost planner
    cancels them one at a time, and each cancel removes its order from the target set
    on the next cycle."""

    def __init__(self, game_data: GameData, need_gold: int,
                 needed_items: frozenset[str],
                 sibling_claims: frozenset[str] = frozenset()) -> None:
        self._gd = game_data
        self._need_gold = need_gold
        self._needed_items = needed_items
        # Order ids a sibling is already cancelling — held as constructor state,
        # not re-read per planner node, because it is a per-CYCLE fact: the
        # planner explores hypothetical futures of THIS cycle, and a claim set
        # that changed mid-search would make `is_satisfied` non-deterministic
        # across nodes of one plan.
        self._sibling_claims = sibling_claims

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return CANCEL_ORDERS_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not cancel_targets(
            state, self._gd, self._need_gold, self._needed_items,
            self._sibling_claims)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"ge_orders_cancelled": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """One GeCancelOrderAction per order id in the cancel-target set."""
        ge_loc = game_data.grand_exchange_location()
        if ge_loc is None:
            return []
        return [
            GeCancelOrderAction(order_id=order_id, ge_location=ge_loc)
            for order_id in cancel_targets(
                state, game_data, self._need_gold, self._needed_items,
                self._sibling_claims)
        ]

    def __repr__(self) -> str:
        return "CancelOrders"
