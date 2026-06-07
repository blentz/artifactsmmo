"""select_consumable (Python) must agree with
Formal.ConsumableSelection.selectConsumable (Lean) over hundreds of random
candidate lists + deficits.

The oracle takes `[deficit, N, code0,restore0,qty0, code1,restore1,qty1, ...]`
(deficit first, then the `[count, ...3-int records]` convention), so the test
sends ONE request and reads result `[0]`.

CODE TIE-BREAK FAITHFULNESS (load-bearing): Lean's `Candidate.code` is a `Nat`
and the final lex tie-break compares codes NUMERICALLY; Python's item code is a
`str` and Python tie-breaks codes by STRING order. For the surrogate to make the
two models compute the SAME function, the code↔string map must be ORDER-PRESERVING
(string order ≡ Nat order) — mere 1:1 uniqueness is NOT enough (`"10" < "2"` but
`10 > 2`). We zero-pad the surrogate code to a fixed width so lexicographic string
order coincides with numeric order, and feed the SAME integer code to the oracle.
Codes are unique per list so the final tie-break is well-defined.

USABILITY FILTER: only candidates with `qty > 0` AND `restore > 0` are usable, so
the strategy generates the full grid (including qty<=0 / restore<=0 that BOTH sides
must skip) to exercise the filter end-to-end. The boundary `restore == deficit`
(a fitter, NOT overheal) is included via the restore/deficit ranges overlapping.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.consumable_selection import select_consumable
from artifactsmmo_cli.ai.game_data import ItemStats
from formal.diff.oracle_client import run_oracle

_cand = st.tuples(
    st.integers(min_value=0, max_value=50),    # code (0..50 -> 2-digit zero-pad)
    st.integers(min_value=-5, max_value=120),  # restore (incl. <= 0, must be skipped)
    st.integers(min_value=-2, max_value=5),    # qty (incl. <= 0, must be skipped)
)


def _code_str(code: int) -> str:
    """Zero-padded so string order == numeric order (mirrors Lean's Nat code)."""
    return f"{code:02d}"


def _oracle_args(raw: list[tuple[int, int, int]], deficit: int) -> list[int]:
    """Flatten into the oracle's `[deficit, N, ...3-int records]` arg array."""
    args: list[int] = [deficit, len(raw)]
    for c, r, q in raw:
        args.extend([c, r, q])
    return args


@settings(max_examples=500)
@given(
    raw=st.lists(_cand, min_size=0, max_size=8, unique_by=lambda t: t[0]),
    deficit=st.integers(min_value=0, max_value=120),
)
def test_selection_matches_lean(raw, deficit):
    inventory = {_code_str(c): q for (c, r, q) in raw}
    item_stats = {
        _code_str(c): ItemStats(code=_code_str(c), level=1, type_="consumable", hp_restore=r)
        for (c, r, q) in raw
    }
    py = select_consumable(inventory, item_stats, deficit)
    lean = run_oracle("consumable_selection", [_oracle_args(raw, deficit)])[0]
    expected_code = -1 if py is None else int(py[0])
    assert lean["selected"] == expected_code


def test_prefers_fitter_over_bigger_overhealer():
    """The overheal bug witness: deficit 10, a big 80-restore potion (overheals)
    and a small 30-restore one (still overheals) — both overheal, so the SMALLEST
    overshoot (30) wins, NOT the max-restore (80) the legacy picker chose."""
    raw = [(7, 80, 1), (3, 30, 1)]
    inventory = {_code_str(c): q for (c, r, q) in raw}
    item_stats = {
        _code_str(c): ItemStats(code=_code_str(c), level=1, type_="consumable", hp_restore=r)
        for (c, r, q) in raw
    }
    py = select_consumable(inventory, item_stats, 10)
    lean = run_oracle("consumable_selection", [_oracle_args(raw, 10)])[0]
    assert py == ("03", 30)
    assert lean["selected"] == 3
    assert lean["selected"] == int(py[0])


def test_fitter_beats_overhealer_boundary():
    """restore == deficit is a FITTER (not overheal); it beats a larger overhealer.
    deficit 50: code 09 restore 50 fits exactly, code 02 restore 80 overheals.
    The exact-fit code 09 wins despite the larger code value, pinning the
    overheal-flag dominance over the code tie-break."""
    raw = [(9, 50, 1), (2, 80, 1)]
    inventory = {_code_str(c): q for (c, r, q) in raw}
    item_stats = {
        _code_str(c): ItemStats(code=_code_str(c), level=1, type_="consumable", hp_restore=r)
        for (c, r, q) in raw
    }
    py = select_consumable(inventory, item_stats, 50)
    lean = run_oracle("consumable_selection", [_oracle_args(raw, 50)])[0]
    assert py == ("09", 50)
    assert lean["selected"] == 9
    assert lean["selected"] == int(py[0])
