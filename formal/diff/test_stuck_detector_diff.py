"""Differential test: the real Python `StuckDetector` must agree with the proved
Lean `detect` model over the SAME buffered history / counter / ack cutoffs.

We drive a real `StuckDetector`: `record(...)` a random sequence of `CycleRecord`s
(optionally `acknowledge(...)` mid-stream), then read its internal buffered state
(`list(self._history)`, `self._cycle_counter`, `self._ack_index`) and feed exactly
that to the Lean oracle. The Lean model abstracts a record as `(state, goal,
noPlan)` — the only fields the detector reads — so we encode state/goal as small
ints and `noPlan = (action_name == "<no_plan>")`.

The suite covers: frozen-fires, osc-fires, noprog-fires, precedence
(frozen+noprog → frozen), ack-suppression (would-fire-frozen but acked → not
frozen), eviction (counter > len via >30 records), and a WINDOW-BOUNDARY case
where the kept-window length lands exactly on the 4/8/10 threshold so an
off-by-one in `_recent_since` flips the verdict.
"""
import random

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal
from formal.diff.oracle_client import run_oracle

_NO_PLAN = "<no_plan>"
_VERDICT = {
    StuckSignal.STATE_FROZEN: "frozen",
    StuckSignal.GOAL_OSCILLATION: "osc",
    StuckSignal.NO_PROGRESS: "noprog",
    None: "none",
}


def _record(state: int, goal: int, no_plan: bool) -> CycleRecord:
    return CycleRecord(
        state_key=(state,),
        goal_name=f"g{goal}",
        action_name=_NO_PLAN if no_plan else f"a{goal}",
        planned_depth=0,
        planner_timed_out=False,
        succeeded=not no_plan,
    )


def _ack_cutoffs(det: StuckDetector) -> tuple[int, int, int]:
    return (
        det._ack_index.get(StuckSignal.STATE_FROZEN, 0),
        det._ack_index.get(StuckSignal.GOAL_OSCILLATION, 0),
        det._ack_index.get(StuckSignal.NO_PROGRESS, 0),
    )


def _oracle_args(det: StuckDetector) -> list[int]:
    history = list(det._history)
    counter = det._cycle_counter
    ack_f, ack_o, ack_n = _ack_cutoffs(det)
    flat: list[int] = [counter, ack_f, ack_o, ack_n, len(history)]
    # state/goal codes are recovered from the synthetic encoding above.
    for rec in history:
        state = rec.state_key[0]
        goal = int(rec.goal_name[1:])
        no_plan = 1 if rec.action_name == _NO_PLAN else 0
        flat += [state, goal, no_plan]
    return flat


def _assert_matches(det: StuckDetector) -> None:
    py = det.detect()
    lean = run_oracle("stuck_detector", [_oracle_args(det)])[0]
    assert _VERDICT[py] == lean["detect"], (
        f"py={_VERDICT[py]} lean={lean['detect']} args={_oracle_args(det)}"
    )


# ---- randomized property test (≥200 examples) ----
@settings(max_examples=260)
@given(
    n=st.integers(min_value=0, max_value=45),
    seed=st.integers(min_value=0, max_value=10_000),
    do_ack=st.booleans(),
    ack_signal=st.sampled_from(list(StuckSignal)),
    n_states=st.integers(min_value=1, max_value=4),
    n_goals=st.integers(min_value=1, max_value=4),
    noplan_p=st.integers(min_value=0, max_value=100),
)
def test_random_histories(n, seed, do_ack, ack_signal, n_states, n_goals, noplan_p):
    rng = random.Random(seed)
    det = StuckDetector()
    ack_at = rng.randint(0, n) if (do_ack and n > 0) else -1
    for i in range(n):
        det.record(_record(
            state=rng.randrange(n_states),
            goal=rng.randrange(n_goals),
            no_plan=rng.randint(0, 100) < noplan_p,
        ))
        if i == ack_at:
            det.acknowledge(ack_signal)
    _assert_matches(det)


# ---- targeted scenarios ----
def test_noprog_fires():
    det = StuckDetector()
    for _ in range(4):
        det.record(_record(0, 0, no_plan=True))
    assert det.detect() == StuckSignal.NO_PROGRESS
    _assert_matches(det)


def test_osc_fires():
    det = StuckDetector()
    for i in range(8):
        det.record(_record(i, i % 2, no_plan=False))  # exactly 2 distinct goals
    assert det.detect() == StuckSignal.GOAL_OSCILLATION
    _assert_matches(det)


def test_frozen_fires():
    det = StuckDetector()
    for i in range(10):
        det.record(_record(0 if i < 5 else i, i % 3, no_plan=False))  # state 0 recurs 5x
    assert det.detect() == StuckSignal.STATE_FROZEN
    _assert_matches(det)


