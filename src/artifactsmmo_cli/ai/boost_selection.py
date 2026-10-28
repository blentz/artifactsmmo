"""Project a utility potion into a utility slot.

``project_equip`` constructs a modified WorldState that models ``code``
force-equipped in a utility slot, so that ``combat_margin`` on the returned
state reads the boosted stats through its one arithmetic path
(``project_loadout_stats``).
"""

import dataclasses

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def project_equip(state: WorldState, code: str | None, game_data: GameData,
                  slot: str = "utility1_slot", *, stock: int) -> WorldState:
    """Return a state with ``stock`` units of ``code`` force-equipped in
    ``slot`` (utility1_slot unless a caller names the other utility slot;
    ``code`` None empties it, holding no units whatever ``stock`` says).

    The stat totals do not move. They are the sheet's, and the sheet leaves a
    worn potion out of them (``equipment.projection``'s module doc, measured
    live): the fight adds the potion a stocked utility slot wears, so wearing
    ``code`` is the slot and its stock alone. Subtracting the potion it
    replaces took off a boost the totals never held.

    Competing utility items are stripped from inventory so pick_loadout
    (called internally by combat_margin) cannot replace ``code`` with a
    higher-scoring utility item, which would defeat the forced-equip
    semantics.
    """
    equipment = {**state.equipment, slot: code}
    # Strip competing utility items from inventory: their presence would let
    # pick_loadout (inside combat_margin) replace ``code`` with a
    # higher-combat-score utility item, defeating forced-equip semantics.
    inventory = {
        k: v for k, v in state.inventory.items()
        if (s := game_data.item_stats(k)) is None
           or s.type_ != "utility"
           or k == code
    }
    units = stock if code else 0
    if slot == "utility1_slot":
        return dataclasses.replace(state, equipment=equipment, inventory=inventory,
                                   utility1_slot_quantity=units)
    return dataclasses.replace(state, equipment=equipment, inventory=inventory,
                               utility2_slot_quantity=units)
