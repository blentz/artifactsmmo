"""Equipment slot vocabulary derives from CharacterSchema and equals the
historical hand-typed maps (no behavior drift)."""

import attrs

from artifactsmmo_api_client.models.character_schema import CharacterSchema

from artifactsmmo_cli.ai.actions.equip import (
    DUPLICATE_SLOT_TYPES,
    ITEM_TYPE_TO_SLOT,
    ITEM_TYPE_TO_SLOTS,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, _DUPLICATE_FILL_TYPES
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyEngine
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS

_HISTORICAL_TYPE_TO_SLOTS = {
    "weapon": ["weapon_slot"],
    "rune": ["rune_slot"],
    "shield": ["shield_slot"],
    "helmet": ["helmet_slot"],
    "body_armor": ["body_armor_slot"],
    "leg_armor": ["leg_armor_slot"],
    "boots": ["boots_slot"],
    "ring": ["ring1_slot", "ring2_slot"],
    "amulet": ["amulet_slot"],
    "artifact": ["artifact1_slot", "artifact2_slot", "artifact3_slot"],
    "utility": ["utility1_slot", "utility2_slot"],
    "bag": ["bag_slot"],
}


def test_equipment_slots_is_schema_slot_fields():
    expected = [f.name for f in attrs.fields(CharacterSchema) if f.name.endswith("_slot")]
    assert EQUIPMENT_SLOTS == expected


def test_type_to_slots_matches_historical():
    assert ITEM_TYPE_TO_SLOTS == _HISTORICAL_TYPE_TO_SLOTS
    assert ITEM_TYPE_TO_SLOT == {t: s[0] for t, s in _HISTORICAL_TYPE_TO_SLOTS.items()}


def test_every_slot_field_maps_to_exactly_one_type():
    flat = [s for slots in ITEM_TYPE_TO_SLOTS.values() for s in slots]
    assert sorted(flat) == sorted(EQUIPMENT_SLOTS)
    assert len(flat) == len(set(flat))


def test_combat_gear_slots_includes_rune_and_artifact():
    """After gear reclassification, combat gear slots include rune/artifact slots.
    Previously _COMBAT_GEAR_SLOTS was a module-level constant without rune/artifact.
    Now derived dynamically from game_data.combat_gear_types via _combat_gear_slots().
    Spec: docs/superpowers/plans/2026-06-28-gear-taxonomy.md
    """
    gd = GameData()
    gd._item_stats = {
        "vampiric_rune": ItemStats(code="vampiric_rune", level=1, type_="rune", lifesteal=10),
        "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact", hp_bonus=25),
        "copper_sword": ItemStats(code="copper_sword", level=1, type_="weapon", attack={"fire": 5}),
        "copper_shield": ItemStats(code="copper_shield", level=1, type_="shield", resistance={"fire": 3}),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet", resistance={"fire": 2}),
        "copper_armor": ItemStats(code="copper_armor", level=1, type_="body_armor", resistance={"fire": 4}),
        "copper_legs": ItemStats(code="copper_legs", level=1, type_="leg_armor", resistance={"fire": 2}),
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots", resistance={"fire": 1}),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring", attack={"fire": 2}),
        "copper_amulet": ItemStats(code="copper_amulet", level=1, type_="amulet", resistance={"fire": 3}),
    }
    obj = CharacterObjective.from_game_data(gd)
    eng = StrategyEngine(obj, BalancedPersonality())
    slots = eng._combat_gear_slots(gd)
    # Core armor/weapon slots (unchanged from old _COMBAT_GEAR_SLOTS).
    assert {"weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
            "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
            "amulet_slot"} <= slots
    # Reclassified: rune and artifact slots now included.
    assert "rune_slot" in slots
    assert "artifact1_slot" in slots
    assert "artifact2_slot" in slots
    assert "artifact3_slot" in slots


def test_dup_fill_is_single_source():
    assert _DUPLICATE_FILL_TYPES is DUPLICATE_SLOT_TYPES
    assert DUPLICATE_SLOT_TYPES == frozenset({"ring", "artifact"})
