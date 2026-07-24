"""CancelOrdersGoal: cancel posted GE orders the bot needs undone now — on-need
(a SELL order whose item the active step needs back; a BUY order while gold is short)
plus TTL (any order aged past `TTL_CYCLES`).

Reactive guard goal (NOT an obtain-graph source): cancelling reverses an order's
escrow and REMOVES it from the open-order set, so a target that is cancelled is gone
from `cancel_targets` on the next evaluation — the firing signal falls false and the
guard cannot spin (fire-and-lose, exactly like DRAIN_BANK_JUNK / GE_BID). This is the
escape that underwrites the liveness guarantee that no posted order's capital is
locked forever.
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
                 needed_items: frozenset[str]) -> None:
        self._gd = game_data
        self._need_gold = need_gold
        self._needed_items = needed_items

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return CANCEL_ORDERS_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not cancel_targets(
            state, self._gd, self._need_gold, self._needed_items)

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
                state, game_data, self._need_gold, self._needed_items)
        ]

    def __repr__(self) -> str:
        return "CancelOrders"
