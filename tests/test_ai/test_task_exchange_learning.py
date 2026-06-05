"""Empirical learning of the taskmaster exchange cost from HTTP 478 / success.

The per-exchange coin cost is not exposed as API data, so GamePlayer raises a
learned minimum past any coin count that failed (478) and pins it to the exact
cost when an exchange succeeds. No hardcoded cost.
"""

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _player() -> GamePlayer:
    p = GamePlayer.__new__(GamePlayer)
    p._task_exchange_min_coins = 1
    # `_learn_task_exchange_cost` now persists to the learning store; tests
    # use the in-memory bypass (history=None means no persistence side
    # effect).
    p.history = None
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


def test_learned_minimum_persists_across_sessions(tmp_path):
    """Trace 2026-05/06: 42 HTTP_478 across ~10 sessions = ~4 rejections per
    re-discovery. Persisting the learned minimum via LearningStore drops the
    second-session rediscovery cost to zero: a fresh GamePlayer hooked up to
    the same DB should pick up the value the prior session learned."""
    db = str(tmp_path / "learn.db")
    store_a = LearningStore(db_path=db, character="hero")
    p1 = GamePlayer.__new__(GamePlayer)
    p1._task_exchange_min_coins = 1
    p1.history = store_a
    prev = make_state(inventory={"tasks_coin": 5})
    p1._learn_task_exchange_cost(_exchange(), prev, prev, "error:HTTP_478")
    assert p1._task_exchange_min_coins == 6
    store_a.close()

    # New session: a fresh store/player binding to the same DB should restore
    # the learned minimum on construction.
    store_b = LearningStore(db_path=db, character="hero")
    restored = store_b.get_learned_int("task_exchange_min_coins", default=1)
    assert restored == 6, (
        f"learned task_exchange_min_coins should persist across sessions; "
        f"got {restored}"
    )
    store_b.close()


def test_learned_minimum_is_per_character(tmp_path):
    """Two characters discovering different exchange costs shouldn't
    overwrite each other's learned bound."""
    db = str(tmp_path / "learn.db")
    a = LearningStore(db_path=db, character="alice")
    b = LearningStore(db_path=db, character="bob")
    a.set_learned_int("task_exchange_min_coins", 6)
    b.set_learned_int("task_exchange_min_coins", 4)
    assert a.get_learned_int("task_exchange_min_coins", 1) == 6
    assert b.get_learned_int("task_exchange_min_coins", 1) == 4
    a.close(); b.close()
