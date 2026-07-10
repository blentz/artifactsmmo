"""Shared test fixtures for AI module tests."""

import attrs
from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_api_client.models.map_layer import MapLayer

from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState


def make_character_schema(**overrides) -> CharacterSchema:
    """Build a fully-populated real CharacterSchema for testing.

    All attrs-required fields (no default) are auto-filled: str→"", int→0,
    ``layer`` enum→MapLayer.OVERWORLD. Callers may override any field via
    keyword arguments (e.g. ``utility1_slot="small_health_potion"``,
    ``utility1_slot_quantity=40``).
    """
    kwargs: dict[str, object] = {}
    for f in attrs.fields(CharacterSchema):
        if f.default is not attrs.NOTHING:
            continue
        if f.name == "layer":
            kwargs[f.name] = MapLayer.OVERWORLD
        elif f.type is str:
            kwargs[f.name] = ""
        else:
            kwargs[f.name] = 0
    kwargs["name"] = "hero"
    kwargs.update(overrides)
    return CharacterSchema(**kwargs)


def make_state(**overrides) -> WorldState:
    """Build a minimal WorldState for testing, with safe defaults.

    Auto-derives ``task_lifecycle_phase`` from ``task_code``/``task_progress``/
    ``task_total`` so existing call-sites (which only set the raw fields) keep
    constructing valid WorldStates after Phase 23c-1. Tests that need to
    construct invariant-violating states should call ``WorldState(...)``
    directly rather than going through this fixture.
    """
    defaults = dict(
        character="testchar",
        level=5,
        xp=100,
        max_xp=500,
        hp=100,
        max_hp=150,
        gold=50,
        skills={"mining": 3, "woodcutting": 2, "fishing": 1, "weaponcrafting": 1,
                "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=0,
        y=0,
        inventory={},
        inventory_max=20,
        inventory_slots_max=20,
        equipment={
            "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
            "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
            "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
            "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
            "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
        },
        cooldown_expires=None,
        task_code=None,
        task_type=None,
        task_progress=0,
        task_total=0,
        bank_items=None,
        bank_gold=None,
        bank_capacity=None,
        pending_items=None,
    )
    defaults.update(overrides)
    if "task_lifecycle_phase" not in defaults:
        defaults["task_lifecycle_phase"] = derive_task_lifecycle_phase(
            defaults["task_code"], defaults["task_progress"], defaults["task_total"]
        )
    return WorldState(**defaults)
