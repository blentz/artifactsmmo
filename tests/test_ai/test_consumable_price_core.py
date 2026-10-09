"""The price of one consumable in seconds (`docs/PLAN_consumable_utility.md`
increment 2; proved `Formal.ConsumablePrice`)."""

from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.consumable_price_core import buy_seconds, consumable_price

HALF = Fraction(1, 2)


class TestBuySeconds:
    def test_gold_over_the_rate(self) -> None:
        assert buy_seconds(40, HALF) == 80

    def test_no_seller(self) -> None:
        assert buy_seconds(None, HALF) is None

    @pytest.mark.parametrize("rate", [Fraction(0), Fraction(-1, 3)])
    def test_no_gold_rate_makes_buying_unpriceable(self, rate: Fraction) -> None:
        assert buy_seconds(40, rate) is None


class TestPrice:
    def test_held_is_free_whatever_the_sides(self) -> None:
        assert consumable_price(3, Fraction(90), 40, HALF) == 0
        assert consumable_price(1, None, None, Fraction(0)) == 0

    def test_buy_when_cheaper(self) -> None:
        assert consumable_price(0, Fraction(90), 40, HALF) == 80

    def test_make_when_cheaper(self) -> None:
        assert consumable_price(0, Fraction(60), 40, HALF) == 60

    def test_a_tie_is_the_shared_value(self) -> None:
        assert consumable_price(0, Fraction(80), 40, HALF) == 80

    def test_make_only(self) -> None:
        assert consumable_price(0, Fraction(90), None, HALF) == 90
        assert consumable_price(0, Fraction(90), 40, Fraction(0)) == 90

    def test_buy_only(self) -> None:
        assert consumable_price(0, None, 40, HALF) == 80

    def test_nothing_serves_it(self) -> None:
        assert consumable_price(0, None, None, HALF) is None
        assert consumable_price(0, None, 40, Fraction(0)) is None

    def test_a_negative_held_count_is_not_held(self) -> None:
        assert consumable_price(-1, Fraction(90), None, HALF) == 90

    def test_negative_sides_raise(self) -> None:
        with pytest.raises(ValueError, match="make_seconds"):
            consumable_price(0, Fraction(-1), None, HALF)
        with pytest.raises(ValueError, match="buy_gold"):
            consumable_price(0, None, -1, HALF)
