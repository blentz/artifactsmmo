"""Tests for player skill max_xp and task reward recording helpers."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _player(tmp_path):
    p = GamePlayer.__new__(GamePlayer)
    p.character = "hero"
    p.history = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    p.game_data = GameData()
    return p


def test_records_skill_max_xp_from_state(tmp_path):
    p = _player(tmp_path)
    state = make_state(skills={"alchemy": 2}, skill_xp={"alchemy": 10})
    p._record_skill_observations(state, {"alchemy": 220})
    assert p.history.skill_max_xp_observations("alchemy") == {2: 220}
    p.history.close()


def test_records_task_reward_on_completion(tmp_path):
    p = _player(tmp_path)
    p.game_data._npc_sell_prices = {"merchant": {"jasper_crystal": 30}}
    prev = make_state(task_code="x", task_type="items", task_progress=28, task_total=29)
    new = make_state(task_code=None, inventory={"jasper_crystal": 2})
    p._record_task_reward_if_completed(prev, new, action_class="CompleteTaskAction", outcome="ok")
    assert p.history.task_reward_sample_count() == 1
    assert p.history.mean_task_reward_value(default=0.0) == 60.0  # 2 * 30
    p.history.close()
