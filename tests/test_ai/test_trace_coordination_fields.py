"""The trace record must witness role coordination, not just the TUI.

`CycleSnapshot` (the TUI surface, `_notify_observer`) gained `role` and
`supply_target` in an earlier task, but the JSONL trace record built by
`_emit_trace` is a *separate* dict that never got the fields — a live
`play --all` run proved the coordination feature works (role_leases +
material_demand rows in the shared DB) while the trace showed no `role` key
at all, making the feature look inert to any postmortem reading the trace.

The same hole recurred one level down: the record carried `state.skill_xp`
(per-cycle xp DELTAS) but never the skill LEVELS, which are the exact input
`role_selection._skill_affinity` ranks on. So the trace showed WHICH role was
chosen and nothing about WHY, and diagnosing "the best miner on the account is
serving alchemy" needed a live API query instead of the trace.
"""

from unittest.mock import MagicMock

from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

PLANNER_STATS = {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1}


def _player(**state_overrides) -> GamePlayer:
    player = GamePlayer(character="hero")
    player.state = make_state(level=17, **state_overrides)
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


def test_skill_levels_are_recorded_alongside_the_skill_xp_deltas():
    """`_skill_affinity` decides on LEVELS. Both keys must be present and they
    must carry different things — asserting only `skills` would still pass if
    the levels were written into the `skill_xp` slot."""
    player = _player(skills={"mining": 21, "alchemy": 16, "fishing": 1},
                     skill_xp={"mining": 40})

    player._emit_trace("Act()", "Goal()", "ok", PLANNER_STATS)

    state = player.tracer.write_cycle.call_args[0][0]["state"]
    assert state["skills"] == {"mining": 21, "alchemy": 16, "fishing": 1}
    assert state["skill_xp"] == {"mining": 40}


def test_turn_in_is_present_on_the_trace_record_for_a_holder():
    """The SAME hole this module was opened for, recurring one feature later:
    the fleet-currency turn-in wrote its `turn_in` block into `CycleSnapshot`
    (the TUI surface) only, and the JSONL record `_emit_trace` builds — the
    artifact a postmortem actually reads — never carried the key at all. A
    75-second live `play Robby --dry-run --trace` produced 7 cycles and ZERO
    records mentioning `turn_in`, while every Task-8 test passed because they
    all asserted on the snapshot. Assert the TRACE record here."""
    player = _player()
    player._turn_in = TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                             price=10, currency="lich_race_medal",
                             buyer="Robby", fleet_total=10)

    player._emit_trace("Act()", "Goal()", "ok", PLANNER_STATS)

    record = player.tracer.write_cycle.call_args[0][0]
    assert record["turn_in"] == {
        "item": "lich_race_trophy",
        "currency": "lich_race_medal",
        "price": 10,
        "fleet_total": 10,
        "buyer": "Robby",
        "role": "holder",
    }


def test_turn_in_is_present_but_null_on_the_trace_record_when_uninvolved():
    """Same present-but-null discipline as `role`/`supply_target` above: a
    reader must be able to tell "no turn-in was possible" from "this child
    never looked", which is the field's whole stated purpose."""
    player = _player()

    player._emit_trace("Act()", "Goal()", "ok", PLANNER_STATS)

    record = player.tracer.write_cycle.call_args[0][0]
    assert "turn_in" in record
    assert record["turn_in"] is None


def test_recorded_skill_levels_are_a_copy_not_the_live_mapping():
    """The record outlives the cycle that built it. Sharing the live dict would
    let a later cycle's skill-up rewrite an already-emitted record."""
    player = _player(skills={"mining": 21})

    player._emit_trace("Act()", "Goal()", "ok", PLANNER_STATS)
    player.state.skills["mining"] = 22

    state = player.tracer.write_cycle.call_args[0][0]["state"]
    assert state["skills"] == {"mining": 21}
