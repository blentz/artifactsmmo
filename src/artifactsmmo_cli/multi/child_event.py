"""ChildEvent: the newline-delimited JSON protocol a `--emit-events` child
writes to stdout and the `play --all` supervisor reads.

Schema module: a discriminated union plus its variants, no behavior.
`CycleSnapshot` is already a pydantic model, so the wire format is generated
from it rather than hand-written, and cannot drift from it.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


class SnapshotEvent(BaseModel):
    kind: Literal["snapshot"] = "snapshot"
    character: str
    payload: CycleSnapshot


class PlanningEvent(BaseModel):
    kind: Literal["planning"] = "planning"
    character: str
    active: bool


class ExitEvent(BaseModel):
    kind: Literal["exit"] = "exit"
    character: str
    reason: str
    """The `exit_reason` play() computes for the learning store, with one
    refinement: an uncaught httpx transport error reports `crash:network` so
    the RestartPolicy can tell a transient failure from a real bug."""


ChildEvent = Annotated[
    SnapshotEvent | PlanningEvent | ExitEvent, Field(discriminator="kind")
]

_ADAPTER: TypeAdapter[ChildEvent] = TypeAdapter(ChildEvent)


def parse_child_event(line: str) -> ChildEvent:
    """Parse one protocol line. Raises `ValidationError` on anything malformed
    or unrecognised — a complete-but-unparseable line means the protocol has
    drifted and must be fixed, never silently dropped."""
    return _ADAPTER.validate_json(line)
