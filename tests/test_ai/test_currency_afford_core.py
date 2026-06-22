"""Pure core: a currency-buy closure leaf is plannable iff affordable or owned."""
from artifactsmmo_cli.ai.goals.currency_afford_core import currency_afford_plannable_pure


def test_unaffordable_unowned_not_plannable():
    assert currency_afford_plannable_pure(True, False, 0, 1) is False


def test_affordable_is_plannable():
    assert currency_afford_plannable_pure(True, True, 0, 1) is True


def test_already_owned_is_plannable():
    assert currency_afford_plannable_pure(True, False, 1, 1) is True


def test_not_a_currency_leaf_stays_plannable():
    assert currency_afford_plannable_pure(False, False, 0, 1) is True
