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
     cycles a *progress tick* costs." A `None` task_progress reading RESETS
     the detector: the next cycle has no previous value to strictly exceed.

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

EXACT-ARITHMETIC CORE (mechanical-extraction P3c):
==================================================

The decision arithmetic lives in `cycles_for_progress_exact`, an exact
`Fraction`-valued core over the extractable subset (the two scans are
explicit single-accumulator folds over per-cycle step functions; the median
is an explicit sorted-list median — middle element when the interval count
is odd, the EXACT `Fraction(a + b, 2)` mean of the two middle elements when
even). The exact core (plus `_strict_step`/`_satisfy_step`/`_median_exact`)
is mechanically extracted to `formal/Formal/Extracted/CyclesForProgress.lean`
and bridged against the proved hand model `Formal.CyclesForProgress`.

`cycles_for_progress_pure` is the preserved public float boundary: it runs
the exact core and converts the single result to `float` at the end. That
conversion is OUTSIDE the proved core (the trusted seam; the differential
suite samples it):

  * odd interval count: the median is an integer; `float(Fraction(m))` is
    exact for every reachable magnitude (cycle indices are far below 2^53).
    NOTE: `statistics.median` used to return this as `int`; the boundary now
    returns the numerically-equal `float`.
  * even count: `float(Fraction(a + b, 2))` is the correctly-rounded double
    of the exact midpoint — bit-identical to the former `(a + b) / 2` float
    division (both are round-to-nearest of the same rational).
  * `warmup_min_samples <= 0` with no intervals is UNREACHABLE in production
    (the only caller passes `WARMUP_MIN_SAMPLES = 10`); on that input the
    empty-list index now raises `IndexError` where `statistics.median`
    raised `StatisticsError` — still a loud failure, never a value.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class CycleRow:
    """Minimal projection of `learning.models.Cycle` for `cycles_for_progress`.

    Mirrors only the fields the function inspects. Other Cycle fields are
    irrelevant to the median computation."""

    cycle_index: int
    task_progress: int | None
    cycles_to_satisfy: int | None


def _strict_step(
    state: tuple[list[int], int | None, int | None], cycle: CycleRow,
) -> tuple[list[int], int | None, int | None]:
    """One chronological step of the STRICT-PROGRESS interval scan.

    Threads `(intervals, last_progress_at, prev_progress)` exactly as the
    original loop did: `prev_progress` is ALWAYS replaced by this cycle's
    `task_progress` — so a `None` reading RESETS the strict-increase
    detector — and an interval is appended only when progress strictly
    increased over the previous reading AND an earlier strict increase
    already seeded `last_progress_at`."""
    intervals = state[0]
    last_progress_at = state[1]
    prev_progress = state[2]
    tp = cycle.task_progress
    if prev_progress is None:
        return (intervals, last_progress_at, tp)
    if tp is None:
        return (intervals, last_progress_at, tp)
    if tp <= prev_progress:
        return (intervals, last_progress_at, tp)
    if last_progress_at is None:
        return (intervals, cycle.cycle_index, tp)
    return ([*intervals, cycle.cycle_index - last_progress_at], cycle.cycle_index, tp)


def _satisfy_step(intervals: list[int], cycle: CycleRow) -> list[int]:
    """One step of the CYCLES-TO-SATISFY scan: append the raw reading when
    it is present and strictly positive."""
    cts = cycle.cycles_to_satisfy
    if cts is None:
        return intervals
    if cts <= 0:
        return intervals
    return [*intervals, cts]


def _median_exact(intervals: list[int]) -> Fraction:
    """Exact `statistics.median` over ints: the middle element when the
    count is odd, the EXACT mean of the two middle elements when even.
    Sorting a multiset of ints is order-independent, so `sorted` here agrees
    with any correct sort (the extracted Lean image uses insertion sort).
    Callers guard non-emptiness (the warm-up gate with `warmup >= 1`)."""
    ordered = sorted(intervals)
    n = len(ordered)
    if n % 2 == 1:
        return Fraction(ordered[n // 2])
    a = ordered[n // 2 - 1]
    b = ordered[n // 2]
    return Fraction(a + b, 2)


def cycles_for_progress_exact(
    rows_newest_first: list[CycleRow], warmup_min_samples: int,
) -> Fraction | None:
    """Exact-rational core of `cycles_for_progress`: the median over the
    concatenated strict-progress and cycles-to-satisfy interval streams, as
    an exact `Fraction`. Mechanically extracted to Lean and bridged against
    `Formal.CyclesForProgress.cyclesForProgressPure` (which the hand
    theorems pin to `median(strictIntervals ++ satisfyIntervals)`)."""
    if len(rows_newest_first) == 0:
        return None
    chrono = list(reversed(rows_newest_first))
    state: tuple[list[int], int | None, int | None] = ([], None, None)
    for cycle in chrono:
        state = _strict_step(state, cycle)
    intervals = state[0]
    for cycle in chrono:
        intervals = _satisfy_step(intervals, cycle)
    if len(intervals) < warmup_min_samples:
        return None
    return _median_exact(intervals)


def cycles_for_progress_pure(
    rows_newest_first: Sequence[CycleRow], warmup_min_samples: int,
) -> float | None:
    """Public float boundary of `cycles_for_progress` (callers untouched).

    `rows_newest_first` is the LearningStore's `recent_goal_cycles` output
    (newest first); the exact core reverses to chronological for delta
    detection, exactly as the production function always did. The single
    `float(...)` conversion below is the trusted seam OUTSIDE the proved
    exact core — see the module header for its exactness argument."""
    median = cycles_for_progress_exact(list(rows_newest_first), warmup_min_samples)
    if median is None:
        return None
    return float(median)
