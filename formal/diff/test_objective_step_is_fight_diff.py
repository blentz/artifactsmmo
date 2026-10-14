"""Differential test for the O5.4 perception binding.

Binds the proved Lean def `Formal.ObjectiveStepFight.objectiveStepIsFightPure`
(via the `objective_step_is_fight` oracle command) to the LIVE production pure
core `objective_step_is_fight_pure` (objective_step_fight_core.py) — the predicate
`strategy_driver.objective_step_goal`'s ReachCharLevel branch calls. A surviving
disagreement means the Lean model of `objectiveStepIsFight` has drifted from the
code that computes it.

Python `None` task fields map to "" for the oracle (both falsy); the Lean def
does the `== "items"` / `!= ""` comparisons itself.
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.objective_step_fight_core import objective_step_is_fight_pure
from formal.diff.oracle_client import run_oracle_structured

_TASK_TYPES = st.sampled_from([None, "", "items", "monsters", "resources", "crafting"])
_TASK_CODES = st.sampled_from([None, "", "t1", "copper_ring", "green_slime"])


def _lean(is_reach: bool, has_monster: bool, task_type: str | None, task_code: str | None,
          task_total: int, task_progress: int, task_pays: bool) -> bool:
    args = [1 if is_reach else 0, 1 if has_monster else 0,
            task_type if task_type is not None else "",
            task_code if task_code is not None else "",
            task_total, task_progress, 1 if task_pays else 0]
    return bool(run_oracle_structured("objective_step_is_fight", [args])[0]["fires"])


def _py(is_reach: bool, has_monster: bool, task_type: str | None, task_code: str | None,
        task_total: int, task_progress: int, task_pays: bool) -> bool:
    return objective_step_is_fight_pure(
        is_reach_char_level=is_reach, has_combat_monster=has_monster,
        task_type=task_type, task_code=task_code, task_total=task_total,
        task_progress=task_progress, task_pays=task_pays)


@given(
    is_reach=st.booleans(),
    has_monster=st.booleans(),
    task_type=_TASK_TYPES,
    task_code=_TASK_CODES,
    task_total=st.integers(min_value=0, max_value=20),
    task_progress=st.integers(min_value=0, max_value=20),
    task_pays=st.booleans(),
)
@settings(max_examples=250, deadline=None)
def test_objective_step_is_fight_matches_oracle(
    is_reach: bool, has_monster: bool, task_type: str | None, task_code: str | None,
    task_total: int, task_progress: int, task_pays: bool,
) -> None:
    args = (is_reach, has_monster, task_type, task_code, task_total, task_progress, task_pays)
    assert _py(*args) == _lean(*args)


def test_a_paying_active_items_task_defers() -> None:
    args = (True, True, "items", "t1", 5, 2, True)
    assert _py(*args) is False
    assert _lean(*args) is False


def test_an_unpaid_active_items_task_fires() -> None:
    args = (True, True, "items", "t1", 5, 2, False)
    assert _py(*args) is True
    assert _lean(*args) is True


def test_a_paying_completed_items_task_fires() -> None:
    args = (True, True, "items", "t1", 5, 5, True)
    assert _py(*args) is True
    assert _lean(*args) is True
