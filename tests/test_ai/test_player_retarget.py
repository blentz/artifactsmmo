"""Tests for monster-task grind retargeting in _winnable_farm_target."""

from unittest.mock import patch

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _player(tmp_path):
    p = GamePlayer.__new__(GamePlayer)
    p.character = "hero"
    p.history = LearningStore(db_path=str(tmp_path / "p.db"), character="hero")
    p.game_data = GameData()
    p.state = None
    p._last_path_plan = None
    return p


def test_pursue_monster_task_retargets_grind(tmp_path):
    """PURSUE monster-task: _winnable_farm_target returns the task's monster code."""
    p = _player(tmp_path)
    p.state = make_state(
        task_code="yellow_slime",
        task_type="monsters",
        task_total=20,
        task_progress=0,
    )
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        result = p._winnable_farm_target()
    assert result == "yellow_slime"
    p.history.close()


def test_pivot_monster_task_does_not_retarget(tmp_path):
    """PIVOT monster-task: falls through to the normal path-aligned / winnable logic."""
    p = _player(tmp_path)
    p.state = make_state(
        task_code="yellow_slime",
        task_type="monsters",
        task_total=20,
        task_progress=0,
    )
    with (
        patch("artifactsmmo_cli.ai.player.task_decision", return_value="pivot"),
        patch.object(p, "_path_aligned_monster", return_value=None),
        patch.object(p, "_pick_winnable_monster", return_value="chicken"),
    ):
        result = p._winnable_farm_target()
    assert result == "chicken"
    p.history.close()


def test_items_task_does_not_retarget(tmp_path):
    """Items-type task: _task_aligned_monster returns None; normal logic applies."""
    p = _player(tmp_path)
    p.state = make_state(
        task_code="ash_wood",
        task_type="items",
        task_total=20,
        task_progress=0,
    )
    with (
        patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"),
        patch.object(p, "_path_aligned_monster", return_value=None),
        patch.object(p, "_pick_winnable_monster", return_value="chicken"),
    ):
        result = p._winnable_farm_target()
    assert result == "chicken"
    p.history.close()


def test_no_state_does_not_retarget(tmp_path):
    """No state: _task_aligned_monster returns None; normal logic applies."""
    p = _player(tmp_path)
    p.state = None
    with (
        patch.object(p, "_path_aligned_monster", return_value=None),
        patch.object(p, "_pick_winnable_monster", return_value="chicken"),
    ):
        result = p._winnable_farm_target()
    assert result == "chicken"
    p.history.close()


def test_completed_task_does_not_retarget(tmp_path):
    """Completed task (progress >= total): _task_aligned_monster returns None."""
    p = _player(tmp_path)
    p.state = make_state(
        task_code="yellow_slime",
        task_type="monsters",
        task_total=20,
        task_progress=20,
    )
    with (
        patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"),
        patch.object(p, "_path_aligned_monster", return_value=None),
        patch.object(p, "_pick_winnable_monster", return_value="chicken"),
    ):
        result = p._winnable_farm_target()
    assert result == "chicken"
    p.history.close()
