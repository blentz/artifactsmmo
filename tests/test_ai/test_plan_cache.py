from artifactsmmo_cli.ai.plan_cache import PlanCache


def _cache(plan):
    # plan elements are opaque to PlanCache (it only indexes), so sentinels suffice.
    return PlanCache(
        selected_goal=object(),
        plan=list(plan),
        crafting_target="copper_ring",
        latch_active=False,
        goal_repr="Goal(copper_ring)",
    )


def test_current_returns_step_at_cursor():
    c = _cache(["a", "b", "c"])
    assert c.current() == "a"
    c.advance()
    assert c.current() == "b"


def test_exhausted_after_last_step():
    c = _cache(["a"])
    assert c.exhausted() is False
    c.advance()
    assert c.exhausted() is True
    assert c.current() is None


def test_empty_plan_is_exhausted_immediately():
    c = _cache([])
    assert c.exhausted() is True
    assert c.current() is None
