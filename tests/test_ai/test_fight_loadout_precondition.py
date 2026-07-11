"""FightAction.is_applicable hard-requires the equipped loadout to match the
best on-hand combat loadout, so the planner sequences OptimizeLoadout first."""

import dataclasses

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _gd() -> GameData:
    """cow: water-weak, water_bow beats copper_pickaxe (mining tool). Monster
    level is seeded at 4 (not the flavor-lore 1) via the real settable
    `_monster_level` property (GameData exposes no `_monster_levels` plural)
    so that xp_per_kill(cow, char_level=13) clears the diff<10 lower gate —
    the loadout gate is being tested in isolation from the xp gate."""
    gd = GameData()
    gd._item_stats = {
        "water_bow": ItemStats(code="water_bow", level=1, type_="weapon",
                               attack={"water": 8}),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    subtype="tool", attack={"earth": 5},
                                    skill_effects={"mining": -10}),
    }
    gd._monster_attack = {"cow": {"earth": 3, "fire": 0, "water": 0, "air": 0}}
    gd._monster_resistance = {"cow": {"earth": 0, "fire": 0, "water": 0, "air": 0}}
    gd._monster_level = {"cow": 4}
    return gd


def _state(equipment: dict[str, str | None], inventory: dict[str, int]) -> WorldState:
    eq = dict(_ALL_SLOTS)
    eq.update(equipment)
    return WorldState(
        character="testchar", level=13, xp=0, max_xp=1000,
        hp=100, max_hp=100, gold=0,
        skills={"mining": 5}, x=0, y=0,
        inventory=inventory, inventory_max=20, inventory_slots_max=20,
        equipment=eq, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


@pytest.fixture
def cow_fight() -> FightAction:
    return FightAction(monster_code="cow", locations=frozenset({(0, 0)}))


def test_inapplicable_when_gathering_tool_equipped(cow_fight: FightAction) -> None:
    """The exact live bug: pickaxe in weapon_slot, water_bow owned in inventory.
    pick_loadout picks water_bow so the equipped pickaxe is suboptimal -> the
    fight is NOT applicable (planner must OptimizeLoadout first)."""
    gd = _gd()
    state = _state(equipment={"weapon_slot": "copper_pickaxe"},
                   inventory={"water_bow": 1})
    assert cow_fight.is_applicable(state, gd) is False


def test_applicable_when_optimal_loadout_equipped(cow_fight: FightAction) -> None:
    """water_bow already equipped and no better weapon owned -> equipped ==
    optimal -> the fight is applicable."""
    gd = _gd()
    state = _state(equipment={"weapon_slot": "water_bow"}, inventory={})
    assert cow_fight.is_applicable(state, gd) is True


def test_loadout_gate_applies_to_drop_farm(cow_fight: FightAction) -> None:
    """drop_farm bypasses ONLY the xp gate; a drop-farm fight with a suboptimal
    loadout is still inapplicable."""
    gd = _gd()
    farm = dataclasses.replace(cow_fight, drop_farm=True)
    state = _state(equipment={"weapon_slot": "copper_pickaxe"},
                   inventory={"water_bow": 1})
    assert farm.is_applicable(state, gd) is False


def test_structurally_applicable_true_when_only_loadout_gate_fails(
    cow_fight: FightAction,
) -> None:
    """Task 5b Part 1: `_structurally_applicable` is the pre-loadout gate set.
    Same suboptimal-loadout state as test_inapplicable_when_gathering_tool_equipped
    (is_applicable False), but every STRUCTURAL gate (locations, inventory room,
    HP floor, level+2, xp-positive) passes -> _structurally_applicable is True.
    This is what lets the directed craft generator admit a dropper whose
    loadout merely needs a swap (Task 5b Part 2/3), instead of bailing to A*."""
    gd = _gd()
    state = _state(equipment={"weapon_slot": "copper_pickaxe"},
                   inventory={"water_bow": 1})
    assert cow_fight.is_applicable(state, gd) is False
    assert cow_fight._structurally_applicable(state, gd) is True


def test_structurally_applicable_false_when_structural_gate_fails(
    cow_fight: FightAction,
) -> None:
    """A structural gate failure (monster over level+2 of the character) makes
    _structurally_applicable False too -- the helper is not a rubber stamp,
    it still enforces the guards is_winnable is blind to."""
    gd = _gd()
    gd._monster_level = {"cow": 20}  # char level 13 + 2 = 15 ceiling; 20 > 15
    state = _state(equipment={"weapon_slot": "water_bow"}, inventory={})
    assert cow_fight._structurally_applicable(state, gd) is False
    assert cow_fight.is_applicable(state, gd) is False
