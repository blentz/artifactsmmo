"""currency_grind_target_pure: how far to grind toward a vendor price this cycle.

Replaces the bare `held + 1` "grind-one-replan" idiom at
strategy_driver.py:514. That idiom exists for a good reason -- a one-shot plan
for a 230-coin price is ~120 fights deep and dies on max_depth (sandwhisper_bag
probe 2026-07-06 @L50: 28K nodes, plan_len=0) -- so the fix must keep plans
SHALLOW. But `held + 1` re-arms every single time a unit lands, and `needed` is
part of the goal's identity (gathering.py:711-720), so the goal's repr churned
every acquisition, resetting sticky-commit keying.

The milestone ladder keeps both properties: the target is an ABSOLUTE multiple of
the batch, so it is stable across the acquisitions within a batch, and it is never
more than one batch ahead of what is held, so the plan stays shallow.

Live case: event_ticket, which drops at 0.5% per gather (changelog 8.2.0), so a
100-ticket vendor price is ~20,000 gather actions.
"""

import pytest

from artifactsmmo_cli.ai.currency_grind_target import currency_grind_target_pure
from artifactsmmo_cli.ai.thresholds import CURRENCY_GRIND_BATCH


def test_batch_constant_is_positive():
    """A zero or negative batch would make the ladder collapse or spin."""
    assert CURRENCY_GRIND_BATCH >= 1


def test_target_is_stable_within_a_batch():
    """THE CHURN FIX. Acquiring a unit must NOT move the target while still
    inside the same batch -- that is what kept the goal's identity changing
    every cycle."""
    targets = {currency_grind_target_pure(held, price=100)
               for held in range(CURRENCY_GRIND_BATCH)}
    assert len(targets) == 1, f"target moved within one batch: {targets}"


def test_target_advances_once_a_batch_completes():
    at_start = currency_grind_target_pure(0, price=100)
    just_past = currency_grind_target_pure(CURRENCY_GRIND_BATCH, price=100)
    assert just_past > at_start
    assert just_past == 2 * at_start


def test_target_never_exceeds_the_price():
    """Overshooting would grind currency the vendor does not want."""
    for held in range(0, 120):
        assert currency_grind_target_pure(held, price=100) <= 100


def test_cheap_price_is_taken_in_one_step():
    """When the whole price fits inside a batch the plan is already shallow, so
    there is no reason to ladder -- ask for the price outright."""
    assert currency_grind_target_pure(0, price=3) == 3


def test_target_always_exceeds_held_while_unaffordable():
    """The goal must always ask for at least one MORE unit, or it would be
    trivially satisfied and the bot would spin without progressing."""
    for held in range(0, 100):
        assert currency_grind_target_pure(held, price=100) > held


def test_target_stays_shallow():
    """Never more than one batch ahead of what is held -- this is the property
    that keeps the planner off the 120-fight cliff the old idiom avoided."""
    for held in range(0, 100):
        assert currency_grind_target_pure(held, price=1000) - held <= CURRENCY_GRIND_BATCH


@pytest.mark.parametrize("price", [0, -5])
def test_non_positive_price_yields_no_grind(price):
    """A vendor price of zero or less is not a grind target; return 0 rather
    than laddering forever."""
    assert currency_grind_target_pure(0, price=price) == 0
