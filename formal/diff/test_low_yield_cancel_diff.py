"""Differential test: the real Python `low_yield_fires_pure` must agree with
the proved Lean `lowYieldFiresPure`.

The Lean model is over EXACT RATIONALS — `current_xp`, `alt_xp`, `confidence`,
`margin`, `min_confidence` are `Rat`. The Python pure boundary operates with
floats in production, but its semantics are arithmetic + comparison only
(`<`, `>=`, `*`, `==`, integer counts), all of which `fractions.Fraction`
supports exactly. The differential feeds `Fraction` inputs to the Python core
and serialises them as (num, den) pairs into the oracle, comparing the
Boolean verdict bit-exactly.

DOMAIN COVERAGE (no rejection of contested cases):
  * `has_task = False` blocks everything.
  * `farm_samples = 0` or `alt_samples = 0` blocks.
  * Zero-fast-path: `current_xp = 0` ∧ `alt_xp > 0` fires regardless of
    confidence or sample count (INTENDED, see test docstring below).
  * Margin gate under positive `current_xp`:
      confidence boundary `< 0.5` vs `>= 0.5`,
      margin boundary `< 1.5*current` vs `>= 1.5*current`.
  * Fractional inputs (Fraction with small denominators).
  * Single-sample alt with low confidence — the zero-fast-path witness.

BOUNDARY-PINNED CASES: the contested zero-fast-path bypass is exercised by an
explicit witness in `test_zero_fast_path_witness`; the confidence and margin
boundaries are exercised in `test_*_boundary`.

PRODUCTION CONSTANTS: `LOW_YIELD_CONFIDENCE_THRESHOLD = 1/2`,
`LOW_YIELD_ALTERNATIVE_MARGIN = 3/2`.
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.learning.low_yield_boundary import low_yield_fires_pure
from formal.diff.oracle_client import run_oracle

MARGIN = Fraction(3, 2)
MIN_CONF = Fraction(1, 2)


def _rat(flat: list[int], frac: Fraction) -> None:
    flat.append(frac.numerator)
    flat.append(frac.denominator)


def _lean_args(has_task: bool, cur: Fraction, alt: Fraction, conf: Fraction,
               farm_n: int, alt_n: int, margin: Fraction, min_conf: Fraction) -> list[int]:
    flat: list[int] = [1 if has_task else 0]
    _rat(flat, cur)
    _rat(flat, alt)
    _rat(flat, conf)
    flat.append(farm_n)
    flat.append(alt_n)
    _rat(flat, margin)
    _rat(flat, min_conf)
    return flat


def _lean_fires(has_task: bool, cur: Fraction, alt: Fraction, conf: Fraction,
                farm_n: int, alt_n: int,
                margin: Fraction = MARGIN, min_conf: Fraction = MIN_CONF) -> bool:
    res = run_oracle("low_yield_cancel",
                     [_lean_args(has_task, cur, alt, conf, farm_n, alt_n, margin, min_conf)])[0]
    return bool(res["fires"])


def _py_fires(has_task: bool, cur: Fraction, alt: Fraction, conf: Fraction,
              farm_n: int, alt_n: int,
              margin: Fraction = MARGIN, min_conf: Fraction = MIN_CONF) -> bool:
    # Pass Fraction inputs so arithmetic stays exact (no float coercion).
    # The pure boundary only does ==, <, >, >=, *, all exact for Fraction.
    return low_yield_fires_pure(
        has_task=has_task,
        current_xp=cur,  # type: ignore[arg-type]
        alt_xp=alt,  # type: ignore[arg-type]
        confidence=conf,  # type: ignore[arg-type]
        farm_samples=farm_n,
        alt_samples=alt_n,
        margin=margin,  # type: ignore[arg-type]
        min_confidence=min_conf,  # type: ignore[arg-type]
    )


# `current_xp`, `alt_xp` ∈ [0, 1000] as exact rationals with small denominator.
_xp_strat = st.fractions(min_value=Fraction(0), max_value=Fraction(1000),
                         max_denominator=6)
# `confidence` ∈ [0, 1] as exact rational with small denominator.
_conf_strat = st.fractions(min_value=Fraction(0), max_value=Fraction(1),
                           max_denominator=6)
# Sample counts in [0, 100] — both zero and positive exercised.
_samples_strat = st.integers(min_value=0, max_value=100)


@settings(max_examples=250)
@given(has_task=st.booleans(), cur=_xp_strat, alt=_xp_strat, conf=_conf_strat,
       farm_n=_samples_strat, alt_n=_samples_strat)
def test_fires_matches_oracle(has_task: bool, cur: Fraction, alt: Fraction,
                              conf: Fraction, farm_n: int, alt_n: int) -> None:
    py = _py_fires(has_task, cur, alt, conf, farm_n, alt_n)
    lean = _lean_fires(has_task, cur, alt, conf, farm_n, alt_n)
    assert py == lean, (py, lean, has_task, cur, alt, conf, farm_n, alt_n)


@settings(max_examples=40)
@given(cur=_xp_strat, alt=_xp_strat, conf=_conf_strat,
       farm_n=_samples_strat, alt_n=_samples_strat)
def test_no_task_never_fires(cur: Fraction, alt: Fraction, conf: Fraction,
                             farm_n: int, alt_n: int) -> None:
    """`has_task = False` is the shell's first guard — both sides must agree False."""
    assert _py_fires(False, cur, alt, conf, farm_n, alt_n) is False
    assert _lean_fires(False, cur, alt, conf, farm_n, alt_n) is False


