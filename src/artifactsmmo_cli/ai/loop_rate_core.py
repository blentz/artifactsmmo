"""Pure core: the fight loop's recovery and its XP rate
(`docs/PLAN_consumable_utility.md` increments 3-4; proved model
`formal/Formal/LoopRate.lean`, differential `formal/diff/test_loop_rate_diff.py`).

RECOVERY. After a fight the character is `missing_hp` short of full. It can rest
(`rest_cooldown_core.rest_cooldown_seconds`: one second per percent missing,
rounded up, at least three) or eat food first and rest off whatever is left.

A FOOD is `(restore, price, held, room)` (USER 2026-10-09, "free until used
up"): the first `held` units are free and every further unit costs `price`, its
replacement in seconds; a `None` price has no replacement, so no more than
`held` units can be eaten. `room` caps the units of it one recovery eats.

THE BAG (Task 8c, ruling C2-food, fix round 1). Every food a recovery eats must
be in the bag, and the bag's room is ONE room shared by all of them: a
recovery takes `qty` units of room in all and `slots` stacks, one per food it
eats any of. So the search is joint: the units it eats sum to at most `qty`,
and it eats of at most `slots` foods. A food the bag has no room for falls back
to the other foods and to Rest, each priced in seconds (a priced alternative,
not a veto). Eating `k > 0` units of one food is ONE use: the
published consumable cooldown is flat whatever the quantity
(`cost_core.CONSUMABLE_COOLDOWN_SECONDS`, "flat, whatever the quantity"), so it
costs `eat_seconds + max(0, k − held) × price`. With nothing left missing there
is nothing to rest (a Rest is never taken at full HP, so the three-second floor
does not apply to a zero remainder).

`recovery_choice` is the EXACT minimum over every feasible count vector, and
the vector that reaches it (`Formal.LoopRate.recovery_le_planCost`: no feasible
vector costs less). The search per food is bounded by the count needed:
`k ≤ ⌈m / restore⌉` where `m` is what is still missing when that food is
reached, `k ≤ held` for a food with no replacement, `k ≤ room`, and `k` no
more than the bag's room left (none at all with no slot left). More units than
`⌈m / restore⌉` restore nothing more and cost no less, so the bound loses no
optimum. Among the cheapest vectors the one eating the FEWEST units in all is
chosen (fewer consumables drawn for the same seconds); on a tie in both, the
fewer units of the earlier food (the search replaces its choice only on a
strictly better pair). The search is a dynamic
programme over (food index, HP still missing, room left, slots left), the room
clamped to what the remaining foods could ever eat and the slots to the foods
left, so a bag with room to spare searches as the room-free programme did.

CONSUMED. The fight's potions are `(used, price, held)`: the drinks past the
held units cost their price, and with no replacement the fight is payable only
while `used ≤ held` (`consumed_seconds` is None otherwise).

XP RATE. `xp_per_second = xp_per_kill / (fight + recovery + consumed)`, all in
seconds; it needs a positive fight duration, which keeps the denominator
positive.

BANK TRIPS (spec 2026-10-18 §2.10). Drops fill the bag, and a full bag stops
the loop until the character deposits. One fight adds `drops_per_fight =
p_win × Σ units` (each drop's expected units per attempt, a lost fight
dropping nothing); a bag with `capacity` units of room for drops fills every
`capacity / drops_per_fight` fights, and each fill costs one trip:
`trip_seconds = 2 × walk + codes × deposit` (to the bank and back, and one
deposit per distinct drop code). So each fight carries `trip_share = trip ×
drops / capacity` seconds of trips. A loop that drops nothing never fills the
bag and makes no trip, whatever its room; one that drops something with no
room (`capacity ≤ 0`) cannot run (None). Proved in `Formal.LoopRate`
(`tripShare`): no trips without drops, more room never adds trips, more drops
or a longer trip never removes them."""

from collections.abc import Callable, Sequence
from fractions import Fraction
from functools import lru_cache

