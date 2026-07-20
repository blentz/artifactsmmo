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
from artifactsmmo_cli.ai.inventory_room import has_room
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

# Item types whose code may legally occupy MORE THAN ONE slot, up to physical
# ownership. Live-server probe 2026-06-14 (character Robby): a 2nd identical
# copper_ring equipped into ring2_slot returned HTTP 200 — the server allows
# duplicate rings. Artifacts (3 slots) JOIN rings here: the game exposes three
# artifact slots and the dual-ring probe establishes the server's per-slot (not
# per-code) equip model, so a 2nd identical artifact is asserted-allowed. This
# is NOT yet live-probed (no character can hold ≥2 of a duplicable artifact yet
# — see the spec's probe trigger: on the first ≥2-owned artifact, confirm the
# 2nd-copy equip returns HTTP 200, else revert "artifact"). All remaining types
# keep the strict one-slot-per-code rule (HTTP 485 "already equipped";
# documented utility small_health_potion case). Shared with
# `equipment/scoring.py` (pick_loadout cap) and the objective layer's
# `_DUPLICATE_FILL_TYPES` (both read this set generically).
DUPLICATE_SLOT_TYPES: frozenset[str] = frozenset({"ring", "artifact"})


@dataclass
class EquipAction(Action):
    """Equip an item from the inventory into its equipment slot."""

    tags: ClassVar[frozenset[str]] = frozenset({"equip"})

    code: str
    slot: str
    quantity: int = 1

    def is_applicable(self, state: WorldState, game_data: GameData) -> bool:
        if state.inventory.get(self.code, 0) < self.quantity:
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
        # NET-SLOT ROOM: equipping C into self.slot displaces the currently
        # worn item O (state.equipment[self.slot]). Quantity is conserved by
        # the swap (added_qty=0: -1 C, +1 O). O needs a NEW slot only if it is
        # a genuinely new stack (not already held elsewhere in inventory); C
        # frees its own slot only if equipping consumes its ENTIRE held stack.
        # Net new-slot need = max(0, O_needs_slot - C_frees_slot). Without
        # this guard a full bag can plan an equip whose displaced item has
        # nowhere to land, which is non-executable on the server.
        displaced = state.equipment.get(self.slot)
        o_needs_slot = 1 if (displaced is not None
                             and displaced not in state.inventory) else 0
        c_frees_slot = 1 if state.inventory.get(self.code, 0) == self.quantity else 0
        new_stacks = max(0, o_needs_slot - c_frees_slot)
        if not has_room(new_stacks, added_qty=0,
                        slots_free=state.inventory_slots_free,
                        qty_free=state.inventory_free):
            return False
        return state.level >= stats.level

    def apply(self, state: WorldState, game_data: GameData) -> WorldState:
        new_inventory = dict(state.inventory)
        new_inventory[self.code] = new_inventory.get(self.code, 0) - self.quantity
        if new_inventory[self.code] <= 0:
            del new_inventory[self.code]

        new_equipment = dict(state.equipment)
        old_item = new_equipment.get(self.slot)
        new_equipment[self.slot] = self.code
        if old_item:
            new_inventory[old_item] = new_inventory.get(old_item, 0) + 1

        # Utility equip is additive for same-code (confirmed by maintainer 2026-06-30).
        # Equipping q of a code into a utility slot that already holds the SAME code
        # ADDS to the stack (M + q); into an empty/different slot it SETS the quantity
        # to q (returning any displaced code to inventory, handled above).
        if self.slot not in ("utility1_slot", "utility2_slot"):
            return dataclasses.replace(
                state,
                inventory=new_inventory,
                equipment=new_equipment,
                cooldown_expires=None,
            )
        prior_qty = (state.utility1_slot_quantity if self.slot == "utility1_slot"
                     else state.utility2_slot_quantity) if old_item == self.code else 0
        qty = prior_qty + self.quantity
        if self.slot == "utility1_slot":
            return dataclasses.replace(
                state,
                inventory=new_inventory,
                equipment=new_equipment,
                cooldown_expires=None,
                utility1_slot_quantity=qty,
            )
        return dataclasses.replace(
            state,
            inventory=new_inventory,
            equipment=new_equipment,
            cooldown_expires=None,
            utility2_slot_quantity=qty,
        )

    def cost(self, state: WorldState, game_data: GameData,
             history: LearningStore | None = None) -> float:
        return 1.0

    def execute(self, state: WorldState, client: AuthenticatedClient) -> WorldState:
        body = EquipSchema(code=self.code, slot=ItemSlot(self.slot.replace("_slot", "")),
                           quantity=self.quantity)
        result = action_equip(client=client, name=state.character, body=[body])
        result = Action._raise_for_error(result, f"Equip {self.code} to {self.slot}")
        return WorldState.from_character_schema(
            result.data.character,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
            raids=state.raids,
        )

    def __repr__(self) -> str:
        if self.quantity > 1:
            return f"Equip({self.code}x{self.quantity}->{self.slot})"
        return f"Equip({self.code}->{self.slot})"
