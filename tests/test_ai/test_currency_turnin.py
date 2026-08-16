"""When does the fleet have enough of a currency to buy the upgrade?"""
import pytest

from artifactsmmo_cli.ai.currency_turnin import (
    fleet_total_pure,
    turn_in_ready_pure,
)


def test_fleet_total_adds_own_siblings_and_bank():
    assert fleet_total_pure({"m": 3}, {"m": 5}, {"m": 2}, "m") == 10


def test_fleet_total_is_zero_for_an_unheld_code():
    assert fleet_total_pure({"m": 3}, {"m": 5}, {"m": 2}, "other") == 0


@pytest.mark.parametrize("total,ready", [(9, False), (10, True), (11, True)])
def test_readiness_is_at_or_above_the_price(total, ready):
    assert turn_in_ready_pure(total, price=10) is ready


def test_readiness_is_false_for_a_priceless_item():
    """A zero price means the catalog never gave us one; buying on that would
    be inventing game data."""
    assert turn_in_ready_pure(10, price=0) is False
