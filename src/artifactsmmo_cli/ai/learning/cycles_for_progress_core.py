"""Pure functional core of `projections.cycles_for_progress`.

Verdict on the two-append-loops question (Phase-3 Task 2, verdict (b)):
================================================================

`cycles_for_progress` builds `intervals` from TWO sources over the same
chronological cycle stream:

  1. STRICT-PROGRESS intervals — distances between cycles where
     `task_progress` strictly increased over the previous cycle. The first
     strict-increase cycle seeds `last_progress_at`; each subsequent
     strict-increase contributes `cycle_index - last_progress_at` to
     `intervals` and updates `last_progress_at`. This measures "how many
     cycles a *progress tick* costs."

  2. CYCLES-TO-SATISFY intervals — for any cycle whose `cycles_to_satisfy`
     is non-None and > 0, the raw value (total cycles since first
     selection of the goal) is appended to `intervals`. This measures
     "how many cycles a full GOAL-SATISFACTION costs."

Can a single cycle contribute to BOTH? YES, by design. Writer evidence:

  * `task_progress` is recorded on EVERY cycle (every action writes it via
    `state.task_progress`, sometimes bumped via `new_progress` after
    `combat`/`crafting`/`task_trade`). See `world_state.py:200` and the
    actions tree (`actions/combat.py:89`, `actions/crafting.py:94`,
    `actions/task_trade.py:61`).
  * `cycles_to_satisfy` is recorded by `player.py:347-368` ONLY on a
    cycle where `outcome == "ok" and selected_goal.is_satisfied(new_state)`
    — i.e. the cycle on which the goal terminates. The value is
    `current_cycle - goal_first_selected_at` from
    `_compute_cycles_to_satisfy` (`player.py:1169-1174`).

The cycle that completes a `FarmItems`-style goal can simultaneously bump
`task_progress` (the final kill that hit `task_total`) AND emit a
`cycles_to_satisfy` reading. They measure ORTHOGONAL events:
"tick-to-tick distance" vs. "total-cycles-since-first-selection". Both
are valid contributions to the median estimate of "what does a unit of
progress cost." This is **intentional dual signal**, not double-counting
of the same event.

The Lean theorem `cyclesForProgressPure_eq_median_concat` pins the
contract `result = median(strictIntervals ++ satisfyIntervals)` over the
genuine concatenation of the two streams.

WARMUP gate: under `WARMUP_MIN_SAMPLES` total intervals, the function
returns `None` so callers fall back to the caller-specific default
(`projections.py:312` uses `or 15.0`).

POSITIVITY: every appended value is positive (strict-progress intervals
are positive because `cycle_index` is strictly increasing in chronological
order — see `_record_learning_cycle` increments — and the satisfy branch
explicitly gates on `cycles_to_satisfy > 0`). So `Some x ⇒ x > 0` and the
`or 15.0` fallback at the call site never collides with a returned 0.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CycleRow:
    """Minimal projection of `learning.models.Cycle` for `cycles_for_progress`.

    Mirrors only the fields the function inspects. Other Cycle fields are
    irrelevant to the median computation."""

    cycle_index: int
    task_progress: int | None
    cycles_to_satisfy: int | None


def cycles_for_progress_pure(
    rows_newest_first: Sequence[CycleRow], warmup_min_samples: int
) -> float | None:
    """Pure functional core of `projections.cycles_for_progress`.

    `rows_newest_first` is the LearningStore's `recent_goal_cycles` output
    (newest first); we reverse to chronological for delta detection,
    exactly as the production function does.
    """
    if not rows_newest_first:
        return None
    chrono = list(reversed(rows_newest_first))

    intervals: list[int] = []
    last_progress_at: int | None = None
    prev_progress: int | None = None
    for cycle in chrono:
        if (prev_progress is not None and cycle.task_progress is not None
                and cycle.task_progress > prev_progress):
            if last_progress_at is not None:
                intervals.append(cycle.cycle_index - last_progress_at)
            last_progress_at = cycle.cycle_index
        prev_progress = cycle.task_progress

    for cycle in chrono:
        if cycle.cycles_to_satisfy is not None and cycle.cycles_to_satisfy > 0:
            intervals.append(cycle.cycles_to_satisfy)

    if len(intervals) < warmup_min_samples:
        return None
    return statistics.median(intervals)
