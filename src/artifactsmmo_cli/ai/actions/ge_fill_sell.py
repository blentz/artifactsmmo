"""GeFillSellOrderAction: BUY an item by filling a standing Grand Exchange sell order.

This is the DUAL of GeFillBuyOrderAction. Filling an existing SELL order is immediate
acquisition — the player buys items from the order and receives them instantly,
paying the standing order's price (a realizable, not speculative, cost — see
buy_source_venue.py). It mirrors NpcBuyAction's gold/slot gates (the buy must keep
gold above GOLD_RESERVE and have free slots) but the venue is the GE tile and the
price comes from the standing sell order. We NEVER post a new order here; we only
fill one that already exists (the anti-surrogate guard).
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_buy_item_my_name_action_grandexchange_buy_post import (
    sync as action_ge_buy,
)
from artifactsmmo_api_client.models.ge_buy_order_schema import GEBuyOrderSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.craft_vs_buy import GOLD_RESERVE  # noqa: F401 — kept for later task
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GeFillSellOrderAction(Action):
    """Move to the Grand Exchange and fill a standing SELL order, buying the item for
    immediate, guaranteed acquisition."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    order_id: str
    item_code: str
    price: int  # the standing order's price per unit (realizable cost)
    quantity: int = 1
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        # Slot-floor: buying mints +quantity; refuse if it would overflow the cap.
        if state.inventory_free < self.quantity:
            return False
        # Gold gate: the buy must leave gold at or above the progression reserve
        # floor (mirrors craft_vs_buy's affordability constraint and NpcBuyAction's
        # gold gate, but honours the dynamic per-state reserve rather than a flat cap).
        if state.gold - self.price * self.quantity < reserve_floor(state, game_data, self.item_code):
            return False
        order = game_data.ge_best_sell_order(self.item_code)
        if order is None:
            return False
        order_id, price, order_qty = order
        # The order this action targets must still stand, still cost what we expect,
        # and still be able to supply the whole quantity in one fill.
        return order_id == self.order_id and price == self.price and order_qty >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        # Defense in depth: assert the slot-floor precondition before mutating
        # (matches NpcBuyAction.apply); any precondition bypass crashes loudly
        # rather than silently overflowing the inventory cap.
        if state.inventory_free < self.quantity:
            raise AssertionError(
                f"GeFillSellOrderAction.apply: inventory_free={state.inventory_free} "
                f"< quantity={self.quantity} — is_applicable invariant violated"
            )
        new_gold = state.gold - self.price * self.quantity
        new_inventory = dict(state.inventory)
        new_inventory[self.item_code] = new_inventory.get(self.item_code, 0) + self.quantity
        dest = self.ge_location or (state.x, state.y)
        return dataclasses.replace(
            state,
            gold=new_gold,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        # Gold cost scaled to action cost (mirrors NpcBuyAction): 1 unit per 10 gold.
        return 2.0 + dist + self.price * self.quantity / 10.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GEBuyOrderSchema(id=self.order_id, quantity=self.quantity)
        result = action_ge_buy(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"GeBuy {self.item_code}×{self.quantity} from {self.order_id}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"GeBuy({self.item_code}×{self.quantity}@{self.order_id})"
