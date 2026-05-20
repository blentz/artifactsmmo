"""DeleteItemAction: remove an item from inventory (no materials returned)."""

from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_delete_item_my_name_action_delete_post import sync as action_delete
from artifactsmmo_api_client.models.simple_item_schema import SimpleItemSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class DeleteItemAction(Action):
    """Delete an item from inventory — frees quantity when bank is inaccessible."""

    tags: ClassVar[frozenset[str]] = frozenset({"cleanup"})

    code: str
    quantity: int = 1
    cost_weight: float = 2.0  # higher = planner avoids this item; set >2 for crafting ingredients

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.inventory.get(self.code, 0) >= self.quantity

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) - self.quantity
        if new_inventory[self.code] <= 0:
            del new_inventory[self.code]
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=state.x,
            y=state.y,
            inventory=new_inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=None,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return self.cost_weight

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        body = SimpleItemSchema(code=self.code, quantity=self.quantity)
        result = action_delete(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Delete {self.code}×{self.quantity}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"Delete({self.code}×{self.quantity})"
