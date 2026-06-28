"""EquipAction and the item-type-to-slot mappings shared by equipment logic."""

import dataclasses
from dataclasses import dataclass
from typing import ClassVar

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.my_characters.action_equip_item_my_name_action_equip_post import sync as action_equip
from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOT as ITEM_TYPE_TO_SLOT
from artifactsmmo_cli.ai.gear_taxonomy import ITEM_TYPE_TO_SLOTS as ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.gear_taxonomy import _derive_type_to_slots as _derive_type_to_slots
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Item types whose code may legally occupy MORE THAN ONE slot, up to physical
# ownership. Live-server probe 2026-06-14 (character Robby): a 2nd identical
# copper_ring equipped into ring2_slot returned HTTP 200 — the server allows
# duplicate rings. Every other type keeps the strict one-slot-per-code rule
# (HTTP 485 "already equipped"; documented utility small_health_potion case).
# Shared with `equipment/scoring.py` (pick_loadout cap) and matches the
# objective layer's `_DUPLICATE_FILL_TYPES`.
DUPLICATE_SLOT_TYPES: frozenset[str] = frozenset({"ring"})


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
        # Slot/type compatibility: the planner enumerates EquipAction over
        # ITEM_TYPE_TO_SLOTS[stats.type_] in player.py, so the matched slot
        # must be one of those for this item's type. A mismatched slot (e.g.
        # equipping a ring code into a helmet slot) would project successfully
        # but fail execute on the server. Without this gate, a stale or buggy
        # caller could produce a non-executable plan.
        if self.slot not in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
            return False
        # ONE SLOT PER CODE — except duplicate-allowed types (rings). For a
        # non-dup code the server rejects equipping a code already worn
        # elsewhere with HTTP 485 ("This item is already equipped"). Without
        # this gate the planner plans a second copy into an empty sibling slot
        # (e.g. small_health_potion already in utility1 -> utility2), the equip
        # 485s, state is unchanged, and the identical plan re-derives every cycle
        # (the Robby utility2 livelock). Keying on code (not slot) keeps two
        # DIFFERENT consumables across the utility slots legal.
        #
        # Rings are EXEMPT: a 2nd identical ring into the sibling slot returns
        # HTTP 200 (probe 2026-06-14). The inventory check above already requires
        # a physical spare copy, so a dup-allowed equip is realizable (mirrors
        # Formal.RealizableLoadout: dup-allowed codes are capped at ownership).
        if stats.type_ not in DUPLICATE_SLOT_TYPES and any(
            equipped == self.code
            for slot, equipped in state.equipment.items()
            if slot != self.slot
        ):
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

        return dataclasses.replace(
            state,
            inventory=new_inventory,
            equipment=new_equipment,
            cooldown_expires=None,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        body = EquipSchema(code=self.code, slot=ItemSlot(self.slot.replace("_slot", "")))
        result = action_equip(client=client, name=state.character, body=[body])
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
