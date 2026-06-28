"""Tests for recipe_closure — the gather/craft action scope for producing items."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import (
    _closure_demand,
    _closure_visited,
    _raw_units,
    raw_material_units,
    recipe_closure,
)


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


def test_raw_material_units_single_level():
    gd = _gd({"copper_bar": {"copper_ore": 10}}, {"copper_rocks": "copper_ore"})
    assert raw_material_units(gd, "copper_bar") == 10


def test_raw_material_units_nested():
    gd = _gd(
        {"steel_bar": {"iron_bar": 1, "coal": 2}, "iron_bar": {"iron_ore": 6}},
        {"iron_rocks": "iron_ore", "coal_rocks": "coal"},
    )
    assert raw_material_units(gd, "steel_bar") == 8   # 1*6 + 2*1


def test_raw_material_units_raw_resource_is_one():
    gd = _gd({}, {"ash_tree": "ash_wood"})
    assert raw_material_units(gd, "ash_wood") == 1


def test_raw_material_units_unknown_is_one():
    assert raw_material_units(_gd({}, {}), "mystery") == 1


def test_raw_material_units_cyclic_terminates():
    gd = _gd({"a": {"b": 1}, "b": {"a": 1}}, {})
    assert raw_material_units(gd, "a") == 1   # cycle guard returns 1 on revisit


# ---------------------------------------------------------------------------
# Fuel discipline of the pure cores (mechanical-extraction P3a). The fuel
# bound `len(recipes) + 1` is UNREACHABLE through the public wrappers (every
# recursing frame marks a distinct recipe key first), so the base cases are
# pinned directly: fuel 0 returns the accumulator/unit unchanged, and a
# cyclic graph at the wrapper's seeding still terminates with the visited
# guard (never the fuel guard) deciding the values.
# ---------------------------------------------------------------------------


def test_pure_cores_fuel_zero_base_cases():
    recipes = {"a": {"b": 2}, "b": {"a": 3}}
    visited = {"seed": 1}
    assert _closure_visited(0, "a", recipes, dict(visited)) == visited
    assert _raw_units(0, "a", recipes, {}, dict(visited)) == 1
    out = {"seed": 4}
    assert _closure_demand(0, "a", 5, recipes, {}, dict(visited), dict(out)) == out


def test_cyclic_recipe_terminates_via_visited_guard_not_fuel():
    # a <-> b cycle: the wrapper seeds fuel len(recipes) + 1 = 3; the visited
    # guard fires first on every path, so doubling the fuel changes nothing.
    recipes = {"a": {"b": 2}, "b": {"a": 3}}
    gd = _gd(recipes, {"rock_a": "a", "rock_b": "b"})
    resources, craftable = recipe_closure(gd, ["a"])
    assert resources == {"rock_a", "rock_b"}
    assert craftable == {"a", "b"}
    # units(a) = 2 * units(b, {a}) = 2 * (3 * units(a, {a,b}) = 1) = 6
    assert raw_material_units(gd, "a") == 6
    assert _raw_units(6, "a", recipes, {}, {}) == _raw_units(3, "a", recipes, {}, {}) == 6
    assert _closure_visited(6, "a", recipes, {}) == _closure_visited(3, "a", recipes, {})
    # demand: a recorded at 1, b at 1*2; the cycle edge back to a is cut by
    # the per-path visited guard (a is on the path), at any adequate fuel.
    assert (_closure_demand(6, "a", 1, recipes, {}, {}, {})
            == _closure_demand(3, "a", 1, recipes, {}, {}, {})
            == {"a": 1, "b": 2})


# ---------------------------------------------------------------------------
# Task 4: ceil-batch yield semantics in the pure cores.
# `yields` is the new parameter; {} → Y=1 everywhere (exact current behaviour).
# ---------------------------------------------------------------------------


def test_closure_demand_ceil_batches_with_yield():
    # Need 3 potions, yield=2 → ⌈3/2⌉ = 2 crafts → 2 herbs (not 3).
    recipes = {"potion": {"herb": 1}}
    yields = {"potion": 2}
    out = _closure_demand(len(recipes) + 1, "potion", 3, recipes, yields, {}, {})
    assert out["potion"] == 3
    assert out["herb"] == 2


def test_closure_demand_yield_one_unchanged():
    # Y=1 (empty yields dict → default 1): existing behaviour unchanged.
    recipes = {"bar": {"ore": 2}}
    out = _closure_demand(len(recipes) + 1, "bar", 3, recipes, {}, {}, {})
    assert out["bar"] == 3 and out["ore"] == 6


def test_raw_units_ceil_batch_with_yield():
    # 4 ore per craft, yield=2 → ⌈4/2⌉ = 2 ore per bar
    recipes = {"bar": {"ore": 4}}
    yields = {"bar": 2}
    assert _raw_units(2, "bar", recipes, yields, {}) == 2


def test_raw_units_ceil_non_divisible():
    # 3 ore per craft, yield=2 → ⌈3/2⌉ = 2 ore per bar (ceil, not floor)
    recipes = {"bar": {"ore": 3}}
    yields = {"bar": 2}
    assert _raw_units(2, "bar", recipes, yields, {}) == 2


def test_raw_units_yield_one_unchanged():
    # Y=1 (empty yields dict): same as current behavior
    recipes = {"bar": {"ore": 2}}
    assert _raw_units(2, "bar", recipes, {}, {}) == 2
