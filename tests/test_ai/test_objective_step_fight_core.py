"""Characterization tests for `objective_step_is_fight_pure`.

Pins the ReachCharLevel -> GrindCharacterXPGoal (Fight-led) routing slice of
`objective_step_goal` (strategy_driver.py:719-752) that the Lean liveness model's
`objectiveStepIsFight` Bool binds to. These tests mirror the production branch
exactly so the differential gate can assert the Lean def agrees.
"""

from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure


def _fire(
    *,
    is_reach_char_level: bool = True,
    target: int = 50,
    level: int = 3,
    has_combat_monster: bool = True,
    task_type: str | None = None,
    task_code: str | None = None,
    task_total: int = 0,
    task_progress: int = 0,
) -> bool:
    return objective_step_is_fight_pure(
        is_reach_char_level=is_reach_char_level,
        target=target,
        level=level,
        has_combat_monster=has_combat_monster,
        task_type=task_type,
        task_code=task_code,
        task_total=task_total,
        task_progress=task_progress,
    )


def test_reach_char_level_with_monster_no_task_fires() -> None:
    assert _fire() is True


def test_non_reach_char_level_never_fires() -> None:
    assert _fire(is_reach_char_level=False) is False


def test_no_combat_monster_does_not_fire() -> None:
    assert _fire(has_combat_monster=False) is False


def test_long_haul_gap_with_active_items_task_defers() -> None:
    # gap = 50 - 3 = 47 > 4, items task in progress -> defer (False)
    assert _fire(
        target=50, level=3, task_type="items", task_code="t1",
        task_total=5, task_progress=2,
    ) is False


def test_small_gap_with_active_items_task_still_fires() -> None:
    # bootstrap path: gap = 4 (not > 4) -> fire even with items task active
    assert _fire(
        target=7, level=3, task_type="items", task_code="t1",
        task_total=5, task_progress=2,
    ) is True


def test_large_gap_without_items_task_fires() -> None:
    assert _fire(target=50, level=3, task_type=None, task_code=None) is True


def test_large_gap_with_completed_items_task_fires() -> None:
    # task_progress >= task_total -> not "active" -> fire
    assert _fire(
        target=50, level=3, task_type="items", task_code="t1",
        task_total=5, task_progress=5,
    ) is True


def test_large_gap_with_non_items_task_fires() -> None:
    assert _fire(
        target=50, level=3, task_type="monsters", task_code="t1",
        task_total=5, task_progress=2,
    ) is True


def test_large_gap_items_task_blank_code_fires() -> None:
    # empty task_code is falsy -> not active -> fire
    assert _fire(
        target=50, level=3, task_type="items", task_code="",
        task_total=5, task_progress=2,
    ) is True
