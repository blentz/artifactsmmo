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


def _stored_player(store: LearningStore) -> GamePlayer:
    p = GamePlayer.__new__(GamePlayer)
    p._task_exchange_min_coins = 1
    p.history = store
    return p


def test_learned_minimum_persists_across_sessions(tmp_path):
    """Trace 2026-05/06: 42 HTTP_478 across ~10 sessions = ~4 rejections per
    re-discovery. A fresh player on the same DB starts from what the prior
    session learned."""
    db = str(tmp_path / "learn.db")
    store_a = LearningStore(db_path=db, character="hero")
    prev = make_state(inventory={"tasks_coin": 5})
    _stored_player(store_a)._learn_task_exchange_cost(_exchange(), prev, prev, "error:HTTP_478")
    store_a.close()

    store_b = LearningStore(db_path=db, character="hero")
    assert _stored_player(store_b)._exchange_min_coins() == 6
    store_b.close()


def test_a_cost_one_character_learns_reaches_a_running_sibling(tmp_path):
    """USER 2026-10-06: the learning is fleet-wide. Live that day Lor pinned
    the exact cost (6) while R2D2, C3P0, HAL and Robby each paid their own 478.
    A sibling already running reads the cost on its next call — no restart."""
    db = str(tmp_path / "learn.db")
    lor = _stored_player(LearningStore(db_path=db, character="Lor"))
    r2d2 = _stored_player(LearningStore(db_path=db, character="R2D2"))
    assert r2d2._exchange_min_coins() == 1
    lor._learn_task_exchange_cost(_exchange(), make_state(inventory={"tasks_coin": 7}),
                                  make_state(inventory={"tasks_coin": 1}), "ok")
    assert r2d2._exchange_min_coins() == 6
    lor.history.close()
    r2d2.history.close()


def test_a_sibling_478_below_the_fleet_bound_never_lowers_it(tmp_path):
    db = str(tmp_path / "learn.db")
    lor = _stored_player(LearningStore(db_path=db, character="Lor"))
    hal = _stored_player(LearningStore(db_path=db, character="HAL"))
    lor._learn_task_exchange_cost(_exchange(), make_state(inventory={"tasks_coin": 5}),
                                  make_state(inventory={"tasks_coin": 5}), "error:HTTP_478")
    stale = make_state(inventory={"tasks_coin": 1})
    hal._learn_task_exchange_cost(_exchange(), stale, stale, "error:HTTP_478")
    assert lor._exchange_min_coins() == hal._exchange_min_coins() == 6
    lor.history.close()
    hal.history.close()


def test_a_success_lowers_a_bound_the_cost_fell_below(tmp_path):
    """The exact cost from a success overwrites the fleet value, so a server
    cost that drops (a season reset) is relearned, not held at the old bound."""
    db = str(tmp_path / "learn.db")
    p = _stored_player(LearningStore(db_path=db, character="Lor"))
    p.history.set_fleet_learned_int("task_exchange_min_coins", 6)
    p._learn_task_exchange_cost(_exchange(), make_state(inventory={"tasks_coin": 6}),
                                make_state(inventory={"tasks_coin": 2}), "ok")
    assert p._exchange_min_coins() == 4
    p.history.close()


def test_an_unchanged_value_is_not_rewritten(tmp_path):
    db = str(tmp_path / "learn.db")
    p = _stored_player(LearningStore(db_path=db, character="Lor"))
    p.history.set_fleet_learned_int("task_exchange_min_coins", 6)
    p.history.set_fleet_learned_int = None  # a write would raise TypeError
    p._learn_task_exchange_cost(_exchange(), make_state(inventory={"tasks_coin": 6}),
                                make_state(inventory={"tasks_coin": 0}), "ok")
    assert p._exchange_min_coins() == 6
    p.history.close()
