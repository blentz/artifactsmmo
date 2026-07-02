"""Unit coverage for strategic_weights — the learned cooldown-seconds-saved
efficiency-weight derivation (#16 Phase 3b). Uses a real LearningStore with
recorded cycles (no mocking the collaborator)."""
import os
import tempfile

import pytest

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.strategic_weights import (
    COMBAT_WEIGHT,
    EFFICIENCY_BUDGET,
    SECONDS_FP,
    strategic_weights,
)
from tests.test_ai.fixtures import make_state


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


def _store(tmp_db_path):
    store = LearningStore(db_path=tmp_db_path, character="testchar")
    store.start_session()
    return store


def _add(store, action_class, action_repr, cd, n, outcome="ok"):
    for i in range(n):
        store.record_cycle(Cycle(
            ts=f"2026-06-21T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="x", outcome=outcome, action_repr=action_repr,
            action_class=action_class, actual_cooldown_seconds=cd,
        ))


def test_cold_history_none_gives_zero_efficiency():
    weights, budget = strategic_weights(make_state(), None)
    assert weights == (COMBAT_WEIGHT, 0, 0, 0, 0)
    assert budget == EFFICIENCY_BUDGET


def test_cold_no_observations_gives_zero_efficiency(tmp_db_path):
    store = _store(tmp_db_path)
    # No cycles → fractions 0 → every efficiency rate 0.
    weights, budget = strategic_weights(make_state(), store)
    assert weights == (COMBAT_WEIGHT, 0, 0, 0, 0)
    assert budget == EFFICIENCY_BUDGET
    store.close()


def test_learned_weights_from_action_mix(tmp_db_path):
    store = _store(tmp_db_path)
    # All three classes have >=5 samples → every cooldown is the LEARNED median,
    # never a fabricated figure. 8 fights + 6 deposits + 6 moves = 20 cycles.
    _add(store, "FightAction", "Fight(x)", 20.0, 8)
    _add(store, "DepositAllAction", "Dep", 4.0, 6)
    _add(store, "MovementAction", "Move", 6.0, 6)
    # f_fight = 8/20 = 0.4, f_trip(deposit) = 6/20 = 0.3.
    weights, budget = strategic_weights(make_state(inventory_max=100), store)
    combat_w, wisdom_w, prospecting_w, inventory_w, haste_w = weights
    assert combat_w == COMBAT_WEIGHT
    # wisdom/prospecting = round(0.001 * fight_cd(20) * f_fight(0.4) * SECONDS_FP)
    expected_xp = round(0.001 * 20.0 * 0.4 * SECONDS_FP)
    assert wisdom_w == expected_xp
    assert prospecting_w == expected_xp
    # inventory reads the LEARNED move(6)/deposit(4) cooldowns, not invented ones:
    # round((2*6.0+4.0)/inv_max(100) * f_trip(0.3) * SECONDS_FP)
    expected_inv = round((2 * 6.0 + 4.0) / 100 * 0.3 * SECONDS_FP)
    assert inventory_w == expected_inv
    assert haste_w == 0  # deferred to the probe
    assert budget == EFFICIENCY_BUDGET
    store.close()


def test_unlearned_move_deposit_cooldown_invents_no_rate(tmp_db_path):
    """When deposits are observed (f_trip > 0) but their cooldown has < 5 samples,
    the inventory-slot weight must stay 0 — the code must NOT fabricate a
    movement/deposit cooldown. Mirrors how `haste` contributes 0 until measured;
    no game cooldown formula exists in the API to source a static figure from."""
    store = _store(tmp_db_path)
    # 8 fights (learned) + 2 deposits + 2 moves (each < 5 → cooldown unlearned).
    _add(store, "FightAction", "Fight(x)", 20.0, 8)
    _add(store, "DepositAllAction", "Dep", 4.0, 2)
    _add(store, "MovementAction", "Move", 6.0, 2)
    weights, _ = strategic_weights(make_state(inventory_max=100), store)
    assert weights[3] == 0  # inventory weight: no invented cooldown
    store.close()


def test_zero_inventory_max_no_division(tmp_db_path):
    store = _store(tmp_db_path)
    _add(store, "DepositAllAction", "Dep", 4.0, 6)
    # inventory_max 0 → inventory rate 0 (no ZeroDivisionError).
    weights, _ = strategic_weights(make_state(inventory_max=0), store)
    assert weights[3] == 0
    store.close()
