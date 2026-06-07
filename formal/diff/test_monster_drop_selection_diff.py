"""select_monster_for_drop (Python) must agree with
Formal.MonsterDropSelection.selectMonsterForDrop (Lean) over hundreds of random
candidate lists.

The oracle takes a variable-length candidate list flattened into a single
`args` array `[N, c0,r0,mn0,mx0,d0, c1,r1,mn1,mx1,d1, ...]` (the same
`[count, ...flat records]` convention `runGatherSelection` uses), so the test
sends ONE request and reads result `[0]`.

CODE TIE-BREAK FAITHFULNESS (load-bearing): Lean's `Candidate.code` is a `Nat`
and the final lex tie-break compares codes NUMERICALLY; Python's
`MonsterDropCandidate.monster_code` is a `str` and Python tie-breaks codes by
STRING order. For the surrogate to make the two models compute the SAME function,
the code↔string map must be ORDER-PRESERVING (string order ≡ Nat order) — mere
1:1 uniqueness is NOT enough (`"10" < "2"` but `10 > 2`). We zero-pad the surrogate
code to a fixed width so lexicographic string order coincides with numeric order,
and feed the SAME integer code to the oracle. Codes are unique per list so the
tie-break is well-defined.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)
from formal.diff.oracle_client import run_oracle

_cand = st.tuples(
    st.integers(min_value=0, max_value=50),    # code (0..50 -> 2-digit zero-pad)
    st.integers(min_value=1, max_value=50),    # rate
    st.integers(min_value=1, max_value=10),    # minQ
    st.integers(min_value=1, max_value=10),    # maxQ (clamped >= minQ below)
    st.integers(min_value=0, max_value=99),    # dist
)


def _code_str(code: int) -> str:
    """Zero-padded so string order == numeric order (mirrors Lean's Nat code)."""
    return f"{code:02d}"


def _oracle_args(raw: list[tuple[int, int, int, int, int]]) -> list[int]:
    """Flatten candidates into the oracle's `[N, ...5-int records]` arg array."""
    args: list[int] = [len(raw)]
    for c, r, mn, mx, d in raw:
        args.extend([c, r, mn, max(mn, mx), d])
    return args


@settings(max_examples=400)
@given(raw=st.lists(_cand, min_size=0, max_size=8, unique_by=lambda t: t[0]))
def test_selection_matches_lean(raw):
    cands = [
        MonsterDropCandidate(_code_str(c), r, mn, max(mn, mx), d)
        for (c, r, mn, mx, d) in raw
    ]
    py = select_monster_for_drop("x", cands)
    lean = run_oracle("monster_drop_selection", [_oracle_args(raw)])[0]
    expected_code = -1 if py is None else int(py)
    assert lean["selected"] == expected_code


def test_code_tiebreak_is_numeric_not_list_order():
    """Full (expected_kills, distance) tie with the SMALLER code appearing
    LAST in list order. Both models must pick the smaller code (5), NOT the
    first-in-list (9). Pins the code tie-break against a constant-third-field
    regression (where Python `min` would first-win on 9 and diverge)."""
    raw = [(9, 1, 1, 1, 0), (5, 1, 1, 1, 0)]
    cands = [MonsterDropCandidate(_code_str(c), r, mn, max(mn, mx), d) for (c, r, mn, mx, d) in raw]
    py = select_monster_for_drop("x", cands)
    lean = run_oracle("monster_drop_selection", [_oracle_args(raw)])[0]
    assert py == "05"
    assert lean["selected"] == 5
    assert lean["selected"] == int(py)


def test_distance_breaks_kills_tie():
    """Equal expected_kills, nearer wins — pins the distance tie-break against a
    dropped-distance regression."""
    raw = [(1, 2, 1, 1, 9), (2, 2, 1, 1, 2)]
    cands = [MonsterDropCandidate(_code_str(c), r, mn, max(mn, mx), d) for (c, r, mn, mx, d) in raw]
    py = select_monster_for_drop("x", cands)
    lean = run_oracle("monster_drop_selection", [_oracle_args(raw)])[0]
    assert py == "02"
    assert lean["selected"] == 2
