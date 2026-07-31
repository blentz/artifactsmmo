"""ChildEvent: the JSONL protocol between a bot child and the supervisor."""

import pytest
from pydantic import ValidationError

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import (
    ExitEvent,
    PlanningEvent,
    SnapshotEvent,
    parse_child_event,
)


def _snap() -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=7, timestamp="2026-07-30T12:00:00Z", character="hero",
        x=1, y=2, level=19, xp=100, max_xp=7200, hp=400, max_hp=475, gold=10,
        selected_goal="ReachLevel(50)", action="Fight(chicken)", outcome="ok",
    )


def test_snapshot_event_round_trips():
    event = SnapshotEvent(character="hero", payload=_snap())
    parsed = parse_child_event(event.model_dump_json())
    assert isinstance(parsed, SnapshotEvent)
    assert parsed.payload.cycle_index == 7
    assert parsed.payload.character == "hero"


def test_planning_event_round_trips():
    parsed = parse_child_event(PlanningEvent(character="hero", active=True).model_dump_json())
    assert isinstance(parsed, PlanningEvent)
    assert parsed.active is True


def test_exit_event_round_trips():
    parsed = parse_child_event(ExitEvent(character="hero", reason="stuck_exit").model_dump_json())
    assert isinstance(parsed, ExitEvent)
    assert parsed.reason == "stuck_exit"


def test_an_unknown_kind_is_an_error_not_a_silent_skip():
    with pytest.raises(ValidationError):
        parse_child_event('{"kind":"telemetry","character":"hero"}')


def test_malformed_json_is_an_error():
    with pytest.raises(ValidationError):
        parse_child_event('{"kind":"snapshot",')
