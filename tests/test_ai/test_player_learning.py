"""Integration: GamePlayer + LearningStore."""

import os
import tempfile

import pytest
from sqlmodel import Session as SqlSession, select

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


@pytest.fixture
def tmp_db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    if os.path.exists(path):
        os.unlink(path)


def test_player_records_cycle_with_deltas(tmp_db_path):
    store = LearningStore(db_path=tmp_db_path, character="testchar")
    store.start_session()

    player = GamePlayer(character="testchar", history=store)
    player.game_data = GameData()
    # inventory_used is sum(inventory.values()), so use inventory dicts
    prev_state = make_state(gold=50, xp=100, hp=80, inventory={"iron_ore": 10})
    new_state = make_state(gold=55, xp=110, hp=85, inventory={"iron_ore": 12})
    player._record_learning_cycle(
        prev_state=prev_state,
        new_state=new_state,
        action_repr="Fight(yellow_slime)",
        action_class="FightAction",
        outcome="ok",
        selected_goal="FarmMonster(yellow_slime)",
        predicted_cost=10.0,
        actual_cooldown_seconds=11.5,
        planner_nodes=5, planner_depth=2,
        planner_timed_out=False, plan_len=1,
    )

    with SqlSession(store._engine) as s:
        rows = list(s.exec(select(Cycle)))
    store.close()

    assert len(rows) == 1
    r = rows[0]
    assert r.action_repr == "Fight(yellow_slime)"
    assert r.outcome == "ok"
    assert r.delta_gold == 5
    assert r.delta_xp == 10
    assert r.delta_hp == 5
    assert r.delta_inv_used == 2
    assert r.actual_cooldown_seconds == 11.5


def test_player_no_history_does_not_write(tmp_db_path):
    player = GamePlayer(character="testchar", history=None)
    player.game_data = GameData()
    # Should not raise
    player._record_learning_cycle(
        prev_state=make_state(),
        new_state=make_state(),
        action_repr="X", action_class="X", outcome="ok",
        selected_goal="G", predicted_cost=0.0, actual_cooldown_seconds=0.0,
        planner_nodes=0, planner_depth=0, planner_timed_out=False, plan_len=0,
    )
