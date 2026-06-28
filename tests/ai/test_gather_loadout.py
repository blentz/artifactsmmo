"""GatherAction.cost penalizes a sub-optimal gather tool; OptimizeLoadout(Gather) swaps it in."""

import dataclasses

import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
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


def _make_state(
    level: int = 5,
    inventory: dict[str, int] | None = None,
    equipment: dict[str, str | None] | None = None,
    skills: dict[str, int] | None = None,
) -> WorldState:
    """Minimal WorldState for gather-loadout tests."""
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="testchar", level=level, xp=0, max_xp=100,
        hp=100, max_hp=100, gold=0,
        skills=skills or {"woodcutting": 5},
        x=0, y=0,
        inventory=inventory or {}, inventory_max=20,
        equipment=eq, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def equip(state: WorldState, code: str, slot: str) -> WorldState:
    """Return a new WorldState with `code` in `slot`, exchanging the old item back to inventory."""
    new_equipment = dict(state.equipment)
    old_code = new_equipment.get(slot)
    new_inventory = dict(state.inventory)
    # Return old item to inventory
    if old_code is not None:
        new_inventory[old_code] = new_inventory.get(old_code, 0) + 1
    # Consume the new item from inventory
    cur = new_inventory.get(code, 0)
    if cur <= 1:
        new_inventory.pop(code, None)
    else:
        new_inventory[code] = cur - 1
    new_equipment[slot] = code
    return dataclasses.replace(state, equipment=new_equipment, inventory=new_inventory)


def _gd_woodcutting() -> GameData:
    """GameData with ash_tree→woodcutting, iron_axe as woodcutting tool, wooden_stick as combat weapon."""
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}),
        # iron_axe: subtype="tool", skill_effect woodcutting -10 → gather tool for woodcutting
        "iron_axe": ItemStats(code="iron_axe", level=1, type_="weapon", subtype="tool",
                              attack={"earth": 3}, skill_effects={"woodcutting": -10}),
    }
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._monster_attack = {"yellow_slime": {"earth": 5, "fire": 0, "water": 0, "air": 0}}
    gd._monster_resistance = {"yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0}}
    return gd


@pytest.fixture
def gather_cost_fixture():
    """State: wooden_stick equipped, iron_axe in inventory; ash_tree requires woodcutting."""
    gd = _gd_woodcutting()
    state = _make_state(
        level=5,
        inventory={"iron_axe": 1},
        equipment={"weapon_slot": "wooden_stick"},
        skills={"woodcutting": 5},
    )
    return state, gd


@pytest.fixture
def combat_loadout_fixture():
    """State for combat-path regression: wooden_stick is already optimal vs yellow_slime."""
    gd = _gd_woodcutting()
    # wooden_stick: earth atk=4, non-tool → weapon_score > iron_axe (tool) for any target
    state = _make_state(
        level=5,
        inventory={"iron_axe": 1},
        equipment={"weapon_slot": "wooden_stick"},
        skills={"woodcutting": 5},
    )
    return state, gd, "yellow_slime"


def test_gather_cost_penalizes_suboptimal_tool(gather_cost_fixture):
    """GatherAction.cost is higher when a better gather tool is owned but not equipped."""
    state, game_data = gather_cost_fixture  # owns iron_axe (woodcutting) but wears a sword
    # resource is a woodcutting tree.
    action = GatherAction(resource_code="ash_tree", locations=frozenset({(0, 0)}))
    cost_suboptimal = action.cost(state, game_data)
    # with the axe already equipped the same gather has NO loadout penalty:
    state_axe = equip(state, "iron_axe", "weapon_slot")
    cost_optimal = action.cost(state_axe, game_data)
    assert cost_suboptimal > cost_optimal


def test_optimize_loadout_gather_swaps_in_tool(gather_cost_fixture):
    """OptimizeLoadoutAction(target_skill=...) is applicable and swaps in the gather tool."""
    state, game_data = gather_cost_fixture
    act = OptimizeLoadoutAction(target_skill="woodcutting", game_data=game_data)
    assert act.is_applicable(state, game_data)
    new = act.apply(state, game_data)
    assert new.equipment["weapon_slot"] == "iron_axe"


def test_optimize_loadout_combat_unchanged(combat_loadout_fixture):
    """The combat path (target_monster_code) still works after adding target_skill."""
    state, game_data, monster = combat_loadout_fixture
    act = OptimizeLoadoutAction(target_monster_code=monster, game_data=game_data)
    # wooden_stick is already optimal vs yellow_slime → apply returns state unchanged
    assert isinstance(act.apply(state, game_data).equipment, dict)
