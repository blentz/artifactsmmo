"""The fight loop's recovery and XP rate (`docs/PLAN_consumable_utility.md`
increments 3-4; proved `Formal.LoopRate`)."""

from fractions import Fraction
from itertools import product

import pytest

from artifactsmmo_cli.ai.loop_rate_core import (
    _recovery_table,
    consumed_seconds,
    count_bound,
    eat_cost,
    food_bound,
    potion_cost,
    recovery_choice,
    recovery_seconds,
    rest_part,
    xp_per_second,
)

EAT = Fraction(3)


class TestParts:
    def test_rest_part(self) -> None:
        assert rest_part(0, 100) == 0
        assert rest_part(-5, 100) == 0
        assert rest_part(1, 100) == 3     # the three-second floor
        assert rest_part(60, 100) == 60
        assert rest_part(250, 100) == 100  # a Rest restores at most one bar

    def test_count_bound_is_the_ceiling(self) -> None:
        assert count_bound(0, 50) == 0
        assert count_bound(50, 50) == 1
        assert count_bound(51, 50) == 2


class TestRecovery:
    def test_no_food_is_resting(self) -> None:
        assert recovery_seconds(60, 100, [], EAT) == 60

    def test_nothing_missing_costs_nothing(self) -> None:
        assert recovery_seconds(0, 100, [(50, Fraction(0), 0)], EAT) == 0
        assert recovery_seconds(-3, 100, [], EAT) == 0

    def test_free_food_is_one_flat_use(self) -> None:
        # Two 50-HP foods in ONE use (the cooldown is flat whatever the quantity).
        assert recovery_seconds(60, 100, [(50, Fraction(0), 0)], EAT) == 3

    def test_a_dear_food_is_eaten_only_while_it_beats_resting(self) -> None:
        # one unit (3 + 40) then rest 10 HP (10 s) = 53 < 60
        assert recovery_seconds(60, 100, [(50, Fraction(40), 0)], EAT) == 53
        # at 60 s a unit it never pays: rest
        assert recovery_seconds(60, 100, [(50, Fraction(60), 0)], EAT) == 60

    def test_two_foods_combine(self) -> None:
        # 90 missing. A 2-s 20-HP food alone: five in one use, 3 + 10 = 13. A
        # 1/2-s 10-HP food: nine in one use, 3 + 9/2 = 15/2, the minimum.
        foods = [(20, Fraction(2), 0), (10, Fraction(1, 2), 0)]
        assert recovery_seconds(90, 100, foods, EAT) == Fraction(15, 2)
        assert recovery_seconds(90, 100, foods[:1], EAT) == 13

    def test_equals_brute_force_over_count_vectors(self) -> None:
        foods = [(20, Fraction(7), 0), (35, Fraction(11, 2), 0), (8, Fraction(1), 0)]
        for missing in range(0, 101, 9):
            best = Fraction(rest_part(missing, 100))
            for counts in product(range(14), range(4), range(14)):
                eaten = sum(k * r for k, (r, _, _) in zip(counts, foods, strict=True))
                cost = sum((EAT + k * p) if k else Fraction(0)
                           for k, (_, p, _) in zip(counts, foods, strict=True))
                best = min(best, cost + rest_part(max(0, missing - eaten), 100))
            assert recovery_seconds(missing, 100, foods, EAT) == best, missing

    def test_never_worse_than_resting(self) -> None:
        for missing in range(0, 120, 7):
            rest = rest_part(missing, 100)
            assert recovery_seconds(missing, 100, [(15, Fraction(9), 0)], EAT) <= rest

    def test_more_missing_never_recovers_faster(self) -> None:
        foods = [(15, Fraction(9), 0), (40, Fraction(30), 0)]
        values = [recovery_seconds(m, 100, foods, EAT) for m in range(0, 110)]
        assert values == sorted(values)

    @pytest.mark.parametrize("args, match", [
        ((10, 0, [], EAT), "max_hp"),
        ((10, 100, [], Fraction(-1)), "eat_seconds"),
        ((10, 100, [(0, Fraction(0), 0)], EAT), "restore"),
        ((10, 100, [(5, Fraction(-1), 0)], EAT), "restore"),
        ((10, 100, [(5, Fraction(1), -1)], EAT), "held"),
    ])
    def test_invalid_inputs_raise(self, args: tuple, match: str) -> None:  # type: ignore[type-arg]
        with pytest.raises(ValueError, match=match):
            recovery_seconds(*args)


