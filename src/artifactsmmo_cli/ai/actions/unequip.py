"""UnequipAction: remove an item from an equipment slot back to inventory."""

from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_unequip_item_my_name_action_unequip_post import (
    sync as action_unequip,
)
from artifactsmmo_api_client.models.item_slot import ItemSlot
from artifactsmmo_api_client.models.unequip_schema import UnequipSchema

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


@dataclass
class UnequipAction(Action):
    """Remove an item from an equipment slot and return it to inventory."""

    tags: ClassVar[frozenset[str]] = frozenset({"equip"})

    slot: str

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        return state.equipment.get(self.slot) is not None

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_equipment = dict(state.equipment)
        item_code = new_equipment.pop(self.slot, None)
        new_equipment[self.slot] = None
        new_inventory = dict(state.inventory)
        if item_code:
            new_inventory[item_code] = new_inventory.get(item_code, 0) + 1
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
            equipment=new_equipment,
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
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        body = UnequipSchema(slot=ItemSlot(self.slot.replace("_slot", "")))
        result = action_unequip(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Unequip {self.slot}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"Unequip({self.slot})"
