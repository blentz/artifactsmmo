"""JsonlEventEmitter: writes ChildEvent lines to a stream, one per line."""

from typing import TextIO

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import (
    ExitEvent,
    PlanningEvent,
    SnapshotEvent,
)


class JsonlEventEmitter:
    """Child-side protocol writer.

    Every line is flushed: the supervisor reads this stream live, so a buffered
    write would stall the TUI until the buffer filled or the child exited.
    """

    def __init__(self, character: str, stream: TextIO) -> None:
        self._character = character
        self._stream = stream

    def _write(self, payload: str) -> None:
        self._stream.write(payload + "\n")
        self._stream.flush()

    def snapshot(self, snap: CycleSnapshot) -> None:
        self._write(
            SnapshotEvent(character=self._character, payload=snap).model_dump_json()
        )

    def planning(self, active: bool) -> None:
        self._write(
            PlanningEvent(character=self._character, active=active).model_dump_json()
        )

    def emit_exit(self, reason: str) -> None:
        self._write(
            ExitEvent(character=self._character, reason=reason).model_dump_json()
        )
