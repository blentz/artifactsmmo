"""Tests for the pure should_expand_bank firing decision.

The function is the differential target proved in
formal/Formal/BankExpansionTiming.lean. These tests pin both gates (fill
threshold via exact cross-multiply, reserve safety) and their interaction.
"""

from artifactsmmo_cli.ai.bank_expansion_timing import (
    HOLD_FILL_DEN,
    HOLD_FILL_NUM,
    TRIGGER_FILL_DEN,
    TRIGGER_FILL_NUM,
    expansion_fires,
    should_expand_bank,
)
from artifactsmmo_cli.ai.goals.expand_bank import _SATISFIED_FILL


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


class TestExpansionFires:
    """`expansion_fires` composes the proven core with the pocket-executability
    conjunct the core deliberately does not carry.

    The reserve is an ACCOUNT floor (`progression_reserve.can_spend`: "one
    reserve governs"), so the core's `gold - cost >= reserve` gate must be fed
    the account balance. Executability — the gold being in the POCKET, where the
    buy_expansion endpoint spends it — is the caller's question, and there is no
    withdraw-gold edge in the action pool, so firing on an account the pocket
    cannot draw from would emit a rung no plan can serve.
    """

    def test_fires_when_pocket_pays_and_account_holds_the_reserve(self):
        """Live Robby 2026-09-12: bank 50/50, cost 3500, pocket 3797, bank 12553,
        reserve 5100. Pocket-only reads 3797-3500=297 < 5100 and refuses; the
        account holds 16350, so the buy is reserve-safe and must fire."""
        assert expansion_fires(50, 50, 3797, 16350, 3500, 5100, 95, 100) is True

    def test_no_fire_when_pocket_cannot_pay_the_cost(self):
        """Account is reserve-safe but the pocket is short. No withdraw-gold edge
        exists, so firing here would be a rung the planner cannot serve."""
        assert expansion_fires(50, 50, 100, 20100, 3500, 0, 95, 100) is False

    def test_no_fire_when_account_falls_below_the_reserve(self):
        """The core's reserve gate still governs — on the account balance."""
        assert expansion_fires(50, 50, 3797, 3797, 3500, 5100, 95, 100) is False

    def test_no_fire_below_fill_threshold_even_when_funded(self):
        assert expansion_fires(10, 50, 3797, 16350, 3500, 0, 95, 100) is False

    def test_pocket_exactly_covering_the_cost_fires(self):
        """Boundary: `pocket >= cost`, so an exact match is executable."""
        assert expansion_fires(50, 50, 3500, 16350, 3500, 5100, 95, 100) is True


def test_hold_threshold_sits_below_the_expansion_trigger():
    """The hold must start BEFORE the expansion wants to fire, or the price is
    still being banked when `expansion_fires` asks for it."""
    assert HOLD_FILL_NUM * TRIGGER_FILL_DEN < TRIGGER_FILL_NUM * HOLD_FILL_DEN


def test_hold_threshold_equals_the_goal_satisfaction_mark():
    """One fill ratio, two roles: ExpandBankGoal stops WANTING to expand below
    it, and the deposit stops banking the price above it. If they drift, a
    character can be unsatisfied-and-unfunded in the gap between them."""
    assert HOLD_FILL_NUM / HOLD_FILL_DEN == _SATISFIED_FILL
