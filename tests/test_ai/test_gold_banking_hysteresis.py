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
    """Whatever a deposit leaves behind, a second deposit would move none of it.

    Asserts BOTH sides: `kept >= RESERVE` catches over-banking, which the
    `bankable_gold(kept, ...) == 0` assertion alone cannot — `max(0, ...)` clamps
    a negative remainder back to zero and the bug passes.
    """
    for pocket in range(RESERVE, RESERVE + 5 * GOLD_CHUNK, 313):
        kept = pocket - bankable_gold(pocket, RESERVE)
        assert kept >= RESERVE, (pocket, kept)
        assert bankable_gold(kept, RESERVE) == 0, (pocket, kept)


def test_a_deposit_after_a_withdrawal_never_breaches_the_reserve():
    """The honest form of "deposit and withdraw cannot trade the same coin".

    A genuine round trip cannot be asserted here: this module has no withdraw and
    no spend to compose with, so that claim is an INTEGRATION property about the
    ferry and is documented rather than tested. What IS assertable is the safety
    bound on the pair — a withdrawal large enough to make a fresh chunk eligible
    is allowed to trigger another deposit, and that deposit still cannot take the
    pocket below the reserve. So the two can never ratchet a character dry.
    """
    for pocket in range(RESERVE, RESERVE + 5 * GOLD_CHUNK, 313):
        kept = pocket - bankable_gold(pocket, RESERVE)
        for withdrawal in (1, 100, GOLD_CHUNK - 1, 5 * GOLD_CHUNK):
            after_ferry = kept + withdrawal
            after_second_deposit = after_ferry - bankable_gold(after_ferry, RESERVE)
            assert after_second_deposit >= RESERVE, (pocket, withdrawal)


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


def test_a_full_slack_leaves_no_sub_headroom_withdrawal():
    """The degenerate end of the headroom rule, exercised rather than asserted.

    At slack 9,999 the headroom is 1, so there is no withdrawal below it — and the
    smallest withdrawal there is, 1, correctly makes a chunk eligible. The previous
    test's filter skips this case; this one shows why that is right.
    """
    pocket = RESERVE + GOLD_CHUNK - 1
    kept = pocket - bankable_gold(pocket, RESERVE)
    assert kept - RESERVE == GOLD_CHUNK - 1
    assert bankable_gold(kept + 1, RESERVE) == GOLD_CHUNK


def test_the_kept_remainder_is_always_under_one_chunk_above_the_reserve():
    """The slack the ferry draws on, bounded: never negative, never a whole chunk."""
    for pocket in range(RESERVE, RESERVE + 10 * GOLD_CHUNK, 271):
        slack = pocket - bankable_gold(pocket, RESERVE) - RESERVE
        assert 0 <= slack < GOLD_CHUNK, (pocket, slack)


def test_the_boundary_ends_are_checked_explicitly():
    """The exact chunk boundaries, which no other test in this file reaches.

    Neither step (313, 271) divides 10,000, so none of the range-based tests ever
    lands on a chunk multiple. These four cases are the only place the boundary
    itself is checked.
    """
    assert bankable_gold(RESERVE, RESERVE) == 0
    assert bankable_gold(RESERVE + GOLD_CHUNK - 1, RESERVE) == 0
    assert bankable_gold(RESERVE + GOLD_CHUNK, RESERVE) == GOLD_CHUNK
    assert bankable_gold(RESERVE + 2 * GOLD_CHUNK - 1, RESERVE) == GOLD_CHUNK
