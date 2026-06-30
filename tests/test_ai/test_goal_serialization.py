"""Round-trip serialization tests for the six plan-bearing goal classes."""

import pytest

from artifactsmmo_cli.ai.goal_serialization import goal_from_dict, goal_to_dict
from artifactsmmo_cli.ai.goals.craft_relief import CraftReliefGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.pursue_task import PursueTaskGoal


def test_gather_round_trips():
    g = GatherMaterialsGoal("copper_ring", {"copper_ore": 6})
    d = goal_to_dict(g)
    assert d["type"] == "GatherMaterialsGoal"
    back = goal_from_dict(d, game_data=None)
    assert repr(back) == repr(g)


def test_gather_needed_round_trips():
    g = GatherMaterialsGoal("ash_plank", {"ash_wood": 10, "copper_ore": 2})
    d = goal_to_dict(g)
    back = goal_from_dict(d, game_data=None)
    assert back._target_item == g._target_item
    assert back._needed == g._needed
    assert repr(back) == repr(g)


def test_craft_relief_round_trips():
    g = CraftReliefGoal("copper_bar", initial_qty=2, batch=3)
    back = goal_from_dict(goal_to_dict(g), game_data=None)
    assert repr(back) == repr(g)
    assert back._batch == 3  # dropped from repr — must still round-trip


def test_craft_relief_defaults_round_trip():
    g = CraftReliefGoal("iron_bar", initial_qty=0)
    d = goal_to_dict(g)
    back = goal_from_dict(d, game_data=None)
    assert back._initial_qty == 0
    assert back._batch == 1
    assert repr(back) == repr(g)


def test_grind_round_trips_target_and_xp():
    """game_data is no longer stored; verify target_monster and initial_xp survive the round-trip."""
    g = GrindCharacterXPGoal("chicken", initial_xp=10)
    back = goal_from_dict(goal_to_dict(g), game_data=None)
    assert back._target_monster == "chicken"
    assert back._initial_xp == 10
    assert repr(back) == repr(g)


def test_grind_round_trips_initial_xp():
    g = GrindCharacterXPGoal("blue_slime", initial_xp=500)
    d = goal_to_dict(g)
    back = goal_from_dict(d, game_data=None)
    assert back._target_monster == "blue_slime"
    assert back._initial_xp == 500


def test_pursue_task_round_trips():
    g = PursueTaskGoal("copper_ore", initial_progress=5, batch=2)
    d = goal_to_dict(g)
    assert d["type"] == "PursueTaskGoal"
    back = goal_from_dict(d, game_data=None)
    assert repr(back) == repr(g)
    assert back._task_code == "copper_ore"
    assert back._initial_progress == 5
    assert back._batch == 2  # dropped from repr — must still round-trip


def test_pursue_task_defaults_round_trip():
    g = PursueTaskGoal("ash_wood", initial_progress=0)
    d = goal_to_dict(g)
    back = goal_from_dict(d, game_data=None)
    assert back._batch == 1
    assert repr(back) == repr(g)


def test_level_skill_round_trips():
    g = LevelSkillGoal("weaponcrafting", target_level=5, initial_skill_xp=100)
    d = goal_to_dict(g)
    assert d["type"] == "LevelSkillGoal"
    back = goal_from_dict(d, game_data=None)
    assert repr(back) == repr(g)
    assert back._skill_name == "weaponcrafting"
    assert back._target_level == 5
    assert back._initial_skill_xp == 100


def test_level_skill_xp_curve_not_serialized():
    g = LevelSkillGoal("gearcrafting", target_level=3)
    d = goal_to_dict(g)
    assert "xp_curve" not in d


def test_upgrade_equipment_no_commitment_round_trips():
    g = UpgradeEquipmentGoal()
    d = goal_to_dict(g)
    assert d["type"] == "UpgradeEquipmentGoal"
    back = goal_from_dict(d, game_data=None)
    assert repr(back) == repr(g)
    assert back._committed_target is None


def test_upgrade_equipment_with_commitment_round_trips():
    g = UpgradeEquipmentGoal(
        initial_equipment={"weapon_slot": "wooden_sword"},
        committed_target=("copper_dagger", "weapon_slot"),
    )
    d = goal_to_dict(g)
    assert d["committed_target"] == ["copper_dagger", "weapon_slot"]
    back = goal_from_dict(d, game_data=None)
    assert repr(back) == repr(g)
    assert back._committed_target == ("copper_dagger", "weapon_slot")
    assert isinstance(back._committed_target, tuple)


def test_upgrade_equipment_initial_equipment_round_trips():
    init_eq = {"weapon_slot": "wooden_sword", "shield_slot": None}
    g = UpgradeEquipmentGoal(initial_equipment=init_eq)
    d = goal_to_dict(g)
    back = goal_from_dict(d, game_data=None)
    assert back._initial_equipment == dict(init_eq)


def test_non_plan_bearing_goal_returns_none():
    class Dummy:  # no serialize()
        pass
    assert goal_to_dict(Dummy()) is None


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown goal type"):
        goal_from_dict({"type": "NonExistent"}, game_data=None)
