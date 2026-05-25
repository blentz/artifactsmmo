"""Empirical learning of the taskmaster exchange cost from HTTP 478 / success.

The per-exchange coin cost is not exposed as API data, so GamePlayer raises a
learned minimum past any coin count that failed (478) and pins it to the exact
cost when an exchange succeeds. No hardcoded cost.
"""

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _player() -> GamePlayer:
    p = GamePlayer.__new__(GamePlayer)
    p._task_exchange_min_coins = 1
    return p


def _exchange() -> TaskExchangeAction:
    return TaskExchangeAction(taskmaster_location=(1, 2), min_coins=1)


def test_478_raises_minimum_past_failed_coin_count():
    p = _player()
    prev = make_state(inventory={"tasks_coin": 5})
    p._learn_task_exchange_cost(_exchange(), prev, prev, "error:HTTP_478")
    assert p._task_exchange_min_coins == 6  # 5 failed -> need > 5


def test_478_never_lowers_the_minimum():
    p = _player()
    p._task_exchange_min_coins = 6
    prev = make_state(inventory={"tasks_coin": 2})
    p._learn_task_exchange_cost(_exchange(), prev, prev, "error:HTTP_478")
    assert p._task_exchange_min_coins == 6  # stays at the higher learned bound


def test_success_pins_minimum_to_exact_cost_from_delta():
    p = _player()
    prev = make_state(inventory={"tasks_coin": 8})
    new = make_state(inventory={"tasks_coin": 2})  # spent 6
    p._learn_task_exchange_cost(_exchange(), prev, new, "ok")
    assert p._task_exchange_min_coins == 6


def test_non_task_exchange_action_is_ignored():
    p = _player()
    action = GatherAction(resource_code="ash_wood", locations=frozenset({(0, 0)}))
    prev = make_state(inventory={"tasks_coin": 5})
    p._learn_task_exchange_cost(action, prev, prev, "error:HTTP_478")
    assert p._task_exchange_min_coins == 1  # untouched
