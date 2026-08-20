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
    """PURSUE monster-task: _winnable_farm_target returns the task's monster code.

    `_is_winnable` is patched because tier 1 now CONSULTS it — before the bypass
    was closed this test needed no monster stats at all, since the task tier
    short-circuited ahead of every beatability read. The assertion is unchanged;
    only the dependency it now has is supplied.
    """
    p = _player(tmp_path)
    p.state = make_state(
        task_code="yellow_slime",
        task_type="monsters",
        task_total=20,
        task_progress=0,
    )
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        with patch.object(GamePlayer, "_is_winnable", return_value=True):
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


# ---------------------------------------------------------------------------
# The tier-1 bypass is CLOSED.
#
# `winnable_cascade` tier 1 took the task's monster with the winnable check
# "INTENTIONALLY bypassed", justified by "a persistent loss loop is caught by the
# stuck/recovery backstop, not here". Measured 2026-08-20: C3P0 went 0 wins / 42
# losses against its task pig, the backstop's remedy was a COUNTDOWN that expires
# whether or not anything changed, and its terminal rung killed the character —
# the fleet's first `stuck_exit` in 345 sessions.
#
# The cascade's own theorems were never wrong: `task_wins` correctly says a
# supplied task monster wins. The SUPPLIER was wrong. So the gate goes in
# `_task_aligned_monster` and `WinnableCascade.lean` keeps its proof.
# ---------------------------------------------------------------------------


def test_an_unwinnable_task_monster_is_not_retargeted(tmp_path):
    """THE FIX. A task cannot force a fight the bot's own model says it loses.

    `_is_winnable` is exactly the check tier 1 skipped: it already projects to
    `max_hp` (so a mid-damage cycle cannot flicker the target) and it already
    carries the learned-loss veto, which C3P0's 0/42 record trips on its own.
    """
    p = _player(tmp_path)
    p.state = make_state(task_code="pig", task_type="monsters",
                         task_total=104, task_progress=0)
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        with patch.object(GamePlayer, "_is_winnable", return_value=False):
            result = p._winnable_farm_target()
    assert result != "pig", "the task still forced an unwinnable fight"
    p.history.close()


def test_a_winnable_task_monster_is_still_retargeted(tmp_path):
    """The task must still drive the grind when the fight is actually winnable —
    closing the bypass must not disable monster tasks altogether."""
    p = _player(tmp_path)
    p.state = make_state(task_code="yellow_slime", task_type="monsters",
                         task_total=20, task_progress=0)
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        with patch.object(GamePlayer, "_is_winnable", return_value=True):
            result = p._winnable_farm_target()
    assert result == "yellow_slime"
    p.history.close()


def test_an_unwinnable_task_monster_falls_through_to_the_winnable_tiers(tmp_path):
    """Falling through is the point: tiers 2 and 3 are already winnability-gated,
    so the character grinds something it CAN beat instead of standing down."""
    p = _player(tmp_path)
    p.state = make_state(task_code="pig", task_type="monsters",
                         task_total=104, task_progress=0)
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        with patch.object(GamePlayer, "_is_winnable",
                          side_effect=lambda m: m != "pig"):
            with patch.object(GamePlayer, "_path_aligned_monster",
                              return_value="chicken"):
                result = p._winnable_farm_target()
    assert result == "chicken"
    p.history.close()
