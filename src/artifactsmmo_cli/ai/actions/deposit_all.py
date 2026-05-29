"""DepositAllAction: move to bank and deposit all bankable inventory items."""

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
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class DepositAllAction(Action):
    """Move to bank and deposit all inventory items."""

    tags: ClassVar[frozenset[str]] = frozenset({"bank", "deposit"})

    bank_location: tuple[int, int] = field(default=(0, 0), repr=False)
    accessible: bool = True  # False when bank is gated behind an unmet achievement (HTTP 496)
    game_data: GameData | None = field(default=None, repr=False)

    def _deposits(self, state: WorldState) -> list[tuple[str, int]]:
        """Items to bank this trip (selective + sell-value ordered), or [] when
        no game_data is available (no banking without data)."""
        if self.game_data is None:
            return []
        return select_bank_deposits(state, self.game_data)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return self.accessible and bool(self._deposits(state))

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        dest = self.bank_location
        new_inventory = dict(state.inventory)
        new_bank = dict(state.bank_items or {})
        for code, qty in self._deposits(state):
            new_bank[code] = new_bank.get(code, 0) + qty
            new_inventory.pop(code, None)
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
        return len(state.inventory) * 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if (state.x, state.y) != self.bank_location:
            state = MoveAction(x=self.bank_location[0], y=self.bank_location[1]).execute(state, client)
        last_state = state
        for code, qty in self._deposits(state):
            body = SimpleItemSchema(code=code, quantity=qty)
            result = deposit_item(client=client, name=state.character, body=[body])
            if result is not None and hasattr(result, "data") and result.data is not None:
                last_state = WorldState.from_character_schema(
                    result.data.character,
                    bank_items=last_state.bank_items,
                    bank_gold=last_state.bank_gold,
                    pending_items=last_state.pending_items,
                    active_events=last_state.active_events,
                )
        return last_state

    def __repr__(self) -> str:
        return "DepositAll"
