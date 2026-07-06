"""Bank-expansion firing decision. ExpandBankGoal should buy a bank expansion only
when the bank is near full AND buying keeps gold at or above the reserve floor.

Two independent gates, both HARD:
  * fill threshold — `used / capacity >= trigger_num / trigger_den`, decided by an
    EXACT integer cross-multiply (`used*trigger_den >= capacity*trigger_num`), never
    a float, so the decision is about the real rational fill ratio not a surrogate.
  * reserve safety — `gold - cost >= reserve`, so the purchase never drains gold
    below the reserve the rest of the bot relies on (the real SAFETY-HOLE this
    closes: the old code fired on bare `gold >= cost`, ignoring the reserve).

The pure `should_expand_bank` is the differential target proved in
formal/Formal/BankExpansionTiming.lean over `Int`.
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
