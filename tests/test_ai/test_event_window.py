"""event_window_sufficient_pure: will the event still be up when we get there,
AND still be up long enough to finish what we planned? (epic P2)

`WorldState.active_events` has carried expirations all along, but nothing outside
`event_availability` read them -- grepping `expir` across ai/goals/ and ai/tiers/
returned zero hits. So the planner would commit a 40-step chain to content that
expires in 90 seconds.

The existing NPC gate checked TRAVEL only, which is the right shape but half the
question: reaching a spawn tile is pointless if the event closes midway through
the ten actions you planned to do there.

Plan cost converts directly to seconds because the planner's cost unit IS 10
seconds -- established by rest_cost_pure, where a full-HP rest is 100s = 10.0.
"""

import pytest

from artifactsmmo_cli.ai.event_availability import (
    EVENT_ARRIVAL_MARGIN_SECONDS,
    EVENT_TRAVEL_SECONDS_PER_TILE,
    PLAN_SECONDS_PER_COST_UNIT,
    event_window_sufficient_pure,
)


def test_ample_window_is_sufficient():
    assert event_window_sufficient_pure(remaining_seconds=3600, distance=5,
                                        plan_cost=2.0) is True


def test_window_shorter_than_travel_is_insufficient():
    """The original NPC question: cannot even get there."""
    assert event_window_sufficient_pure(remaining_seconds=10, distance=20,
                                        plan_cost=0.0) is False


def test_window_that_covers_travel_but_not_the_plan_is_insufficient():
    """THE P2 CASE. 5 tiles is 25s of travel and the window has 90s, so the old
    travel-only gate would say yes -- but the plan needs 40 cost units = 400s."""
    assert event_window_sufficient_pure(remaining_seconds=90, distance=5,
                                        plan_cost=40.0) is False
    # ...and the same trip with a short plan is fine.
    assert event_window_sufficient_pure(remaining_seconds=90, distance=5,
                                        plan_cost=2.0) is True


def test_margin_is_required_on_top():
    """A window that covers travel+plan EXACTLY still refuses: arriving as the
    event closes wastes the trip."""
    distance, plan_cost = 4, 1.0
    exact = distance * EVENT_TRAVEL_SECONDS_PER_TILE + plan_cost * PLAN_SECONDS_PER_COST_UNIT
    assert event_window_sufficient_pure(remaining_seconds=exact,
                                        distance=distance, plan_cost=plan_cost) is False
    assert event_window_sufficient_pure(
        remaining_seconds=exact + EVENT_ARRIVAL_MARGIN_SECONDS + 1,
        distance=distance, plan_cost=plan_cost) is True


def test_expired_window_is_insufficient():
    assert event_window_sufficient_pure(remaining_seconds=0, distance=0,
                                        plan_cost=0.0) is False
    assert event_window_sufficient_pure(remaining_seconds=-5, distance=0,
                                        plan_cost=0.0) is False


def test_cost_unit_is_ten_seconds():
    """Pinned because the conversion is the whole basis of the plan-length half:
    the planner's cost unit is 10s (rest_cost_pure: a full-HP rest is 100s =
    10.0). If that ever changes, this gate silently mis-scales."""
    assert PLAN_SECONDS_PER_COST_UNIT == 10.0


@pytest.mark.parametrize("plan_cost", [0.0, -1.0])
def test_non_positive_plan_cost_degrades_to_the_travel_question(plan_cost):
    """A caller with no plan yet (or a nonsense one) still gets the travel gate
    rather than an exception -- that is the pre-P2 behaviour, preserved."""
    assert event_window_sufficient_pure(remaining_seconds=3600, distance=1,
                                        plan_cost=plan_cost) is True
    assert event_window_sufficient_pure(remaining_seconds=5, distance=100,
                                        plan_cost=plan_cost) is False
