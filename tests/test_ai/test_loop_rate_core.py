"""The fight loop's recovery and XP rate (`docs/PLAN_consumable_utility.md`
increment 3; proved `Formal.LoopRate`)."""

from fractions import Fraction
from itertools import product

import pytest

from artifactsmmo_cli.ai.loop_rate_core import count_bound, recovery_seconds, rest_part, xp_per_second

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
        assert recovery_seconds(0, 100, [(50, Fraction(0))], EAT) == 0
        assert recovery_seconds(-3, 100, [], EAT) == 0

    def test_free_food_is_one_flat_use(self) -> None:
        # Two 50-HP foods in ONE use (the cooldown is flat whatever the quantity).
        assert recovery_seconds(60, 100, [(50, Fraction(0))], EAT) == 3

    def test_a_dear_food_is_eaten_only_while_it_beats_resting(self) -> None:
        # one unit (3 + 40) then rest 10 HP (10 s) = 53 < 60
        assert recovery_seconds(60, 100, [(50, Fraction(40))], EAT) == 53
        # at 60 s a unit it never pays: rest
        assert recovery_seconds(60, 100, [(50, Fraction(60))], EAT) == 60

    def test_two_foods_combine(self) -> None:
        # 90 missing. A 2-s 20-HP food alone: five in one use, 3 + 10 = 13. A
        # 1/2-s 10-HP food: nine in one use, 3 + 9/2 = 15/2, the minimum.
        foods = [(20, Fraction(2)), (10, Fraction(1, 2))]
        assert recovery_seconds(90, 100, foods, EAT) == Fraction(15, 2)
        assert recovery_seconds(90, 100, foods[:1], EAT) == 13

    def test_equals_brute_force_over_count_vectors(self) -> None:
        foods = [(20, Fraction(7)), (35, Fraction(11, 2)), (8, Fraction(1))]
        for missing in range(0, 101, 9):
            best = Fraction(rest_part(missing, 100))
            for counts in product(range(14), range(4), range(14)):
                eaten = sum(k * r for k, (r, _) in zip(counts, foods, strict=True))
                cost = sum((EAT + k * p) if k else Fraction(0)
                           for k, (_, p) in zip(counts, foods, strict=True))
                best = min(best, cost + rest_part(max(0, missing - eaten), 100))
            assert recovery_seconds(missing, 100, foods, EAT) == best, missing

    def test_never_worse_than_resting(self) -> None:
        for missing in range(0, 120, 7):
            rest = rest_part(missing, 100)
            assert recovery_seconds(missing, 100, [(15, Fraction(9))], EAT) <= rest

    def test_more_missing_never_recovers_faster(self) -> None:
        foods = [(15, Fraction(9)), (40, Fraction(30))]
        values = [recovery_seconds(m, 100, foods, EAT) for m in range(0, 110)]
        assert values == sorted(values)

    @pytest.mark.parametrize("args, match", [
        ((10, 0, [], EAT), "max_hp"),
        ((10, 100, [], Fraction(-1)), "eat_seconds"),
        ((10, 100, [(0, Fraction(0))], EAT), "restore"),
        ((10, 100, [(5, Fraction(-1))], EAT), "restore"),
    ])
    def test_invalid_inputs_raise(self, args: tuple, match: str) -> None:  # type: ignore[type-arg]
        with pytest.raises(ValueError, match=match):
            recovery_seconds(*args)


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
