"""JsonlEventEmitter: child-side protocol writer."""

import io

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import (
    ExitEvent,
    PlanningEvent,
    SnapshotEvent,
    parse_child_event,
)
from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter


def _snap(cycle_index: int = 1) -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=cycle_index, timestamp="2026-07-30T12:00:00Z", character="hero",
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )


def test_each_event_is_one_parseable_line():
    stream = io.StringIO()
    emitter = JsonlEventEmitter(character="hero", stream=stream)
    emitter.snapshot(_snap(1))
    emitter.planning(True)
    emitter.emit_exit("normal")
    lines = stream.getvalue().splitlines()
    assert len(lines) == 3
    kinds = [type(parse_child_event(line)) for line in lines]
    assert kinds == [SnapshotEvent, PlanningEvent, ExitEvent]


def test_every_line_carries_the_character():
    stream = io.StringIO()
    JsonlEventEmitter(character="alice", stream=stream).planning(False)
    assert parse_child_event(stream.getvalue()).character == "alice"


def test_each_write_is_flushed():
    """The parent reads this stream live; a buffered write would stall the TUI
    until the buffer filled or the child exited."""
    flushes = []

    class _Counting(io.StringIO):
        def flush(self) -> None:
            flushes.append(1)

    emitter = JsonlEventEmitter(character="hero", stream=_Counting())
    emitter.snapshot(_snap())
    emitter.planning(True)
    assert len(flushes) == 2
