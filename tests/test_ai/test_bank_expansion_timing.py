"""Tests for the pure should_expand_bank firing decision.

The function is the differential target proved in
formal/Formal/BankExpansionTiming.lean. These tests pin both gates (fill
threshold via exact cross-multiply, reserve safety) and their interaction.
"""

from artifactsmmo_cli.ai.bank_expansion_timing import should_expand_bank


class TestShouldExpandBank:
    def test_fires_when_full_and_affordable_above_reserve(self):
        # concrete true-witness: 95/100 fill threshold, 96/100 used, gold-cost above reserve
        assert should_expand_bank(96, 100, 600, 50, 500, 95, 100) is True

    def test_no_fire_below_threshold(self):
        # 90/100 used < 95% threshold even though affordable above reserve
        assert should_expand_bank(90, 100, 600, 50, 500, 95, 100) is False

    def test_no_fire_when_unaffordable_below_reserve(self):
        # at threshold but gold-cost = 540 < 550 reserve
        assert should_expand_bank(96, 100, 600, 60, 550, 95, 100) is False

    def test_exact_threshold_boundary_fires(self):
        # used*den == cap*num exactly (95*100 == 100*95): >= so it fires
        assert should_expand_bank(95, 100, 600, 50, 500, 95, 100) is True

    def test_exact_reserve_boundary_fires(self):
        # gold-cost == reserve exactly (600-100 == 500): >= so it fires
        assert should_expand_bank(96, 100, 600, 100, 500, 95, 100) is True

    def test_one_below_reserve_boundary_no_fire(self):
        # gold-cost == 499 < 500 reserve
        assert should_expand_bank(96, 100, 600, 101, 500, 95, 100) is False

    def test_zero_reserve_only_requires_nonnegative_gold(self):
        # reserve=0: gold-cost=550 >= 0
        assert should_expand_bank(96, 100, 600, 50, 0, 95, 100) is True

    def test_cross_multiply_is_exact_not_float(self):
        # 2/3 used vs 95/100 threshold: 2*100=200 < 3*95=285 -> below threshold.
        # A float 0.666... < 0.95 agrees here, but the integer form is exact.
        assert should_expand_bank(2, 3, 600, 50, 500, 95, 100) is False
        # 96/100 vs 95/100: 96*100=9600 >= 100*95=9500 -> at/above.
        assert should_expand_bank(96, 100, 600, 50, 500, 95, 100) is True

    def test_both_gates_must_hold(self):
        # below threshold AND below reserve -> False
        assert should_expand_bank(10, 100, 100, 60, 500, 95, 100) is False
