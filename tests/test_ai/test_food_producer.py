"""Only the role that owns a food's craft makes it, unless nobody holds that
role (spec 2026-10-13 §4)."""

from artifactsmmo_cli.ai.food_producer import food_owner, may_make_food
from artifactsmmo_cli.ai.game_data import GameData, ItemStats


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_trout": ItemStats(code="cooked_trout", level=1, type_="consumable",
                                  hp_restore=100, crafting_skill="cooking", crafting_level=1),
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=50),
    }
    return gd


def test_cooking_is_the_fisher_s():
    assert food_owner("cooked_trout", _gd()) == "fisher"
    assert food_owner("apple", _gd()) is None


def test_the_fisher_makes_food_and_nobody_else_does_while_one_is_held():
    gd = _gd()
    assert may_make_food("cooked_trout", "fisher", frozenset({"fisher", "miner"}), gd)
    assert not may_make_food("cooked_trout", "miner", frozenset({"fisher", "miner"}), gd)
    assert not may_make_food("cooked_trout", None, frozenset({"fisher"}), gd)


def test_with_no_fisher_in_the_fleet_anyone_makes_food():
    """The fleet must not starve while the role is unheld (Review Focus 2)."""
    assert may_make_food("cooked_trout", "miner", frozenset({"miner"}), _gd())


def test_a_lone_character_makes_its_own_food():
    """Single-character run: no role, no fleet (Review Focus 1)."""
    assert may_make_food("cooked_trout", None, frozenset(), _gd())


def test_a_food_no_role_crafts_is_anyone_s():
    assert may_make_food("apple", "miner", frozenset({"fisher"}), _gd())
