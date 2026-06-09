"""Tests for skill_grind_target: the shallow in-skill item to craft now."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "iron_dagger": ItemStats(code="iron_dagger", level=10, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=10),
        "wooden_staff": ItemStats(code="wooden_staff", level=3, type_="weapon",
                                  crafting_skill="weaponcrafting", crafting_level=3),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "iron_dagger": {"iron_bar": 6},
        "wooden_staff": {"ash_plank": 4},
    }
    return gd


def test_picks_highest_craftable_at_current_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3})
    assert skill_grind_target("weaponcrafting", state, gd) == "wooden_staff"


def test_prefers_materials_in_hand_over_higher_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       inventory={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_counts_bank_toward_materials_in_hand():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 3},
                       bank_items={"copper_bar": 6})
    assert skill_grind_target("weaponcrafting", state, gd) == "copper_dagger"


def test_none_when_nothing_craftable_at_level():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 0})
    assert skill_grind_target("weaponcrafting", state, gd) is None


def test_none_for_skill_with_no_recipes():
    gd = _gd()
    state = make_state(skills={"alchemy": 5})
    assert skill_grind_target("alchemy", state, gd) is None
