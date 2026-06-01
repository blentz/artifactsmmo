"""TaskTradeAction: submit gathered items toward an items-type task."""

import dataclasses
from dataclasses import dataclass, field
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_task_trade_my_name_action_task_trade_post import (
    sync as action_task_trade,
)
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class TaskTradeAction(Action):
    """Submit items toward an items-type task at the taskmaster."""

    tags: ClassVar[frozenset[str]] = frozenset({"task"})

    code: str
    quantity: int = 1
    taskmaster_location: tuple[int, int] | None = field(default=None, repr=False)

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if self.taskmaster_location is None:
            return False
        if state.task_type != "items" or state.task_code != self.code:
            return False
        return state.inventory.get(self.code, 0) >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        remaining = new_inventory.get(self.code, 0) - self.quantity
        if remaining <= 0:
            new_inventory.pop(self.code, None)
        else:
            new_inventory[self.code] = remaining
        dest = self.taskmaster_location or (state.x, state.y)
        new_progress = state.task_progress + self.quantity
        return dataclasses.replace(
            state,
            x=dest[0],
            y=dest[1],
            inventory=new_inventory,
            cooldown_expires=None,
            task_progress=new_progress,
            task_lifecycle_phase=derive_task_lifecycle_phase(
                state.task_code, new_progress, state.task_total
            ),
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        dest = self.taskmaster_location or (state.x, state.y)
        dist = abs(dest[0] - state.x) + abs(dest[1] - state.y)
        return 2.0 + dist

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        if self.taskmaster_location and (state.x, state.y) != self.taskmaster_location:
            state = MoveAction(x=self.taskmaster_location[0], y=self.taskmaster_location[1]).execute(state, client)
        body = SimpleItemSchema(code=self.code, quantity=self.quantity)
        result = action_task_trade(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"TaskTrade {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"TaskTrade({self.code}×{self.quantity})"
