import pytest

from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.should_replan import refresh_only, should_replan


def _cache(cursor=0, plan_len=3, cycles=0):
    return PlanCache(
        selected_goal=object(),
        plan=["a"] * plan_len,
        crafting_target=None,
        plan_level=1,
        goal_repr="g",
        cursor=cursor,
        cycles_since_replan=cycles,
    )


def _ok_hit_args():
    # cache present, last action ok, goal unsatisfied, level unchanged,
    # under the interval, step applicable -> reuse (False).
    return dict(
        cache=_cache(),
        last_outcome="ok",
        level=1,
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


def test_a_level_up_since_plan_time_replans():
    """Phase 4-3b: a level-up is a re-rank fact read off the state, replacing
    the RegearEdge latch."""
    args = _ok_hit_args()
    args["level"] = 2  # the plan was made at level 1
    assert should_replan(**args) is True


def test_interval_bound_replans():
    args = _ok_hit_args()
    args["cache"] = _cache(cycles=20)
    assert should_replan(**args) is True


def test_inapplicable_step_replans():
    args = _ok_hit_args()
    args["step_applicable"] = False
    assert should_replan(**args) is True


def _refresh_args(**over):
    args = dict(_ok_hit_args(), cache=_cache(cycles=20))
    args.update(over)
    return args


def test_the_staleness_bound_alone_is_a_refresh():
    assert should_replan(**_refresh_args()) is True
    assert refresh_only(**_refresh_args()) is True
    assert refresh_only(**_refresh_args(last_outcome=None)) is True


@pytest.mark.parametrize("over", [
    dict(cache=None),
    dict(last_outcome="error:cooldown"),
    dict(goal_satisfied=True),
    dict(cache=_cache(cursor=3, cycles=20)),
    dict(level=2),
    dict(cache=_cache(cycles=19)),
    dict(step_applicable=False),
])
def test_any_other_trigger_is_not_a_refresh(over):
    """A committed plan survives the periodic re-decide only when nothing but
    the staleness bound asks for it (Phase 2d-L1c)."""
    assert refresh_only(**_refresh_args(**over)) is False
