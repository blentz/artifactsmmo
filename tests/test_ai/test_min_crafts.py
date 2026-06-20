"""min_crafts: lower bound on CRAFT actions to obtain qty of item, holdings-credited."""

from artifactsmmo_cli.ai.min_crafts import min_crafts

R = {"feather_coat": {"feather": 5, "ash_plank": 2}, "ash_plank": {"ash_wood": 10}}


def test_raw_leaf_zero_crafts():
    assert min_crafts("ash_wood", 5, R, {}) == 0
    assert min_crafts("feather", 5, R, {}) == 0  # monster drop, no recipe


def test_one_level_craft():
    assert min_crafts("ash_plank", 1, R, {}) == 1          # craft the plank
    assert min_crafts("ash_plank", 2, R, {}) == 1          # 1 craft action (batched lower bound)


def test_feather_coat_counts_planks_and_coat():
    # craft ash_plank (1) + craft feather_coat (1) = 2 craftable nodes to produce
    assert min_crafts("feather_coat", 1, R, {}) == 2


def test_held_craftable_credited():
    # 2 ash_plank already held -> only the coat craft remains
    assert min_crafts("feather_coat", 1, R, {"ash_plank": 2}) == 1
    # feather_coat itself held -> 0 crafts
    assert min_crafts("feather_coat", 1, R, {"feather_coat": 1}) == 0


def test_cyclic_recipe_terminates():
    # A cyclic recipe exhausts fuel and returns the accumulated count, not a crash.
    # fuel = len(recipes)+1 = 2; the cycle fires twice (+1 each), then fuel==0 returns state.
    recipes: dict[str, dict[str, int]] = {"a": {"a": 1}}
    assert min_crafts("a", 5, recipes, {}) == 2
