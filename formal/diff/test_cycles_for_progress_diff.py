"""Differential test: the real Python `cycles_for_progress_pure` must agree
with the proved Lean `cyclesForProgressPure` over the exact rational domain.

Background (Phase-3 Task 2, verdict (b)):
=========================================

The Python function builds a `list[int]` of intervals from TWO sources walking
the same chronological cycle stream — strict-increase markers AND
`cycles_to_satisfy` events — then returns `statistics.median(intervals)` when
warmup is reached.

The Lean oracle reproduces the EXACT integer median over `ℚ` (mid-point of two
ints when the count is even; the middle int when odd). Python's
`statistics.median` on a list of ints returns either an int (odd) or
`(a + b) / 2` float (even); for the small integer ranges this test generates,
both are exactly representable as a `Fraction`.

PRODUCTION DOMAIN: `WARMUP_MIN_SAMPLES = 10` (`projections.py:23`) — always
≥ 1 at the call site. We exercise `warmup ∈ [1, 10]` in the diff: at
`warmup = 0` `statistics.median` on an empty list crashes, which is
unreachable in production but would surface as a divergence between Python
(raises) and the Lean oracle (returns `some 0`). The production-reachable
input domain has `warmup ≥ 1`, so we bound the strategy to match.

INPUT-DOMAIN REALITY (writer evidence, see `cycles_for_progress_core.py`
header):
  * `cycle_index` is a strictly-increasing non-negative `int` per cycle.
  * `task_progress` is `int | None`; it can stay flat, jump up, or reset to 0.
  * `cycles_to_satisfy` is `int | None`; non-None only on the cycle that
    satisfied a goal; always non-negative.

The strategy generates Hypothesis-driven CHRONOLOGICAL row streams (with
strictly-increasing `cycle_index`), then REVERSES them to match the
production `recent_goal_cycles` newest-first convention.

The five branches the task explicitly demands are exercised:
  (i)   strict-increase-only (no satisfy readings)
  (ii)  satisfy-only (no strict increases)
  (iii) BOTH on a single cycle (the contested verdict-(b) case)
  (iv)  below-warmup-threshold
  (v)   positivity-of-result (every interval is >0 ⇒ result is >0).
"""
from __future__ import annotations

from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.learning.cycles_for_progress_core import (
    CycleRow,
    cycles_for_progress_pure,
)
from formal.diff.oracle_client import run_oracle


def _lean_args(rows_newest_first: list[CycleRow], warmup: int) -> list[int]:
    flat: list[int] = [warmup, len(rows_newest_first)]
    for r in rows_newest_first:
        flat.append(r.cycle_index)
        if r.task_progress is None:
            flat += [0, 0]
        else:
            flat += [1, r.task_progress]
        if r.cycles_to_satisfy is None:
            flat += [0, 0]
        else:
            flat += [1, r.cycles_to_satisfy]
    return flat


def _lean(rows_newest_first: list[CycleRow], warmup: int) -> Fraction | None:
    res = run_oracle("cycles_for_progress", [_lean_args(rows_newest_first, warmup)])[0]
    if not res["present"]:
        return None
    return Fraction(res["num"], res["den"])


def _py_as_fraction(rows_newest_first: list[CycleRow], warmup: int) -> Fraction | None:
    """Run the pure core and convert the float result to an EXACT Fraction.

    `statistics.median` on a list of ints returns either an int (odd length)
    or the float midpoint (even length). For the integer ranges in this test
    the midpoint `(a + b) / 2` is exactly representable as a float, so
    `Fraction.from_float` is exact. We use `Fraction(median_value)` which
    handles both int and float cases."""
    v = cycles_for_progress_pure(rows_newest_first, warmup)
    if v is None:
        return None
    return Fraction(v) if isinstance(v, int) else Fraction(v).limit_denominator(10**9)


# ------------------------------------------------------------ chronological row builder

_progress = st.integers(min_value=0, max_value=20)
_cycles_to_satisfy = st.integers(min_value=1, max_value=50)


@st.composite
def _row_stream(draw, *, min_rows: int, max_rows: int,
                allow_satisfy: bool = True,
                allow_strict_progress: bool = True) -> list[CycleRow]:
    """Generate a chronological row stream with strictly-increasing cycle_index.
    Returned in NEWEST-FIRST order (matching `recent_goal_cycles`)."""
    n = draw(st.integers(min_value=min_rows, max_value=max_rows))
    start = draw(st.integers(min_value=0, max_value=1000))
    indices = [start + i for i in range(n)]
    # task_progress: either always None, or a monotone-ish sequence.
    progress_mode = draw(st.sampled_from(["none", "stream"])) if allow_strict_progress else "none"
    if progress_mode == "stream":
        tp: list[int | None] = []
        cur = 0
        for _ in range(n):
            bump = draw(st.integers(min_value=0, max_value=2))
            cur += bump
            tp.append(cur)
    else:
        tp = [None] * n
    # cycles_to_satisfy: sparse, on at most a few cycles.
    cs: list[int | None] = [None] * n
    if allow_satisfy and n > 0:
        n_sat = draw(st.integers(min_value=0, max_value=min(3, n)))
        positions = draw(st.lists(st.integers(min_value=0, max_value=n - 1),
                                  min_size=n_sat, max_size=n_sat, unique=True))
        for p in positions:
            cs[p] = draw(_cycles_to_satisfy)
    chrono = [CycleRow(cycle_index=indices[i], task_progress=tp[i],
                       cycles_to_satisfy=cs[i]) for i in range(n)]
    return list(reversed(chrono))  # newest-first


