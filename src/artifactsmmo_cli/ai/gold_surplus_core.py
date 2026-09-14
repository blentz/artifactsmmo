"""Pure arithmetic for what pocket gold is surplus to a character's needs.

No I/O and no project imports: every input is an int the caller has already
measured, which is what makes this property-testable over whole ranges rather
than case by case. The impure composition — which reserve, which fill — lives in
`DepositAllAction`.
"""

GOLD_CHUNK = 10_000
"""Gold moves between pocket and bank in whole units of this size.

CHUNKING IS HYSTERESIS, NOT TIDINESS. `GatherMaterialsGoal.relevant_actions`
admits a deficit-sized `WithdrawGold` whenever pocket gold cannot cover a plan's
gold-priced leaves (the GAP-3 ferry, gathering.py:613). Banking every coin above
the reserve would leave the pocket at exactly the reserve, so ANY ferry
withdrawal at all — however small — would be banked straight back next cycle:
the `Withdraw`/`DepositAll` oscillation this codebase has already shipped once.
Keeping the sub-chunk remainder is what stops that.

The genuine round trip — the ferry withdraws what a plan's leaves need, the
plan SPENDS it, and the pocket returns to a non-bankable state — is an
INTEGRATION property this pure module cannot assert; the spend that closes the
loop lives outside it. Unspent, the true bound this module does guarantee is
the HEADROOM (`GOLD_CHUNK - slack`): a withdrawal strictly below it cannot
re-trigger a deposit.
"""


def bankable_gold(pocket: int, reserve: int, chunk: int = GOLD_CHUNK) -> int:
    """Whole `chunk` units of `pocket` above `reserve`; 0 when short.

    Guarantees `pocket - bankable_gold(pocket, reserve) >= reserve` whenever the
    pocket can cover the reserve at all — the invariant that makes banking
    unable to breach a reservation.
    """
    return max(0, (pocket - reserve) // chunk) * chunk


def expansion_hold(bank_used: int, bank_capacity: int, next_expansion_cost: int,
                   hold_num: int, hold_den: int) -> int:
    """`next_expansion_cost` while a bank expansion is in play, else 0.

    A BANK EXPANSION IS NEVER A RESERVED GEAR CODE — `ExpandBankGoal.value` says
    so — and `reserved_targets` reserves only the cheapest unmet ITEM purchase.
    So nothing else protects the gold an expansion needs, and banking the pocket
    empty would starve it silently: `expansion_fires` requires `pocket_gold >=
    cost`, so the rung simply never fires. No error, no plan, and a bank that
    cannot expand is a livelock this fleet has already hit.

    A WITHDRAW FERRY CANNOT FIX THAT, which is why the hold is here instead.
    Both `ExpandBankGoal.value` and the arbiter's BANK_EXPAND guard call the
    same `expansion_fires`, so a pocket-short character's goal returns 0.0 and
    its `relevant_actions` is never consulted — nothing would ever ask for the
    gold back.

    Capacity 0 means capacity was never read, and UNKNOWN IS NOT FULL: hold
    nothing rather than invent a fill ratio. Exact integer cross-multiply, no
    float, matching `bank_expansion_timing`.
    """
    if bank_capacity <= 0:
        return 0
    if bank_used * hold_den < bank_capacity * hold_num:
        return 0
    return next_expansion_cost
