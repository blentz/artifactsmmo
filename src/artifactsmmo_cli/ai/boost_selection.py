"""Project a utility potion into a utility slot.

``project_equip`` constructs a modified WorldState that models ``code``
force-equipped in utility1_slot, so that ``combat_margin`` on the returned
state reads the boosted stats without a second arithmetic path.
"""

import dataclasses

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def project_equip(state: WorldState, code: str | None, game_data: GameData,
                  slot: str = "utility1_slot") -> WorldState:
    """Return a state with ``code`` force-equipped in ``slot`` (utility1_slot
    unless a caller names the other utility slot; ``code`` None empties it).

    Pre-applies the stat delta from swapping utility1_slot to ``code`` into
    the state's raw stat fields (attack, resistance, dmg_elements, dmg,
    critical_strike, initiative, max_hp), so that project_loadout_stats
    (called internally by combat_margin) sees zero delta for utility1_slot
    and uses the pre-applied stats directly.

    Competing utility items are stripped from inventory so pick_loadout
    (also called internally by combat_margin) cannot replace ``code`` with
    a higher-scoring utility item, which would defeat the forced-equip
    semantics.

    This approach reuses combat_margin end-to-end without a second
    arithmetic path: pick_loadout retains ``code`` in utility1_slot (the
    only utility candidate once competing inventory items are stripped),
    project_loadout_stats sees no delta for that slot, and the projected
    stats equal the pre-applied modified_state fields.
    """
    old_code = state.equipment.get(slot)
    old_s = game_data.item_stats(old_code) if old_code else None
    new_s = game_data.item_stats(code) if code else None
    resistance = {
        e: state.resistance.get(e, 0)
           + (new_s.resistance.get(e, 0) if new_s else 0)
           - (old_s.resistance.get(e, 0) if old_s else 0)
        for e in ELEMENTS
    }
    attack = {
        e: state.attack.get(e, 0)
           + (new_s.attack.get(e, 0) if new_s else 0)
           - (old_s.attack.get(e, 0) if old_s else 0)
        for e in ELEMENTS
    }
    dmg_elements = {
        e: state.dmg_elements.get(e, 0)
           + (new_s.dmg_elements.get(e, 0) if new_s else 0)
           - (old_s.dmg_elements.get(e, 0) if old_s else 0)
        for e in ELEMENTS
    }
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
    return dataclasses.replace(
        state,
        equipment=equipment,
        inventory=inventory,
        attack=attack,
        resistance=resistance,
        dmg_elements=dmg_elements,
        dmg=state.dmg + (new_s.dmg if new_s else 0) - (old_s.dmg if old_s else 0),
        critical_strike=(
            state.critical_strike
            + (new_s.critical_strike if new_s else 0)
            - (old_s.critical_strike if old_s else 0)
        ),
        initiative=(
            state.initiative
            + (new_s.initiative if new_s else 0)
            - (old_s.initiative if old_s else 0)
        ),
        max_hp=(
            state.max_hp
            + (new_s.hp_bonus if new_s else 0)
            - (old_s.hp_bonus if old_s else 0)
        ),
    )

