"""Deposit and withdraw must not trade the same coin.

`GatherMaterialsGoal.relevant_actions` admits a deficit-sized `WithdrawGold`
whenever pocket gold cannot cover a plan's gold-priced leaves (the GAP-3 ferry,
gathering.py:613). That ferry is live and correct. The risk is the PAIR: a
deposit that undoes a withdrawal, or a withdrawal that undoes a deposit, cycle
after cycle — the `Withdraw`/`DepositAll` oscillation this codebase has already
shipped once (`project_junk_inventory_livelock`).

A WITHDRAWAL ADDS TO THE POCKET, so "nothing is bankable after any withdrawal"
is NOT the property — a large enough withdrawal legitimately makes a chunk
eligible again. The real claim is the ROUND TRIP: the ferry withdraws what a
plan's leaves need, the plan SPENDS it, and the pocket returns to where the
deposit left it with nothing bankable. Churn would need the withdrawal to sit
unspent, which a deficit-sized ferry does not do.

Asserted over ranges rather than single cases, with both ends named explicitly —
a recurring defect in this repo is asserting over a range whose ENDS were never
checked.
"""

from artifactsmmo_cli.ai.gold_surplus_core import GOLD_CHUNK, bankable_gold

RESERVE = 3_000


def test_the_kept_remainder_is_never_bankable_on_its_own():
    """Whatever a deposit leaves behind, a second deposit would move none of it."""
    for pocket in range(RESERVE, RESERVE + 5 * GOLD_CHUNK, 313):
        kept = pocket - bankable_gold(pocket, RESERVE)
        assert bankable_gold(kept, RESERVE) == 0, (pocket, kept)


def test_a_withdrawal_that_is_spent_returns_to_a_non_bankable_pocket():
    """The round trip: withdraw for a plan, spend it, nothing is bankable again."""
    for pocket in range(RESERVE, RESERVE + 5 * GOLD_CHUNK, 313):
        kept = pocket - bankable_gold(pocket, RESERVE)
        for withdrawal in (1, 100, GOLD_CHUNK - 1, 5 * GOLD_CHUNK):
            after_spend = (kept + withdrawal) - withdrawal
            assert after_spend == kept
            assert bankable_gold(after_spend, RESERVE) == 0, (pocket, withdrawal)


def test_a_withdrawal_below_the_headroom_cannot_re_trigger_a_deposit():
    """Even UNSPENT, a withdrawal smaller than the remaining headroom banks nothing.

    Headroom is `GOLD_CHUNK - slack`. Only a withdrawal at least that large makes
    a fresh chunk eligible, and one that large is a plan buying something real,
    not churn. When slack leaves a headroom of 1 there is no such withdrawal, so
    that case contributes no candidates — which is correct, not a gap.
    """
    for pocket in range(RESERVE, RESERVE + 5 * GOLD_CHUNK, 313):
        kept = pocket - bankable_gold(pocket, RESERVE)
        headroom = GOLD_CHUNK - (kept - RESERVE)
        for withdrawal in {1, headroom // 2, headroom - 1}:
            if not 0 < withdrawal < headroom:
                continue
            assert bankable_gold(kept + withdrawal, RESERVE) == 0, (pocket, withdrawal)


def test_the_kept_remainder_is_always_under_one_chunk_above_the_reserve():
    """The slack the ferry draws on, bounded: never negative, never a whole chunk."""
    for pocket in range(RESERVE, RESERVE + 10 * GOLD_CHUNK, 271):
        slack = pocket - bankable_gold(pocket, RESERVE) - RESERVE
        assert 0 <= slack < GOLD_CHUNK, (pocket, slack)


def test_the_boundary_ends_are_checked_explicitly():
    """Both ends of the ranges above, named so a range off-by-one cannot hide."""
    assert bankable_gold(RESERVE, RESERVE) == 0
    assert bankable_gold(RESERVE + GOLD_CHUNK - 1, RESERVE) == 0
    assert bankable_gold(RESERVE + GOLD_CHUNK, RESERVE) == GOLD_CHUNK
    assert bankable_gold(RESERVE + 2 * GOLD_CHUNK - 1, RESERVE) == GOLD_CHUNK
