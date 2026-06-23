import pytest

from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.should_replan import should_replan


def _cache(cursor=0, plan_len=3, latch=False, cycles=0):
    return PlanCache(
        selected_goal=object(),
        plan=["a"] * plan_len,
        crafting_target=None,
        latch_active=latch,
        goal_repr="g",
        cursor=cursor,
        cycles_since_replan=cycles,
    )


def _ok_hit_args():
    # cache present, last action ok, goal unsatisfied, latch unchanged,
    # under the interval, step applicable -> reuse (False).
    return dict(
        cache=_cache(),
        last_outcome="ok",
        latch_active=False,
        goal_satisfied=False,
        step_applicable=True,
        replan_interval=20,
    )


def test_cache_hit_reuses():
    assert should_replan(**_ok_hit_args()) is False


def test_cold_start_replans():
    args = _ok_hit_args()
    args["cache"] = None
    assert should_replan(**args) is True


@pytest.mark.parametrize("outcome", ["error:fight_lost", "error:cooldown", "error:network"])
def test_non_ok_outcome_replans(outcome):
    args = _ok_hit_args()
    args["last_outcome"] = outcome
    assert should_replan(**args) is True


def test_goal_satisfied_replans():
    args = _ok_hit_args()
    args["goal_satisfied"] = True
    assert should_replan(**args) is True


def test_exhausted_plan_replans():
    args = _ok_hit_args()
    args["cache"] = _cache(cursor=3, plan_len=3)  # cursor == len -> exhausted
    assert should_replan(**args) is True


def test_latch_change_replans():
    args = _ok_hit_args()
    args["latch_active"] = True  # cache.latch_active is False -> changed
    assert should_replan(**args) is True


def test_interval_bound_replans():
    args = _ok_hit_args()
    args["cache"] = _cache(cycles=20)
    assert should_replan(**args) is True


def test_inapplicable_step_replans():
    args = _ok_hit_args()
    args["step_applicable"] = False
    assert should_replan(**args) is True
