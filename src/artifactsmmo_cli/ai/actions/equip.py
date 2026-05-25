"""EquipAction and the item-type-to-slot mappings shared by equipment logic."""

from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_equip_item_my_name_action_equip_post import sync as action_equip
from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

ITEM_TYPE_TO_SLOT: dict[str, str] = {
    "weapon": "weapon_slot",
    "shield": "shield_slot",
    "helmet": "helmet_slot",
    "body_armor": "body_armor_slot",
    "leg_armor": "leg_armor_slot",
    "boots": "boots_slot",
    "ring": "ring1_slot",
    "amulet": "amulet_slot",
    "artifact": "artifact1_slot",
    "utility": "utility1_slot",
    "bag": "bag_slot",
    "rune": "rune_slot",
}

# All eligible slots per item type. Types with multiple slots (ring, artifact, utility)
# are filled left-to-right; the planner considers each slot independently.
ITEM_TYPE_TO_SLOTS: dict[str, list[str]] = {
    **{k: [v] for k, v in ITEM_TYPE_TO_SLOT.items()},
    "ring": ["ring1_slot", "ring2_slot"],
    "artifact": ["artifact1_slot", "artifact2_slot", "artifact3_slot"],
    "utility": ["utility1_slot", "utility2_slot"],
}


@dataclass
class EquipAction(Action):
    """Equip an item from the inventory into its equipment slot."""

    tags: ClassVar[frozenset[str]] = frozenset({"equip"})

    code: str
    slot: str

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.inventory.get(self.code, 0) <= 0:
            return False
        stats = game_data.item_stats(self.code)
        if stats is None:
            return False
        return state.level >= stats.level

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) - 1
        if new_inventory[self.code] <= 0:
            del new_inventory[self.code]

        new_equipment = dict(state.equipment)
        old_item = new_equipment.get(self.slot)
        new_equipment[self.slot] = self.code
        if old_item:
            new_inventory[old_item] = new_inventory.get(old_item, 0) + 1

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
        body = EquipSchema(code=self.code, slot=ItemSlot(self.slot.replace("_slot", "")))
        result = action_equip(client=client, name=state.character, body=body)
        result = Action._raise_for_error(result, f"Equip {self.code} to {self.slot}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def __repr__(self) -> str:
        return f"Equip({self.code}->{self.slot})"
