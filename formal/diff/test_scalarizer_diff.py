"""Differential test: the real Python `scalar_yield_pure` / `coins_spent_from_delta`
must agree with the proved Lean `scalarYield` / `coinsSpent`.

The Lean model works in EXACT RATIONAL arithmetic (`Rat`, no scaling), because the
bot's real `Yield` fields are FRACTIONAL float averages of integer per-cycle deltas
(`projections.py:117-123`, `totals / n`) and `coin_value = total_value /
total_coins_spent` is a fractional ratio. So the scalar the bot actually compares is

    scalar = char_xp * char_scalar * (level + 1)
           + Σ skill_xp[s] * weight(s)
           + gold / gold_per_xp
           + tasks_coins * coin_value / gold_per_xp

over the RATIONALS. We exercise that real fractional domain directly: every numeric
input is an exact `fractions.Fraction` (denominators 1..6, so genuinely non-integer
values appear), and we call `scalar_yield_pure` with `Fraction` weights
(char_scalar = 1, baseline = 1/5, relevant = 2, gold_per_xp = 100) so EVERY operation
inside the core stays exact (a Fraction `*`/`/` is exact; there is no float coercion).
The Lean oracle reconstructs each input as an exact `Rat` from a (numerator,
denominator) pair and emits the scalar's exact numerator/denominator, which we compare
to the Python `Fraction` result EXACTLY. No `<1e-3` slack, no integer-only rejection.

Production still passes the float constants `0.2` etc. to the same generic core; that
behavior is unchanged — only this differential test substitutes exact `Fraction`
weights to verify the rational identity bit-for-bit.

Sign/range reality: char_xp/skill_xp deltas ≥ 0 and tasks_coins ≥ 0 (XP and drop
counts never go negative in this game), gold ranges over NEGATIVES too (a cycle can
spend gold), coin_value ≥ 0 (a ratio of non-negatives; DEFAULT 5 ≥ 0). Zeros and ties
are included. We also assert the proved PROPERTIES hold on the fractional Python side
(monotonicity bumps never decrease the scalar, relevant ≥ baseline) and the
coin-inversion identity (over Int counts).
"""
from fractions import Fraction

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.learning.scalar_core import coins_spent_from_delta, scalar_yield_pure
from formal.diff.oracle_client import run_oracle

# Production constants as EXACT rationals (the core is generic in its weights;
# production passes the float forms 0.2/2.0/100.0/1.0 — same values).
BASELINE_W = Fraction(1, 5)
RELEVANT_W = Fraction(2)
GOLD_PER_XP = Fraction(100)
CHAR_SCALAR = Fraction(1)
DEFAULT_COIN_VALUE = Fraction(5)


def _py_scalar(char_xp, level, skill_terms, active_set, gold, tasks_coins, coin_value):
    """Exact Fraction value of `scalar_yield_pure` (no float coercion anywhere)."""
    skill_xp = {name: Fraction(xp) for name, xp, _active in skill_terms}
    val = scalar_yield_pure(
        Fraction(char_xp), level, skill_xp, active_set,
        Fraction(gold), Fraction(tasks_coins), Fraction(coin_value),
        baseline_w=BASELINE_W, relevant_w=RELEVANT_W,
        gold_per_xp=GOLD_PER_XP, char_scalar=CHAR_SCALAR,
    )
    assert isinstance(val, Fraction), val  # stayed exact, no float crept in
    return val


def _rat(flat, frac):
    """Append a Fraction to the flat oracle arg list as (numerator, denominator)."""
    flat += [frac.numerator, frac.denominator]


def _lean_args(char_xp, level, gold, tasks_coins, coin_value, skill_terms, active_set):
    """Build the flat oracle arg list for kind 'scalarizer' (rational num/den pairs)."""
    flat: list[int] = []
    _rat(flat, Fraction(char_xp))
    _rat(flat, Fraction(level))
    _rat(flat, Fraction(gold))
    _rat(flat, Fraction(tasks_coins))
    _rat(flat, Fraction(coin_value))
    _rat(flat, CHAR_SCALAR)
    _rat(flat, Fraction(1, GOLD_PER_XP))  # goldUnit = 1/gold_per_xp = 1/100
    flat.append(len(skill_terms))
    for name, xp, active in skill_terms:
        w = RELEVANT_W if active else BASELINE_W
        _rat(flat, w)
        _rat(flat, Fraction(xp))
    return flat


def _lean_scalar(*args):
    res = run_oracle("scalarizer", [_lean_args(*args)])[0]
    return Fraction(res["scalar_num"], res["scalar_den"])


# A skill term: (name, xp_delta_fraction, is_active). Names are distinct by index.
# xp deltas are FRACTIONAL averages: numerator 0..50000, denominator 1..6.
_skill_terms = st.lists(
    st.tuples(
        st.fractions(min_value=0, max_value=50_000, max_denominator=6),
        st.booleans(),
    ),
    min_size=0, max_size=5,
).map(lambda lst: [(f"s{i}", xp, active) for i, (xp, active) in enumerate(lst)])

