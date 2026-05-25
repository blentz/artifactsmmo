"""Tests for task_batch_size — the inventory-bounded units-per-plan count."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_batch import BATCH_CAP, task_batch_size
from tests.test_ai.fixtures import make_state


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
