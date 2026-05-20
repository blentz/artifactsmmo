"""Tests for ExpandBankGoal."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from tests.test_ai.fixtures import make_state


def make_gd(bank_capacity=30, next_expansion_cost=1000) -> GameData:
    gd = GameData()
    gd._bank_capacity = bank_capacity
    gd._next_expansion_cost = next_expansion_cost
    return gd


class TestExpandBankGoal:
    def test_value_zero_when_bank_under_threshold(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        # 20/30 = 0.67, below 0.95
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(20)})
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_insufficient_gold(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=5000)
        state = make_state(gold=100, bank_items={f"item_{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 0.0

    def test_value_40_when_full_and_can_afford(self):
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 40.0

    def test_value_zero_when_bank_unknown(self):
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd()
        state = make_state(gold=2000, bank_items=None)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_inaccessible(self):
        goal = ExpandBankGoal(bank_accessible=False)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(29)})
        assert goal.value(state, gd) == 0.0

    def test_is_satisfied_when_bank_unknown(self):
        """If we haven't fetched bank items, treat as satisfied (no urgency)."""
        goal = ExpandBankGoal(bank_accessible=True)
        state = make_state(bank_items=None)
        assert goal.is_satisfied(state) is True

    def test_is_satisfied_when_capacity_used_below_90pct(self):
        goal = ExpandBankGoal(bank_accessible=True, game_data=make_gd(bank_capacity=30))
        # 20 < 30*0.9 (27) → satisfied
        state = make_state(bank_items={f"item_{i}": 1 for i in range(20)})
        assert goal.is_satisfied(state) is True

    def test_is_not_satisfied_when_capacity_at_or_above_90pct(self):
        goal = ExpandBankGoal(bank_accessible=True, game_data=make_gd(bank_capacity=30))
        state = make_state(bank_items={f"item_{i}": 1 for i in range(27)})
        assert goal.is_satisfied(state) is False

    def test_re_triggers_after_expansion_to_larger_bank(self):
        """Regression: a hardcoded `< 27` made the goal report satisfied at
        100% of a post-expansion 60-slot bank. With actual capacity, a bank
        expanded to 60 is unsatisfied at 55 used."""
        goal = ExpandBankGoal(bank_accessible=True, game_data=make_gd(bank_capacity=60))
        state = make_state(bank_items={f"item_{i}": 1 for i in range(55)})
        assert goal.is_satisfied(state) is False

    def test_value_zero_when_satisfied_even_if_otherwise_triggered(self):
        """Value/is_satisfied consistency — never report urgency when already satisfied."""
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        # Bank at 80% — satisfied (below 90% threshold)
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(24)})
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_repr(self):
        assert repr(ExpandBankGoal()) == "ExpandBank"