@settings(max_examples=200)
@given(rows=_row_stream(min_rows=0, max_rows=15),
       warmup=st.integers(min_value=1, max_value=10))
def test_python_matches_lean_general(rows: list[CycleRow], warmup: int) -> None:
    """EXACT identity: Python pure-core == Lean Rat oracle on Hypothesis-generated
    streams that mix all five branches (strict-only, satisfy-only, both, below
    warmup, above warmup)."""
    py = _py_as_fraction(rows, warmup)
    lean = _lean(rows, warmup)
    assert py == lean, f"py={py!r} lean={lean!r} rows={rows!r} W={warmup}"


@settings(max_examples=100)
@given(rows=_row_stream(min_rows=3, max_rows=15, allow_satisfy=False),
       warmup=st.integers(min_value=1, max_value=4))
def test_strict_increase_only_branch(rows: list[CycleRow], warmup: int) -> None:
    """Branch (i): no satisfy readings — every contribution is a strict-increase
    interval (or warm-up returns None)."""
    py = _py_as_fraction(rows, warmup)
    lean = _lean(rows, warmup)
    assert py == lean


@settings(max_examples=100)
@given(rows=_row_stream(min_rows=3, max_rows=15, allow_strict_progress=False),
       warmup=st.integers(min_value=1, max_value=4))
def test_satisfy_only_branch(rows: list[CycleRow], warmup: int) -> None:
    """Branch (ii): no strict-increase intervals — every contribution comes
    from `cycles_to_satisfy > 0`."""
    py = _py_as_fraction(rows, warmup)
    lean = _lean(rows, warmup)
    assert py == lean


@settings(max_examples=50)
@given(
    a_bump=st.integers(min_value=1, max_value=5),
    b_bump=st.integers(min_value=1, max_value=5),
    satisfy_val=_cycles_to_satisfy,
    start=st.integers(min_value=0, max_value=100),
)
def test_both_on_single_cycle_intentional_double_signal(
    a_bump: int, b_bump: int, satisfy_val: int, start: int
) -> None:
    """Branch (iii): construct a row stream where the FINAL chronological row
    simultaneously bumps `task_progress` (a strict-increase event) AND
    records `cycles_to_satisfy > 0` (the satisfy event).

    Per the verdict-(b) intent (`cycles_for_progress_core.py` header), the
    two events are different measurements and BOTH contribute. The Lean
    oracle agrees exactly on what the Python computes — including this
    intentional dual signal. This pins the production semantics."""
    # chronological: progress sequence  0 -> a_bump (strict) -> a_bump+b_bump (strict; final)
    # The final row also carries cycles_to_satisfy.
    chrono = [
        CycleRow(cycle_index=start + 0, task_progress=0, cycles_to_satisfy=None),
        CycleRow(cycle_index=start + 1, task_progress=a_bump, cycles_to_satisfy=None),
        CycleRow(cycle_index=start + 2, task_progress=a_bump + b_bump,
                 cycles_to_satisfy=satisfy_val),
    ]
    rows = list(reversed(chrono))
    # warmup=2 to admit the (1 strict interval + 1 satisfy interval) = 2 elements case.
    py = _py_as_fraction(rows, 2)
    lean = _lean(rows, 2)
    assert py == lean
    # Verify the contribution count: 1 strict-increase interval (cycle 2 minus
    # cycle 1) and 1 satisfy interval. Median of [1, satisfy_val] is what we got.
    assert py is not None
    expected = Fraction(1 + satisfy_val, 2)
    assert py == expected


@settings(max_examples=50)
@given(rows=_row_stream(min_rows=0, max_rows=4),
       warmup=st.integers(min_value=5, max_value=10))
def test_below_warmup_returns_none(rows: list[CycleRow], warmup: int) -> None:
    """Branch (iv): tiny streams always fall below WARMUP (≤ 4 intervals
    possible; gate ≥ 5), so the result MUST be None on both sides."""
    py = _py_as_fraction(rows, warmup)
    lean = _lean(rows, warmup)
    assert py is None
    assert lean is None


@settings(max_examples=100)
@given(rows=_row_stream(min_rows=5, max_rows=15),
       warmup=st.integers(min_value=1, max_value=2))
def test_result_positivity_when_present(rows: list[CycleRow], warmup: int) -> None:
    """Branch (v): when the result is present, it is STRICTLY positive — the
    `or 15.0` caller-fallback at `projections.py:312` never collides with a
    returned 0 (no flapping bug). This pins the production positivity
    invariant the Lean `allIntervals_pos` theorem proves under
    `monoChrono` — exercised on Hypothesis-generated chronological streams
    (the generator enforces strictly-increasing cycle_index)."""
    py = _py_as_fraction(rows, warmup)
    lean = _lean(rows, warmup)
    assert py == lean
    if py is not None:
        assert py > 0, f"non-positive result {py} on rows={rows}"
