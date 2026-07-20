"""DepositItemAction: move to bank and deposit a specific item."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_deposit_bank_item_my_name_action_bank_deposit_item_post import (
    sync as deposit_item,
)
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class DepositItemAction(Action):
    """Move to bank and deposit a specific item (single code, batch quantity).

    The disposal-route DEPOSIT arm (`ai/disposal_route.py`): banks one
    overstocked code's excess in one cycle, unlike `DepositAllAction` which
    sweeps every bankable code through `select_bank_deposits`.
    """

    tags: ClassVar[frozenset[str]] = frozenset({"bank", "deposit"})

    code: str
    quantity: int
    bank_location: tuple[int, int] = field(default=(0, 0), repr=False)
    accessible: bool = True  # False when bank is gated behind an unmet achievement (HTTP 496)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return (
            state.inventory.get(self.code, 0) >= self.quantity
            and bank_has_room(self.accessible, state.bank_items,
                              game_data.bank_capacity)
        )

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) - self.quantity
        if new_inventory[self.code] <= 0:
            del new_inventory[self.code]
        new_bank = dict(state.bank_items or {})
        new_bank[self.code] = new_bank.get(self.code, 0) + self.quantity
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            bank_items=new_bank,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.bank_location
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        body = SimpleItemSchema(code=self.code, quantity=self.quantity)
        result = deposit_item(client=client, name=state.character, body=[body])
        result = Action._raise_for_error(result, f"DepositItem {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        return f"DepositItem({self.code}×{self.quantity})"
