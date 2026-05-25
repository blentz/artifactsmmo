"""Tests for recipe_closure — the gather/craft action scope for producing items."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import recipe_closure


def _gd(recipes, drops):
    gd = GameData()
    gd._crafting_recipes = recipes
    gd._resource_drops = drops
    return gd


def test_single_level_closure():
    gd = _gd({"copper_bar": {"copper_ore": 6}}, {"copper_rocks": "copper_ore"})
    resources, craftable = recipe_closure(gd, ["copper_bar"])
    assert resources == {"copper_rocks"}
    assert craftable == {"copper_bar"}


def test_nested_recipe_closure():
    # steel_bar <- (iron_bar <- iron_ore) + coal; iron_ore from iron_rocks, coal from coal_rocks.
    gd = _gd(
        {"steel_bar": {"iron_bar": 1, "coal": 2}, "iron_bar": {"iron_ore": 6}},
        {"iron_rocks": "iron_ore", "coal_rocks": "coal"},
    )
    resources, craftable = recipe_closure(gd, ["steel_bar"])
    assert resources == {"iron_rocks", "coal_rocks"}
    assert craftable == {"steel_bar", "iron_bar"}


def test_raw_resource_root_has_no_craftable():
    # ash_wood is gathered directly, not crafted.
    gd = _gd({}, {"ash_tree": "ash_wood"})
    resources, craftable = recipe_closure(gd, ["ash_wood"])
    assert resources == {"ash_tree"}
    assert craftable == set()


def test_unknown_item_yields_empty_closure():
    gd = _gd({}, {})
    resources, craftable = recipe_closure(gd, ["mystery"])
    assert resources == set()
    assert craftable == set()


def test_multiple_roots_union():
    gd = _gd(
        {"copper_bar": {"copper_ore": 6}, "iron_bar": {"iron_ore": 6}},
        {"copper_rocks": "copper_ore", "iron_rocks": "iron_ore"},
    )
    resources, craftable = recipe_closure(gd, ["copper_bar", "iron_bar"])
    assert resources == {"copper_rocks", "iron_rocks"}
    assert craftable == {"copper_bar", "iron_bar"}


def test_cyclic_recipe_terminates():
    # Defensive: a pathological self-referential recipe must not infinite-loop.
    gd = _gd({"a": {"b": 1}, "b": {"a": 1}}, {})
    resources, craftable = recipe_closure(gd, ["a"])
    assert craftable == {"a", "b"}
    assert resources == set()
