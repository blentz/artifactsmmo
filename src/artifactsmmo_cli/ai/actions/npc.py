"""NpcBuyAction: purchase an item from an NPC merchant."""

import dataclasses
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_npc_buy_item_my_name_action_npc_buy_post import (
    sync as action_npc_buy,
)
from artifactsmmo_api_client.models.npc_merchant_buy_schema import NpcMerchantBuySchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.event_availability import event_npc_tradeable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class NpcBuyAction(Action):
    """Move to an NPC merchant and purchase an item."""

    tags: ClassVar[frozenset[str]] = frozenset({"npc"})

    npc_code: str
    item_code: str
    quantity: int = 1
    npc_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.npc_location is None:
            return False
        price = game_data.npc_sells_item(self.npc_code, self.item_code)
        if price is None:
            return False
        if state.gold < price * self.quantity:
            return False
        return event_npc_tradeable(
            self.npc_code, game_data,
            x=state.x, y=state.y,
            active_events=state.active_events,
            now=datetime.now(timezone.utc),
        )

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        price = game_data.npc_sells_item(self.npc_code, self.item_code) or 0
        new_gold = state.gold - price * self.quantity
        new_inventory = dict(state.inventory)
        new_inventory[self.item_code] = new_inventory.get(self.item_code, 0) + self.quantity
        dest = self.npc_location or (state.x, state.y)
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
        dest = self.npc_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        price = game_data.npc_sells_item(self.npc_code, self.item_code) or 0
        # Gold cost scaled to action cost: 1 unit per 10 gold.
        return 2.0 + dist + price * self.quantity / 10.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.npc_location and (state.x, state.y) != self.npc_location:
            state = MoveAction(x=self.npc_location[0], y=self.npc_location[1]).execute(state, client)
        body = NpcMerchantBuySchema(code=self.item_code, quantity=self.quantity)
        result = action_npc_buy(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"NpcBuy {self.item_code}×{self.quantity} from {self.npc_code}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"NpcBuy({self.item_code}×{self.quantity}@{self.npc_code})"
