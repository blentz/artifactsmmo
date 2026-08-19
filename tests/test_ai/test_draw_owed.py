"""`GamePlayer._draw_owed_for_course` — ACCEPT_TASK's gate, and the USER's
no-immediate-redraw rule expressed in the one place that persists across cycles.

The rung sits above the objective step (S-051), so an ungated redraw would spin
accept/discard there at a coin a cycle. These pin the two rules that stop it: a new
course owes a draw, and holding a task means the draw has been taken.
"""

from types import SimpleNamespace

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


@pytest.fixture
def player():
    p = GamePlayer(character="probe", history=None)
    p.state = make_state(task_code=None, task_total=0)
    return p


def _decision(root: str | None):
    return SimpleNamespace(chosen_root=root)


def test_a_fresh_character_owes_its_first_draw(player):
    assert player._draw_owed_for_course() is True


def test_holding_a_task_means_the_draw_was_taken(player):
    player.state = make_state(task_code="chicken", task_type="monsters",
                              task_total=10, task_progress=0)
    assert player._draw_owed_for_course() is False


def test_a_discard_does_not_re_arm_the_draw(player):
    """THE RULE. S-048 sends a dead draw back and `task_code` goes None — and the
    flag stays DOWN until the course itself changes. Re-arming here is exactly
    the accept/discard spin the promotion would otherwise open."""
    player._last_decision = _decision("ObtainItem(staff)")
    player.state = make_state(task_code="chicken", task_type="monsters",
                              task_total=10)
    assert player._draw_owed_for_course() is False          # draw taken
    player.state = make_state(task_code=None, task_total=0)  # discarded
    assert player._draw_owed_for_course() is False, "a discard must not redraw"


def test_a_new_course_owes_a_fresh_draw(player):
    player._last_decision = _decision("ObtainItem(staff)")
    player.state = make_state(task_code="chicken", task_type="monsters",
                              task_total=10)
    assert player._draw_owed_for_course() is False
    player.state = make_state(task_code=None, task_total=0)
    assert player._draw_owed_for_course() is False
    # the objective moves on — one draw is owed for the new course
    player._last_decision = _decision("ReachCharLevel(30)")
    assert player._draw_owed_for_course() is True


def test_the_same_course_owes_only_one_draw(player):
    """Idempotent across cycles: re-asking within a course must not re-arm after
    the draw has been taken and given back."""
    player._last_decision = _decision("ReachCharLevel(30)")
    assert player._draw_owed_for_course() is True
    player.state = make_state(task_code="pig", task_type="monsters", task_total=5)
    assert player._draw_owed_for_course() is False
    player.state = make_state(task_code=None, task_total=0)
    for _ in range(3):
        assert player._draw_owed_for_course() is False


def test_the_gate_reaches_the_selection_context(player, monkeypatch):
    """Runtime wiring, not just the helper: the flag must arrive on the ctx the
    means predicate reads, or the rung stays dormant however correct this is."""
    player.game_data = GameData()
    monkeypatch.setattr(player, "_winnable_farm_target", lambda: None)
    monkeypatch.setattr(player, "_draw_owed_for_course", lambda: True)
    assert player._selection_context().draw_owed is True
    monkeypatch.setattr(player, "_draw_owed_for_course", lambda: False)
    assert player._selection_context().draw_owed is False
