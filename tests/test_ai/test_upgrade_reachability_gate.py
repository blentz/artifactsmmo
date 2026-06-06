"""UpgradeEquipmentGoal.is_plannable: the provably-sound depth-based reachability
gate (formal/Formal/PlannerDepthBound.lean).

A committed UpgradeEquipment target that needs more gather actions than the
goal's max_depth can NEVER be planned (the planner never returns a plan longer
than max_depth), so the arbiter must skip it instead of burning the 90s search
budget. copper_boots from scratch = 8 copper_bar × 10 copper_ore = 80 gathers ≫
max_depth 15 — the real Robby first-cycle stall.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from tests.test_ai.fixtures import make_state


def _gd_boots() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    return gd


def test_not_plannable_when_from_scratch_exceeds_max_depth():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={})  # boots_slot empty by default
    assert goal.is_plannable(state, _gd_boots()) is False


def test_plannable_when_materials_in_inventory():
    # 8 copper_bar in hand ⇒ 0 gathers ⇒ short craft+equip plan within max_depth.
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={"copper_bar": 8})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_materials_in_bank():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={"copper_bar": 8})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_target_already_owned():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={"copper_boots": 1})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_already_satisfied():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(equipment={"boots_slot": "copper_boots"})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_no_upgrade_target():
    """Uncommitted goal with no available upgrade: find_upgrade_target is None,
    so there is nothing to gate — defer to normal planning (returns True)."""
    goal = UpgradeEquipmentGoal()  # uncommitted, empty game_data ⇒ no upgrade
    state = make_state(inventory={})
    assert goal.is_plannable(state, GameData()) is True