class TestHeld:
    def test_food_bound(self) -> None:
        assert food_bound(90, 20, Fraction(1), 2) == 5      # priced: ⌈90/20⌉
        assert food_bound(90, 20, None, 2) == 2             # no replacement: the held two
        assert food_bound(90, 20, None, 9) == 5

    def test_eat_cost(self) -> None:
        assert eat_cost(0, EAT, Fraction(7), 0) == 0
        assert eat_cost(3, EAT, Fraction(7), 0) == 3 + 21
        assert eat_cost(3, EAT, Fraction(7), 2) == 3 + 7    # two held, one bought
        assert eat_cost(3, EAT, Fraction(7), 5) == 3
        assert eat_cost(2, EAT, None, 5) == 3

    def test_held_units_are_free_then_priced(self) -> None:
        # 60 s a unit never pays (Rest 60 s) — but two held 50-HP units are free.
        assert recovery_seconds(60, 100, [(50, Fraction(60), 2)], EAT) == 3
        # One held: eat it free (3 s) and rest the other 10 HP (10 s).
        assert recovery_seconds(60, 100, [(50, Fraction(60), 1)], EAT) == 13
        # One held, 5 s past it: two in one use (3 + 5) beats resting 10 HP.
        assert recovery_choice(60, 100, [(50, Fraction(5), 1)], EAT) == (8, (2,))

    def test_no_replacement_caps_at_held(self) -> None:
        assert recovery_choice(60, 100, [(50, None, 1)], EAT) == (13, (1,))
        assert recovery_choice(60, 100, [(50, None, 0)], EAT) == (60, (0,))

    def test_more_held_never_slows_recovery(self) -> None:
        for held in range(0, 6):
            for missing in range(0, 101, 13):
                more = recovery_seconds(missing, 100, [(20, Fraction(9), held + 1)], EAT)
                assert more <= recovery_seconds(missing, 100, [(20, Fraction(9), held)], EAT)

    def test_the_choice_eats_the_fewest_units_among_the_cheapest(self) -> None:
        # Both free and held: one 400-HP unit covers what four 100-HP units do,
        # in the same one use (3 s) — the choice eats one, whatever the order.
        foods = [(100, Fraction(0), 9), (400, Fraction(0), 9)]
        assert recovery_choice(350, 1000, foods, EAT) == (3, (0, 1))
        assert recovery_choice(350, 1000, foods[::-1], EAT) == (3, (1, 0))

    def test_a_full_tie_keeps_the_fewer_of_the_earlier_food(self) -> None:
        foods = [(50, Fraction(0), 9), (50, Fraction(0), 9)]
        assert recovery_choice(50, 100, foods, EAT) == (3, (0, 1))

    def test_the_choice_costs_its_value(self) -> None:
        foods = [(20, Fraction(7), 1), (35, Fraction(11, 2), 0), (8, None, 3)]
        for missing in range(0, 101, 7):
            value, counts = recovery_choice(missing, 100, foods, EAT)
            eaten = sum(k * r for k, (r, _, _) in zip(counts, foods, strict=True))
            cost = sum(eat_cost(k, EAT, p, h) for k, (_, p, h) in zip(counts, foods, strict=True))
            assert value == cost + rest_part(max(0, missing - eaten), 100), missing
            assert counts[2] <= 3


class TestConsumed:
    def test_potion_cost(self) -> None:
        assert potion_cost(5, Fraction(7), 3) == 14
        assert potion_cost(2, Fraction(7), 3) == 0
        assert potion_cost(2, None, 3) == 0
        assert potion_cost(4, None, 3) is None

    def test_consumed_seconds(self) -> None:
        assert consumed_seconds([]) == 0
        assert consumed_seconds([(5, Fraction(7), 3), (1, Fraction(2), 0)]) == 16
        assert consumed_seconds([(5, Fraction(7), 3), (6, None, 5)]) is None

    @pytest.mark.parametrize("potion", [(-1, Fraction(1), 0), (1, Fraction(1), -1),
                                        (1, Fraction(-1), 0)])
    def test_invalid_potions_raise(self, potion: tuple[int, Fraction, int]) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            consumed_seconds([potion])


class TestXpPerSecond:
    def test_rate(self) -> None:
        assert xp_per_second(30, Fraction(30), Fraction(60), Fraction(0)) == Fraction(1, 3)

    def test_no_xp_no_rate(self) -> None:
        assert xp_per_second(0, Fraction(30), Fraction(60), Fraction(5)) == 0

    def test_longer_is_slower(self) -> None:
        base = xp_per_second(30, Fraction(30), Fraction(10), Fraction(0))
        assert xp_per_second(30, Fraction(31), Fraction(10), Fraction(0)) < base
        assert xp_per_second(30, Fraction(30), Fraction(11), Fraction(0)) < base
        assert xp_per_second(30, Fraction(30), Fraction(10), Fraction(1)) < base

    @pytest.mark.parametrize("args, match", [
        ((30, Fraction(0), Fraction(0), Fraction(0)), "fight_seconds"),
        ((-1, Fraction(30), Fraction(0), Fraction(0)), "non-negative"),
        ((30, Fraction(30), Fraction(-1), Fraction(0)), "non-negative"),
        ((30, Fraction(30), Fraction(0), Fraction(-1)), "non-negative"),
    ])
    def test_invalid_inputs_raise(self, args: tuple, match: str) -> None:  # type: ignore[type-arg]
        with pytest.raises(ValueError, match=match):
            xp_per_second(*args)


def test_one_table_answers_every_query_on_the_same_menu() -> None:
    """The programme's entries depend on the menu, never on the HP a query
    starts from, so a band's loadouts and monsters share one table: the second
    query on the same menu builds no new table and answers exactly what a fresh
    table answers."""
    menu = ((30, Fraction(7), 2), (75, Fraction(40), 0), (12, None, 3))
    _recovery_table.cache_clear()
    first = recovery_choice(140, 300, menu, EAT)
    shared = recovery_choice(95, 300, list(menu), EAT)
    assert _recovery_table.cache_info().currsize == 1
    _recovery_table.cache_clear()
    assert recovery_choice(95, 300, menu, EAT) == shared
    assert recovery_choice(140, 300, menu, EAT) == first
    assert _recovery_table.cache_info().currsize == 1