@settings(max_examples=40)
@given(cur=_xp_strat, alt=_xp_strat, conf=_conf_strat, alt_n=_samples_strat)
def test_no_farm_samples_never_fires(cur: Fraction, alt: Fraction, conf: Fraction,
                                     alt_n: int) -> None:
    """`farm_samples = 0` blocks regardless of everything else."""
    assert _py_fires(True, cur, alt, conf, 0, alt_n) is False
    assert _lean_fires(True, cur, alt, conf, 0, alt_n) is False


@settings(max_examples=40)
@given(cur=_xp_strat, alt=_xp_strat, conf=_conf_strat, farm_n=_samples_strat)
def test_no_alt_samples_never_fires(cur: Fraction, alt: Fraction, conf: Fraction,
                                    farm_n: int) -> None:
    """`alt_samples = 0` blocks regardless of everything else."""
    assert _py_fires(True, cur, alt, conf, farm_n, 0) is False
    assert _lean_fires(True, cur, alt, conf, farm_n, 0) is False


def test_zero_fast_path_witness() -> None:
    """The INTENDED zero-fast-path bypass: `current_xp = 0`, `alt_xp = 1`,
    confidence = 0 (< 0.5 gate), alt_samples = 1. Fires on both sides."""
    assert _py_fires(True, Fraction(0), Fraction(1), Fraction(0), 1, 1) is True
    assert _lean_fires(True, Fraction(0), Fraction(1), Fraction(0), 1, 1) is True


def test_zero_alt_with_zero_current_blocks_fast_path() -> None:
    """`current_xp = 0` AND `alt_xp = 0` — fast-path requires alt > 0, gate
    requires conf ≥ 0.5. At conf=0 both block."""
    assert _py_fires(True, Fraction(0), Fraction(0), Fraction(0), 5, 5) is False
    assert _lean_fires(True, Fraction(0), Fraction(0), Fraction(0), 5, 5) is False


def test_confidence_boundary_below() -> None:
    """confidence = 49/100 < 1/2 ⇒ no fire (positive current)."""
    assert _py_fires(True, Fraction(1), Fraction(100), Fraction(49, 100), 10, 10) is False
    assert _lean_fires(True, Fraction(1), Fraction(100), Fraction(49, 100), 10, 10) is False


def test_confidence_boundary_at() -> None:
    """confidence = 1/2 is exactly the gate (>=) — fires when margin met."""
    assert _py_fires(True, Fraction(1), Fraction(3, 2), Fraction(1, 2), 10, 10) is True
    assert _lean_fires(True, Fraction(1), Fraction(3, 2), Fraction(1, 2), 10, 10) is True


def test_margin_boundary_below() -> None:
    """alt = 149/100 < 1.5 * 1 ⇒ no fire even at full confidence."""
    assert _py_fires(True, Fraction(1), Fraction(149, 100), Fraction(1), 10, 10) is False
    assert _lean_fires(True, Fraction(1), Fraction(149, 100), Fraction(1), 10, 10) is False


def test_margin_boundary_at() -> None:
    """alt = 3 == 2 * 1.5 — exactly meets the >= margin."""
    assert _py_fires(True, Fraction(2), Fraction(3), Fraction(1), 10, 10) is True
    assert _lean_fires(True, Fraction(2), Fraction(3), Fraction(1), 10, 10) is True


@settings(max_examples=40)
@given(alt=_xp_strat, conf=_conf_strat,
       farm_n=st.integers(min_value=1, max_value=100),
       alt_n=st.integers(min_value=1, max_value=100))
def test_zero_fast_path_fires_when_alt_positive(alt: Fraction, conf: Fraction,
                                                farm_n: int, alt_n: int) -> None:
    """For any `alt > 0` and `current = 0` with samples positive, the rule
    fires REGARDLESS of confidence. Mirrors `zero_fast_path_fires_unconditionally`."""
    if alt <= 0:
        return
    assert _py_fires(True, Fraction(0), alt, conf, farm_n, alt_n) is True
    assert _lean_fires(True, Fraction(0), alt, conf, farm_n, alt_n) is True
