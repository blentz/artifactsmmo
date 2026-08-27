"""PostBuyBidGoal: post discretionary GE buy orders for objective-step materials
that are slow to self-craft, so long as the bid is cheaper than the NPC/fill
alternative and we are not already acquiring the item another way.

Reactive means (NOT an obtain-graph source): a posted bid fills asynchronously,
so this never claims to synchronously satisfy a material need — it replaces an
otherwise-more-expensive acquisition with a cheaper deferred one. Fire-and-lose,
exactly like DRAIN_BANK_JUNK: posting a bid creates an open order for the item,
which SUPPRESSES it on the next evaluation (`ge_bid_candidates` skips open-order
codes), so the firing signal falls false and the means cannot spin. Suppression
also keeps bid and self-craft mutually exclusive (`bid_vs_craft`).
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.ge_post_buy import GePostBuyOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_bid import ge_bid_candidates
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

POST_BUY_BID_VALUE = 16.0
"""Discretionary opportunistic-acquisition value: above DRAIN_BANK_JUNK (15) —
acquiring a needed material beats draining junk — and below RECYCLE_SURPLUS (20)
and the housekeeping investments, so a bid never preempts material recovery or
objective/gear work. Sits above WAIT."""


class PostBuyBidGoal(Goal):
    """Post one GE buy order per biddable objective-step material.

    The candidate set is `ge_bid.ge_bid_candidates` (shared with the GE_BID
    firing guard). Each `(item, qty, post_price)` becomes one
    `GePostBuyOrderAction`; the least-cost planner posts them one at a time, and
    each post suppresses its item on the next cycle."""

    def __init__(self, game_data: GameData, ctx: SelectionContext) -> None:
        self._gd = game_data
        self._ctx = ctx

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return POST_BUY_BID_VALUE

    def is_satisfied(self, state: WorldState) -> bool:
        return not ge_bid_candidates(
            state, self._gd, self._ctx, TTL_CYCLES)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"ge_bids_posted": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """One GePostBuyOrderAction per biddable objective-step material."""
        ge_loc = game_data.grand_exchange_location()
        if ge_loc is None:
            return []
        return [
            GePostBuyOrderAction(item_code=item, quantity=qty, price=price,
                                 ge_location=ge_loc)
            for item, qty, price in ge_bid_candidates(
                state, game_data, self._ctx, TTL_CYCLES)
        ]

    def __repr__(self) -> str:
        return "PostBuyBid"
