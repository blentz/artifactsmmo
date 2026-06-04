"""Item 9c diff test: task_lifecycle.derive_task_lifecycle_phase.

Production: derives the lifecycle phase from raw task fields. Pure
function; the diff test pins each of the 4 phase outcomes against a
mutation budget that mutators (`> → >=`, `0 → 1`, etc.) would break.
"""

from __future__ import annotations

from artifactsmmo_cli.ai.task_lifecycle import (
    TaskLifecyclePhase,
    derive_task_lifecycle_phase,
)


def test_none_when_task_code_absent():
    assert derive_task_lifecycle_phase(None, 0, 0) == TaskLifecyclePhase.NONE
    assert derive_task_lifecycle_phase(None, 5, 10) == TaskLifecyclePhase.NONE


def test_none_when_task_code_empty_string():
    assert derive_task_lifecycle_phase("", 0, 0) == TaskLifecyclePhase.NONE
    # Empty string is the post-turn-in placeholder.
    assert derive_task_lifecycle_phase("", 10, 10) == TaskLifecyclePhase.NONE


def test_none_when_task_total_zero_despite_code():
    # Phantom-task edge case.
    assert derive_task_lifecycle_phase("copper_ore", 0, 0) == TaskLifecyclePhase.NONE
    assert derive_task_lifecycle_phase("copper_ore", 5, 0) == TaskLifecyclePhase.NONE


def test_accepted_at_zero_progress():
    assert derive_task_lifecycle_phase("copper_ore", 0, 10) == TaskLifecyclePhase.ACCEPTED


def test_in_progress_mid_task():
    assert derive_task_lifecycle_phase("copper_ore", 1, 10) == TaskLifecyclePhase.IN_PROGRESS
    assert derive_task_lifecycle_phase("copper_ore", 9, 10) == TaskLifecyclePhase.IN_PROGRESS


def test_complete_when_progress_reaches_total():
    assert derive_task_lifecycle_phase("copper_ore", 10, 10) == TaskLifecyclePhase.COMPLETE


def test_complete_when_progress_exceeds_total():
    # Server can briefly report progress > total during the turn-in race.
    assert derive_task_lifecycle_phase("copper_ore", 11, 10) == TaskLifecyclePhase.COMPLETE
