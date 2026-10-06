"""Differential test: the live turn order (`intention_progress.rotate`, then the
first plannable goal, which is what `select_pure` walks to) must pick EXACTLY
what the proved `Formal.TurnRotation.pick` picks, over random step/fallback
groups, turn logs and plannable sets — and over the turn logs `record_turn`
itself produces, turn after turn.

The Lean model numbers the group's candidates by walk position and reads a
never-served goal's turn as 0; the live log omits it. Served turns are compared
as they are: `record_turn` writes strictly increasing positive integers.
"""
from unittest.mock import MagicMock

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.arbiter_select import BAND_FALLBACK_STEP, BAND_STEP, Candidate
from artifactsmmo_cli.ai.intention_progress import record_turn, rotate
from formal.diff.oracle_client import run_oracle


def _group(n: int, step_first: bool) -> list[Candidate]:
    return [Candidate(goal=MagicMock(), repr_=f"G{i}",
                      band=BAND_STEP if (i == 0 and step_first) else BAND_FALLBACK_STEP)
            for i in range(n)]


def _python_pick(cands: list[Candidate], turns: dict[str, int],
                 plannable: list[bool]) -> int:
    position = {c.repr_: i for i, c in enumerate(cands)}
    for c in rotate(cands, turns):
        if plannable[position[c.repr_]]:
            return position[c.repr_]
    return -1


def _lean_pick(n: int, turns: dict[str, int], plannable: list[bool]) -> int:
    args = [n, *(turns.get(f"G{i}", 0) for i in range(n)), *(int(b) for b in plannable)]
    return run_oracle("turn_rotation_pick", [args])[0]["pick"]


@st.composite
def _cases(draw):  # type: ignore[no-untyped-def]
    n = draw(st.integers(min_value=0, max_value=8))
    served = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    order = draw(st.permutations(list(range(n))))
    turn_of = {i: rank + 1 for rank, i in enumerate(order)}
    turns = {f"G{i}": turn_of[i] * 3 for i in range(n) if served[i]}
    plannable = draw(st.lists(st.booleans(), min_size=n, max_size=n))
    return n, turns, plannable, draw(st.booleans())


@settings(max_examples=400, deadline=None)
@given(_cases())
def test_rotate_picks_what_lean_picks(case):
    n, turns, plannable, step_first = case
    cands = _group(n, step_first)
    assert _python_pick(cands, turns, plannable) == _lean_pick(n, turns, plannable), case


@settings(max_examples=100, deadline=None)
@given(n=st.integers(min_value=1, max_value=6),
       plannable=st.lists(st.booleans(), min_size=6, max_size=6),
       rounds=st.integers(min_value=1, max_value=14))
def test_record_turn_sequences_stay_in_lockstep(n, plannable, rounds):
    """Each turn the picked goal spends its budget (`record_turn`); the two
    sides must agree on every pick along the way, and every plannable goal
    must be picked within n turns of the first (`rotation_fair_bound`)."""
    plannable = plannable[:n]
    cands = _group(n, step_first=True)
    turns: dict[str, int] = {}
    picked: list[int] = []
    for _ in range(rounds):
        got = _python_pick(cands, turns, plannable)
        assert got == _lean_pick(n, turns, plannable), (turns, plannable)
        if got < 0:
            break
        picked.append(got)
        turns = record_turn(turns, f"G{got}")
    if picked and rounds >= n:
        assert {i for i in range(n) if plannable[i]} <= set(picked[:n])


def test_the_live_defect_shape():
    """Two of four served (A at 1, B at 2): the third is picked, where the
    one-goal yield returned A."""
    turns = {"G0": 1, "G1": 2}
    assert _lean_pick(4, turns, [True] * 4) == 2
    assert _python_pick(_group(4, True), turns, [True] * 4) == 2
