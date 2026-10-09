"""Pure core: the fight loop's recovery and its XP rate
(`docs/PLAN_consumable_utility.md` increment 3; proved model
`formal/Formal/LoopRate.lean`, differential `formal/diff/test_loop_rate_diff.py`).

RECOVERY. After a fight the character is `missing_hp` short of full. It can rest
(`rest_cooldown_core.rest_cooldown_seconds`: one second per percent missing,
rounded up, at least three) or eat food first and rest off whatever is left.
Eating `k > 0` units of one food is ONE use: the published consumable cooldown
is flat whatever the quantity (`cost_core.CONSUMABLE_COOLDOWN_SECONDS`, "flat,
whatever the quantity"), so it costs `eat_seconds + k × price`. With nothing
left missing there is nothing to rest (a Rest is never taken at full HP, so the
three-second floor does not apply to a zero remainder).

`recovery_seconds` is the EXACT minimum over every count vector. The search per
food is bounded by the count needed: `k ≤ ⌈m / restore⌉` where `m` is what is
still missing when that food is reached. More units than that restore nothing
more (the remainder is already 0) and cost no less (price and cooldown are
non-negative), so the bound loses no optimum
(`Formal.LoopRate.recovery_le_rest`, `recovery_mono_missing` rest on it). The
search is a dynamic programme over (food index, HP still missing), so its work
is `Σ_foods (missing + 1) × (bound + 1)` at worst — not the product of bounds.

XP RATE. `xp_per_second = xp_per_kill / (fight + recovery + consumed)`, all in
seconds; it needs a positive fight duration, which keeps the denominator
positive."""

from collections.abc import Sequence
from fractions import Fraction

from artifactsmmo_cli.ai.rest_cooldown_core import rest_cooldown_seconds


def rest_part(missing: int, max_hp: int) -> int:
    """Seconds of resting `missing` HP off: 0 when nothing is missing."""
    return 0 if missing <= 0 else rest_cooldown_seconds(missing, max_hp)


def count_bound(missing: int, restore: int) -> int:
    """Most units of a `restore`-HP food worth eating for `missing` HP: ⌈m / r⌉."""
    return -(-missing // restore)


def recovery_seconds(missing_hp: int, max_hp: int, food: Sequence[tuple[int, Fraction]],
                     eat_seconds: Fraction) -> Fraction:
    """The cheapest way, in seconds, to recover `missing_hp` (see the module doc).
    `food` is `(restore_hp, price_seconds)` per food, each usable any number of
    times; restores must be positive, prices and `eat_seconds` non-negative."""
    if max_hp <= 0:
        raise ValueError(f"max_hp {max_hp} must be positive")
    if eat_seconds < 0:
        raise ValueError(f"eat_seconds {eat_seconds} must be non-negative")
    for restore, price in food:
        if restore <= 0 or price < 0:
            raise ValueError(f"food ({restore}, {price}) needs restore > 0 and price >= 0")
    foods = tuple(food)
    memo: dict[tuple[int, int], Fraction] = {}

    def best(index: int, missing: int) -> Fraction:
        key = (index, missing)
        if key in memo:
            return memo[key]
        if index == len(foods):
            value = Fraction(rest_part(missing, max_hp))
        else:
            restore, price = foods[index]
            value = min((eat_seconds if k > 0 else Fraction(0)) + k * price
                        + best(index + 1, max(0, missing - k * restore))
                        for k in range(count_bound(missing, restore) + 1))
        memo[key] = value
        return value

    return best(0, max(0, missing_hp))


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
