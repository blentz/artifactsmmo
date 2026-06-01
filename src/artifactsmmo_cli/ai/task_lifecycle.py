"""Taskmaster task lifecycle phase enum and derivation helper.

Phase 23c-1 introduces an explicit lifecycle-phase signal on
:class:`artifactsmmo_cli.ai.world_state.WorldState`, derived deterministically
from the raw task fields ``(task_code, task_progress, task_total)`` via
:func:`derive_task_lifecycle_phase`. The phase replaces several opaque
firing-Bool checks scattered across tier predicates and is the field the
Phase 23c-2 Lean ``State`` will reference.

The enum and helper share this module per CLAUDE.md's "one *behavioral* class
per file" rule — :class:`TaskLifecyclePhase` is a pure data enum and the helper
is a small companion function with no behavior beyond pure derivation.
"""

from enum import Enum


class TaskLifecyclePhase(Enum):
    """Lifecycle phase of the character's taskmaster task.

    Derived deterministically from ``(task_code, task_progress, task_total)``
    by :func:`derive_task_lifecycle_phase`. Stored on
    :class:`artifactsmmo_cli.ai.world_state.WorldState` as the canonical
    "where in the task pipeline are we?" signal.

    The phase is invariant-by-construction: ``WorldState.__post_init__``
    asserts the stored phase matches the derived value, so any direct
    WorldState construction with mismatched fields is a programmer error
    caught at instantiation.
    """

    NONE = "none"
    """No task accepted."""

    ACCEPTED = "accepted"
    """Task accepted, no progress yet (``task_progress == 0``)."""

    IN_PROGRESS = "in_progress"
    """Task in progress (``0 < task_progress < task_total``)."""

    COMPLETE = "complete"
    """Task ready for turn-in (``task_progress >= task_total``, ``task_total > 0``)."""


def derive_task_lifecycle_phase(
    task_code: str | None,
    task_progress: int,
    task_total: int,
) -> TaskLifecyclePhase:
    """Derive the lifecycle phase from raw task fields.

    Single source of truth for the phase. ``task_code`` falsy (None or
    empty string) maps to :attr:`TaskLifecyclePhase.NONE` regardless of
    progress/total — covers both the pre-acceptance state and the
    post-turn-in state where ``CompleteTaskAction`` leaves ``task_code=""``.

    A ``task_code`` set with ``task_total == 0`` is treated as NONE: this is
    the server-paired contract (a real task always has total > 0). This
    excludes the phantom-task edge case where the API briefly reports a
    task code without a total.
    """
    if not task_code:
        return TaskLifecyclePhase.NONE
    if task_total <= 0:
        return TaskLifecyclePhase.NONE
    if task_progress >= task_total:
        return TaskLifecyclePhase.COMPLETE
    if task_progress == 0:
        return TaskLifecyclePhase.ACCEPTED
    return TaskLifecyclePhase.IN_PROGRESS
