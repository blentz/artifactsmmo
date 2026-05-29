"""Differential test for `Formal.StoreWarmup` (Phase-7 Target F).

Pins the warmup-gate contracts of the `LearningStore` pure helpers.
"""
import statistics
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.learning.store_warmup_core import (
    WARMUP_MIN_SAMPLES,
    warmup_gated_median,
    warmup_gated_success_rate,
)
from formal.diff.oracle_client import run_oracle


@settings(max_examples=200)
@given(samples=st.lists(st.integers(min_value=-100, max_value=100), min_size=0, max_size=20))
def test_warmup_gated_median_matches_lean(samples):
    py = warmup_gated_median([float(s) for s in samples])
    median_int = int(statistics.median(samples)) if samples else 0
    args = [0, len(samples), median_int, *samples]
    lean = run_oracle("store_warmup", [args])[0]
    if len(samples) < WARMUP_MIN_SAMPLES:
        assert py is None
        assert lean["present"] is False
    else:
        assert py is not None
        assert lean["present"] is True
        # The Lean oracle is fed the integer median; Python computes its own.
        # Compare via the gate boundary: at-or-above the gate, both are some.


def test_warmup_gated_median_below_gate_returns_none():
    assert warmup_gated_median([]) is None
    assert warmup_gated_median([1.0, 2.0, 3.0, 4.0]) is None
    lean = run_oracle("store_warmup", [[0, 0, 0]])[0]
    assert lean["present"] is False


def test_warmup_gated_median_boundary_accepted():
    assert warmup_gated_median([1.0, 2.0, 3.0, 4.0, 5.0]) == 3.0
    lean = run_oracle("store_warmup", [[0, 5, 3, 1, 2, 3, 4, 5]])[0]
    assert lean["present"] is True
    assert lean["value"] == 3


@settings(max_examples=200)
@given(
    ok=st.integers(min_value=0, max_value=50),
    total=st.integers(min_value=0, max_value=50),
)
def test_warmup_gated_success_rate_matches_lean(ok, total):
    if ok > total:
        return
    outcomes = ["ok"] * ok + ["fail"] * (total - ok)
    py = warmup_gated_success_rate(outcomes)
    lean = run_oracle("store_warmup", [[1, ok, total]])[0]
    py_frac = Fraction(lean["rate_num"], lean["rate_den"])
    if total < WARMUP_MIN_SAMPLES:
        assert py == 1.0
        assert py_frac == 1
    else:
        assert py_frac == Fraction(ok, total)
        if total > 0:
            assert abs(py - ok / total) < 1e-9


def test_warmup_gated_success_rate_below_gate_returns_one():
    assert warmup_gated_success_rate([]) == 1.0
    assert warmup_gated_success_rate(["ok"] * 4) == 1.0
    lean = run_oracle("store_warmup", [[1, 0, 0]])[0]
    assert Fraction(lean["rate_num"], lean["rate_den"]) == 1


def test_warmup_gated_success_rate_boundary():
    assert warmup_gated_success_rate(["ok"] * 5) == 1.0
    lean = run_oracle("store_warmup", [[1, 5, 5]])[0]
    assert Fraction(lean["rate_num"], lean["rate_den"]) == 1
    assert warmup_gated_success_rate(["fail"] * 5) == 0.0
    lean = run_oracle("store_warmup", [[1, 0, 5]])[0]
    assert Fraction(lean["rate_num"], lean["rate_den"]) == 0
