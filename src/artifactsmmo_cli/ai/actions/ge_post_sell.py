"""GePostSellOrderAction: POST a new Grand Exchange sell order, escrowing the item.

Unlike GeFillBuyOrderAction (which fills a standing buy order for immediate gold),
posting lists our OWN sell order: the item leaves the inventory now (escrow) and the
gold arrives later when a buyer fills it. Settlement is reconciled from the API each
cycle (see reconciliation). The price is chosen fail-closed and floor-bounded by
ge_post_pricing.sell_post_price at the call site — this action just carries it.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_create_sell_order_my_name_action_grandexchange_create_sell_order_post import (  # noqa: E501
    sync as action_ge_create_sell_order,
)
from artifactsmmo_api_client.models.ge_order_creation_schema import GEOrderCreationSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.cost_core import distance_cost_pure
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GePostSellOrderAction(Action):
    """Move to the Grand Exchange and post a new sell order, escrowing the item."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    item_code: str
    quantity: int
    price: int
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        return state.inventory.get(self.item_code, 0) >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        held = state.inventory.get(self.item_code, 0)
        if held < self.quantity:
            raise AssertionError(
                f"GePostSellOrderAction.apply: held={held} < quantity={self.quantity} "
                f"— is_applicable invariant violated"
            )
        new_inventory = dict(state.inventory)
        remaining = held - self.quantity
        if remaining <= 0:
            new_inventory.pop(self.item_code, None)
        else:
            new_inventory[self.item_code] = remaining
        dest = self.ge_location or (state.x, state.y)
        # Optimistic predicted id; reconciliation replaces it with the real id.
        new_order = OpenOrder(
            id=f"pending:{self.item_code}:{self.price}", code=self.item_code,
            qty=self.quantity, price=self.price, side=OrderSide.SELL, age=0,
        )
        new_orders = tuple(sorted(
            (*state.open_orders, new_order),
            key=lambda o: (o.side.value, o.code, o.price, o.id),
        ))
        return dataclasses.replace(
            state, x=dest[0], y=dest[1], inventory=new_inventory,
            open_orders=new_orders, cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return distance_cost_pure(2.0, dist)

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GEOrderCreationSchema(code=self.item_code, quantity=self.quantity, price=self.price)
        result = action_ge_create_sell_order(client=client, name=state.character, body=body)
        result = Action._raise_for_error(
            result, f"GePostSell {self.item_code}×{self.quantity}@{self.price}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids, open_orders=state.open_orders,
        )

    def __repr__(self) -> str:
        return f"GePostSell({self.item_code}×{self.quantity}@{self.price})"
