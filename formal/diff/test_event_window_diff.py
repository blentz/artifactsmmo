"""event_npc_tradeable (Python) must agree with Formal.EventWindow.eventNpcTradeable.

Drives the LIVE `event_npc_tradeable` over randomized event/active/spawn/time
configurations, derives the SAME six integers the proved `Int` model consumes
from those exact inputs, and asserts the boolean verdicts are identical.

FLOAT → INT FAITHFULNESS: the Python constants `EVENT_TRAVEL_SECONDS_PER_TILE`
(5.0) and `EVENT_ARRIVAL_MARGIN_SECONDS` (10.0) are exact integers in double, and
the Manhattan `distance` is an integer, so `distance * 5.0 == distance * 5` and
`margin == 10` exactly; `remaining` is `int((expiration - now).total_seconds())`.
The only op is a single `>` comparison of these exact values, so the float
boolean equals the Int-model boolean — checked here, not just asserted.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import example, given, settings, strategies as st

from artifactsmmo_cli.ai.event_availability import (
    EVENT_ARRIVAL_MARGIN_SECONDS,
    EVENT_TRAVEL_SECONDS_PER_TILE,
    event_npc_tradeable,
)
from artifactsmmo_cli.ai.game_data import GameData
from formal.diff.oracle_client import run_oracle

_NPC = "gold_merchant"
_EVENT = "gold_event"
_NOW = datetime(2026, 6, 7, 12, 0, 0, tzinfo=timezone.utc)


def _game_data(is_event: bool, has_spawn: bool, spawn: tuple[int, int]) -> GameData:
    gd = GameData()
    if is_event:
        gd._npc_event_code.update({_NPC: _EVENT})
        if has_spawn:
            gd._npc_locations = {_NPC: spawn}
    return gd


@settings(max_examples=500)
# Exact-boundary witnesses (active, spawned event): remaining == travel + margin
# (window too tight by exactly 0 — must REFUSE) and remaining == travel+margin+1
# (just open). These pin the `>` vs `>=` arrival-margin boundary. travel for
# (sx,sy)=(5,0),(x,y)=(0,0) is 5*5=25, margin=10, so boundary = 35.
@example(is_event=True, active=True, has_spawn=True, sx=5, sy=0, x=0, y=0,
         boundary=0)
@example(is_event=True, active=True, has_spawn=True, sx=5, sy=0, x=0, y=0,
         boundary=1)
@example(is_event=True, active=True, has_spawn=True, sx=5, sy=0, x=0, y=0,
         boundary=-1)
@given(
    is_event=st.booleans(),
    active=st.booleans(),
    has_spawn=st.booleans(),
    sx=st.integers(-50, 50),
    sy=st.integers(-50, 50),
    x=st.integers(-50, 50),
    y=st.integers(-50, 50),
    # `boundary` offsets remaining relative to the exact arrival boundary
    # (travel + margin); the wide span around 0 stresses the `>` comparison.
    boundary=st.integers(-400, 7200),
)
def test_event_window_matches_lean(
    is_event, active, has_spawn, sx, sy, x, y, boundary
):
    spawn = (sx, sy)
    gd = _game_data(is_event, has_spawn, spawn)
    distance0 = abs(sx - x) + abs(sy - y)
    travel0 = distance0 * int(EVENT_TRAVEL_SECONDS_PER_TILE)
    margin0 = int(EVENT_ARRIVAL_MARGIN_SECONDS)
    remaining_seconds = travel0 + margin0 + boundary
    expiration = _NOW + timedelta(seconds=remaining_seconds)
    active_events = {_EVENT: expiration} if active else {}

    py = event_npc_tradeable(
        _NPC, gd, x=x, y=y, active_events=active_events, now=_NOW,
    )

    # Derive the six ints the proved Int model consumes from the SAME inputs.
    spawn_present = is_event and has_spawn
    distance = abs(sx - x) + abs(sy - y)
    travel = distance * int(EVENT_TRAVEL_SECONDS_PER_TILE)
    margin = int(EVENT_ARRIVAL_MARGIN_SECONDS)
    remaining = int((expiration - _NOW).total_seconds())
    args = [
        1 if is_event else 0,
        1 if active else 0,
        1 if spawn_present else 0,
        remaining,
        travel,
        margin,
    ]
    lean = run_oracle("event_window", [args])[0]
    assert lean["tradeable"] == (1 if py else 0)
