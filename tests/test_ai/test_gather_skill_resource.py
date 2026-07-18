from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gather_skill_resource import (
    best_gather_resource_drop,
    first_craftable_level,
)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "small_health_potion": ItemStats(code="small_health_potion", level=5,
                                          type_="utility", hp_restore=30,
                                          crafting_skill="alchemy", crafting_level=5),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
    }
    # resource_skill: code -> (skill, level); resource_drops: resource -> drop item
    gd._resource_skill = {"sunflower_field": ("alchemy", 1),
                          "nettle": ("alchemy", 20),
                          "ash_tree": ("woodcutting", 1)}
    gd._resource_drops = {"sunflower_field": "sunflower", "nettle": "nettle_leaf",
                          "ash_tree": "ash_wood"}
    return gd


def test_best_gather_resource_picks_highest_usable():
    gd = _gd()
    # alchemy at level 5: sunflower_field(1) usable, nettle(20) not -> sunflower
    assert best_gather_resource_drop("alchemy", 5, gd) == "sunflower"


def test_best_gather_resource_none_when_no_usable():
    gd = _gd()
    # alchemy at level 0: no alchemy resource at level <= 0
    assert best_gather_resource_drop("alchemy", 0, gd) is None


def test_best_gather_resource_none_for_nongatherable_skill():
    gd = _gd()
    assert best_gather_resource_drop("cooking", 10, gd) is None


def test_best_gather_resource_highest_of_several():
    gd = _gd()
    # at alchemy 25 both sunflower(1) and nettle(20) usable -> nettle (highest)
    assert best_gather_resource_drop("alchemy", 25, gd) == "nettle_leaf"


def test_first_craftable_level_alchemy():
    assert first_craftable_level("alchemy", _gd()) == 5


def test_first_craftable_level_cooking():
    assert first_craftable_level("cooking", _gd()) == 1


def test_first_craftable_level_none_when_no_recipe():
    assert first_craftable_level("mining", _gd()) is None
