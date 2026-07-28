"""The captured fight transcript reaches the observer's CycleSnapshot.

`_notify_observer` gates on the executed action's type, exactly as it does for
the LevelSkill grind expansion, so a prior fight's record cannot leak onto an
unrelated cycle.
"""

import json
from unittest.mock import MagicMock

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state

RECORD = FightRecord(
    started_at="2026-07-27T23:30:30.455000",
    result="win",
    turns=27,
    opponent="mushmush",
    logs=("Fight start: Robby HP: 485/485 vs Mushmush HP: 350/350",),
    hp_before=485,
    hp_after=275,
    xp=45,
    gold=12,
    drops=(),
)


def _notify(action) -> CycleSnapshot:
    """Drive _notify_observer and return the snapshot handed to the observer."""
    calls: list[CycleSnapshot] = []
    player = GamePlayer(character="hero", cycle_observer=calls.append)
    player.state = make_state(level=17)
    player._notify_observer(
        "FarmMonster(mushmush)", repr(action), "ok", goal_rank_trace=[],
        action=action,
    )
    return calls[0]


def test_fight_action_record_rides_the_snapshot():
    action = FightAction(monster_code="mushmush")
    action.last_fight = RECORD

    assert _notify(action).fight == RECORD


def test_non_fight_action_leaves_it_none():
    assert _notify(MoveAction(x=1, y=1)).fight is None


def test_fight_action_without_a_record_leaves_it_none():
    assert _notify(FightAction(monster_code="mushmush")).fight is None


def test_fight_survives_the_snapshot_round_trip():
    """The snapshot is serialised to traces.jsonl; the record must dump cleanly."""
    action = FightAction(monster_code="mushmush")
    action.last_fight = RECORD

    dumped = _notify(action).model_dump()

    assert dumped["fight"]["turns"] == 27
    assert dumped["fight"]["logs"] == RECORD.logs
    assert json.loads(_notify(action).model_dump_json())["fight"]["turns"] == 27


# ── the TRACE surface ────────────────────────────────────────────────────────
# play-trace-*.jsonl is written by `_emit_trace` via `tracer.write_cycle`, a
# SEPARATE surface from the CycleSnapshot/TUI one above. The transcript itself
# is deliberately excluded: it is 96.8% of the record (measured over 31 real
# fights: 5190 B with logs, 168 B without), it is prose nothing is allowed to
# parse, and it stays reachable from the server log via `started_at`. What the
# trace keeps is exactly what `predict_win` can be scored against.

def _emit(action, tracer):
    player = GamePlayer(character="hero")
    player.state = make_state(level=17)
    player.tracer = tracer
    player._emit_trace(
        "Fight(mushmush)", "FarmMonster(mushmush)", "ok",
        {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1},
        fight=GamePlayer._fight_of(action),
    )
    return tracer.write_cycle.call_args[0][0]


def test_trace_carries_the_structured_fight_fields():
    action = FightAction(monster_code="mushmush")
    action.last_fight = RECORD

    record = _emit(action, MagicMock())

    assert record["fight"]["result"] == "win"
    assert record["fight"]["turns"] == 27
    assert record["fight"]["opponent"] == "mushmush"
    assert record["fight"]["hp_before"] == 485
    assert record["fight"]["hp_after"] == 275
    assert record["fight"]["started_at"] == RECORD.started_at


def test_trace_omits_the_transcript():
    """96.8% of the record, unparseable by rule, and retrievable by started_at."""
    action = FightAction(monster_code="mushmush")
    action.last_fight = RECORD

    assert "logs" not in _emit(action, MagicMock())["fight"]


def test_trace_record_is_json_serialisable():
    action = FightAction(monster_code="mushmush")
    action.last_fight = RECORD

    assert json.loads(json.dumps(_emit(action, MagicMock())["fight"]))["turns"] == 27


def test_non_fight_cycle_has_no_fight_key():
    assert "fight" not in _emit(MoveAction(x=1, y=1), MagicMock())


def test_fight_cycle_without_a_record_has_no_fight_key():
    assert "fight" not in _emit(FightAction(monster_code="mushmush"), MagicMock())


def test_both_surfaces_share_one_gate():
    """The snapshot and the trace must never disagree about whether a cycle
    fought — they read the same `_fight_of`."""
    action = FightAction(monster_code="mushmush")
    action.last_fight = RECORD

    assert GamePlayer._fight_of(action) is RECORD
    assert GamePlayer._fight_of(MoveAction(x=1, y=1)) is None
