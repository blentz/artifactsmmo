"""Shared test fixtures for AI module tests."""

from artifactsmmo_cli.ai.world_state import WorldState


def make_state(**overrides) -> WorldState:
    """Build a minimal WorldState for testing, with safe defaults."""
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
        pending_items=None,
    )
    defaults.update(overrides)
    return WorldState(**defaults)
