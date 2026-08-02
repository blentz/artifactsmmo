"""The trace record must witness role coordination, not just the TUI.

`CycleSnapshot` (the TUI surface, `_notify_observer`) gained `role` and
`supply_target` in an earlier task, but the JSONL trace record built by
`_emit_trace` is a *separate* dict that never got the fields — a live
`play --all` run proved the coordination feature works (role_leases +
material_demand rows in the shared DB) while the trace showed no `role` key
at all, making the feature look inert to any postmortem reading the trace.
"""

from unittest.mock import MagicMock

from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

PLANNER_STATS = {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1}


def _player() -> GamePlayer:
    player = GamePlayer(character="hero")
    player.state = make_state(level=17)
    player.tracer = MagicMock()
    return player


def test_role_and_supply_target_present_when_a_role_is_held():
    player = _player()
    player._role = "miner"
    player._supply_target = ("iron_ore", 10, 3)

    player._emit_trace("Act()", "Goal()", "ok", PLANNER_STATS)

    record = player.tracer.write_cycle.call_args[0][0]
    assert record["role"] == "miner"
    assert record["supply_target"] == repr(("iron_ore", 10, 3))


def test_role_and_supply_target_are_present_but_null_with_no_role():
    """A missing key and a null key mean different things to a downstream
    reader ('never emitted this shape' vs. 'observed, no role held'). Every
    cycle emits both keys; the value is null when no role is held — the
    same discipline `aged_pick` already follows on this same record."""
    player = _player()

    player._emit_trace("Act()", "Goal()", "ok", PLANNER_STATS)

    record = player.tracer.write_cycle.call_args[0][0]
    assert "role" in record
    assert record["role"] is None
    assert "supply_target" in record
    assert record["supply_target"] is None
