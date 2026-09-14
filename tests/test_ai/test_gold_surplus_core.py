"""How much pocket gold is surplus, and how much an imminent expansion holds back.

Gold is per-character; the bank is the account-wide pool. Across 184,010 cycles
the fleet never moved gold between them, so Lor carried 28,016 while Robby
carried 1,672 on one account. This module decides what moves.

THE KEPT REMAINDER IS THE POINT. `GatherMaterialsGoal` admits a deficit-sized
`WithdrawGold` (the GAP-3 ferry, gathering.py:613). Banking everything above the
reserve would leave the pocket at exactly the reserve, so any ferry withdrawal
at all would be banked straight back next cycle — the `Withdraw`/`DepositAll`
oscillation this codebase has already shipped once. Keeping the sub-chunk
remainder is what stops that.

The genuine round trip — the ferry withdraws what a plan needs, the plan
spends it, and the pocket returns to a non-bankable state — is an
INTEGRATION property, not one these unit tests can assert; unspent, the true
bound is the HEADROOM (`GOLD_CHUNK - slack`).
"""

from artifactsmmo_cli.ai.gold_surplus_core import (
    GOLD_CHUNK,
    bankable_gold,
    expansion_hold,
)


def test_chunk_is_ten_thousand():
    assert GOLD_CHUNK == 10_000


def test_below_one_chunk_above_the_reserve_banks_nothing():
    assert bankable_gold(pocket=12_999, reserve=3_000) == 0


def test_exactly_one_chunk_above_the_reserve_banks_one():
    assert bankable_gold(pocket=13_000, reserve=3_000) == 10_000


def test_the_remainder_is_always_kept():
    """Lor's live case: 28,016 pocket, 3,000 reserve -> bank 20,000, keep 8,016."""
    assert bankable_gold(pocket=28_016, reserve=3_000) == 20_000


def test_a_reserve_above_the_pocket_banks_nothing():
    """Saving for something out of reach is a real state, not an error."""
    assert bankable_gold(pocket=500, reserve=9_000) == 0


def test_a_reserve_equal_to_the_pocket_banks_nothing():
    assert bankable_gold(pocket=9_000, reserve=9_000) == 0


def test_banking_never_breaches_the_reserve():
    """The property, not a case: whatever is banked, the reserve survives."""
    for pocket in range(0, 60_001, 997):
        for reserve in (0, 100, 3_000, 9_999, 25_000):
            kept = pocket - bankable_gold(pocket, reserve)
            assert kept >= min(reserve, pocket), (pocket, reserve, kept)


def test_banked_amount_is_always_a_whole_number_of_chunks():
    for pocket in range(0, 60_001, 997):
        assert bankable_gold(pocket, 3_000) % GOLD_CHUNK == 0


def test_no_expansion_hold_below_the_threshold():
    """69 of 100 slots is under 70% — the expansion is not in play yet."""
    assert expansion_hold(bank_used=69, bank_capacity=100,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 0


def test_expansion_holds_the_cost_at_the_threshold():
    assert expansion_hold(bank_used=70, bank_capacity=100,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 3_500


def test_expansion_holds_the_cost_above_the_threshold():
    assert expansion_hold(bank_used=95, bank_capacity=100,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 3_500


def test_unknown_capacity_holds_nothing():
    """Capacity 0 means capacity was never read. UNKNOWN IS NOT FULL."""
    assert expansion_hold(bank_used=70, bank_capacity=0,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 0


def test_the_fill_comparison_is_exact_at_the_boundary():
    """7 of 10 is exactly 70%: an int-truncating comparison would miss it, and a
    float one would be a house-rule violation."""
    assert expansion_hold(bank_used=7, bank_capacity=10,
                          next_expansion_cost=3_500,
                          hold_num=70, hold_den=100) == 3_500
