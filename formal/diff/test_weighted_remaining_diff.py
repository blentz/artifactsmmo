"""Differential test: the real Python `weighted_remaining_pure` /
`is_complete_pure` must agree with the proved Lean `weightedRemaining` /
`isComplete`.

The Lean model works in EXACT RATIONAL arithmetic (`Rat`, no scaling); the
production fractions are deficit / target ratios produced as floats from
integer numerators / denominators (`objective.py:102-106`) and the personality
weights are floats returned by `Personality.category_weight` (BalancedPersonality
returns 1.0). Both are RATIONAL, so we exercise the real fractional domain
directly: every numeric input is an exact `fractions.Fraction`, and we call
`weighted_remaining_pure` with `Fraction` tuples so EVERY operation stays exact
(a Fraction `*`/`+` is exact; no float coercion). The Lean oracle reconstructs
each input as an exact `Rat` from a (numerator, denominator) pair and emits the
scalar's exact numerator / denominator, compared to the Python `Fraction` result
EXACTLY.

Sign/range reality: production fractions are in `[0, 1]` (deficit ≤ target ≥ 0),
production weights are STRICTLY POSITIVE under the documented contract (P1 ships
`BalancedPersonality` = (1, 1, 1); see `personality.py` docstring). The
positive-equivalence strategy honours this contract. A SEPARATE bug-teeth
strategy generates one zero weight + a nonzero fraction in that category to
exercise the proved
`Formal.WeightedRemaining.bug_teeth_witness` — confirming that the equivalence
FAILS exactly where the Lean witness says, on the real Python.
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.objective_completion import (
    is_complete_pure,
    weighted_remaining_pure,
)
from formal.diff.oracle_client import run_oracle


def _rat(flat: list[int], frac: Fraction) -> None:
    flat += [frac.numerator, frac.denominator]


def _lean_args(weights: tuple[Fraction, ...], fractions: tuple[Fraction, ...]) -> list[int]:
    assert len(weights) == len(fractions)
    flat: list[int] = [len(weights)]
    for w, f in zip(weights, fractions):
        _rat(flat, w)
        _rat(flat, f)
    return flat


def _lean(weights: tuple[Fraction, ...], fractions: tuple[Fraction, ...]) -> tuple[Fraction, bool]:
    res = run_oracle("weighted_remaining", [_lean_args(weights, fractions)])[0]
    return Fraction(res["wr_num"], res["wr_den"]), bool(res["is_complete"])


# Production-realistic strategies: weights are STRICTLY POSITIVE rationals; fractions
# are non-negative rationals in [0, 1]. Denominators 1..6 give genuinely non-integer
# values. Arity = 3 (the production CATEGORIES tuple).
_frac01 = st.fractions(min_value=0, max_value=1, max_denominator=6)
_weight_pos = st.fractions(min_value=Fraction(1, 6), max_value=10, max_denominator=6)


@settings(max_examples=200)
@given(
    w0=_weight_pos, w1=_weight_pos, w2=_weight_pos,
    f0=_frac01, f1=_frac01, f2=_frac01,
)
def test_python_matches_lean_positive(
    w0: Fraction, w1: Fraction, w2: Fraction,
    f0: Fraction, f1: Fraction, f2: Fraction,
) -> None:
    """EXACT identity: Python Fraction == Lean Rat oracle, with STRICTLY POSITIVE
    weights (the production contract); `is_complete_pure` agrees with the Lean
    `isComplete` predicate on the same triple."""
    weights = (w0, w1, w2)
    fractions_ = (f0, f1, f2)
    # Call the Python pure core with Fraction tuples — every op stays exact.
    # (The production core declares tuple[float, float, float], but the * and +
    # operators on Fraction are exact; type annotations don't affect runtime.)
    py_scalar = weighted_remaining_pure(weights, fractions_)  # type: ignore[arg-type]
    assert isinstance(py_scalar, Fraction)
    py_complete = is_complete_pure(fractions_)  # type: ignore[arg-type]
    lean_scalar, lean_complete = _lean(weights, fractions_)
    assert py_scalar == lean_scalar
    assert py_complete == lean_complete


@settings(max_examples=200)
@given(
    w0=_weight_pos, w1=_weight_pos, w2=_weight_pos,
    f0=_frac01, f1=_frac01, f2=_frac01,
)
def test_zero_iff_complete_under_positivity(
    w0: Fraction, w1: Fraction, w2: Fraction,
    f0: Fraction, f1: Fraction, f2: Fraction,
) -> None:
    """Under STRICTLY POSITIVE weights, the Python is_complete agrees with the
    scalar-is-zero test bit-for-bit (the proved
    `zero_iff_complete_pos` direction). Exercises both directions across the
    fractional domain."""
    weights = (w0, w1, w2)
    fractions_ = (f0, f1, f2)
    py_scalar = weighted_remaining_pure(weights, fractions_)  # type: ignore[arg-type]
    py_complete = is_complete_pure(fractions_)  # type: ignore[arg-type]
    assert (py_scalar == 0) == py_complete


@settings(max_examples=100)
@given(
    bump=_frac01,
    w0=_weight_pos, w1=_weight_pos, w2=_weight_pos,
    f0=_frac01, f1=_frac01, f2=_frac01,
)
def test_mono_in_fraction(
    bump: Fraction,
    w0: Fraction, w1: Fraction, w2: Fraction,
    f0: Fraction, f1: Fraction, f2: Fraction,
) -> None:
    """Monotonicity: bumping any single fraction never decreases the scalar
    (the proved `mono_head` fact applied at index 0). Exercised across all
    three positions by symmetry — each gets the bump in turn."""
    weights = (w0, w1, w2)
    base = (f0, f1, f2)
    bumped0 = (f0 + bump, f1, f2)
    bumped1 = (f0, f1 + bump, f2)
    bumped2 = (f0, f1, f2 + bump)
    s_base = weighted_remaining_pure(weights, base)  # type: ignore[arg-type]
    for bumped in (bumped0, bumped1, bumped2):
        s_bumped = weighted_remaining_pure(weights, bumped)  # type: ignore[arg-type]
        assert s_bumped >= s_base


# Bug-teeth strategy: ONE zero weight (the contract violation), the zeroed
# category has a NONZERO fraction, the other two categories have ZERO fractions.
# The proved `bug_teeth_witness` says this produces scalar 0 with ¬is_complete —
# the latent defect a zero-weight personality would expose. We assert it FAILS
# the equivalence on the real Python (proving the bug-teeth is FAITHFUL — the
# Python exhibits exactly the divergence Lean predicts).
_pos_frac = st.fractions(min_value=Fraction(1, 6), max_value=1, max_denominator=6)


@settings(max_examples=50)
@given(zero_idx=st.integers(min_value=0, max_value=2),
       w_other_a=_weight_pos, w_other_b=_weight_pos, f_zeroed=_pos_frac)
def test_bug_teeth_zero_weight_breaks_equivalence(
    zero_idx: int, w_other_a: Fraction, w_other_b: Fraction, f_zeroed: Fraction
) -> None:
    """Concrete bug-teeth: one zero weight at `zero_idx`, that category has a
    nonzero fraction, the other categories have zero fractions. Python returns
    scalar 0 (the zero weight absorbs the nonzero fraction) but
    `is_complete_pure` is FALSE (the zeroed category's fraction is positive).
    The Lean oracle mirrors this exactly: same scalar 0, same is_complete=False.
    This is the latent defect a future zero-weight personality would expose."""
    others = [w_other_a, w_other_b]
    weights_list: list[Fraction] = []
    for i in range(3):
        if i == zero_idx:
            weights_list.append(Fraction(0))
        else:
            weights_list.append(others.pop(0))
    fractions_list = [Fraction(0)] * 3
    fractions_list[zero_idx] = f_zeroed
    w_tup = (weights_list[0], weights_list[1], weights_list[2])
    f_tup = (fractions_list[0], fractions_list[1], fractions_list[2])
    py_scalar = weighted_remaining_pure(w_tup, f_tup)  # type: ignore[arg-type]
    py_complete = is_complete_pure(f_tup)  # type: ignore[arg-type]
    assert py_scalar == 0, py_scalar  # zero weight absorbs the nonzero fraction
    assert py_complete is False  # but the objective is NOT complete
    # Lean oracle agrees:
    lean_scalar, lean_complete = _lean(w_tup, f_tup)
    assert lean_scalar == 0
    assert lean_complete is False
    # And this BREAKS the would-be equivalence (the bug-teeth signal):
    assert (py_scalar == 0) != py_complete
