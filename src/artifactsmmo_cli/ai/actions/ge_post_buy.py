"""GePostBuyOrderAction: POST a new Grand Exchange buy order, escrowing the gold.

Dual of GePostSellOrderAction. Gold leaves now (escrow); the item arrives later,
into the character's pending list, when a seller fills the order — reconciled from
the API each cycle. The price is chosen fail-closed and ceiling-bounded by
ge_post_pricing.buy_post_price at the call site. Honours the progression reserve
floor exactly like GeFillSellOrderAction so bidding never starves core spending.
"""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_ge_create_buy_order_my_name_action_grandexchange_create_buy_order_post import (  # noqa: E501
    sync as action_ge_create_buy_order,
)
from artifactsmmo_api_client.models.ge_buy_order_creation_schema import GEBuyOrderCreationSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.progression_reserve import reserve_floor
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class GePostBuyOrderAction(Action):
    """Move to the Grand Exchange and post a new buy order, escrowing the gold."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    item_code: str
    quantity: int
    price: int
    ge_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.ge_location is None:
            return False
        cost = self.price * self.quantity
        return state.gold - cost >= reserve_floor(state, game_data, self.item_code)

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        cost = self.price * self.quantity
        if state.gold - cost < reserve_floor(state, game_data, self.item_code):
            raise AssertionError(
                f"GePostBuyOrderAction.apply: gold={state.gold} - cost={cost} below "
                f"reserve floor — is_applicable invariant violated"
            )
        dest = self.ge_location or (state.x, state.y)
        new_order = OpenOrder(
            id=f"pending:{self.item_code}:{self.price}", code=self.item_code,
            qty=self.quantity, price=self.price, side=OrderSide.BUY, age=0,
        )
        new_orders = tuple(sorted(
            (*state.open_orders, new_order),
            key=lambda o: (o.side.value, o.code, o.price, o.id),
        ))
        return dataclasses.replace(
            state, gold=state.gold - cost, x=dest[0], y=dest[1],
            open_orders=new_orders, cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.ge_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist + self.price * self.quantity / 10.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.ge_location and (state.x, state.y) != self.ge_location:
            state = MoveAction(x=self.ge_location[0], y=self.ge_location[1]).execute(state, client)
        body = GEBuyOrderCreationSchema(code=self.item_code, quantity=self.quantity, price=self.price)
        result = action_ge_create_buy_order(client=client, name=state.character, body=body)
        result = Action._raise_for_error(
            result, f"GePostBuy {self.item_code}×{self.quantity}@{self.price}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items, bank_gold=state.bank_gold,
            pending_items=state.pending_items, active_events=state.active_events,
            raids=state.raids, open_orders=state.open_orders,
        )

    def __repr__(self) -> str:
        return f"GePostBuy({self.item_code}×{self.quantity}@{self.price})"
