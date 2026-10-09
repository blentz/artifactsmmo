"""Pure core: the price of one consumable, in seconds
(`docs/PLAN_consumable_utility.md` increment 2; proved model
`formal/Formal/ConsumablePrice.lean`, differential
`formal/diff/test_consumable_price_diff.py`).

The USER's ruling (2026-10-09): "held stock (bag, bank, utility slots) is free.
With none held, its price is the cheaper of replacement time (make it: the
acquisition walk) and gold value (buy it) — the classic build/buy."

* `held > 0` — the price is 0;
* otherwise the minimum of the AVAILABLE sides:
  * `make_seconds` — the acquisition walk in seconds (None: no route);
  * `buy_gold / gold_per_second` — the cheapest current gold price converted at
    the grind target's gold rate (None: nobody sells it for gold; a rate of 0 or
    less makes buying unpriceable, since a second of fighting earns no gold to
    pay with);
* None when neither side is available.

Exact `Fraction` arithmetic: the Lean model compares the two sides by
cross-multiplication, so a tie is a tie in both."""

from fractions import Fraction


def buy_seconds(buy_gold: int | None, gold_per_second: Fraction) -> Fraction | None:
    """Seconds of fighting that earn `buy_gold`, or None when buying is unavailable."""
    if buy_gold is None or gold_per_second <= 0:
        return None
    return Fraction(buy_gold) / gold_per_second


def consumable_price(held: int, make_seconds: Fraction | None, buy_gold: int | None,
                     gold_per_second: Fraction) -> Fraction | None:
    """The price in seconds of one more unit of a consumable (see the module doc).
    `make_seconds` and `buy_gold` must be non-negative when present."""
    if make_seconds is not None and make_seconds < 0:
        raise ValueError(f"make_seconds {make_seconds} must be non-negative")
    if buy_gold is not None and buy_gold < 0:
        raise ValueError(f"buy_gold {buy_gold} must be non-negative")
    if held > 0:
        return Fraction(0)
    buy = buy_seconds(buy_gold, gold_per_second)
    if make_seconds is None:
        return buy
    if buy is None:
        return make_seconds
    return make_seconds if make_seconds <= buy else buy
