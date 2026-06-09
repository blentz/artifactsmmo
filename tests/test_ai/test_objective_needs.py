"""Tests for objective_needs: the committed objective's unmet NeedSet."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.objective_needs import objective_needs
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon",
                                crafting_skill="weaponcrafting", crafting_level=10),
        "iron_bar": ItemStats(code="iron_bar", level=10, type_="resource",
                              crafting_skill="mining", crafting_level=10),
        "iron_ore": ItemStats(code="iron_ore", level=10, type_="resource"),
        "magic_orb": ItemStats(code="magic_orb", level=5, type_="resource"),
    }
    gd._crafting_recipes = {
        "iron_sword": {"iron_bar": 6, "magic_orb": 1},
        "iron_bar": {"iron_ore": 1},
    }
    gd._resource_drops = {"iron_rocks": "iron_ore"}
    gd._resource_skill = {"iron_rocks": ("mining", 10)}
    return gd


def test_obtain_item_collects_unowned_closure_materials():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "iron_bar" in needs.materials
    assert "iron_ore" in needs.materials
    assert needs.materials and "magic_orb" not in needs.materials


def test_obtain_item_gating_skill_in_skill_xp():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "weaponcrafting" in needs.skill_xp


def test_buy_only_input_recorded():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1, "mining": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "magic_orb" in needs.buy_only


def test_owned_material_not_a_need():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10, "mining": 10},
                       inventory={"iron_bar": 6, "iron_ore": 6})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert "iron_bar" not in needs.materials
    assert "weaponcrafting" not in needs.skill_xp


def test_reach_skill_level_objective_needs_that_skill():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1})
    needs = objective_needs(ReachSkillLevel("weaponcrafting", 5), state, gd)
    assert needs.skill_xp == frozenset({"weaponcrafting"})


def test_reach_char_level_sets_char_xp():
    gd = _gd()
    state = make_state(level=4)
    needs = objective_needs(ReachCharLevel(6), state, gd)
    assert needs.char_xp is True


def test_empty_when_obtain_item_owned():
    gd = _gd()
    state = make_state(inventory={"iron_sword": 1})
    needs = objective_needs(ObtainItem("iron_sword"), state, gd)
    assert needs.is_empty
