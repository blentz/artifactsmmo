"""`WorldState.raids` must survive an action's state rebuild.

Sibling of test_active_events_preserved.py. `from_character_schema` defaults
`raids=[]` (world_state.py:219,290), and every action that rebuilds state from a
server response used to pass `active_events=` but never `raids=` -- 28 sites. So
the live raid snapshot evaporated after the first EXECUTED action, and only
`player.py` ever put it back. Any future planner consumer of `active_raids` would
have silently seen an empty list mid-plan.

This is epic P1 (docs/PLAN_events_raids_epic.md). It carries no behaviour on its
own -- nothing consumes raids yet -- but without it P4's ParticipateRaid would be
built on a field that does not survive its own plan.

NOTE: `execute()` paths cannot be exercised without a live client, so this covers
the `apply()` half, which is what the PLANNER walks. The execute-half threading is
verified by mypy (the kwarg exists on from_character_schema) and by the
grep-completeness check recorded in the P1 commit.
"""
from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.raid_info import RaidInfo
from tests.test_ai.fixtures import make_state


def _raid() -> RaidInfo:
    """A raid with a live instance. `is_active()` keys on status == "active",
    not on the timestamps, so status is what makes this non-vacuous."""
    now = datetime.now(timezone.utc)
    return RaidInfo(code="enchanted_fairy", name="Enchanted Fairy",
                    monster="pixie", status="active",
                    next_start_at=now + timedelta(days=1),
                    remaining_hp=5000, total_hp=10000,
                    window_ends_at=now + timedelta(hours=1))


def test_move_apply_preserves_raids():
    raids = [_raid()]
    state = make_state(x=0, y=0, raids=raids)
    new = MoveAction(x=1, y=0).apply(state, GameData())
    assert new.raids == raids


def test_rest_apply_preserves_raids():
    """A second action kind, so the test is not satisfied by MoveAction alone
    happening to use dataclasses.replace."""
    raids = [_raid()]
    state = make_state(hp=10, max_hp=100, raids=raids)
    new = RestAction().apply(state, GameData())
    assert new.raids == raids


def test_active_raids_survives_a_two_step_plan():
    """The failure mode this guards: raids present at plan start, gone by step 2.

    `active_raids` filters `raids` by window, so it is the property a future
    ParticipateRaid gate would actually read."""
    raids = [_raid()]
    state = make_state(x=0, y=0, hp=10, max_hp=100, raids=raids)
    assert state.active_raids, "fixture must start with an ACTIVE raid or this is vacuous"
    step1 = MoveAction(x=1, y=0).apply(state, GameData())
    step2 = RestAction().apply(step1, GameData())
    assert step2.active_raids == state.active_raids
