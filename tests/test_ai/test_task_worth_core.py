"""A task's worth: XP, GOLD (short and the faster source), DROPS (USER
2026-10-07, `docs/PLAN_task_value.md`). Proved model `Formal.TaskWorth`."""

from fractions import Fraction

from artifactsmmo_cli.ai.task_worth_core import (
    WORTHLESS,
    TaskWorth,
    TaskWorthInputs,
    cancel_due,
    dominates,
    draw_owed,
    task_worth,
)


def _inputs(**over) -> TaskWorthInputs:
    base = dict(feasible=True, xp_positive=False, gold_short=False,
                task_gold_rate=Fraction(0), other_gold_rate=Fraction(0), drop_aligned=False)
    return TaskWorthInputs(**{**base, **over})


def test_an_infeasible_task_is_worthless_whatever_its_reasons() -> None:
    inputs = _inputs(feasible=False, xp_positive=True, gold_short=True,
                     task_gold_rate=Fraction(9), drop_aligned=True)
    assert task_worth(inputs) == WORTHLESS


def test_gold_needs_a_shortfall_and_the_faster_source() -> None:
    assert task_worth(_inputs(gold_short=True, task_gold_rate=Fraction(5, 2),
                              other_gold_rate=Fraction(2))).gold
    assert not task_worth(_inputs(gold_short=False, task_gold_rate=Fraction(5))).gold
    assert not task_worth(_inputs(gold_short=True, task_gold_rate=Fraction(2),
                                  other_gold_rate=Fraction(2))).gold


def test_xp_and_drops_alone_are_reasons() -> None:
    assert task_worth(_inputs(xp_positive=True)) == TaskWorth(True, False, False)
    assert task_worth(_inputs(drop_aligned=True)) == TaskWorth(False, False, True)


def test_a_worthless_task_is_cancelled_only_with_a_coin_and_unmet() -> None:
    assert cancel_due(WORTHLESS, coin=True, met=False)
    assert not cancel_due(WORTHLESS, coin=False, met=False)
    assert not cancel_due(WORTHLESS, coin=True, met=True)
    assert not cancel_due(TaskWorth(False, False, True), coin=True, met=False)


def test_a_draw_is_owed_when_the_pool_holds_a_worthy_task() -> None:
    assert draw_owed([WORTHLESS, TaskWorth(False, True, False)])
    assert not draw_owed([WORTHLESS, WORTHLESS])
    assert not draw_owed([])


def test_a_strict_superset_dominates() -> None:
    gold_drops, drops = TaskWorth(False, True, True), TaskWorth(False, False, True)
    assert dominates(gold_drops, drops)
    assert not dominates(drops, gold_drops)
    assert not dominates(drops, drops)
    assert not dominates(TaskWorth(True, False, False), drops)
