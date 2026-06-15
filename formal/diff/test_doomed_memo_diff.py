"""Differential test: the real Python `DoomedMemo` (exponential-backoff no-plan
memo) must agree with the kernel-proved Lean `Formal.DoomedMemo` over ALL inputs.

Two surfaces are pinned:
  * `_ttl(failures)` ⇔ `Formal.DoomedMemo.ttl` — the geometric re-probe window
    (×2 per consecutive failure, capped at max_retry).
  * `is_doomed(...)` ⇔ `Formal.DoomedMemo.isDoomed` — the skip decision, including
    signature invalidation (a changed plannability signature ⇒ not doomed) and the
    window/expiry boundary (liveness: the goal is always re-probed eventually).

The live `is_doomed` is exercised through the live `mark` (consecutive same-signature
marks escalate the failure count), so this is the real state machine, not a re-impl.
"""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.doomed_memo import DoomedMemo
from formal.diff.oracle_client import run_oracle
from tests.test_ai.fixtures import make_state


@given(
    base=st.integers(min_value=1, max_value=64),
    max_retry=st.integers(min_value=0, max_value=500),
    failures=st.integers(min_value=1, max_value=12),
)
def test_ttl_matches_oracle(base, max_retry, failures):
    py = DoomedMemo(base, max_retry)._ttl(failures)
    lean = run_oracle("doomed_ttl", [[base, max_retry, failures]])[0]["ttl"]
    assert py == lean, f"ttl divergence at base={base} max={max_retry} f={failures}: {py} != {lean}"


@given(
    base=st.integers(min_value=1, max_value=64),
    max_retry=st.integers(min_value=0, max_value=500),
    failures=st.integers(min_value=1, max_value=6),
    set_at=st.integers(min_value=0, max_value=50),
    gap=st.integers(min_value=0, max_value=400),
    same_sig=st.booleans(),
)
def test_is_doomed_matches_oracle(base, max_retry, failures, set_at, gap, same_sig):
    cycle = set_at + gap
    memo = DoomedMemo(base, max_retry)
    set_state = make_state(level=1)                       # signature A
    query_state = make_state(level=1 if same_sig else 2)  # A (same) or B (different)
    goal = "G"
    # `failures` consecutive same-signature marks escalate the count to `failures`,
    # all recorded at cycle `set_at`.
    for _ in range(failures):
        memo.mark(goal, set_state, set_at)
    py = memo.is_doomed(goal, query_state, cycle)
    lean = run_oracle(
        "doomed_is_doomed",
        [[base, max_retry, 0, set_at, failures, 0 if same_sig else 1, cycle]],
    )[0]["doomed"]
    assert py == lean, (
        f"is_doomed divergence base={base} max={max_retry} f={failures} "
        f"set_at={set_at} cycle={cycle} same_sig={same_sig}: py={py} lean={lean}"
    )


def test_is_doomed_window_boundary_matches_oracle():
    """Pin the EXACT ttl boundary so the `< vs <=` mutant is killed: at
    gap == ttl the goal is no longer doomed; at gap == ttl-1 it still is."""
    base, max_retry = 20, 160
    for failures, ttl in [(1, 20), (2, 40), (3, 80), (4, 160)]:
        for gap in (ttl - 1, ttl):
            memo = DoomedMemo(base, max_retry)
            state = make_state(level=1)
            for _ in range(failures):
                memo.mark("G", state, 0)
            py = memo.is_doomed("G", state, gap)
            lean = run_oracle(
                "doomed_is_doomed", [[base, max_retry, 0, 0, failures, 0, gap]]
            )[0]["doomed"]
            assert py == lean
            assert py == (gap < ttl)


def test_unmarked_goal_never_doomed():
    """A goal that was never marked is not doomed (the `entry is None` branch)."""
    memo = DoomedMemo(20, 160)
    assert memo.is_doomed("never", make_state(level=1), 100) is False
