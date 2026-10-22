"""select_monster_for_drop (Python) must agree with
Formal.MonsterDropSelection.selectMonsterForDrop (Lean) over hundreds of random
candidate lists.

Each candidate's key is the LEARNED expected kills per unit (ruling T16a):
`1 / drop_chance_core.units_per_attempt(...)` over a random API rate, quantity
range, observed attempts and hits, prospecting slope and prospecting — the very
function every production picker ranks by — so the oracle is asked about the
rationals production computes, not hand-picked ones.

The oracle takes a variable-length candidate list flattened into a single
`args` array `[N, c0,an0,ad0,d0, c1,an1,ad1,d1, ...]` (the same
`[count, ...flat records]` convention `runArbiterSelect` uses), the attempts as
an exact `(num, den)` pair, so the test sends ONE request and reads result `[0]`.

CODE TIE-BREAK FAITHFULNESS (load-bearing): Lean's `Candidate.code` is a `Nat`
and the final lex tie-break compares codes NUMERICALLY; Python's
`MonsterDropCandidate.monster_code` is a `str` and Python tie-breaks codes by STRING
order. For the surrogate to make the two models compute the SAME function, the
code↔string map must be ORDER-PRESERVING (string order ≡ Nat order) — mere 1:1
uniqueness is NOT enough (`"10" < "2"` but `10 > 2`). We zero-pad the surrogate
code to a fixed width so lexicographic string order coincides with numeric order,
and feed the SAME integer code to the oracle. Codes are unique per list so the
tie-break is well-defined.
"""

from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.drop_chance_core import units_per_attempt
from artifactsmmo_cli.ai.monster_drop_selection import MonsterDropCandidate, select_monster_for_drop
from formal.diff.oracle_client import run_oracle


@st.composite
def _attempts(draw: st.DrawFn) -> Fraction:
    """A learned expected-kills per unit: the reciprocal of `units_per_attempt`
    over a random drop row and random evidence."""
    rate = draw(st.integers(min_value=1, max_value=500))
    min_q = draw(st.integers(min_value=1, max_value=10))
    max_q = draw(st.integers(min_value=min_q, max_value=10))
    observed = draw(st.integers(min_value=0, max_value=1000))
    hits = draw(st.integers(min_value=0, max_value=observed))
    k = draw(st.fractions(min_value=0, max_value=1, max_denominator=20))
    prospecting = draw(st.integers(min_value=0, max_value=200))
    return 1 / units_per_attempt(rate, min_q, max_q, observed, hits, k, prospecting)


_cand = st.tuples(
    st.integers(min_value=0, max_value=50),    # code (0..50 -> 2-digit zero-pad)
    st.one_of(_attempts(), st.sampled_from([Fraction(1), Fraction(300), Fraction(683, 3)])),
    st.integers(min_value=0, max_value=99),    # dist
)


def _code_str(code: int) -> str:
    """Zero-padded so string order == numeric order (mirrors Lean's Nat code)."""
    return f"{code:02d}"


def _oracle_args(raw: list[tuple[int, Fraction, int]]) -> list[int]:
    """Flatten candidates into the oracle's `[N, ...4-int records]` arg array."""
    args: list[int] = [len(raw)]
    for c, a, d in raw:
        args.extend([c, a.numerator, a.denominator, d])
    return args


def _select(raw: list[tuple[int, Fraction, int]]) -> tuple[str | None, int]:
    py = select_monster_for_drop("x", [MonsterDropCandidate(_code_str(c), a, d) for c, a, d in raw])
    lean = run_oracle("monster_drop_selection", [_oracle_args(raw)])[0]
    return py, lean["selected"]


@settings(max_examples=400, deadline=None)
@given(raw=st.lists(_cand, min_size=0, max_size=8, unique_by=lambda t: t[0]))
def test_selection_matches_lean(raw):
    py, lean = _select(raw)
    assert lean == (-1 if py is None else int(py))


def test_code_tiebreak_is_numeric_not_list_order():
    """Full (expected kills, distance) tie with the SMALLER code appearing
    LAST in list order. Both models must pick the smaller code (5), NOT the
    first-in-list (9). Pins the code tie-break against a constant-third-field
    regression (where Python `min` would first-win on 9 and diverge)."""
    py, lean = _select([(9, Fraction(1), 0), (5, Fraction(1), 0)])
    assert py == "05"
    assert lean == 5


def test_distance_breaks_an_attempts_tie():
    """Equal expected kills, nearer wins — pins the distance tie-break against a
    dropped-distance regression."""
    py, lean = _select([(1, Fraction(2), 9), (2, Fraction(2), 2)])
    assert py == "02"
    assert lean == 2


def test_observations_flip_the_pick():
    """Two droppers of one item: the 1-in-100 monster beats the 1-in-300 one
    under the prior, and 1,000 wins against it without the drop make it the
    dearer one (1100 vs 300 kills a unit). Both models flip together."""
    rare_prior = 1 / units_per_attempt(100, 1, 1, 0, 0, Fraction(0), 0)
    rare_seen = 1 / units_per_attempt(100, 1, 1, 1000, 0, Fraction(0), 0)
    common = 1 / units_per_attempt(300, 1, 1, 0, 0, Fraction(0), 0)
    assert (rare_prior, rare_seen, common) == (100, 1100, 300)
    assert _select([(1, rare_prior, 5), (2, common, 5)]) == ("01", 1)
    assert _select([(1, rare_seen, 5), (2, common, 5)]) == ("02", 2)
