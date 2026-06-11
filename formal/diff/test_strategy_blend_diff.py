"""Differential test: the real Python pure cores `balancing` and `learned_blend`
must agree with the proved Lean `balancingScaled` and `learnedBlend` exactly.

P4a: the production cores are EXACT `fractions.Fraction` arithmetic. The Lean
Rat oracle and the production functions are compared bit-exactly with NO float
mirror and NO tolerance — `balancing` returns the exact rational directly
(the old `_balancing_fraction` local mirror is gone; the diff now drives the
production function itself), and `learned_blend` takes/returns Fractions.

For `balancing`, the Lean model is scaled by 4 (over `Int`) and the Python
formula is `(1 + (1/4) * (leader - current - 2))` clamped to `[1/2, 2]`.
We compare `scaled / 4 == balancing(leader, current)` exactly.
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


@settings(max_examples=300)
@given(
    leader=st.integers(min_value=-50, max_value=200),
    current=st.integers(min_value=-50, max_value=200),
)
def test_balancing_matches_lean(leader: int, current: int) -> None:
    # P4a: the PRODUCTION core is exact Fraction arithmetic — compare it to
    # the Lean Rat oracle directly, bit-exactly (exact == exact, no mirror).
    py_frac = balancing(leader, current)
    assert isinstance(py_frac, Fraction)
    lean = run_oracle("strategy_blend", [[0, leader, current]])[0]
    # Lean returns the scaled-by-4 Int.
    assert Fraction(lean["scaled"], 4) == py_frac
    # The proved band bounds.
    assert BALANCE_MIN <= py_frac <= BALANCE_MAX


def test_balancing_threshold_identity() -> None:
    """leader - current = 2 ⇒ multiplier = 1 (exactly). Boundary witness.
    The isinstance pin is the DETERMINISTIC kill for the P4a float-seed
    mutant (`1.0 + ...` contaminates the unclamped mid-band result into
    a float; at the threshold the result is unclamped)."""
    for leader in range(0, 20):
        current = leader - 2
        result = balancing(leader, current)
        assert result == Fraction(1)
        assert isinstance(result, Fraction)
        lean = run_oracle("strategy_blend", [[0, leader, current]])[0]
        assert lean["scaled"] == 4  # = 4 * 1


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
    `balanceMaxScaled`) in lockstep. P4a: the constants are exact Fractions
    (same rational values the float constants always denoted)."""
    assert Fraction(1, 4) == BALANCE_K
    assert BALANCE_THRESHOLD == 2
    assert Fraction(1, 2) == BALANCE_MIN
    assert Fraction(2) == BALANCE_MAX
