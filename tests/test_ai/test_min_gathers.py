"""Tests for min_gathers: a SOUND lower bound on the number of GatherActions a
plan needs to obtain `qty` of `item`, given current holdings.

Soundness anchor (formal/Formal/PlannerDepthBound.lean): a gather mints exactly
+1 (gather_apply_core.gather_apply_pure), so any plan crafting `item` from raw
materials needs at least `min_gathers` gather steps. Combined with the planner's
`plan_length_le_max_depth` invariant, `min_gathers(target) > max_depth` proves
the goal is unreachable — the justification for the UpgradeEquipment skip gate.
"""

from artifactsmmo_cli.ai.min_gathers import min_gathers


def test_raw_item_with_no_holdings_needs_one_gather_per_unit():
    # copper_ore is raw (no recipe); need 5, own none → 5 gathers.
    assert min_gathers("copper_ore", 5, recipes={}, owned={}) == 5


def test_owned_units_reduce_required_gathers():
    assert min_gathers("copper_ore", 5, recipes={}, owned={"copper_ore": 3}) == 2


def test_owned_covers_everything_needs_zero():
    assert min_gathers("copper_ore", 5, recipes={}, owned={"copper_ore": 9}) == 0


def test_one_level_recipe_expands_to_raw():
    # copper_bar = 10 copper_ore; need 2 bars, own nothing → 20 ore gathers.
    recipes = {"copper_bar": {"copper_ore": 10}}
    assert min_gathers("copper_bar", 2, recipes=recipes, owned={}) == 20


def test_owned_intermediate_short_circuits_subtree():
    # Own 2 copper_bar already → crafting 2 bars needs no ore.
    recipes = {"copper_bar": {"copper_ore": 10}}
    assert min_gathers("copper_bar", 2, recipes=recipes, owned={"copper_bar": 2}) == 0


def test_copper_boots_from_scratch_is_eighty():
    # The bug witness: copper_boots = 8 copper_bar, copper_bar = 10 copper_ore.
    # From scratch ⇒ 80 copper_ore gathers ≫ UpgradeEquipment max_depth (15).
    recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    assert min_gathers("copper_boots", 1, recipes=recipes, owned={}) == 80


def test_owned_partial_intermediate_reduces_remaining():
    # copper_boots needs 8 bars; own 3 bars → craft 5 more bars → 50 ore.
    recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    assert min_gathers("copper_boots", 1, recipes=recipes, owned={"copper_bar": 3}) == 50


def test_does_not_mutate_caller_owned():
    owned = {"copper_bar": 3}
    recipes = {"copper_boots": {"copper_bar": 8}, "copper_bar": {"copper_ore": 10}}
    min_gathers("copper_boots", 1, recipes=recipes, owned=owned)
    assert owned == {"copper_bar": 3}, "must not consume the caller's dict"
