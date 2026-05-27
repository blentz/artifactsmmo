"""Differential test: real Python `SkillXpCurve` must agree with the proved Lean
`SkillXpCurve` defs on the MODELED integer/count/branch outputs.

We compare ONLY the parts the Lean model proves exactly:
* `required_xp(level)` for OBSERVED levels and the two zero-branches (no data /
  no observed level below). The abstracted geometric float estimate (unobserved
  level above an anchor) is OUT OF MODEL SCOPE and NOT compared.
* `confidence` as the exact rational `conf_num / conf_den` (compared via the
  (num, den) pair, i.e. cross-multiplied equality — no float compare).
* `is_confident` (bool).
* `cycles_to_level` BRANCH: 0 (target ≤ current) / inf-sentinel (xp ≤ 0) /
  finite-flag. The finite float quotient itself is NOT compared (abstracted).
* `total_xp_to_reach` over a FULLY-OBSERVED range (where the Python sum is exact
  integer arithmetic with no estimate terms).
* `uses_default`: whether `growth_ratio()` falls back to DEFAULT_GROWTH_RATIO
  (equivalently, fewer than two consecutive observed levels), compared as a bool.
"""
import math
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.learning.skill_xp_curve import DEFAULT_GROWTH_RATIO, SkillXpCurve
from formal.diff.oracle_client import run_oracle


def _encode(observed: dict[int, int], current: int, target: int,
            xp_per_cycle: int, query_level: int) -> list[int]:
    pairs = sorted(observed.items())
    args = [len(pairs)]
    for lvl, xp in pairs:
        args += [lvl, xp]
    args += [current, target, xp_per_cycle, query_level]
    return args


_observed_strat = st.dictionaries(
    keys=st.integers(min_value=1, max_value=15),
    values=st.integers(min_value=0, max_value=500),
    max_size=8,
)


@settings(max_examples=300)
@given(
    observed=_observed_strat,
    current=st.integers(min_value=1, max_value=15),
    span=st.integers(min_value=0, max_value=6),
    xp_per_cycle=st.integers(min_value=-5, max_value=50),
    query_pick=st.integers(min_value=0, max_value=20),
)
def test_python_matches_lean(observed, current, span, xp_per_cycle, query_pick):
    target = current + span
    curve = SkillXpCurve(observed=dict(observed))

    # Choose a query level that lands on the MODELED domain of required_xp:
    # an observed level, or a level with no observed key below it (zero branch).
    # (Never an unobserved-above-anchor level, whose value is the abstracted
    # estimate and out of scope.)
    if observed:
        keys = sorted(observed)
        min_key = keys[0]
        candidates = list(keys) + [min_key - 1, 0]  # observed + below-all (zero)
        query_level = candidates[query_pick % len(candidates)]
        # guard: if query_level not observed, ensure no observed level is below it
        if query_level not in observed and any(k < query_level for k in observed):
            query_level = min_key  # fall back to an observed level
    else:
        query_level = query_pick  # empty observed -> always 0

    lean = run_oracle(
        "skill_xp_curve",
        [_encode(dict(observed), current, target, xp_per_cycle, query_level)],
    )[0]

    # required_xp (modeled domain only)
    assert curve.required_xp(query_level) == lean["required_xp"]

    # confidence as exact rational via (num, den) pair
    levels = list(range(current, target))
    py_num = sum(1 for lvl in levels if lvl in observed)
    py_den = len(levels)
    assert py_num == lean["conf_num"]
    assert py_den == lean["conf_den"]
    # cross-check the real Python `confidence()` float equals the Lean rational
    # conf_num/conf_den exactly (this is what kills a confidence off-by-one).
    py_conf = curve.confidence(current, target)
    if py_den == 0:
        assert py_conf == 1.0
        assert lean["conf_den"] == 0
    else:
        assert Fraction(py_conf).limit_denominator(10**6) == \
            Fraction(lean["conf_num"], lean["conf_den"])

    # is_confident
    assert curve.is_confident(current, target) == lean["is_confident"]

    # cycles branch
    py_cycles = curve.cycles_to_level(current, target, float(xp_per_cycle))
    if target <= current:
        assert py_cycles == 0.0
        assert lean["cycles_branch"] == 0
    elif xp_per_cycle <= 0:
        assert math.isinf(py_cycles)
        assert lean["cycles_branch"] == -1
    else:
        assert math.isfinite(py_cycles)
        assert lean["cycles_branch"] == 1

    # uses_default: growth_ratio falls back to the documented default iff the
    # `ratios` list is empty (fewer than two consecutive observed levels). We
    # replicate the Python guard structurally rather than via float-equality on
    # the mean (a computed mean could coincidentally equal 1.5).
    py_ratios_empty = not [
        lvl for lvl in observed
        if lvl + 1 in observed and observed[lvl] > 0
    ]
    assert py_ratios_empty == lean["uses_default"]
    # when ratios is empty, growth_ratio() must be exactly the default
    if py_ratios_empty:
        assert curve.growth_ratio() == DEFAULT_GROWTH_RATIO

    # total over the gap: only meaningful (exact) when the range is fully
    # observed (every gap level present) -> no estimate terms in the Python sum.
    if all(lvl in observed for lvl in levels):
        assert curve.total_xp_to_reach(current, target) == lean["total"]


def test_fully_observed_total_and_confidence():
    """Deterministic fully-observed range: total is the exact integer sum and
    confidence is 1 (every gap level observed). Pins the exact-sum branch."""
    observed = {3: 30, 4: 40, 5: 55, 6: 70}
    curve = SkillXpCurve(observed=observed)
    lean = run_oracle("skill_xp_curve", [_encode(observed, 3, 7, 10, 3)])[0]
    assert curve.total_xp_to_reach(3, 7) == lean["total"] == 30 + 40 + 55 + 70
    assert curve.is_confident(3, 7) is True
    assert lean["is_confident"] is True
    assert lean["conf_num"] == lean["conf_den"] == 4


def test_uses_default_with_no_consecutive_pair():
    """Non-consecutive observed levels -> growth_ratio falls back to default."""
    observed = {2: 20, 5: 50}  # no (lvl, lvl+1) pair
    curve = SkillXpCurve(observed=observed)
    lean = run_oracle("skill_xp_curve", [_encode(observed, 2, 4, 5, 2)])[0]
    assert curve.growth_ratio() == DEFAULT_GROWTH_RATIO
    assert lean["uses_default"] is True


def test_zero_below_all_observed():
    """A query level below all observed keys returns 0 (no requirement known)."""
    observed = {5: 100, 6: 150}
    curve = SkillXpCurve(observed=observed)
    lean = run_oracle("skill_xp_curve", [_encode(observed, 5, 7, 10, 4)])[0]
    assert curve.required_xp(4) == lean["required_xp"] == 0
