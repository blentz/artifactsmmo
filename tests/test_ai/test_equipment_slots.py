"""Equipment slot vocabulary derives from CharacterSchema and equals the
historical hand-typed maps (no behavior drift)."""

import attrs
from artifactsmmo_api_client.models.character_schema import CharacterSchema

from artifactsmmo_cli.ai.actions.equip import (
    DUPLICATE_SLOT_TYPES,
    ITEM_TYPE_TO_SLOT,
    ITEM_TYPE_TO_SLOTS,
)
from artifactsmmo_cli.ai.tiers.objective import _DUPLICATE_FILL_TYPES
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
    assert expected == EQUIPMENT_SLOTS


def test_type_to_slots_matches_historical():
    assert ITEM_TYPE_TO_SLOTS == _HISTORICAL_TYPE_TO_SLOTS
    assert {t: s[0] for t, s in _HISTORICAL_TYPE_TO_SLOTS.items()} == ITEM_TYPE_TO_SLOT


def test_every_slot_field_maps_to_exactly_one_type():
    flat = [s for slots in ITEM_TYPE_TO_SLOTS.values() for s in slots]
    assert sorted(flat) == sorted(EQUIPMENT_SLOTS)
    assert len(flat) == len(set(flat))


def test_dup_fill_is_single_source():
    assert _DUPLICATE_FILL_TYPES is DUPLICATE_SLOT_TYPES
    assert frozenset({"ring", "artifact"}) == DUPLICATE_SLOT_TYPES
