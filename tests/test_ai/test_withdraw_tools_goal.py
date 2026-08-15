"""Unit tests for `WithdrawToolsGoal` — pull strictly-better bank tools into the bag.

The goal only ferries the tool bank->inventory; the proven gather re-arm
(GATHER_LOADOUT_PENALTY + OptimizeLoadout(Gather)) equips it on the next
gather plan once the tool is owned.
"""

from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.withdraw_tools import WithdrawToolsGoal
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(inventory=None, equipment=None, bank_items=None) -> WorldState:
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
        bank_items=bank_items, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def test_not_satisfied_while_tool_is_only_in_bank() -> None:
    goal = WithdrawToolsGoal(fills={"mining": "copper_pickaxe"})
    state = _make_state(bank_items={"copper_pickaxe": 1})
    assert not goal.is_satisfied(state)


def test_satisfied_once_tool_is_in_inventory() -> None:
    goal = WithdrawToolsGoal(fills={"mining": "copper_pickaxe"})
    state = _make_state(inventory={"copper_pickaxe": 1})
    assert goal.is_satisfied(state)


def test_satisfied_once_tool_is_equipped() -> None:
    goal = WithdrawToolsGoal(fills={"mining": "copper_pickaxe"})
    state = _make_state(equipment={"weapon_slot": "copper_pickaxe"})
    assert goal.is_satisfied(state)


def test_zero_inventory_count_is_not_held() -> None:
    goal = WithdrawToolsGoal(fills={"mining": "copper_pickaxe"})
    state = _make_state(inventory={"copper_pickaxe": 0})
    assert not goal.is_satisfied(state)


def test_relevant_actions_are_unit_withdraws_of_missing_tools() -> None:
    goal = WithdrawToolsGoal(fills={"mining": "copper_pickaxe", "woodcutting": "copper_axe"},
                             bank_location=(4, 1), accessible=True)
    state = _make_state(inventory={"copper_axe": 1},
                        bank_items={"copper_pickaxe": 1})
    actions = goal.relevant_actions([], state, GameData())
    assert actions == [WithdrawItemAction(code="copper_pickaxe", quantity=1,
                                          bank_location=(4, 1), accessible=True)]


def test_value_zero_when_satisfied_positive_otherwise() -> None:
    goal = WithdrawToolsGoal(fills={"mining": "copper_pickaxe"})
    gd = GameData()
    assert goal.value(_make_state(inventory={"copper_pickaxe": 1}), gd) == 0.0
    assert goal.value(_make_state(bank_items={"copper_pickaxe": 1}), gd) > 0.0


def test_desired_state_is_sorted_unique_codes() -> None:
    goal = WithdrawToolsGoal(fills={"woodcutting": "copper_axe", "mining": "copper_pickaxe"})
    state = _make_state()
    assert goal.desired_state(state, GameData()) == {
        "tools_held": ("copper_axe", "copper_pickaxe"),
    }


def test_repr_is_deterministic() -> None:
    goal = WithdrawToolsGoal(fills={"woodcutting": "copper_axe", "mining": "copper_pickaxe"})
    assert repr(goal) == ("WithdrawTools([('mining', 'copper_pickaxe'), "
                          "('woodcutting', 'copper_axe')])")
