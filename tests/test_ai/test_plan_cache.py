import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.plan_cache import PlanCache


@pytest.fixture
def game_data() -> GameData:
    """A minimal GameData: drop_item() falls back to the bare resource_code
    when no drop table is configured, which is all these tests need."""
    return GameData()


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


def test_cursor_holds_until_the_batch_target_is_reached(game_data):
    gather = GatherAction(resource_code="spruce_tree", quantity=3,
                          locations=frozenset({(0, 0)}))
    cache = PlanCache(selected_goal=object(), plan=[gather, object()],
                      crafting_target=None, latch_active=False,
                      goal_repr="G")
    drop = gather.drop_item(game_data)
    cache.arm_step({drop: 5}, game_data)
    assert cache.step_target == 8
    assert cache.batch_satisfied({drop: 6}, game_data) is False
    assert cache.batch_satisfied({drop: 8}, game_data) is True


def test_a_lucky_multi_unit_drop_satisfies_early(game_data):
    """The target is a state predicate, not a counter, so overshoot advances
    instead of hanging."""
    gather = GatherAction(resource_code="spruce_tree", quantity=3,
                          locations=frozenset({(0, 0)}))
    cache = PlanCache(selected_goal=object(), plan=[gather],
                      crafting_target=None, latch_active=False, goal_repr="G")
    drop = gather.drop_item(game_data)
    cache.arm_step({drop: 0}, game_data)
    assert cache.batch_satisfied({drop: 12}, game_data) is True


def test_unbatched_steps_are_always_satisfied(game_data):
    cache = PlanCache(selected_goal=object(), plan=[object()],
                      crafting_target=None, latch_active=False, goal_repr="G")
    cache.arm_step({}, game_data)
    assert cache.step_target is None
    assert cache.batch_satisfied({}, game_data) is True