from artifactsmmo_cli.ai.rest_cooldown_core import rest_cooldown_seconds

Food = tuple[int, Fraction | None, int, int]
"""`(restore HP, price seconds or None, held units, room units)`."""

Potion = tuple[int, Fraction | None, int]
"""`(units used, price seconds or None, held units)`."""


def rest_part(missing: int, max_hp: int) -> int:
    """Seconds of resting `missing` HP off: 0 when nothing is missing."""
    return 0 if missing <= 0 else rest_cooldown_seconds(missing, max_hp)


def count_bound(missing: int, restore: int) -> int:
    """Most units of a `restore`-HP food worth eating for `missing` HP: ⌈m / r⌉."""
    return -(-missing // restore)


def food_bound(missing: int, restore: int, price: Fraction | None, held: int,
               room: int) -> int:
    """The most units of a food the search tries: ⌈m / r⌉, no more than are
    held when the food has no replacement, and no more than the bag's `room`."""
    bound = min(count_bound(missing, restore), room)
    return bound if price is not None else min(bound, held)


def eat_cost(units: int, eat_seconds: Fraction, price: Fraction | None, held: int) -> Fraction:
    """One use of `units` units: the flat cooldown once, plus the price of every
    unit past the held ones (a food with no replacement is never asked past
    them: `food_bound`)."""
    if units == 0:
        return Fraction(0)
    past = max(0, units - held)
    return eat_seconds if price is None else eat_seconds + past * price


def _validate(max_hp: int, food: Sequence[Food], eat_seconds: Fraction, qty: int,
              slots: int) -> None:
    if max_hp <= 0:
        raise ValueError(f"max_hp {max_hp} must be positive")
    if eat_seconds < 0:
        raise ValueError(f"eat_seconds {eat_seconds} must be non-negative")
    if qty < 0 or slots < 0:
        raise ValueError(f"qty {qty} and slots {slots} must be non-negative")
    for restore, price, held, room in food:
        if restore <= 0 or (price is not None and price < 0) or held < 0 or room < 0:
            raise ValueError(f"food ({restore}, {price}, {held}, {room}) needs restore > 0, "
                             f"price >= 0, held >= 0 and room >= 0")


RECOVERY_TABLES = 64
"""Recovery tables kept (`_recovery_table`): one per distinct `(max_hp, food
menu, eat seconds)`, least recently used dropped first."""


@lru_cache(maxsize=RECOVERY_TABLES, typed=True)
def _recovery_table(max_hp: int, foods: tuple[Food, ...],
                    eat_seconds: Fraction) -> Callable[[int, int, int, int],
                                                       tuple[Fraction, int, tuple[int, ...]]]:
    """The dynamic programme over (food index, HP still missing, bag room left,
    slots left) for one menu. Its entries depend only on `max_hp`, the menu and
    `eat_seconds` — never on the HP or the room a query starts from — so one
    table answers every query against the same menu: every loadout and every
    monster of a cycle, and the next cycle's while the menu holds (a band ranks
    each monster's loadouts against one menu). The room is clamped to the units
    the foods left could ever eat and the slots to the foods left: past those
    they bind nothing, so the clamp changes no answer and keeps the table the
    room-free programme's size when the bag has room to spare."""
    memo: dict[tuple[int, int, int, int], tuple[Fraction, int, tuple[int, ...]]] = {}
    needs: dict[tuple[int, int], int] = {}

    def need(index: int, missing: int) -> int:
        key = (index, missing)
        if key not in needs:
            needs[key] = sum(food_bound(missing, restore, price, held, room)
                             for restore, price, held, room in foods[index:])
        return needs[key]

    def best(index: int, missing: int, qty: int, slots: int) -> tuple[Fraction, int, tuple[int, ...]]:
        qty = min(qty, need(index, missing))
        slots = min(slots, len(foods) - index)
        key = (index, missing, qty, slots)
        if key in memo:
            return memo[key]
        if index == len(foods):
            choice: tuple[Fraction, int, tuple[int, ...]] = (Fraction(rest_part(missing, max_hp)), 0, ())
        else:
            restore, price, held, room = foods[index]
            rest_value, rest_units, rest_counts = best(index + 1, missing, qty, slots)
            choice = (rest_value, rest_units, (0, *rest_counts))
            bound = 0 if slots == 0 else min(food_bound(missing, restore, price, held, room), qty)
            for k in range(1, bound + 1):
                tail_value, tail_units, tail_counts = best(index + 1, max(0, missing - k * restore),
                                                           qty - k, slots - 1)
                value = eat_cost(k, eat_seconds, price, held) + tail_value
                if (value, k + tail_units) < choice[:2]:
                    choice = (value, k + tail_units, (k, *tail_counts))
        memo[key] = choice
        return choice

    return best


def recovery_choice(missing_hp: int, max_hp: int, food: Sequence[Food],
                    eat_seconds: Fraction, qty: int, slots: int) -> tuple[Fraction, tuple[int, ...]]:
    """The cheapest way, in seconds, to recover `missing_hp`, and the units of
    each food it eats, from a bag with `qty` units of room and `slots` stacks
    for its foods (see the module doc). Restores must be positive, prices, held
    counts, rooms, `qty`, `slots` and `eat_seconds` non-negative."""
    _validate(max_hp, food, eat_seconds, qty, slots)
    value, _, counts = _recovery_table(max_hp, tuple(food), eat_seconds)(0, max(0, missing_hp),
                                                                         qty, slots)
    return value, counts


def recovery_seconds(missing_hp: int, max_hp: int, food: Sequence[Food],
                     eat_seconds: Fraction, qty: int, slots: int) -> Fraction:
    """The cheapest recovery of `missing_hp`, in seconds (`recovery_choice`)."""
    return recovery_choice(missing_hp, max_hp, food, eat_seconds, qty, slots)[0]


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


def expected_xp_per_second(xp_per_kill: int, p_win: Fraction, fight_seconds: Fraction,
                           extra_seconds: Fraction) -> Fraction:
    """XP per second of a loop whose fight wins with probability `p_win`
    (renewal-reward: expected XP over expected seconds; spec 2026-10-15 §2).
    `extra_seconds` is the expected recovery, consumed price and walk back."""
    if fight_seconds <= 0:
        raise ValueError(f"fight_seconds {fight_seconds} must be positive")
    if xp_per_kill < 0 or extra_seconds < 0 or not 0 <= p_win <= 1:
        raise ValueError(f"xp {xp_per_kill}, extra {extra_seconds}, p_win {p_win} out of range")
    return p_win * xp_per_kill / (fight_seconds + extra_seconds)


def drops_per_fight(p_win: Fraction, units: Sequence[Fraction]) -> Fraction:
    """Item units one fight adds to the bag, expected: the win probability times
    every drop's expected units per attempt (a loss drops nothing)."""
    if not 0 <= p_win <= 1 or any(u < 0 for u in units):
        raise ValueError(f"p_win {p_win} and units {list(units)} out of range")
    return p_win * sum(units, Fraction(0))


def trip_seconds(walk_seconds: int, deposit_seconds: Fraction, codes: int) -> Fraction:
    """One bank trip: the walk to the bank and back, and one deposit per
    distinct drop code."""
    if walk_seconds < 0 or deposit_seconds < 0 or codes < 0:
        raise ValueError(f"walk {walk_seconds}, deposit {deposit_seconds} and codes {codes} "
                         "must be non-negative")
    return 2 * walk_seconds + codes * deposit_seconds


def trip_share(trip: Fraction, drops: Fraction, capacity: int) -> Fraction | None:
    """The trip seconds one fight carries: `trip × drops / capacity`; 0 without
    drops (the bag never fills), None with drops and no room for them."""
    if trip < 0 or drops < 0:
        raise ValueError(f"trip {trip} and drops {drops} must be non-negative")
    if drops == 0:
        return Fraction(0)
    if capacity <= 0:
        return None
    return trip * drops / capacity
