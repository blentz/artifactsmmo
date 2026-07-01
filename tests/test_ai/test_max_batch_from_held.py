from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure


def test_batch_is_min_floor_times_yield():
    # need [2,3], held [10,6], yield 1 -> min(10//2, 6//3)=min(5,2)=2 runs -> 2 potions
    assert max_batch_from_held_pure([2, 3], [10, 6], 1) == 2


def test_yield_multiplies_runs():
    assert max_batch_from_held_pure([2, 3], [10, 6], 5) == 10  # 2 runs * 5


def test_zero_when_any_ingredient_short():
    assert max_batch_from_held_pure([2, 3], [10, 0], 1) == 0


def test_empty_recipe_zero():
    assert max_batch_from_held_pure([], [], 1) == 0


def test_single_ingredient_floor_division():
    assert max_batch_from_held_pure([3], [10], 1) == 3  # 10 // 3 == 3


def test_yield_zero_gives_zero():
    assert max_batch_from_held_pure([2], [10], 0) == 0
