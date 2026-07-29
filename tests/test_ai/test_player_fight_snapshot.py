"""The captured fight transcript reaches the observer's CycleSnapshot.

`_notify_observer` gates on the executed action's type, exactly as it does for
the LevelSkill grind expansion, so a prior fight's record cannot leak onto an
unrelated cycle.
"""

import json
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
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
        fight=player._fight_of(action),
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

    assert GamePlayer(character='hero')._fight_of(action) is RECORD
    assert GamePlayer(character='hero')._fight_of(MoveAction(x=1, y=1)) is None


# ── fights executed as GRIND LEGS ────────────────────────────────────────────
# A skill grind runs its leg through `_execute` (player.py:1125), so a Fight leg
# does capture its own transcript — but the CYCLE's observers are handed the
# outer LevelSkill, so nothing read it. Live Robby 2026-07-29: 59 fights on the
# server across a 1263-cycle run, 0 recorded, because every one of them was a
# grind leg rather than a top-level Fight cycle.

def _grind_player(leg) -> GamePlayer:
    player = GamePlayer(character="hero", cycle_observer=lambda s: None)
    player.state = make_state(level=17)
    player._last_grind_leg = leg
    return player


def _grind_snapshot(player, action) -> CycleSnapshot:
    calls: list[CycleSnapshot] = []
    player.set_cycle_observer(calls.append)
    player._notify_observer("Grind()", repr(action), "ok", goal_rank_trace=[],
                            action=action)
    return calls[0]


def test_a_fight_leg_reaches_the_snapshot_through_the_levelskill_cycle():
    fought = FightAction(monster_code="mushmush")
    fought.last_fight = RECORD
    player = _grind_player(fought)

    snap = _grind_snapshot(player, LevelSkill(skill="gearcrafting", target_level=15))

    assert snap.fight == RECORD


def test_a_non_fight_leg_yields_nothing():
    player = _grind_player(MoveAction(x=1, y=1))

    assert player._fight_of(LevelSkill(skill="gearcrafting", target_level=15)) is None


def test_a_grind_that_never_reached_a_leg_yields_nothing():
    """The 32 live `grind produced no leg` cycles must not borrow a record."""
    player = _grind_player(None)

    assert player._fight_of(LevelSkill(skill="gearcrafting", target_level=15)) is None


def test_a_stale_leg_never_leaks_onto_a_later_grind():
    fought = FightAction(monster_code="mushmush")
    fought.last_fight = RECORD
    player = _grind_player(fought)
    # a fresh, non-recursive grind clears the leg before planning one
    player._last_grind_leg = None

    assert player._fight_of(LevelSkill(skill="gearcrafting", target_level=15)) is None


def test_a_top_level_fight_still_reads_its_own_record():
    """The LevelSkill arm must not shadow the direct one."""
    fought = FightAction(monster_code="mushmush")
    fought.last_fight = RECORD
    player = _grind_player(None)

    assert player._fight_of(fought) is RECORD


def test_a_lost_fight_leg_is_still_recorded():
    """FightAction.execute sets last_fight BEFORE raising, and the leg is
    stashed before `_execute` runs, so a grind-embedded loss survives."""
    lost = FightAction(monster_code="cyclops")
    lost.last_fight = RECORD.model_copy(update={"result": "loss", "hp_after": 0})
    player = _grind_player(lost)

    rec = player._fight_of(LevelSkill(skill="gearcrafting", target_level=15))

    assert rec is not None and rec.result == "loss"


def test_end_to_end_a_grind_cycle_that_fights_records_the_fight():
    """Drives the REAL path: `_execute(LevelSkill)` -> `_execute_level_skill`
    -> planner returns a Fight leg -> `_execute(leg)`.

    The unit tests above set `_last_grind_leg` directly, which is how the
    original bug survived: they exercised the gate, not the route the bot
    actually takes.
    """
    player = GamePlayer(character="hero")
    player.state = make_state(level=17)
    player.game_data = MagicMock()
    player.tracer = MagicMock()

    leg = FightAction(monster_code="mushmush", locations=frozenset({(0, 0)}))
    grind = LevelSkill(skill="gearcrafting", target_level=15)

    def fake_execute_leg(state, client):
        leg.last_fight = RECORD
        return state

    with (
        patch.object(type(leg), "execute", side_effect=fake_execute_leg),
        patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=MagicMock()),
        patch.object(player, "_build_actions", return_value=[]),
        patch.object(player.planner, "plan", return_value=[leg]),
    ):
        _, outcome = player._execute(grind, MagicMock())

    assert outcome == "ok"
    assert player._last_grind_leg is leg
    player._emit_trace(repr(grind), "Grind()", outcome,
                      {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1},
                      fight=player._fight_of(grind))
    record = player.tracer.write_cycle.call_args[0][0]
    assert record["fight"]["opponent"] == "mushmush"
    assert record["fight"]["turns"] == 27
