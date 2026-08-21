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

    `_is_winnable` and `xp_per_kill` are patched because tier 1 now CONSULTS
    both — before the bypass was closed this test needed no monster stats at all,
    since the task tier short-circuited ahead of every read. The assertion is
    unchanged; only the dependencies it now has are supplied.
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
            with patch.object(type(p.game_data), "xp_per_kill", lambda s, c, lv: 20):
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
            with patch.object(type(p.game_data), "xp_per_kill", lambda s, c, lv: 20):
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


def test_a_GREY_task_monster_is_not_retargeted(tmp_path):
    """Winnable is not the same as USEFUL, and the grind needs both.

    `FightAction._structurally_applicable` refuses a fight with
    `xp_per_kill == 0` — the server's zero-xp band, `char_level - monster_level
    >= 10`. So handing `GrindCharacterXPGoal` a grey monster produces a goal that
    is ranked, planned, and CANNOT plan: live HAL sat at
    `GrindCharacterXP(sheep)` priority 30.0, plan_len 0 in 3 nodes, for 12
    consecutive cycles of `Wait` — sheep is level 5 against HAL's 17, a gap of 12.

    Tier 3 (`_pick_winnable_monster`) has always applied this filter. Tier 1 did
    not, so the task could inject a target the action layer would always reject.
    Same supplier/consumer mismatch the winnability gate fixed, one predicate
    over.
    """
    p = _player(tmp_path)
    p.state = make_state(level=17, task_code="sheep", task_type="monsters",
                         task_total=317, task_progress=0)
    p.game_data._monster_levels = {"sheep": 5}
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        with patch.object(GamePlayer, "_is_winnable", return_value=True):
            with patch.object(type(p.game_data), "xp_per_kill", lambda s, c, lv: 0):
                result = p._winnable_farm_target()
    assert result != "sheep", "a grey task monster still reached the grind"
    p.history.close()


def test_an_xp_positive_task_monster_is_still_retargeted(tmp_path):
    """The filter must not disable monster tasks whose monster actually pays."""
    p = _player(tmp_path)
    p.state = make_state(level=17, task_code="highwayman", task_type="monsters",
                         task_total=20, task_progress=0)
    with patch("artifactsmmo_cli.ai.player.task_decision", return_value="pursue"):
        with patch.object(GamePlayer, "_is_winnable", return_value=True):
            with patch.object(type(p.game_data), "xp_per_kill", lambda s, c, lv: 33):
                result = p._winnable_farm_target()
    assert result == "highwayman"
    p.history.close()
