"""Select the best craftable-now boost potion by combat-margin gain vs a monster.

``best_boost_potion`` ranks utility items carrying a boost effect
(dmg_elements, resistance, or hp_bonus > 0) that are craftable now, by
the margin gain they yield against a specific monster.  Returns the code
with the greatest strictly-positive gain; None when none qualifies.
Deterministic smallest-code tie-break (sorted iteration, strict > comparison).

``project_equip`` constructs a modified WorldState that models ``code``
force-equipped in utility1_slot, so that ``combat_margin`` on the returned
state reads the boosted stats without a second arithmetic path.
"""

import dataclasses

from artifactsmmo_cli.ai.combat import combat_margin
from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def project_equip(state: WorldState, code: str, game_data: GameData) -> WorldState:
    """Return a state with ``code`` force-equipped in utility1_slot.

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
    old_code = state.equipment.get("utility1_slot")
    old_s = game_data.item_stats(old_code) if old_code else None
    new_s = game_data.item_stats(code)
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
    equipment = {**state.equipment, "utility1_slot": code}
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


def best_boost_potion(
    state: WorldState, game_data: GameData, monster_code: str
) -> str | None:
    """Return the craftable-now boost potion that maximises combat-margin gain.

    Candidate set: items with type_=="utility" carrying a boost effect
    (dmg_elements or resistance non-empty, or hp_bonus > 0 — NOT hp_restore,
    which is a heal) that are craftable-now (crafting_skill is not None and
    state.skills[crafting_skill] >= crafting_level).

    Ranking: gain = combat_margin(project_equip(state, code, game_data),
    game_data, monster_code) - combat_margin(state, game_data, monster_code).

    Returns the code with the greatest STRICTLY POSITIVE gain; None when none
    qualifies.  Deterministic smallest-code tie-break: sorted() iteration with
    a strict ``>`` comparison keeps the first (alphabetically smallest) code
    among equals.
    """
    baseline = combat_margin(state, game_data, monster_code)
    best_code: str | None = None
    best_gain = 0
    for code in sorted(game_data.crafting_recipes):
        stats = game_data.item_stats(code)
        if stats is None or stats.type_ != "utility":
            continue
        if not (stats.dmg_elements or stats.resistance or stats.hp_bonus > 0):
            continue
        if stats.crafting_skill is None:
            continue
        if state.skills.get(stats.crafting_skill, 0) < stats.crafting_level:
            continue
        projected = project_equip(state, code, game_data)
        gain = combat_margin(projected, game_data, monster_code) - baseline
        if gain > best_gain:
            best_code = code
            best_gain = gain
    return best_code
