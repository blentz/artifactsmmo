"""Tests for `bid_vs_craft`: craft-time estimate + GE-bid gate.

Fixture pattern mirrors `tests/test_ai/test_requirement_graph.py`'s `_gd`
helper: a bare `GameData()` with its private catalog attributes assigned
directly (the established construction pattern for these pure `ai/` modules —
no `catalog_fixtures.make_game_data_with_recipes` helper exists in this repo).
"""

from artifactsmmo_cli.ai.bid_vs_craft import (
    closure_leaf_kinds,
    estimate_craft_seconds,
    should_bid,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.source_kind import SourceKind


def _gd(recipes=None, drops=None, monster_drops=None):
    gd = GameData()
    gd._crafting_recipes = recipes or {}
    gd._resource_drops = drops or {}
    if monster_drops is not None:
        gd._monster_drops = monster_drops
    return gd


def test_closure_leaf_kinds_flags_drop_based():
    # steel <- iron x2; iron has no recipe and no gather resource, only a
    # monster drop (1-in-5 from "mob") -> the closure bottoms out in DROP.
    # `_monster_drops` is keyed by MONSTER code (`monster_catalog.drops`):
    # {monster_code: [(item_code, rate, min_qty, max_qty), ...]}.
    gd = _gd(
        recipes={"steel": {"iron": 2}},
        monster_drops={"mob": [("iron", 5, 1, 1)]},
    )
    kinds = closure_leaf_kinds("steel", gd)
    assert SourceKind.DROP in kinds


def test_closure_leaf_kinds_deterministic_only_when_gathered():
    # plank <- wood x2; wood is gathered from "tree" (deterministic), never
    # dropped by a monster -> no DROP leaf.
    gd = _gd(recipes={"plank": {"wood": 2}}, drops={"tree": "wood"})
    kinds = closure_leaf_kinds("plank", gd)
    assert SourceKind.DROP not in kinds
    assert SourceKind.GATHER in kinds


def test_drop_recipe_costs_more_than_deterministic():
    gd = _gd(
        recipes={"steel": {"iron": 2}},
        monster_drops={"mob": [("iron", 20, 1, 1)]},  # rare drop -> many fights
    )
    drop_cost = estimate_craft_seconds("steel", 1, gd)

    gd2 = _gd(recipes={"plank": {"wood": 2}}, drops={"tree": "wood"})  # deterministic gather
    det_cost = estimate_craft_seconds("plank", 1, gd2)

    assert drop_cost > det_cost


def test_estimate_craft_seconds_scales_with_qty():
    gd = _gd(recipes={"plank": {"wood": 2}}, drops={"tree": "wood"})
    one = estimate_craft_seconds("plank", 1, gd)
    two = estimate_craft_seconds("plank", 2, gd)
    assert two > one


def test_should_bid_true_when_craft_slower_than_horizon():
    gd = _gd(
        recipes={"steel": {"iron": 2}},
        monster_drops={"mob": [("iron", 50, 1, 1)]},  # very slow to self-craft
    )
    assert should_bid("steel", 1, bid_fill_horizon_s=30.0, game_data=gd) is True


def test_should_bid_false_when_craft_faster_than_horizon():
    gd = _gd(recipes={"plank": {"wood": 2}}, drops={"tree": "wood"})
    assert should_bid("plank", 1, bid_fill_horizon_s=300.0, game_data=gd) is False


def test_should_bid_boundary_is_strict_greater_than():
    gd = _gd(recipes={"plank": {"wood": 2}}, drops={"tree": "wood"})
    exact = estimate_craft_seconds("plank", 1, gd)
    assert should_bid("plank", 1, bid_fill_horizon_s=exact, game_data=gd) is False


def test_drop_leg_prefers_lowest_expected_kills_monster():
    # iron drops from two monsters: "rare" (1-in-100) and "common" (1-in-2).
    # The estimator must pick the cheaper source, not the first/worst one.
    gd_worst_only = _gd(
        recipes={"steel": {"iron": 1}},
        monster_drops={"rare": [("iron", 100, 1, 1)]},
    )
    gd_both = _gd(
        recipes={"steel": {"iron": 1}},
        monster_drops={"rare": [("iron", 100, 1, 1)], "common": [("iron", 2, 1, 1)]},
    )
    assert estimate_craft_seconds("steel", 1, gd_both) < estimate_craft_seconds("steel", 1, gd_worst_only)
