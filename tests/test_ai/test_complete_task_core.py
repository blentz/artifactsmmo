"""Pure core: completing a task mints `coin_reward` tasks_coin into inventory."""
from artifactsmmo_cli.ai.actions.complete_task_core import complete_task_apply_pure


def test_mints_coins_into_empty_inventory():
    assert complete_task_apply_pure({}, 3) == {"tasks_coin": 3}


def test_adds_to_existing_coin_stack():
    assert complete_task_apply_pure({"tasks_coin": 2}, 3) == {"tasks_coin": 5}


def test_preserves_other_items():
    out = complete_task_apply_pure({"copper_ore": 4, "tasks_coin": 1}, 2)
    assert out == {"copper_ore": 4, "tasks_coin": 3}


def test_does_not_mutate_input():
    inv = {"tasks_coin": 1}
    complete_task_apply_pure(inv, 2)
    assert inv == {"tasks_coin": 1}
