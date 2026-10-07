"""Differential test: the live task worth (`ai/task_worth_core`) must agree with
the proved `Formal.TaskWorth.worth` / `cancelDue` on random inputs, gold rates
included (Fractions, compared in Lean by cross-multiplication)."""
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.task_worth_core import TaskWorthInputs, cancel_due, draw_due, task_worth
from formal.diff.oracle_client import run_oracle

_rate = st.builds(Fraction, st.integers(min_value=0, max_value=500),
                  st.integers(min_value=1, max_value=60))


@settings(max_examples=500, deadline=None)
@given(feasible=st.booleans(), xp=st.booleans(), short=st.booleans(),
       task=_rate, other=_rate, drops=st.booleans(), coin=st.booleans(), met=st.booleans())
def test_task_worth_matches_lean(feasible, xp, short, task, other, drops, coin, met):
    inputs = TaskWorthInputs(feasible=feasible, xp_positive=xp, gold_short=short,
                             task_gold_rate=task, other_gold_rate=other, drop_aligned=drops)
    worth = task_worth(inputs)
    args = [int(feasible), int(xp), int(short), task.numerator, task.denominator,
            other.numerator, other.denominator, int(drops), int(coin), int(met)]
    lean = run_oracle("task_worth", [args])[0]
    assert (lean["xp"], lean["gold"], lean["drops"]) == (worth.xp, worth.gold, worth.drops), args
    assert lean["cancel"] == cancel_due(worth, coin, met), args


def test_equal_rates_are_not_faster():
    """The boundary: task gold exactly as fast as other gold is no GOLD reason."""
    rate = Fraction(7, 3)
    inputs = TaskWorthInputs(True, False, True, rate, rate, False)
    assert not task_worth(inputs).gold
    lean = run_oracle("task_worth", [[1, 0, 1, 7, 3, 7, 3, 0, 1, 0]])[0]
    assert lean["gold"] is False and lean["cancel"] is True


@settings(max_examples=500, deadline=None)
@given(size=st.integers(min_value=0, max_value=40), data=st.data(),
       reward=st.integers(min_value=0, max_value=10))
def test_draw_due_matches_lean(size, data, reward):
    worthy = data.draw(st.integers(min_value=0, max_value=size))
    lean = run_oracle("task_draw_due", [[worthy, size, reward]])[0]
    assert lean["due"] == draw_due(worthy, size, reward), (worthy, size, reward)


def test_the_live_pools_owe_a_draw():
    """2026-10-07, level 30-32: 9/21 and 7/21 worthy, 4 coins a completion."""
    assert draw_due(9, 21, 4) and draw_due(7, 21, 4)
    assert run_oracle("task_draw_due", [[7, 21, 4]])[0]["due"] is True
    assert not draw_due(4, 21, 4)  # 17 rerolls > 4 * 4
