"""A failed cycle records WHY it failed, not just that it did.

`outcome` collapses three distinct dead-ends onto one label: `error:other`
covers LevelSkill's cyclic-dependency guard, its no-rung guard, and its
empty-sub-plan guard alike. The message was printed to stdout and discarded, so
a postmortem could only infer the cause from planner node counts (live Robby
2026-07-28, cycles 91-92: `LevelSkill(gearcrafting) grind produced no leg`,
identifiable only because the cycle-level search showed 4287 nodes against
`goals_tried`'s 4).
"""

from unittest.mock import MagicMock, patch

import httpx
import pytest

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

PLANNER_STATS = {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1}


def _player() -> GamePlayer:
    player = GamePlayer(character="hero")
    player.state = make_state(level=17)
    player.tracer = MagicMock()
    return player


def _run(player, exc):
    """Execute an action that raises `exc`, then emit the cycle's trace record."""
    action = MagicMock()
    action.execute.side_effect = exc
    with patch.object(player, "_fetch_world_state", return_value=player.state):
        _, outcome = player._execute(action, MagicMock())
    player._emit_trace("Act()", "Goal()", outcome, PLANNER_STATS)
    return outcome, player.tracer.write_cycle.call_args[0][0]


def test_runtime_error_message_is_recorded():
    outcome, record = _run(
        _player(), RuntimeError("LevelSkill(gearcrafting) grind produced no leg"))

    assert outcome == "error:other"
    assert record["error"] == "LevelSkill(gearcrafting) grind produced no leg"


def test_the_three_error_other_dead_ends_are_now_distinguishable():
    """The whole point: one label, three causes, previously indistinguishable."""
    messages = [
        "cyclic skill-grind dependency for gearcrafting: ['gearcrafting']",
        "LevelSkill(gearcrafting) has no grind rung at execution — "
        "is_applicable should have gated this",
        "LevelSkill(gearcrafting) grind produced no leg",
    ]

    recorded = [_run(_player(), RuntimeError(m))[1]["error"] for m in messages]

    assert recorded == messages


def test_fight_lost_message_is_recorded():
    outcome, record = _run(_player(), RuntimeError("fight_lost: cyclops (turns=41)"))

    assert outcome == "error:fight_lost"
    assert record["error"] == "fight_lost: cyclops (turns=41)"


def test_api_error_message_is_recorded():
    outcome, record = _run(_player(), ApiActionError(478, "missing item"))

    assert outcome == "error:HTTP_478"
    assert "missing item" in record["error"]


def test_network_error_message_is_recorded():
    outcome, record = _run(_player(), httpx.ReadTimeout("timed out"))

    assert outcome == "error:network"
    assert record["error"]


def test_successful_cycle_records_no_error():
    player = _player()
    action = MagicMock()
    action.execute.return_value = player.state

    _, outcome = player._execute(action, MagicMock())
    player._emit_trace("Act()", "Goal()", outcome, PLANNER_STATS)

    assert outcome == "ok"
    assert "error" not in player.tracer.write_cycle.call_args[0][0]


def test_a_stale_message_never_leaks_onto_a_later_cycle():
    """Same discipline as the grind expansion and the fight record: cleared at
    the start of every execution, so a prior failure cannot mislabel a later
    cycle."""
    player = _player()
    _run(player, RuntimeError("boom"))

    good = MagicMock()
    good.execute.return_value = player.state
    _, outcome = player._execute(good, MagicMock())
    player._emit_trace("Act()", "Goal()", outcome, PLANNER_STATS)

    assert "error" not in player.tracer.write_cycle.call_args[0][0]


def test_no_plan_cycle_does_not_inherit_an_earlier_error():
    """`_execute` never runs on a no-plan cycle, so the field is not
    cleared — the emission must gate on the outcome, not on the field alone."""
    player = _player()
    _run(player, RuntimeError("boom"))

    player._emit_trace("<no_plan>", "<none>", "no_plan", PLANNER_STATS)

    assert "error" not in player.tracer.write_cycle.call_args[0][0]


@pytest.mark.parametrize("blank", [RuntimeError(""), httpx.ReadTimeout("")])
def test_an_empty_message_still_records_something_identifiable(blank):
    """A bare exception must not produce an empty `error` string that reads as
    'no reason recorded'."""
    _, record = _run(_player(), blank)

    assert record["error"]
