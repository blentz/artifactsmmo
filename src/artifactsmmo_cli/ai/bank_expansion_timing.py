"""Bank-expansion firing decision. ExpandBankGoal should buy a bank expansion only
when the bank is near full, the POCKET can pay the price, AND buying keeps the
ACCOUNT at or above the reserve floor.

`should_expand_bank` is the proven two-gate core; `expansion_fires` composes it
with the pocket-executability conjunct and is what both call sites ask. Two
gates, both HARD:
  * fill threshold — `used / capacity >= trigger_num / trigger_den`, decided by an
    EXACT integer cross-multiply (`used*trigger_den >= capacity*trigger_num`), never
    a float, so the decision is about the real rational fill ratio not a surrogate.
  * reserve safety — `gold - cost >= reserve`, so the purchase never drains gold
    below the reserve the rest of the bot relies on (the real SAFETY-HOLE this
    closes: the old code fired on bare `gold >= cost`, ignoring the reserve).

The pure `should_expand_bank` is the differential target proved in
formal/Formal/BankExpansionTiming.lean over `Int`.

WHICH BALANCE THE RESERVE GATE READS. The reserve is a property of the ACCOUNT —
one bank, one gold balance shared by every character (`progression_reserve
.account_gold`), and `can_spend` is the single definition every other gold sink
asks. Both bank-expansion call sites passed `state.gold`, the POCKET, against
that account-scoped floor, so a character refused an expansion the account could
plainly fund. Live Robby 2026-09-12: pocket 3797, bank 12553, cost 3500, reserve
5100 — the pocket reading is 297 and refuses, the account reading is 12850 and
approves. He sat wedged at 157/158 items with a full bank for 10 hours.

WHY EXECUTABILITY IS A SEPARATE CONJUNCT. `can_spend`'s own contract puts it
with the caller: "whether the gold is in the right place to be spent at this
venue". The buy_expansion endpoint spends the character's POCKET, and there is
no withdraw-gold edge in the action pool, so an account-only gate would fire a
rung `BuyBankExpansionAction.is_applicable` then refuses — a zero-length plan
candidate, the exact defect class the 2026-07-06 drift fix was about. It lives
in `expansion_fires` rather than at the two call sites so the goal and the
arbiter guard cannot drift apart again.
"""

TRIGGER_FILL_NUM = 95
TRIGGER_FILL_DEN = 100
"""The bank-near-full trigger (95%), owned by the decision module so every
gate on "should the bank expand" — ExpandBankGoal.value and the arbiter's
BANK_EXPAND means guard — reads the SAME ratio and cannot drift."""


def should_expand_bank(
    used: int,
    capacity: int,
    gold: int,
    cost: int,
    reserve: int,
    trigger_num: int,
    trigger_den: int,
) -> bool:
    """True iff the bank is at or above the rational fill threshold
    (`used*trigger_den >= capacity*trigger_num`) AND buying the expansion keeps
    gold at or above the reserve (`gold - cost >= reserve`). Both are hard gates;
    the fill check is an exact integer cross-multiply (no float)."""
    at_threshold = used * trigger_den >= capacity * trigger_num
    reserve_safe = gold - cost >= reserve
    return at_threshold and reserve_safe


def expansion_fires(
    used: int,
    capacity: int,
    pocket_gold: int,
    account_gold: int,
    cost: int,
    reserve: int,
    trigger_num: int,
    trigger_den: int,
) -> bool:
    """True iff the expansion should be bought: the pocket can pay `cost` AND the
    proven core fires on the ACCOUNT balance (fill threshold + reserve safety).

    The ONE decision both `ExpandBankGoal.value` and the arbiter's BANK_EXPAND
    means guard ask, so the two cannot re-type it differently. See the module
    docstring for which balance each gate reads and why."""
    return pocket_gold >= cost and should_expand_bank(
        used, capacity, account_gold, cost, reserve, trigger_num, trigger_den)
