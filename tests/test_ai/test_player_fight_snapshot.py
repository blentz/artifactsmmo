"""The captured fight transcript reaches the observer's CycleSnapshot.

`_notify_observer` gates on the executed action's type, exactly as it does for
the LevelSkill grind expansion, so a prior fight's record cannot leak onto an
unrelated cycle.
"""

import json

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
