"""Pure core: the fight loop's recovery and its XP rate
(`docs/PLAN_consumable_utility.md` increments 3-4; proved model
`formal/Formal/LoopRate.lean`, differential `formal/diff/test_loop_rate_diff.py`).

RECOVERY. After a fight the character is `missing_hp` short of full. It can rest
(`rest_cooldown_core.rest_cooldown_seconds`: one second per percent missing,
rounded up, at least three) or eat food first and rest off whatever is left.

A FOOD is `(restore, price, held)` (USER 2026-10-09, "free until used up"):
the first `held` units are free and every further unit costs `price`, its
replacement in seconds; a `None` price has no replacement, so no more than
`held` units can be eaten. Eating `k > 0` units of one food is ONE use: the
published consumable cooldown is flat whatever the quantity
(`cost_core.CONSUMABLE_COOLDOWN_SECONDS`, "flat, whatever the quantity"), so it
costs `eat_seconds + max(0, k − held) × price`. With nothing left missing there
is nothing to rest (a Rest is never taken at full HP, so the three-second floor
does not apply to a zero remainder).

`recovery_choice` is the EXACT minimum over every feasible count vector, and
the vector that reaches it (`Formal.LoopRate.recovery_le_planCost`: no feasible
vector costs less). The search per food is bounded by the count needed:
`k ≤ ⌈m / restore⌉` where `m` is what is still missing when that food is
reached, and `k ≤ held` for a food with no replacement. More units than
`⌈m / restore⌉` restore nothing more and cost no less, so the bound loses no
optimum. Among the cheapest vectors the one eating the FEWEST units in all is
chosen (fewer consumables drawn for the same seconds); on a tie in both, the
fewer units of the earlier food (the search replaces its choice only on a
strictly better pair). The search is a dynamic
programme over (food index, HP still missing), so its work is
`Σ_foods (missing + 1) × (bound + 1)` at worst — not the product of bounds.

CONSUMED. The fight's potions are `(used, price, held)`: the drinks past the
held units cost their price, and with no replacement the fight is payable only
while `used ≤ held` (`consumed_seconds` is None otherwise).

XP RATE. `xp_per_second = xp_per_kill / (fight + recovery + consumed)`, all in
seconds; it needs a positive fight duration, which keeps the denominator
positive."""

from collections.abc import Sequence
from fractions import Fraction

from artifactsmmo_cli.ai.rest_cooldown_core import rest_cooldown_seconds

Food = tuple[int, Fraction | None, int]
"""`(restore HP, price seconds or None, held units)`."""

Potion = tuple[int, Fraction | None, int]
"""`(units used, price seconds or None, held units)`."""


def rest_part(missing: int, max_hp: int) -> int:
    """Seconds of resting `missing` HP off: 0 when nothing is missing."""
    return 0 if missing <= 0 else rest_cooldown_seconds(missing, max_hp)


def count_bound(missing: int, restore: int) -> int:
    """Most units of a `restore`-HP food worth eating for `missing` HP: ⌈m / r⌉."""
    return -(-missing // restore)


def food_bound(missing: int, restore: int, price: Fraction | None, held: int) -> int:
    """The most units of a food the search tries: ⌈m / r⌉, and no more than are
    held when the food has no replacement."""
    bound = count_bound(missing, restore)
    return bound if price is not None else min(bound, held)


def eat_cost(units: int, eat_seconds: Fraction, price: Fraction | None, held: int) -> Fraction:
    """One use of `units` units: the flat cooldown once, plus the price of every
    unit past the held ones (a food with no replacement is never asked past
    them: `food_bound`)."""
    if units == 0:
        return Fraction(0)
    past = max(0, units - held)
    return eat_seconds if price is None else eat_seconds + past * price


def _validate(max_hp: int, food: Sequence[Food], eat_seconds: Fraction) -> None:
    if max_hp <= 0:
        raise ValueError(f"max_hp {max_hp} must be positive")
    if eat_seconds < 0:
        raise ValueError(f"eat_seconds {eat_seconds} must be non-negative")
    for restore, price, held in food:
        if restore <= 0 or (price is not None and price < 0) or held < 0:
            raise ValueError(f"food ({restore}, {price}, {held}) needs restore > 0, "
                             f"price >= 0 and held >= 0")


def recovery_choice(missing_hp: int, max_hp: int, food: Sequence[Food],
                    eat_seconds: Fraction) -> tuple[Fraction, tuple[int, ...]]:
    """The cheapest way, in seconds, to recover `missing_hp`, and the units of
    each food it eats (see the module doc). Restores must be positive, prices,
    held counts and `eat_seconds` non-negative."""
    _validate(max_hp, food, eat_seconds)
    foods = tuple(food)
    memo: dict[tuple[int, int], tuple[Fraction, int, tuple[int, ...]]] = {}

    def best(index: int, missing: int) -> tuple[Fraction, int, tuple[int, ...]]:
        key = (index, missing)
        if key in memo:
            return memo[key]
        if index == len(foods):
            choice: tuple[Fraction, int, tuple[int, ...]] = (Fraction(rest_part(missing, max_hp)), 0, ())
        else:
            restore, price, held = foods[index]
            rest_value, rest_units, rest_counts = best(index + 1, missing)
            choice = (rest_value, rest_units, (0, *rest_counts))
            for k in range(1, food_bound(missing, restore, price, held) + 1):
                tail_value, tail_units, tail_counts = best(index + 1, max(0, missing - k * restore))
                value = eat_cost(k, eat_seconds, price, held) + tail_value
                if (value, k + tail_units) < choice[:2]:
                    choice = (value, k + tail_units, (k, *tail_counts))
        memo[key] = choice
        return choice

    value, _, counts = best(0, max(0, missing_hp))
    return value, counts


def recovery_seconds(missing_hp: int, max_hp: int, food: Sequence[Food],
                     eat_seconds: Fraction) -> Fraction:
    """The cheapest recovery of `missing_hp`, in seconds (`recovery_choice`)."""
    return recovery_choice(missing_hp, max_hp, food, eat_seconds)[0]


def potion_cost(used: int, price: Fraction | None, held: int) -> Fraction | None:
    """The price of `used` drinks past `held`; None when they cannot be paid for."""
    past = max(0, used - held)
    if price is None:
        return Fraction(0) if past == 0 else None
    return past * price


def consumed_seconds(potions: Sequence[Potion]) -> Fraction | None:
    """The fight's consumed price; None when some drink cannot be paid for."""
    total = Fraction(0)
    for used, price, held in potions:
        if used < 0 or held < 0 or (price is not None and price < 0):
            raise ValueError(f"potion ({used}, {price}, {held}) needs non-negative terms")
        cost = potion_cost(used, price, held)
        if cost is None:
            return None
        total += cost
    return total


def xp_per_second(xp_per_kill: int, fight_seconds: Fraction, recovery: Fraction,
                  consumed_price_seconds: Fraction) -> Fraction:
    """XP per second of one loop: a fight, its recovery and the price of what it
    consumed. `fight_seconds` must be positive, the other terms non-negative."""
    if fight_seconds <= 0:
        raise ValueError(f"fight_seconds {fight_seconds} must be positive")
    if xp_per_kill < 0 or recovery < 0 or consumed_price_seconds < 0:
        raise ValueError(f"xp {xp_per_kill}, recovery {recovery} and consumed "
                         f"{consumed_price_seconds} must be non-negative")
    return Fraction(xp_per_kill) / (fight_seconds + recovery + consumed_price_seconds)
