"""Differential test: the LIVE production task-trade transition
(`task_trade_step` / `task_trade_applicable`, the extracted cores that
`TaskTradeAction.is_applicable` / `.apply` now call) must agree with the proven
inventory-COUPLED termination model `Formal.Liveness.ItemsTaskRun.trade`.

This is the live-path differential that binds the proven coupled termination
model to the REAL running bot. `TaskTradeAction.apply` consumes `quantity` held
task items and advances `task_progress` by `quantity`; the proven model's
per-unit `trade` consumes ONE held item and advances progress by ONE, only
while `0 < held ∧ progress < total`. The faithful correspondence is:

    the live `task_trade_step(held, progress, quantity)` over the REACHABLE
    trading domain == `quantity`-fold application of `ItemsTaskRun.trade`.

## Why the domain is RESTRICTED (and why that is honest, not rigging)

The planner only ever fires `TaskTradeAction` from states that satisfy BOTH:

* the ACTION guard `held >= quantity >= 1` — `is_applicable` returns False
  otherwise, so the live `apply` is never reached with `held < quantity`; and
* the GOAL stop guard `progress < total` — `PursueTaskGoal.is_satisfied`
  returns True at `progress >= total`, so the arbiter stops selecting the
  pursue goal and TaskTrade is never planned once the task is complete.

Within a single multi-unit trade the planner also never overshoots `total`
(the batch `k` is clamped to `remaining = total - progress`, proven by
`TaskBatch`), so `progress + quantity <= total` on every fired trade. That is
precisely the domain where every per-unit `ItemsTaskRun.trade` in the
`quantity`-fold replicate FIRES (`replicate_trade_progress_of_room`). Restricting
the Hypothesis search to this set is NOT hiding a divergence — it is the genuine
precondition under which the live planner ever calls TaskTrade. The boundary
tests below pin the edges of that domain explicitly, and the
`progress >= total` no-fire case is checked separately (the live action guard
now refuses it, conforming to `trade_stuck_at_total`).
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.task_trade_core import (
    task_trade_applicable,
    task_trade_step,
)
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(
    progress=st.integers(min_value=0, max_value=200),
    room=st.integers(min_value=1, max_value=200),
    quantity=st.integers(min_value=1, max_value=200),
    surplus=st.integers(min_value=0, max_value=50),
)
def test_step_matches_quantity_fold_trade(progress, room, quantity, surplus):
    """Over the reachable trading domain the live `task_trade_step` equals
    `quantity`-fold `ItemsTaskRun.trade` (held decremented by quantity, progress
    incremented by quantity)."""
    total = progress + room
    # Reachable domain: held >= quantity (the action guard) and the trade does
    # not overshoot total (the batch clamp). `quantity` is forced to fit the room.
    quantity = min(quantity, room)
    held = quantity + surplus  # held >= quantity, possibly with surplus held

    # Live production transition (the extracted core the real apply calls).
    new_held, new_progress = task_trade_step(held, progress, quantity)

    # Proven model: quantity-fold trade via the oracle.
    lean = run_oracle("items_task_run", [[held, progress, total, quantity]])[0]
    assert new_held == lean["held"]
    assert new_progress == lean["progress"]
    # The coupling: held dropped by exactly quantity, progress rose by exactly quantity.
    assert new_held == held - quantity
    assert new_progress == progress + quantity

    # And the live applicability matches per-unit fireability over the domain:
    # in this domain held >= quantity >= 1 (so held > 0) and progress < total.
    assert task_trade_applicable(held, quantity, progress, total) is True
    assert lean["applicable"] is True


@settings(max_examples=300)
@given(
    held=st.integers(min_value=0, max_value=50),
    quantity=st.integers(min_value=0, max_value=50),
    progress=st.integers(min_value=0, max_value=50),
    total=st.integers(min_value=0, max_value=50),
)
def test_applicable_reachable_domain_predicate(held, quantity, progress, total):
    """`task_trade_applicable` is exactly the reachable-domain predicate:
    the action guard (held >= quantity >= 1) AND the goal stop (progress < total).

    Cross-check against the oracle's per-unit fireability at the SUFFICIENT-held
    boundary: when held >= quantity >= 1, the live predicate's truth coincides
    with `0 < held ∧ progress < total` (the per-unit trade firing condition),
    because held >= quantity >= 1 implies held > 0."""
    py = task_trade_applicable(held, quantity, progress, total)
    expected = (quantity >= 1) and (held >= quantity) and (progress < total)
    assert py is expected
    if py:
        # held >= quantity >= 1 ⇒ held > 0, so the per-unit trade is fireable.
        lean = run_oracle("items_task_run", [[held, progress, total, quantity]])[0]
        assert lean["applicable"] is True


def test_boundary_exact_room_fully_drains():
    """quantity == room == held: every held item consumed, progress hits total
    exactly (the `held_accounts` shape — held drains to 0, progress reaches
    total)."""
    held, progress, total, quantity = 3, 0, 3, 3
    new_held, new_progress = task_trade_step(held, progress, quantity)
    assert (new_held, new_progress) == (0, 3)
    lean = run_oracle("items_task_run", [[held, progress, total, quantity]])[0]
    assert lean["held"] == 0
    assert lean["progress"] == 3


def test_boundary_surplus_held_untouched():
    """held > quantity: only `quantity` items consumed, the surplus stays held."""
    held, progress, total, quantity = 10, 5, 20, 5
    new_held, new_progress = task_trade_step(held, progress, quantity)
    assert (new_held, new_progress) == (5, 10)
    lean = run_oracle("items_task_run", [[held, progress, total, quantity]])[0]
    assert lean["held"] == 5
    assert lean["progress"] == 10


def test_progress_at_total_is_not_applicable():
    """progress >= total: the live action guard refuses (no over-trade past
    total), conforming to `ItemsTaskRun.trade_stuck_at_total`."""
    assert task_trade_applicable(held=10, quantity=5, progress=20, total=20) is False
    lean = run_oracle("items_task_run", [[10, 20, 20, 5]])[0]
    # The per-unit trade is NOT fireable at progress == total.
    assert lean["applicable"] is False
    # And folding any number of trades is a no-op there.
    assert lean["held"] == 10
    assert lean["progress"] == 20


def test_held_below_quantity_is_not_applicable():
    """held < quantity: the live action guard refuses (insufficient inventory)."""
    assert task_trade_applicable(held=2, quantity=5, progress=0, total=20) is False


def test_quantity_zero_is_not_applicable():
    """quantity < 1: the live action guard refuses (no degenerate empty trade)."""
    assert task_trade_applicable(held=10, quantity=0, progress=0, total=20) is False
