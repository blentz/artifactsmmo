"""Differential: the production Tier-2 sticky override (`sticky_select_core`) must
compute the SAME function as the kernel-proved Lean `StickySelect.stickyChoose` /
`nextLast`. The Lean side carries the no-zombie theorems (`sticky_requires_progress`,
`no_infinite_sticky_hold`); this binds those proofs to the running code.

Encoding (oracle `sticky_choose`): [n, ratioNum, ratioDen, lastChosen("" = none),
then per candidate: repr, scoreNum, scoreDen]. `next_last`: [hasChosen, repr, progressed].
"""
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.tiers.sticky_select_core import (
    StickyCand,
    next_last,
    sticky_choose,
)
from formal.diff.oracle_client import run_oracle


@st.composite
def _cand_lists(draw):
    n = draw(st.integers(min_value=1, max_value=5))
    cands = []
    for i in range(n):
        num = draw(st.integers(min_value=0, max_value=200))
        den = draw(st.integers(min_value=1, max_value=12))
        cands.append(StickyCand(repr_=f"r{i}", score=Fraction(num, den)))
    return cands


@settings(max_examples=400)
@given(
    cands=_cand_lists(),
    ratio_num=st.integers(min_value=1, max_value=30),
    ratio_den=st.integers(min_value=1, max_value=10),
    last_choice=st.integers(min_value=-1, max_value=5),
)
def test_sticky_choose_matches_oracle(cands, ratio_num, ratio_den, last_choice):
    ratio = Fraction(ratio_num, ratio_den)
    # last_choice: -1 -> none; 0..n-1 -> that candidate's repr; >=n -> a repr not present.
    if last_choice < 0:
        last_chosen = None
    elif last_choice < len(cands):
        last_chosen = cands[last_choice].repr_
    else:
        last_chosen = "absent"
    py = sticky_choose(cands, last_chosen, ratio)
    py_repr = py.repr_ if py is not None else None

    args: list[object] = [len(cands), ratio_num, ratio_den, last_chosen or ""]
    for c in cands:
        args += [c.repr_, c.score.numerator, c.score.denominator]
    oracle = run_oracle("sticky_choose", [args])[0]
    assert oracle == py_repr, (
        f"cands={[(c.repr_, c.score) for c in cands]} last={last_chosen} "
        f"ratio={ratio}: oracle={oracle} python={py_repr}")


@settings(max_examples=100)
@given(
    has_chosen=st.booleans(),
    progressed=st.booleans(),
    repr_idx=st.integers(min_value=0, max_value=3),
)
def test_next_last_matches_oracle(has_chosen, progressed, repr_idx):
    chosen_repr = f"root{repr_idx}" if has_chosen else None
    py = next_last(chosen_repr, progressed)
    args = [1 if has_chosen else 0, chosen_repr or "", 1 if progressed else 0]
    oracle = run_oracle("next_last", [args])[0]
    assert oracle == py, f"chosen={chosen_repr} prog={progressed}: oracle={oracle} py={py}"
