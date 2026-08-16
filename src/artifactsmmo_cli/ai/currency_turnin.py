"""When the fleet's dual-role stock is enough to buy the thing it pays for.

Pure over plain mappings so the whole decision is testable without a
coordination DB, five characters, or a live account.

THE THRESHOLD IS THE VENDOR'S PRICE, NOT A TUNED CONSTANT. `lich_race_trophy`
costs exactly 10 `lich_race_medal`; asking for a margin on top would be a
number nobody could derive from the game."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True)
class TurnIn:
    """A resolved turn-in: what to buy, where, in what currency, by whom."""

    item_code: str
    npc_code: str
    price: int
    currency: str
    buyer: str
    fleet_total: int


def fleet_total_pure(own: Mapping[str, int], siblings: Mapping[str, int],
                     bank: Mapping[str, int], code: str) -> int:
    """Units of `code` the whole account can reach: this character's worn and
    carried units, every live sibling's, and the shared bank.

    The bank is added exactly once because only one of the three arguments is
    allowed to carry it — see `HoldingLedger`, which never publishes it."""
    return own.get(code, 0) + siblings.get(code, 0) + bank.get(code, 0)


def turn_in_ready_pure(fleet_total: int, price: int) -> bool:
    """True when the fleet can pay the vendor's price outright."""
    if price <= 0:
        return False
    return fleet_total >= price


def buyer_bank_draw_pure(price: int, buyer_held: int) -> int:
    """Units the buyer must WITHDRAW, given what it already holds itself.

    The withdraw IS the bank's contribution, so it must NOT net the bank out
    the way a recall would: a non-buyer sibling never computes a quota at
    all — it surrenders its ENTIRE holding of the currency, unconditionally
    (see `CurrencyTurnInGoal`/`_adopt_sibling_claim` and the
    `WHY NOT A QUOTA` note in `player.py`). The buyer is the only role that
    ever sizes a draw against its own holdings, because it is the only role
    whose contribution is bounded by a specific price rather than "give up
    everything you have."

    THE LIVELOCK THIS PREVENTS (fix-round-2, CRITICAL): the elected buyer
    wears 1 medal, carries 1, and the bank holds 8 of a price of 10. The
    fleet total is 10 so this character wins the election, but a withdraw
    sized to 10 is never applicable against a bank of 8, so the buyer plans
    nothing — forever, every cycle, while holding the claim. Sizing the
    withdraw to `price - held` makes the bank's 8 exactly enough."""
    return max(0, price - buyer_held)
