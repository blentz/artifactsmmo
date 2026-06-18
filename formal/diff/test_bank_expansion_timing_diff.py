"""should_expand_bank (Python) must agree with
Formal.BankExpansionTiming.shouldExpandBank (Lean) over int grids.

The oracle takes a flat 7-int arg array
`[used, capacity, gold, cost, reserve, triggerNum, triggerDen]` and emits
`{"expand": 1}` / `{"expand": 0}`. The Python core returns a bool; the test
compares against `int(...)`.

Reserve is sampled from {0, 500} (a representative reserve floor plus the
no-reserve corner) so the SAFETY gate is exercised at a non-zero floor and at the
degenerate zero floor; the trigger is sampled near the production 95/100 plus a
few alternates so the cross-multiply boundary is exercised exactly.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.bank_expansion_timing import should_expand_bank
from formal.diff.oracle_client import run_oracle


@settings(max_examples=500)
@given(
    used=st.integers(0, 120),
    capacity=st.integers(0, 120),
    gold=st.integers(0, 2000),
    cost=st.integers(0, 2000),
    reserve=st.sampled_from([0, 500]),
    trigger=st.sampled_from([(95, 100), (90, 100), (1, 1), (3, 4), (0, 1)]),
)
def test_decision_matches_lean(used, capacity, gold, cost, reserve, trigger):
    tn, td = trigger
    py = should_expand_bank(used, capacity, gold, cost, reserve, tn, td)
    lean = run_oracle(
        "bank_expansion_timing", [[used, capacity, gold, cost, reserve, tn, td]]
    )[0]
    assert lean["expand"] == (1 if py else 0)


def test_safety_hole_witness():
    """Pin the SAFETY-HOLE the fix closes: bank full and gold >= cost (the old
    bare check would fire), but buying drops gold below the reserve, so the
    decision must be False on BOTH sides. used=96/100 >= 95/100 threshold;
    gold-cost = 520-100 = 420 < 500 reserve."""
    py = should_expand_bank(96, 100, 520, 100, 500, 95, 100)
    lean = run_oracle("bank_expansion_timing", [[96, 100, 520, 100, 500, 95, 100]])[0]
    assert py is False
    assert lean["expand"] == 0


def test_true_witness():
    """The documented non-vacuity witness fires on both sides."""
    py = should_expand_bank(96, 100, 600, 50, 500, 95, 100)
    lean = run_oracle("bank_expansion_timing", [[96, 100, 600, 50, 500, 95, 100]])[0]
    assert py is True
    assert lean["expand"] == 1