def test_precedence_frozen_over_noprog():
    # last-10 all state 0 (frozen) AND last-4 all <no_plan> (noprog) -> frozen wins.
    det = StuckDetector()
    for _ in range(10):
        det.record(_record(0, 0, no_plan=True))
    assert det.detect() == StuckSignal.STATE_FROZEN
    _assert_matches(det)


def test_ack_suppression_frozen():
    # would fire frozen, but acknowledge resets the window -> not frozen.
    det = StuckDetector()
    for _ in range(10):
        det.record(_record(0, 0, no_plan=False))
    assert det.detect() == StuckSignal.STATE_FROZEN
    det.acknowledge(StuckSignal.STATE_FROZEN)
    assert det.detect() != StuckSignal.STATE_FROZEN
    _assert_matches(det)


def test_eviction_counter_gt_len():
    # >30 records: deque evicts, counter > len(history); ack mid-stream so the
    # cutoff lands on an evicted global index (exercises start_idx arithmetic).
    det = StuckDetector()
    for i in range(20):
        det.record(_record(i % 2, i % 2, no_plan=False))
    det.acknowledge(StuckSignal.STATE_FROZEN)  # cutoff = 20
    for i in range(25):  # total 45 > maxlen 30 -> eviction
        det.record(_record(0, 0, no_plan=False))
    assert det._cycle_counter == 45
    assert len(det._history) == 30
    _assert_matches(det)


def test_window_boundary_frozen_exact_10():
    # Build so the post-ack frozen window is EXACTLY 10 records, all state 0:
    # ack at counter c, then record exactly 10 fresh state-0 records.
    # An off-by-one in start_idx (+1 or -1) changes which records clear the
    # cutoff, flipping the window length off 10 and the verdict off frozen.
    det = StuckDetector()
    for _ in range(7):  # noise, then ack
        det.record(_record(9, 5, no_plan=False))
    det.acknowledge(StuckSignal.STATE_FROZEN)  # cutoff = 7
    for _ in range(10):  # exactly 10 fresh state-0 records: window len == 10
        det.record(_record(0, 0, no_plan=False))
    lean = run_oracle("stuck_detector", [_oracle_args(det)])[0]
    assert lean["frozen_window_len"] == 10
    assert det.detect() == StuckSignal.STATE_FROZEN
    _assert_matches(det)


def test_window_boundary_noprog_exact_4():
    det = StuckDetector()
    for _ in range(3):
        det.record(_record(1, 1, no_plan=False))
    det.acknowledge(StuckSignal.NO_PROGRESS)  # cutoff = 3
    for _ in range(4):  # exactly 4 fresh <no_plan> records
        det.record(_record(2, 2, no_plan=True))
    lean = run_oracle("stuck_detector", [_oracle_args(det)])[0]
    assert lean["noprog_window_len"] == 4
    assert det.detect() == StuckSignal.NO_PROGRESS
    _assert_matches(det)


def test_window_boundary_noprog_one_short():
    # Post-ack window holds exactly 3 <no_plan> records (one BELOW the threshold of
    # 4), and the record at the cutoff boundary is ALSO <no_plan>. Normal: window
    # len 3 -> no fire. A start_idx+i+1 over-include bug would pull that boundary
    # record in -> len 4, all <no_plan> -> wrongly fires noprog. Pins the +1 side.
    det = StuckDetector()
    for _ in range(4):  # idx 0..3, all <no_plan>
        det.record(_record(7, 7, no_plan=True))
    det.acknowledge(StuckSignal.NO_PROGRESS)  # cutoff = 4
    for _ in range(3):  # idx 4..6, fresh <no_plan>
        det.record(_record(8, 8, no_plan=True))
    lean = run_oracle("stuck_detector", [_oracle_args(det)])[0]
    assert lean["noprog_window_len"] == 3
    assert det.detect() != StuckSignal.NO_PROGRESS
    _assert_matches(det)


def test_window_boundary_osc_exact_8():
    det = StuckDetector()
    for _ in range(5):
        det.record(_record(3, 3, no_plan=False))
    det.acknowledge(StuckSignal.GOAL_OSCILLATION)  # cutoff = 5
    for i in range(8):  # exactly 8 fresh records, exactly 2 distinct goals
        det.record(_record(i, i % 2, no_plan=False))
    lean = run_oracle("stuck_detector", [_oracle_args(det)])[0]
    assert lean["osc_window_len"] == 8
    assert det.detect() == StuckSignal.GOAL_OSCILLATION
    _assert_matches(det)