_frac_charxp = st.fractions(min_value=0, max_value=100_000, max_denominator=6)
_frac_gold = st.fractions(min_value=-100_000, max_value=100_000, max_denominator=6)
_frac_tcoins = st.fractions(min_value=0, max_value=10_000, max_denominator=6)
_frac_cv = st.fractions(min_value=0, max_value=1_000, max_denominator=6)
_frac_bump = st.fractions(min_value=0, max_value=10_000, max_denominator=6)


@settings(max_examples=250)
@given(
    char_xp=_frac_charxp,
    level=st.integers(min_value=0, max_value=50),
    gold=_frac_gold,
    tasks_coins=_frac_tcoins,
    coin_value=_frac_cv,
    skill_terms=_skill_terms,
)
def test_python_matches_lean(char_xp, level, gold, tasks_coins, coin_value, skill_terms):
    """EXACT fractional identity: Python Fraction scalar == Lean Rat oracle scalar."""
    active_set = {name for name, _xp, active in skill_terms if active}
    py = _py_scalar(char_xp, level, skill_terms, active_set, gold, tasks_coins, coin_value)
    lean = _lean_scalar(char_xp, level, gold, tasks_coins, coin_value, skill_terms, active_set)
    assert py == lean


@settings(max_examples=200)
@given(
    char_xp=_frac_charxp,
    bump=_frac_bump,
    level=st.integers(min_value=0, max_value=50),
    gold=_frac_gold,
    tasks_coins=_frac_tcoins,
    coin_value=_frac_cv,
    skill_terms=_skill_terms,
)
def test_mono_charxp(char_xp, bump, level, gold, tasks_coins, coin_value, skill_terms):
    active_set = {name for name, _xp, active in skill_terms if active}
    lo = _py_scalar(char_xp, level, skill_terms, active_set, gold, tasks_coins, coin_value)
    hi = _py_scalar(char_xp + bump, level, skill_terms, active_set, gold, tasks_coins, coin_value)
    assert hi >= lo
    # Cross-check both endpoints against the Lean oracle EXACTLY.
    assert _lean_scalar(char_xp, level, gold, tasks_coins, coin_value, skill_terms, active_set) == lo
    assert _lean_scalar(char_xp + bump, level, gold, tasks_coins, coin_value, skill_terms, active_set) == hi


@settings(max_examples=200)
@given(
    gold=_frac_gold,
    bump=_frac_bump,
    tcoins=_frac_tcoins,
    cbump=_frac_bump,
    coin_value=_frac_cv,
)
def test_mono_gold_and_coins(gold, bump, tcoins, cbump, coin_value):
    # gold monotonicity (gold may be negative) over the fractional domain.
    g_lo = _py_scalar(0, 0, [], set(), gold, 0, 0)
    g_hi = _py_scalar(0, 0, [], set(), gold + bump, 0, 0)
    assert g_hi >= g_lo
    # tasks_coins monotonicity (coin_value ≥ 0) over the fractional domain.
    c_lo = _py_scalar(0, 0, [], set(), 0, tcoins, coin_value)
    c_hi = _py_scalar(0, 0, [], set(), 0, tcoins + cbump, coin_value)
    assert c_hi >= c_lo


@settings(max_examples=200)
@given(
    base_xp=st.fractions(min_value=0, max_value=50_000, max_denominator=6),
    bump=st.fractions(min_value=0, max_value=50_000, max_denominator=6),
    active=st.booleans(),
    rest=_skill_terms,
)
def test_mono_skillxp(base_xp, bump, active, rest):
    # one skill term bumped; weight (relevant or baseline) ≥ 0 so score never drops.
    terms_lo = [("focus", base_xp, active), *rest]
    terms_hi = [("focus", base_xp + bump, active), *rest]
    active_lo = {n for n, _x, a in terms_lo if a}
    active_hi = {n for n, _x, a in terms_hi if a}
    lo = _py_scalar(0, 0, terms_lo, active_lo, 0, 0, 0)
    hi = _py_scalar(0, 0, terms_hi, active_hi, 0, 0, 0)
    assert hi >= lo


@settings(max_examples=200)
@given(xp=st.fractions(min_value=0, max_value=50_000, max_denominator=6))
def test_relevant_weight_dominates(xp):
    """One unit of active-skill xp scores >= the same fractional xp at baseline."""
    relevant = _py_scalar(0, 0, [("s0", xp, True)], {"s0"}, 0, 0, 0)
    baseline = _py_scalar(0, 0, [("s0", xp, False)], set(), 0, 0, 0)
    assert relevant >= baseline
    assert relevant == RELEVANT_W * Fraction(xp) and baseline == BASELINE_W * Fraction(xp)


@settings(max_examples=200)
@given(
    received=st.integers(min_value=-1_000, max_value=1_000),
    delta=st.integers(min_value=-1_000, max_value=1_000),
)
def test_coins_spent_inversion(received, delta):
    py = coins_spent_from_delta(received, delta)
    lean = run_oracle("coins_spent", [[received, delta]])[0]
    assert py == lean["coins_spent"]
    # received - coins_spent inverts back to delta (no sign error).
    assert received - py == delta == lean["inverted_delta"]
