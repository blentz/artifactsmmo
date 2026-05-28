"""Differential test: the real Python pure cores `balancing` and `learned_blend`
must agree with the proved Lean `balancingScaled` and `learnedBlend` exactly.

We use `fractions.Fraction` for `learned_blend` inputs so the comparison is
BIT-EXACT over ℚ (the Lean model and the Python pure core agree as exact
rationals; the Python production passes float constants `0.25, 0.5, 2.0,
1 - w, w` which are exact-representable rationals, but to dodge any float
round-off in the Hypothesis examples we compute the pure core with `Fraction`
inputs).

For `balancing`, the Lean model is scaled by 4 (over `Int`) and the Python
formula is `(1 + (1/4) * (leader - current - 2))` clamped to `[0.5, 2.0]`.
We compare `scaled / 4 == python_result_as_fraction`.
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.strategy_blend import (
    BALANCE_K,
    BALANCE_MAX,
    BALANCE_MIN,
    BALANCE_THRESHOLD,
    balancing,
    learned_blend,
)
from formal.diff.oracle_client import run_oracle


def _balancing_fraction(leader: int, current: int) -> Fraction:
    """Exact-rational mirror of `balancing` so we can compare bit-exactly."""
    raw = Fraction(1) + Fraction(1, 4) * (
        Fraction(leader) - Fraction(current) - Fraction(BALANCE_THRESHOLD)
    )
    lo = Fraction(1, 2)
    hi = Fraction(2)
    return max(lo, min(hi, raw))


@settings(max_examples=300)
@given(
    leader=st.integers(min_value=-50, max_value=200),
    current=st.integers(min_value=-50, max_value=200),
)
def test_balancing_matches_lean(leader: int, current: int) -> None:
    py_frac = _balancing_fraction(leader, current)
    lean = run_oracle("strategy_blend", [[0, leader, current]])[0]
    # Lean returns the scaled-by-4 Int.
    assert Fraction(lean["scaled"], 4) == py_frac
    # The float core agrees on every input where float is exact (0.25 = 1/4
    # makes the formula exact at machine doubles for small ints).
    assert balancing(leader, current) == float(py_frac)
    # The proved band bounds.
    assert BALANCE_MIN <= float(py_frac) <= BALANCE_MAX


def test_balancing_threshold_identity() -> None:
    """leader - current = 2 ⇒ multiplier = 1.0 (exactly). Boundary witness."""
    for leader in range(0, 20):
        current = leader - 2
        assert balancing(leader, current) == 1.0
        lean = run_oracle("strategy_blend", [[0, leader, current]])[0]
        assert lean["scaled"] == 4  # = 4 * 1.0


def test_balancing_upper_clamp_against_lean() -> None:
    """Arbitrarily large gap clamps to BALANCE_MAX (= 2.0)."""
    lean = run_oracle("strategy_blend", [[0, 1000, 0]])[0]
    assert lean["scaled"] == 8  # = 4 * 2.0
    assert balancing(1000, 0) == BALANCE_MAX


def test_balancing_lower_clamp_against_lean() -> None:
    """leader = current ⇒ multiplier clamps to BALANCE_MIN (= 0.5)."""
    lean = run_oracle("strategy_blend", [[0, 5, 5]])[0]
    assert lean["scaled"] == 2  # = 4 * 0.5
    assert balancing(5, 5) == BALANCE_MIN


# --- learned_blend ----------------------------------------------------------


def _fraction_args(value: Fraction, normalized: Fraction, w: Fraction) -> list[int]:
    return [
        1,  # query=1 (learned_blend)
        value.numerator, value.denominator,
        normalized.numerator, normalized.denominator,
        w.numerator, w.denominator,
    ]


@settings(max_examples=300)
@given(
    value_num=st.integers(min_value=-100, max_value=100),
    value_den=st.integers(min_value=1, max_value=10),
    normalized_num=st.integers(min_value=0, max_value=100),
    normalized_den=st.integers(min_value=1, max_value=100),
    w_num=st.integers(min_value=0, max_value=100),
    w_den=st.integers(min_value=1, max_value=100),
)
def test_learned_blend_matches_lean(
    value_num: int, value_den: int,
    normalized_num: int, normalized_den: int,
    w_num: int, w_den: int,
) -> None:
    value = Fraction(value_num, value_den)
    # normalized ∈ [0, 1]
    normalized = min(Fraction(1), Fraction(normalized_num, normalized_den))
    # w ∈ [0, 1] (bound theorem hypothesis)
    w = min(Fraction(1), Fraction(w_num, w_den))
    # Call the REAL production function so source mutations are caught (Fraction
    # arithmetic in `learned_blend` stays exact, since `*` and `+` on Fractions
    # are exact). Earlier this inlined the formula locally and let three
    # `learned_blend` mutations survive the gate.
    py = learned_blend(value, normalized, w)
    lean = run_oracle("strategy_blend", [_fraction_args(value, normalized, w)])[0]
    assert Fraction(lean["blend_num"], lean["blend_den"]) == py
    # Convex bound (the anti-Phase-1 property).
    assert min(value, normalized) <= py <= max(value, normalized)


def test_learned_blend_w_zero_identity_against_lean() -> None:
    """w = 0 ⇒ blend = value, INDEPENDENT of normalized."""
    value, normalized, w = Fraction(3, 10), Fraction(99, 100), Fraction(0)
    py = learned_blend(value, normalized, w)
    args = _fraction_args(value, normalized, w)
    lean = run_oracle("strategy_blend", [args])[0]
    assert py == Fraction(3, 10)
    assert Fraction(lean["blend_num"], lean["blend_den"]) == py


def test_learned_blend_w_one_picks_normalized_against_lean() -> None:
    """w = 1 ⇒ blend = normalized."""
    value, normalized, w = Fraction(3, 10), Fraction(99, 100), Fraction(1)
    py = learned_blend(value, normalized, w)
    args = _fraction_args(value, normalized, w)
    lean = run_oracle("strategy_blend", [args])[0]
    assert py == Fraction(99, 100)
    assert Fraction(lean["blend_num"], lean["blend_den"]) == py


def test_learned_blend_convex_endpoint_witnesses() -> None:
    """Concrete boundary witnesses for the convex bound: at value = 3/10 and
    normalized = 8/10, blend(w=1/4) lies strictly between."""
    value, normalized, w = Fraction(3, 10), Fraction(8, 10), Fraction(1, 4)
    py = learned_blend(value, normalized, w)
    args = _fraction_args(value, normalized, w)
    lean = run_oracle("strategy_blend", [args])[0]
    blend = Fraction(lean["blend_num"], lean["blend_den"])
    assert py == Fraction(17, 40)
    assert blend == py
    assert Fraction(3, 10) < blend < Fraction(8, 10)


def test_balance_constants_unchanged() -> None:
    """Pin the production constants the proof depends on. Any retune must
    update the Lean model (`balanceK`, `balanceThresh`, `balanceMinScaled`,
    `balanceMaxScaled`) in lockstep."""
    assert BALANCE_K == 0.25
    assert BALANCE_THRESHOLD == 2
    assert BALANCE_MIN == 0.5
    assert BALANCE_MAX == 2.0
