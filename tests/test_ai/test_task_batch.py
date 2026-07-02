"""Tests for task_batch_size — the inventory-bounded units-per-plan count."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import (
    BATCH_CAP,
    craft_batch_size_pure,
    task_batch_size,
    task_batch_size_pure,
)
from tests.test_ai.fixtures import make_state

_RECIPES = {"T": {"M": 2}}   # 2 raw M per unit of T
_DROPS = {"R": "M"}


def test_craft_batch_demand_bounded():
    # plenty of space, small demand -> demand wins
    assert craft_batch_size_pure("T", 3, {}, 100, _RECIPES, _DROPS) == 3


def test_craft_batch_inventory_bounded():
    # free=9, held=0, mats_per_unit=2 -> usable=(9-3)=6, fit=3 < demand 10
    assert craft_batch_size_pure("T", 10, {}, 9, _RECIPES, _DROPS) == 3


def test_craft_batch_cap_bounded():
    # huge demand + space -> capped at BATCH_CAP
    assert craft_batch_size_pure("T", 999, {}, 10_000, _RECIPES, _DROPS) == BATCH_CAP


def test_craft_batch_counts_held_drops_as_free():
    # held M reduces the space pressure: held=6 adds to usable
    # free=3, held=6 -> usable=(3+6-3)=6, fit=3
    assert craft_batch_size_pure("T", 10, {"M": 6}, 3, _RECIPES, _DROPS) == 3


def test_craft_batch_floors_at_one():
    # no space -> still 1 (never 0)
    assert craft_batch_size_pure("T", 5, {}, 0, _RECIPES, _DROPS) == 1


def test_craft_batch_base_item_no_raws():
    # code with no recipe -> mats_per_unit 0 -> demand/cap bounded, no div-by-zero
    assert craft_batch_size_pure("M", 4, {}, 100, _RECIPES, _DROPS) == 4


def test_craft_batch_no_code_or_no_demand_floors_at_one():
    # code None or non-positive demand -> 1 (never reaches the recipe walk)
    assert craft_batch_size_pure(None, 4, {}, 100, _RECIPES, _DROPS) == 1
    assert craft_batch_size_pure("T", 0, {}, 100, _RECIPES, _DROPS) == 1


def test_craft_batch_zero_mats_per_unit_skips_fit():
    # a degenerate zero-quantity recipe -> mats_per_unit 0 -> demand/cap only,
    # never divides by zero.
    zero_recipe = {"Z": {"M": 0}}
    assert craft_batch_size_pure("Z", 4, {}, 100, zero_recipe, _DROPS) == 4
    assert craft_batch_size_pure("Z", 999, {}, 100, zero_recipe, _DROPS) == BATCH_CAP


def test_task_batch_wrapper_matches_prior_outputs():
    # task path delegates: items task, total 8, progress 0, ample space -> min(8, cap)
    assert task_batch_size_pure("items", "T", 8, 0, {}, 100, _RECIPES, _DROPS) == 8
    # non-items task -> 1
    assert task_batch_size_pure("monsters", "T", 8, 0, {}, 100, _RECIPES, _DROPS) == 1


def _gd():
    gd = GameData()
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    return gd


def _task_state(progress=0, total=20, inventory=None, inventory_max=100):
    return make_state(task_code="copper_bar", task_type="items",
                      task_progress=progress, task_total=total,
                      inventory=inventory or {}, inventory_max=inventory_max)


def test_fill_inventory_fit_clamp():
    state = _task_state(progress=2, total=20, inventory={}, inventory_max=100)
    assert task_batch_size(state, _gd()) == 9


def test_remaining_clamp():
    state = _task_state(progress=18, total=20, inventory={}, inventory_max=100)
    assert task_batch_size(state, _gd()) == 2


def test_cap_clamp():
    state = _task_state(progress=0, total=50, inventory={}, inventory_max=1000)
    assert task_batch_size(state, _gd()) == BATCH_CAP


def test_nearly_full_floors_at_one():
    state = _task_state(progress=0, total=20, inventory={"junk": 95}, inventory_max=100)
    assert task_batch_size(state, _gd()) == 1


def test_held_recipe_keeps_k_stable():
    gd = _gd()
    empty = _task_state(progress=0, total=20, inventory={}, inventory_max=100)
    holding = _task_state(progress=0, total=20, inventory={"copper_ore": 40}, inventory_max=100)
    assert task_batch_size(holding, gd) == task_batch_size(empty, gd)


def test_non_items_task_returns_one():
    state = make_state(task_code="chicken", task_type="monsters", task_total=20, task_progress=0)
    assert task_batch_size(state, _gd()) == 1


def test_no_task_returns_one():
    assert task_batch_size(make_state(), _gd()) == 1


def test_completed_task_returns_one():
    state = _task_state(progress=20, total=20)
    assert task_batch_size(state, _gd()) == 1
