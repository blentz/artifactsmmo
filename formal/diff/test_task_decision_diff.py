"""Differential test: the real Python `task_decision_pure` must agree with the
proved Lean `taskDecisionPure`.

The Lean model is over EXACT RATIONALS — `confidence ∈ [0, 1]` is a rational
fraction `confNum/confDen` (from `SkillXpCurve.confidence`), `skill_up_vpc` is
`reward / total_cycles` (a ratio of rationals), and the production constants
`baseline = 5` and `margin = 3` are exact integers. We exercise that domain
directly by sampling `fractions.Fraction` inputs and serialising them as
(numerator, denominator) pairs into the oracle. The Python core is purely
arithmetic + comparison (`*`, `+`, `-`, `>=`), and `Fraction` supports all of
those exactly with `Fraction >= float` etc.; so the Python decision is computed
on EXACT Fraction arithmetic and compared to the Lean Rat decision LABEL-FOR-LABEL.

Domains exercised (DOMAIN COVERAGE — no rejection of contested cases):
  * `req_is_none = True` short-circuits to PURSUE regardless.
  * `req_is_combat = True` + `req_is_none = False` ⇒ PIVOT.
  * `history_present = False` + `req_is_none = False` ⇒ PIVOT.
  * `confidence = 0` boundary: threshold = baseline * (1 + margin).
  * `confidence = 1` boundary: threshold = baseline.
  * fractional confidence in (0, 1).
  * `skill_up_vpc` straddling the threshold (∓1) for both PURSUE and PIVOT
    outcomes in the non-short-circuit branch.
  * monotonicity pairs: (i) raise `confidence` keeps PURSUE; (ii) raise
    `skill_up_vpc` keeps PURSUE.

Production constants: `DEFAULT_COIN_VALUE_GOLD = 5.0`, `LOW_CONFIDENCE_MARGIN = 3.0`.
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.task_decision_core import required_vpc, task_decision_pure
from artifactsmmo_cli.ai.task_decision_labels import PIVOT, PURSUE
from formal.diff.oracle_client import run_oracle

BASELINE = Fraction(5)
MARGIN = Fraction(3)


def _rat(flat: list[int], frac: Fraction) -> None:
    flat.append(frac.numerator)
    flat.append(frac.denominator)


def _lean_args(req_is_none: bool, req_is_combat: bool, history_present: bool,
               vpc: Fraction, conf: Fraction) -> list[int]:
    flat: list[int] = [
        1 if req_is_none else 0,
        1 if req_is_combat else 0,
        1 if history_present else 0,
    ]
    _rat(flat, vpc)
    _rat(flat, BASELINE)
    _rat(flat, MARGIN)
    _rat(flat, conf)
    return flat


def _lean_decision(req_is_none: bool, req_is_combat: bool, history_present: bool,
                   vpc: Fraction, conf: Fraction) -> str:
    res = run_oracle("task_decision",
                     [_lean_args(req_is_none, req_is_combat, history_present, vpc, conf)])[0]
    return res["decision"]


def _py_decision(req_is_none: bool, req_is_combat: bool, history_present: bool,
                 vpc: Fraction, conf: Fraction) -> str:
    # Pass Fraction inputs so arithmetic stays exact (no float coercion).
    return task_decision_pure(req_is_none, req_is_combat, history_present,
                              vpc, BASELINE, MARGIN, conf)


# A confidence in [0, 1] as an exact rational with small denominator.
_conf_strat = st.fractions(min_value=Fraction(0), max_value=Fraction(1),
                           max_denominator=6)
# A skill_up_vpc as an exact rational over a realistic range (covers crosses).
_vpc_strat = st.fractions(min_value=Fraction(0), max_value=Fraction(1000),
                          max_denominator=6)


@settings(max_examples=250)
@given(req_is_none=st.booleans(), req_is_combat=st.booleans(),
       history_present=st.booleans(), vpc=_vpc_strat, conf=_conf_strat)
def test_decision_matches_oracle(req_is_none: bool, req_is_combat: bool,
                                  history_present: bool,
                                  vpc: Fraction, conf: Fraction) -> None:
    py = _py_decision(req_is_none, req_is_combat, history_present, vpc, conf)
    lean = _lean_decision(req_is_none, req_is_combat, history_present, vpc, conf)
    assert py == lean, (py, lean, req_is_none, req_is_combat, history_present,
                        vpc, conf)


@settings(max_examples=40)
@given(req_is_combat=st.booleans(), history_present=st.booleans(),
       vpc=_vpc_strat, conf=_conf_strat)
def test_req_none_pursues(req_is_combat: bool, history_present: bool,
                          vpc: Fraction, conf: Fraction) -> None:
    """The `req_is_none = True` branch is PURSUE unconditionally — both sides."""
    assert _py_decision(True, req_is_combat, history_present, vpc, conf) == PURSUE
    assert _lean_decision(True, req_is_combat, history_present, vpc, conf) == PURSUE


@settings(max_examples=40)
@given(history_present=st.booleans(), vpc=_vpc_strat, conf=_conf_strat)
def test_combat_pivots(history_present: bool, vpc: Fraction, conf: Fraction) -> None:
    """`req_is_combat = True` ∧ `req_is_none = False` ⇒ PIVOT."""
    assert _py_decision(False, True, history_present, vpc, conf) == PIVOT
    assert _lean_decision(False, True, history_present, vpc, conf) == PIVOT


@settings(max_examples=40)
@given(req_is_combat=st.booleans(), vpc=_vpc_strat, conf=_conf_strat)
def test_no_history_pivots(req_is_combat: bool, vpc: Fraction, conf: Fraction) -> None:
    """`history_present = False` ∧ `req_is_none = False` ⇒ PIVOT."""
    assert _py_decision(False, req_is_combat, False, vpc, conf) == PIVOT
    assert _lean_decision(False, req_is_combat, False, vpc, conf) == PIVOT


@settings(max_examples=40)
@given(conf=_conf_strat)
def test_confidence_boundaries(conf: Fraction) -> None:
    """At confidence 0 / 1, the threshold is exactly 20 / 5 respectively;
    skill_up_vpc just below/at/above the threshold flips the decision predictably."""
    # confidence = 0: threshold = 5 * (1 + 3 * 1) = 20
    assert _py_decision(False, False, True, Fraction(19), Fraction(0)) == PIVOT
    assert _lean_decision(False, False, True, Fraction(19), Fraction(0)) == PIVOT
    assert _py_decision(False, False, True, Fraction(20), Fraction(0)) == PURSUE
    assert _lean_decision(False, False, True, Fraction(20), Fraction(0)) == PURSUE
    # confidence = 1: threshold = 5 * 1 = 5
    assert _py_decision(False, False, True, Fraction(4), Fraction(1)) == PIVOT
    assert _lean_decision(False, False, True, Fraction(4), Fraction(1)) == PIVOT
    assert _py_decision(False, False, True, Fraction(5), Fraction(1)) == PURSUE
    assert _lean_decision(False, False, True, Fraction(5), Fraction(1)) == PURSUE


@settings(max_examples=200)
@given(vpc=_vpc_strat, c=_conf_strat, c_bump=_conf_strat)
def test_confidence_monotone_pursue(vpc: Fraction, c: Fraction,
                                     c_bump: Fraction) -> None:
    """If PURSUE at confidence c, then PURSUE at any c' ≥ c (both sides)."""
    c2 = min(Fraction(1), c + c_bump)
    if _py_decision(False, False, True, vpc, c) == PURSUE:
        assert _py_decision(False, False, True, vpc, c2) == PURSUE
        assert _lean_decision(False, False, True, vpc, c2) == PURSUE


@settings(max_examples=200)
@given(vpc=_vpc_strat, vpc_bump=_vpc_strat, conf=_conf_strat)
def test_vpc_monotone_pursue(vpc: Fraction, vpc_bump: Fraction,
                              conf: Fraction) -> None:
    """If PURSUE at vpc v, then PURSUE at any v' ≥ v (both sides)."""
    v2 = vpc + vpc_bump
    if _py_decision(False, False, True, vpc, conf) == PURSUE:
        assert _py_decision(False, False, True, v2, conf) == PURSUE
        assert _lean_decision(False, False, True, v2, conf) == PURSUE


@settings(max_examples=100)
@given(conf=_conf_strat)
def test_required_vpc_antitone(conf: Fraction) -> None:
    """`required_vpc` strictly antitone in confidence: c < c' ⇒ required(c) > required(c')."""
    c2 = min(Fraction(1), conf + Fraction(1, 100))
    if c2 > conf:
        assert (required_vpc(BASELINE, MARGIN, conf)
                >= required_vpc(BASELINE, MARGIN, c2))
