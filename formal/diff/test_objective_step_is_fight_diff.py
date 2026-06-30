"""Differential test for the O5.4 perception binding.

Binds the proved Lean def `Formal.ObjectiveStepFight.objectiveStepIsFightPure`
(via the `objective_step_is_fight` oracle command) to the LIVE production pure
core `objective_step_is_fight_pure` (objective_step_fight_core.py) — the predicate
that `strategy_driver.objective_step_goal`'s ReachCharLevel branch actually calls.
A surviving disagreement means the Lean model of `objectiveStepIsFight` has
drifted from the code that computes it.

Python `None` task fields map to "" for the oracle (both falsy); the Lean def
does the `== "items"` / `!= ""` comparisons itself.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from formal.diff.oracle_client import run_oracle_structured

# Include "items" (the stand-down type), other real types, None and "" (falsy).
_TASK_TYPES = st.sampled_from([None, "", "items", "monsters", "resources", "crafting"])
_TASK_CODES = st.sampled_from([None, "", "t1", "copper_ring", "green_slime"])


def _oracle_args(
    is_reach: bool, target: int, level: int, has_monster: bool,
    task_type: str | None, task_code: str | None, task_total: int, task_progress: int,
) -> list:
    return [
        1 if is_reach else 0,
        target,
        level,
        1 if has_monster else 0,
        task_type if task_type is not None else "",
        task_code if task_code is not None else "",
        task_total,
        task_progress,
    ]


def _lean(*args) -> bool:
    res = run_oracle_structured("objective_step_is_fight", [_oracle_args(*args)])[0]
    return bool(res["fires"])


def _py(
    is_reach: bool, target: int, level: int, has_monster: bool,
    task_type: str | None, task_code: str | None, task_total: int, task_progress: int,
) -> bool:
    return objective_step_is_fight_pure(
        is_reach_char_level=is_reach,
        target=target,
        level=level,
        has_combat_monster=has_monster,
        task_type=task_type,
        task_code=task_code,
        task_total=task_total,
        task_progress=task_progress,
    )


@given(
    is_reach=st.booleans(),
    target=st.integers(min_value=0, max_value=50),
    level=st.integers(min_value=1, max_value=50),
    has_monster=st.booleans(),
    task_type=_TASK_TYPES,
    task_code=_TASK_CODES,
    task_total=st.integers(min_value=0, max_value=20),
    task_progress=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=250, deadline=None)
def test_objective_step_is_fight_matches_oracle(
    is_reach: bool, target: int, level: int, has_monster: bool,
    task_type: str | None, task_code: str | None, task_total: int, task_progress: int,
) -> None:
    args = (is_reach, target, level, has_monster, task_type, task_code, task_total, task_progress)
    assert _py(*args) == _lean(*args)


def test_boundary_gap_exactly_four_with_active_items_task_fires() -> None:
    # gap == 4 is NOT > 4, so the bootstrap path fires despite an active items task.
    args = (True, 7, 3, True, "items", "t1", 5, 2)
    assert _py(*args) is True
    assert _lean(*args) is True


def test_boundary_gap_five_with_active_items_task_defers() -> None:
    # gap == 5 (> 4) with an active items task -> long-haul stand-down -> no fire.
    args = (True, 8, 3, True, "items", "t1", 5, 2)
    assert _py(*args) is False
    assert _lean(*args) is False
