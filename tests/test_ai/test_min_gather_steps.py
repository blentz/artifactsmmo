from artifactsmmo_cli.ai.min_gather_steps import min_gather_steps

RECIPES = {
    "greater_wooden_staff": {"spruce_plank": 6, "blue_slimeball": 2},
    "spruce_plank": {"spruce_wood": 10},
}


def test_raw_leaf_is_one_step_regardless_of_quantity():
    """A batched gather mints N units in one action, so 60 spruce_wood is ONE
    step, not 60. This is the whole point of the module."""
    assert min_gather_steps("spruce_wood", 60, RECIPES, {}) == 1


def test_one_step_per_distinct_raw_material():
    """staff <- 6 spruce_plank (<- spruce_wood) + 2 blue_slimeball.
    Two distinct raw leaves => two gather steps."""
    assert min_gather_steps("greater_wooden_staff", 1, RECIPES, {}) == 2


def test_owned_covers_a_leaf_and_removes_its_step():
    owned = {"spruce_plank": 6}
    assert min_gather_steps("greater_wooden_staff", 1, RECIPES, owned) == 1


def test_fully_owned_target_needs_no_gathers():
    assert min_gather_steps("greater_wooden_staff", 1, RECIPES,
                            {"greater_wooden_staff": 1}) == 0


def test_owned_is_not_mutated():
    owned = {"spruce_plank": 6}
    min_gather_steps("greater_wooden_staff", 1, RECIPES, owned)
    assert owned == {"spruce_plank": 6}


def test_same_leaf_reached_twice_counts_once():
    """A leaf shared by two branches is one gather step, not two: one batched
    action covers the summed demand."""
    recipes = {"widget": {"left": 1, "right": 1},
               "left": {"ore": 4}, "right": {"ore": 7}}
    assert min_gather_steps("widget", 1, recipes, {}) == 1


def test_cyclic_recipe_terminates():
    """Fuel-bounded like min_gathers/min_crafts: a cycle must not RecursionError."""
    recipes = {"a": {"b": 1}, "b": {"a": 1}}
    assert min_gather_steps("a", 1, recipes, {}) >= 0
