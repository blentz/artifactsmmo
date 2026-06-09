"""has_craftable_upgrade_any_slot: the latch-clear test (gear is level-appropriate
when no craftable upgrade remains for any slot)."""
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_appropriateness import has_craftable_upgrade_any_slot
from tests.test_ai.fixtures import make_state


def _gd_with_boots():
    gd = GameData()
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_true_when_a_craftable_upgrade_exists():
    state = make_state(level=4)  # empty boots_slot, can craft copper_boots
    assert has_craftable_upgrade_any_slot(state, _gd_with_boots()) is True


def test_false_when_no_craftable_upgrade():
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    assert has_craftable_upgrade_any_slot(make_state(level=4), gd) is False
