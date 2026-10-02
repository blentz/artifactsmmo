"""The learned recycle yield: a fixed total per unit, drawn at random from the
recipe's materials (`ai/recycle_yield`)."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recycle_yield import recycle_unit_yield

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def test_a_one_material_recipe_gets_the_whole_total():
    assert recycle_unit_yield({"copper_bar": 6}, 2) == {"copper_bar": 2}


def test_the_expectation_is_proportional_and_rounded_down():
    """iron_dagger (6 iron_bar + 2 feather), total 2: 1.5 bars and 0.5 feathers
    expected, of which the planner counts the whole units."""
    assert recycle_unit_yield({"iron_bar": 6, "feather": 2}, 2) == {"iron_bar": 1, "feather": 0}
    assert recycle_unit_yield({"iron_bar": 5, "red_slimeball": 4, "flying_wing": 3}, 3) == {
        "iron_bar": 1, "red_slimeball": 1, "flying_wing": 0}


def test_game_data_answers_only_for_a_learned_craftable():
    gd = GameData()
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6}}
    assert gd.recycle_unit_yield("copper_helmet") is None, "never recycled: unknown"
    gd.recycle_totals = {"copper_helmet": 2, "copper_ore": 3}
    assert gd.recycle_unit_yield("copper_helmet") == {"copper_bar": 2}
    assert gd.recycle_unit_yield("copper_ore") is None, "no recipe: nothing to recycle into"
    assert dict(gd.recycle_totals) == {"copper_helmet": 2, "copper_ore": 3}


def test_the_bundle_carries_the_fleets_learned_totals():
    """The committed bundle declares the totals the fleet had observed at
    capture, so offline worlds recycle the way the live one does."""
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    assert gd.recycle_totals["copper_helmet"] == 2
    assert gd.recycle_totals["fire_ring"] == 3
    assert "copper_axe" not in gd.recycle_totals


def test_a_learned_craft_yield_overrides_the_api_prior():
    gd = GameData()
    gd._crafting_recipes = {"potion": {"herb": 1}, "bar": {"ore": 10}}
    gd._craft_yields = {"potion": 2}
    assert (gd.craft_yield("potion"), gd.craft_yield("bar")) == (2, 1)
    gd.learned_craft_yields = {"bar": 3}
    assert (gd.craft_yield("potion"), gd.craft_yield("bar")) == (2, 3)
    assert dict(gd.craft_yields) == {"potion": 2, "bar": 3}
    assert dict(gd.learned_craft_yields) == {"bar": 3}


def test_a_changed_learned_yield_clears_the_derived_memos_and_an_equal_one_does_not():
    """The requirement graph's size fingerprint cannot see a changed value, so
    the setter clears it; re-setting the same map (the per-cycle refresh) does
    not, or the graph would rebuild every cycle."""
    gd = GameData()
    gd._crafting_recipes = {"bar": {"ore": 10}}
    gd._craft_yields = {"bar": 1}  # same key, so the map's SIZE does not change
    graph = gd.requirement_graph.graph()
    cost = gd.recipe_cost
    cost.full_cost("bar")
    gd.learned_craft_yields = {"bar": 3}
    rebuilt = gd.requirement_graph.graph()
    assert rebuilt is not graph and rebuilt.yields["bar"] == 3
    gd.learned_craft_yields = {"bar": 3}
    assert gd.requirement_graph.graph() is rebuilt


def test_the_bundle_carries_the_fleets_learned_craft_yields():
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    assert gd.learned_craft_yields["small_health_potion"] == 2
    assert gd.learned_craft_yields["copper_bar"] == 1
