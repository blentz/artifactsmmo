from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.goals.equip_owned_gear import EQUIP_GEAR_VALUE, EquipOwnedGoal
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}

def _make_state(inventory=None, equipment=None) -> WorldState:
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="c", level=10, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory=inventory or {}, inventory_max=20,
        inventory_slots_max=len(inventory or {}),
        equipment=eq, cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )

def test_unsatisfied_and_valued_when_fill_pending() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide"})
    state = _make_state(inventory={"novice_guide": 1}, equipment={"artifact1_slot": None})
    assert goal.is_satisfied(state) is False
    assert goal.value(state, GameData()) == EQUIP_GEAR_VALUE

def test_satisfied_when_target_slot_filled() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide"})
    state = _make_state(equipment={"artifact1_slot": "novice_guide"})
    assert goal.is_satisfied(state) is True
    assert goal.value(state, GameData()) == 0.0

def test_desired_state_targets_fill_slots() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide"})
    state = _make_state(inventory={"novice_guide": 1})
    assert goal.desired_state(state, GameData()) == {"equipment": {"artifact1_slot": "novice_guide"}}

def test_relevant_actions_emit_equip_per_fill() -> None:
    goal = EquipOwnedGoal(fills={"artifact1_slot": "novice_guide", "weapon_slot": "wooden_staff"})
    state = _make_state(inventory={"novice_guide": 1, "wooden_staff": 1})
    acts = goal.relevant_actions([], state, GameData())
    assert {(a.code, a.slot) for a in acts} == {("novice_guide", "artifact1_slot"), ("wooden_staff", "weapon_slot")}
    assert all(isinstance(a, EquipAction) for a in acts)

def test_empty_fills_is_satisfied_zero_value() -> None:
    goal = EquipOwnedGoal(fills={})
    state = _make_state()
    assert goal.is_satisfied(state) is True
    assert goal.value(state, GameData()) == 0.0
