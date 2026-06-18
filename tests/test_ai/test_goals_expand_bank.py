"""Tests for ExpandBankGoal.

After the Phase-8b bank-capacity projection fix:
  - `is_satisfied` reads `state.bank_capacity` first (None → game_data fallback).
  - `value` still reads `game_data._bank_capacity` for the cycle-time trigger.

So tests that previously pinned the goal via `game_data=` keep working through
the fallback path, and new tests pin the projection path by setting
`bank_capacity` on the state directly.
"""

from artifactsmmo_cli.ai.actions.bank_expansion import (
    BANK_EXPANSION_SLOTS,
    BuyBankExpansionAction,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from tests.test_ai.fixtures import make_state


def _gd_buyable_armor_and_full_bank() -> GameData:
    """GameData with a near-full bank, cheap expansion, and an expensive buyable gear upgrade.

    Bank: 29/30 (96.7% full, above the 95% trigger).
    Expansion cost: 20 (very cheap).
    iron_armor: level-5 body armor, sold by NPC for 600, no crafting recipe.

    The progression reserve floor is 600 (iron_armor price). With gold=610:
      - old flat reserve (500): 610-20=590 >= 500 → old code FIRES (test RED before fix)
      - reserve_floor=600:       610-20=590  < 600 → new code BLOCKS (test GREEN after fix)
    """
    gd = GameData()
    gd._bank_capacity = 30
    gd._next_expansion_cost = 20
    gd._item_stats = {
        "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
        "rags": ItemStats(code="rags", level=1, type_="body_armor", hp_bonus=5),
    }
    gd._npc_stock = {"merchant": {"iron_armor": 600}}
    gd._monster_level = {"chicken": 1}
    return gd


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

    def test_value_zero_when_buy_would_drain_below_reserve(self):
        """SAFETY-HOLE fix: bank full and gold >= cost but buying drops gold below the
        progression reserve floor, so the goal must NOT fire.
        reserve_floor=500 (iron_armor), gold=520, cost=100 → post-buy 420 < 500."""
        gd = make_gd(bank_capacity=30, next_expansion_cost=100)
        gd._item_stats = {
            "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
            "rags": ItemStats(code="rags", level=1, type_="body_armor", hp_bonus=5),
        }
        gd._npc_stock = {"merchant": {"iron_armor": 500}}
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        state = make_state(
            level=5, gold=520, equipment={"body_armor_slot": "rags"},
            bank_items={f"item_{i}": 1 for i in range(29)},
        )
        assert goal.value(state, gd) == 0.0

    def test_value_40_when_buy_keeps_gold_at_reserve(self):
        """Boundary: post-buy gold exactly equals the progression reserve floor → fires.
        reserve_floor=500 (iron_armor), gold=600, cost=100 → post-buy 500 >= 500."""
        gd = make_gd(bank_capacity=30, next_expansion_cost=100)
        gd._item_stats = {
            "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
            "rags": ItemStats(code="rags", level=1, type_="body_armor", hp_bonus=5),
        }
        gd._npc_stock = {"merchant": {"iron_armor": 500}}
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        state = make_state(
            level=5, gold=600, equipment={"body_armor_slot": "rags"},
            bank_items={f"item_{i}": 1 for i in range(29)},
        )
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
        # state.bank_capacity is the new projection-aware source-of-truth.
        goal = ExpandBankGoal(bank_accessible=True)
        # 20 < 30*0.9 (27) → satisfied
        state = make_state(bank_items={f"item_{i}": 1 for i in range(20)}, bank_capacity=30)
        assert goal.is_satisfied(state) is True

    def test_is_not_satisfied_when_capacity_at_or_above_90pct(self):
        goal = ExpandBankGoal(bank_accessible=True)
        state = make_state(bank_items={f"item_{i}": 1 for i in range(27)}, bank_capacity=30)
        assert goal.is_satisfied(state) is False

    def test_re_triggers_after_expansion_to_larger_bank(self):
        """Regression: a hardcoded `< 27` made the goal report satisfied at
        100% of a post-expansion 60-slot bank. With actual capacity, a bank
        expanded to 60 is unsatisfied at 55 used."""
        goal = ExpandBankGoal(bank_accessible=True)
        state = make_state(bank_items={f"item_{i}": 1 for i in range(55)}, bank_capacity=60)
        assert goal.is_satisfied(state) is False

    def test_value_zero_when_satisfied_even_if_otherwise_triggered(self):
        """Value/is_satisfied consistency — never report urgency when already satisfied."""
        goal = ExpandBankGoal(bank_accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        # Bank at 80% — satisfied (below 90% threshold). is_satisfied falls
        # back to game_data._bank_capacity because state.bank_capacity is None.
        state = make_state(gold=2000, bank_items={f"item_{i}": 1 for i in range(24)})
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_state_capacity_takes_precedence_over_game_data(self):
        """The projection path: state.bank_capacity overrides game_data._bank_capacity.
        Without this, BuyBankExpansionAction.apply could never flip the goal."""
        goal = ExpandBankGoal(bank_accessible=True, game_data=make_gd(bank_capacity=30))
        # 27 fills 30-slot bank to 90% (unsatisfied under game_data) but only
        # 54% of a projected 50-slot bank (satisfied under state).
        state = make_state(bank_items={f"item_{i}": 1 for i in range(27)}, bank_capacity=50)
        assert goal.is_satisfied(state) is True

    def test_projection_chain_flips_goal_satisfied(self):
        """End-to-end: a chain of BuyBankExpansionAction.apply over an
        unsatisfied state reaches the satisfied region. This is the bug-fix
        contract that closes REAL BUG #15."""
        action = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=100)
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        # Bank at 100% fill on a 30-slot bank — unsatisfied.
        state = make_state(
            gold=1000, x=4, y=0,
            bank_items={f"item_{i}": 1 for i in range(30)},
            bank_capacity=30,
        )
        assert goal.is_satisfied(state) is False
        # One expansion mints 20 slots → capacity 50, 30 items = 60% < 90%.
        post = action.apply(state, gd)
        assert post.bank_capacity == 30 + BANK_EXPANSION_SLOTS
        assert goal.is_satisfied(post) is True

    def test_repr(self):
        assert repr(ExpandBankGoal()) == "ExpandBank"

    def test_expand_bank_respects_progression_reserve(self):
        """Bank expansion is WITHHELD when buying it would breach the progression reserve.

        gold=610, expansion cost=20, iron_armor reserve=600.
        Old flat reserve (500): 610-20=590 >= 500 → old code fires.
        Dynamic reserve_floor=600:  610-20=590  < 600 → new code blocks → 0.0.
        """
        gd = _gd_buyable_armor_and_full_bank()
        goal = ExpandBankGoal(bank_accessible=True, game_data=gd)
        state = make_state(
            level=5, gold=610,
            equipment={"body_armor_slot": "rags"},
            bank_items={f"item_{i}": 1 for i in range(29)},
        )
        assert goal.priority(state, gd) == 0.0
