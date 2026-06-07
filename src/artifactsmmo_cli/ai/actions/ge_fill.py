"""GeFillBuyOrderAction: sell an item into a standing Grand Exchange buy order.

Filling an existing buy order is immediate liquidation — the player sells items
into the order and receives the gold instantly (the buyer gets the items in their
pending list). Mirrors NpcSellAction, but the venue is the GE tile and the proceeds
come from the standing order's price (a realizable, not speculative, figure — see
liquidation_venue.py). We NEVER post a new order here; we only fill one that exists.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_fill_my_name_action_grandexchange_fill_post import (
    sync as action_ge_fill,
)
from artifactsmmo_api_client.models.ge_fill_buy_order_schema import GEFillBuyOrderSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GeFillBuyOrderAction(Action):
    """Move to the Grand Exchange and fill a standing buy order, selling the item
    for immediate gold."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    order_id: str
    item_code: str
    price: int  # the standing order's price per unit (realizable proceeds)
    quantity: int = 1
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        if state.inventory.get(self.item_code, 0) < self.quantity:
            return False
        order = game_data.ge_best_buy_order(self.item_code)
        if order is None:
            return False
        order_id, price, order_qty = order
        # The order this action targets must still stand, still pay what we expect,
        # and still be able to absorb the whole quantity in one fill.
        return order_id == self.order_id and price == self.price and order_qty >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_gold = state.gold + self.price * self.quantity
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(self.item_code, 0) - self.quantity
        if remaining <= 0:
            new_inventory.pop(self.item_code, None)
        else:
            new_inventory[self.item_code] = remaining
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
        return 1.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GEFillBuyOrderSchema(id=self.order_id, quantity=self.quantity)
        result = action_ge_fill(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"GeFill {self.item_code}×{self.quantity} into {self.order_id}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"GeFill({self.item_code}×{self.quantity}@{self.order_id})"
