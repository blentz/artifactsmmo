"""forced_craft_grind: the (skill, level) of an UNAVOIDABLE craft-skill grind."""

from artifactsmmo_cli.ai.forced_craft_grind import forced_craft_grind
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "fire_bow": ItemStats(code="fire_bow", level=10, type_="weapon",
                              crafting_skill="weaponcrafting", crafting_level=10),
        "spruce_plank": ItemStats(code="spruce_plank", level=1, type_="resource",
                                  subtype="craft"),
        "red_slimeball": ItemStats(code="red_slimeball", level=1, type_="resource",
                                   subtype="mob"),
    }
    gd._crafting_recipes = {"fire_bow": {"spruce_plank": 6, "red_slimeball": 2}}
    return gd


def test_forced_grind_when_craft_is_the_only_route_and_skill_unmet():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7})
    assert forced_craft_grind("fire_bow", 1, state, gd) == ("weaponcrafting", 10)


def test_no_grind_when_skill_already_met():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 10})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_when_target_already_owned():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7}, inventory={"fire_bow": 1})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_when_target_in_bank():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7}, bank_items={"fire_bow": 1})
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_when_a_winnable_dropper_exists():
    """A non-craft obtain route (monster drop) makes the grind avoidable.

    `obtain_sources`'s DROP branch requires BOTH `is_winnable` (a real
    combat-stat prediction, not merely a low monster level/hp) AND a known
    spawn tile in `game_data.all_monster_locations` (the same mapping
    `factory.py` builds `FightAction`s from -- see obtain_sources.py's
    `_drop_sources`). `make_state`'s bare defaults carry NO player attack
    (`attack={}`, `dmg=0`), which makes `predict_win`'s `raw_player <= 0`
    guard return False regardless of how harmless the monster is -- so this
    fixture must give the player real attack (mirrors the `_fighter_state`
    idiom in `test_obtain_sources.py`) AND register the monster's spawn tile
    via `gd._monster_locations`, exactly like `test_obtain_sources.py`'s
    `_build_game_data` wires its own winnable "slime" dropper.
    """
    gd = _gd()
    gd._monster_level = {"fire_imp": 1}
    gd._monster_hp = {"fire_imp": 1}
    gd._monster_drops = {"fire_imp": [("fire_bow", 100, 1, 1)]}
    gd._monster_locations = {"fire_imp": [(0, 1)]}
    from tests.test_ai._monster_fixture import fill_monster_stat_defaults
    fill_monster_stat_defaults(gd)
    state = make_state(skills={"weaponcrafting": 7}, attack={"fire": 20}, dmg=0)
    assert forced_craft_grind("fire_bow", 1, state, gd) is None


def test_no_grind_for_non_craftable_target():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 7})
    assert forced_craft_grind("old_boots", 1, state, gd) is None  # not in _item_stats


def test_no_grind_when_recipe_missing_despite_crafting_skill():
    """Malformed-data guard: `ItemStats.crafting_skill` is set but no recipe
    is on file for it (mirrors the `mystery_part`/`phantom_part` shape in
    `test_obtain_sources.py`'s `_build_game_data` -- dropped/malformed gear
    data). Must not be treated as a forced grind with no recipe to plan."""
    gd = _gd()
    gd._item_stats["phantom_gear"] = ItemStats(
        code="phantom_gear", level=10, type_="weapon",
        crafting_skill="weaponcrafting", crafting_level=10)
    state = make_state(skills={"weaponcrafting": 7})
    assert forced_craft_grind("phantom_gear", 1, state, gd) is None
