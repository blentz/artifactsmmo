"""Tests for recipe_closure — the gather/craft action scope for producing items."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import (
    _closure_demand,
    _closure_visited,
    _raw_units,
    closure_demand,
    gather_serves_closure,
    raw_material_units,
    recipe_closure,
)


def _gd(recipes, drops, yields=None, drops_full=None):
    gd = GameData()
    gd._crafting_recipes = recipes
    gd._resource_drops = drops
    if yields is not None:
        gd._craft_yields = yields
    if drops_full is not None:
        gd._resource_drops_full = drops_full
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


# --- GAP-7 (2026-07-08): needed_resources reads the FULL drop set -----------
# The pure core takes a one-drop-per-resource map; the wrapper unions its
# verdicts across the secondary-drop layers of resource_drops_full (see
# _secondary_drop_layers). These tests pin the widening at the wrapper.

def test_secondary_drop_marks_resource_needed():
    # small_pearls is nobody's PRIMARY drop but a rare secondary of the
    # fishing spots — the l35 witness. The spot must read as needed.
    gd = _gd(
        {},
        {"bass_spot": "bass", "trout_spot": "trout"},
        drops_full={
            "bass_spot": [("bass", 1, 1, 1), ("small_pearls", 300, 1, 1)],
            "trout_spot": [("trout", 1, 1, 1), ("small_pearls", 300, 1, 1)],
        },
    )
    resources, craftable = recipe_closure(gd, ["small_pearls"])
    assert resources == {"bass_spot", "trout_spot"}
    assert craftable == set()


def test_secondary_drop_full_table_absent_is_primary_only():
    # No full drop table (the diff-harness / bare-GameData shape): behavior
    # is byte-identical to the pre-GAP-7 primary-map read.
    gd = _gd({}, {"copper_rocks": "copper_ore"})
    resources, _craftable = recipe_closure(gd, ["copper_ore"])
    assert resources == {"copper_rocks"}
    assert recipe_closure(gd, ["small_pearls"]) == (set(), set())


def test_secondary_drop_layers_dedup_and_depth():
    # One resource with three distinct secondaries (two duplicated in the
    # table) plus its primary repeated: layers dedup, skip the primary, and
    # every secondary still gets its verdict (the deepest layer included).
    gd = _gd(
        {},
        {"rocks": "stone"},
        drops_full={"rocks": [
            ("stone", 1, 1, 1),        # primary — excluded from layers
            ("topaz", 100, 1, 1),
            ("topaz", 100, 1, 1),      # duplicate — dedup'd
            ("emerald", 150, 1, 1),
            ("ruby", 200, 1, 1),       # 3rd secondary — deepest layer
        ]},
    )
    for gem in ("topaz", "emerald", "ruby"):
        resources, _ = recipe_closure(gd, [gem])
        assert resources == {"rocks"}, gem
    # An item the resource does not drop stays un-needed.
    assert recipe_closure(gd, ["sapphire"])[0] == set()


def test_secondary_drop_via_recipe_closure_material():
    # The secondary drop feeds a RECIPE material (not the root itself): the
    # closure walk still marks it and the resource is needed.
    gd = _gd(
        {"pearl_ring": {"small_pearls": 2, "gold_bar": 1},
         "gold_bar": {"gold_ore": 5}},
        {"bass_spot": "bass", "gold_rocks": "gold_ore"},
        drops_full={"bass_spot": [("bass", 1, 1, 1),
                                  ("small_pearls", 300, 1, 1)]},
    )
    resources, craftable = recipe_closure(gd, ["pearl_ring"])
    assert resources == {"bass_spot", "gold_rocks"}
    assert craftable == {"pearl_ring", "gold_bar"}


def test_gather_serves_closure_override_arm():
    # Targeted secondary-drop variant: judged by the OVERRIDE item alone.
    primary = {"bass_spot": "bass"}
    assert gather_serves_closure("bass_spot", "small_pearls", primary,
                                 {"small_pearls": 1})
    assert not gather_serves_closure("bass_spot", "small_pearls", primary,
                                     {"copper_ore": 1})


def test_gather_serves_closure_primary_arm():
    # Plain gather: judged by the resource's primary drop.
    primary = {"copper_rocks": "copper_ore"}
    assert gather_serves_closure("copper_rocks", None, primary,
                                 {"copper_ore": 6})
    assert not gather_serves_closure("copper_rocks", None, primary,
                                     {"iron_ore": 6})
    # Unknown resource (no primary drop): never admissible.
    assert not gather_serves_closure("mystery_rocks", None, primary,
                                     {"copper_ore": 6})


def test_secondary_drop_union_keeps_primary_resources():
    # Primary-only resources and secondary-only resources union cleanly.
    gd = _gd(
        {},
        {"copper_rocks": "copper_ore", "bass_spot": "bass"},
        drops_full={"bass_spot": [("bass", 1, 1, 1),
                                  ("small_pearls", 300, 1, 1)]},
    )
    resources, _ = recipe_closure(gd, ["copper_ore", "small_pearls"])
    assert resources == {"copper_rocks", "bass_spot"}


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


def test_closure_demand_skips_non_positive_recipe_quantities():
    """A recipe entry with a non-positive quantity contributes NO demand and is not
    walked: it is not a material the craft consumes, so recording it would reserve bag
    space (and protect from disposal) an item the chain never needs. The `qty_per <= 0`
    guard is what makes the demand map a demand map."""
    recipes = {"a": {"b": 0, "c": 2}}
    assert _closure_demand(4, "a", 1, recipes, {}, {}, {}) == {"a": 1, "c": 2}


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


# ---------------------------------------------------------------------------
# Task 4 spec-compliance: public wrappers default to game_data.craft_yields
# (the prior map), not {} — so the feature is live for all 10 callers that
# omit yields. Explicit yields arg still overrides.
# ---------------------------------------------------------------------------


def test_raw_material_units_uses_prior_map_by_default():
    # craft_yields has potion=2; omitting yields arg must use that prior map.
    # Need 1 potion, yield=2 → ⌈4/2⌉ = 2 ore (4 ore per batch, 1 potion wanted)
    gd = _gd({"potion": {"herb": 4}}, {}, yields={"potion": 2})
    # Without prior map default: would return 4 (Y=1). With prior map: ⌈4/2⌉=2.
    assert raw_material_units(gd, "potion") == 2


def test_raw_material_units_explicit_yields_overrides_prior():
    # game_data prior says potion=2, but caller passes yields={"potion": 4}.
    # Explicit override must win: ⌈4/4⌉ = 1 ore.
    gd = _gd({"potion": {"herb": 4}}, {}, yields={"potion": 2})
    assert raw_material_units(gd, "potion", yields={"potion": 4}) == 1


def test_raw_material_units_empty_prior_is_noop():
    # Empty craft_yields (today's all-Y=1 data) ⇒ exact same result as before.
    gd = _gd({"bar": {"ore": 2}}, {})
    assert raw_material_units(gd, "bar") == 2


def test_closure_demand_uses_prior_map_by_default():
    # Need 3 potions, prior yields=2 → ⌈3/2⌉=2 crafts → 2 herbs.
    gd = _gd({"potion": {"herb": 1}}, {}, yields={"potion": 2})
    out: dict[str, int] = {}
    closure_demand("potion", 3, gd, out, frozenset())
    assert out["potion"] == 3
    assert out["herb"] == 2  # not 3


def test_closure_demand_explicit_yields_overrides_prior():
    # Prior says potion=2, caller passes yields={"potion": 3}.
    # Override: ⌈3/3⌉=1 craft → 1 herb.
    gd = _gd({"potion": {"herb": 1}}, {}, yields={"potion": 2})
    out: dict[str, int] = {}
    closure_demand("potion", 3, gd, out, frozenset(), yields={"potion": 3})
    assert out["herb"] == 1


def test_closure_demand_empty_prior_is_noop():
    # Empty craft_yields (today's data) ⇒ same result as Y=1.
    gd = _gd({"bar": {"ore": 2}}, {})
    out: dict[str, int] = {}
    closure_demand("bar", 3, gd, out, frozenset())
    assert out["bar"] == 3 and out["ore"] == 6
