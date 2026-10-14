"""Characterization tests for `objective_step_is_fight_pure` (spec 2026-10-14
items-task-pays §1): a ReachCharLevel step is Fight-led unless an items task
is in progress AND it pays. The level gap plays no part."""

import pytest

from artifactsmmo_cli.ai.objective_step_fight_core import (
    items_task_active,
    objective_step_is_fight_pure,
)


def _fire(*, is_reach_char_level: bool = True, has_combat_monster: bool = True,
          task_type: str | None = None, task_code: str | None = None,
          task_total: int = 0, task_progress: int = 0, task_pays: bool = False) -> bool:
    return objective_step_is_fight_pure(
        is_reach_char_level=is_reach_char_level, has_combat_monster=has_combat_monster,
        task_type=task_type, task_code=task_code, task_total=task_total,
        task_progress=task_progress, task_pays=task_pays)


ACTIVE = {"task_type": "items", "task_code": "t1", "task_total": 5, "task_progress": 2}


def test_reach_char_level_with_monster_no_task_fires() -> None:
    assert _fire() is True


def test_non_reach_char_level_never_fires() -> None:
    assert _fire(is_reach_char_level=False) is False


def test_no_combat_monster_does_not_fire() -> None:
    assert _fire(has_combat_monster=False) is False


def test_a_paying_active_items_task_defers() -> None:
    assert _fire(**ACTIVE, task_pays=True) is False


def test_an_unpaid_active_items_task_fights() -> None:
    """HAL 2026-10-14: a worthless items task no longer defers the grind."""
    assert _fire(**ACTIVE, task_pays=False) is True


def test_a_paid_task_that_is_not_active_fights() -> None:
    assert _fire(task_type="items", task_code="t1", task_total=5, task_progress=5,
                 task_pays=True) is True
    assert _fire(task_type="monsters", task_code="t1", task_total=5, task_progress=2,
                 task_pays=True) is True
    assert _fire(task_type="items", task_code="", task_total=5, task_progress=2,
                 task_pays=True) is True
    assert _fire(task_type="items", task_code=None, task_total=5, task_progress=2,
                 task_pays=True) is True


@pytest.mark.parametrize(("task_type", "task_code", "total", "progress", "active"), [
    ("items", "t1", 5, 2, True),
    ("items", "t1", 5, 5, False),
    ("items", "t1", 0, 0, False),
    ("monsters", "t1", 5, 2, False),
    ("items", "", 5, 2, False),
    (None, None, 0, 0, False),
])
def test_items_task_active(task_type: str | None, task_code: str | None, total: int,
                           progress: int, active: bool) -> None:
    assert items_task_active(task_type, task_code, total, progress) is active
