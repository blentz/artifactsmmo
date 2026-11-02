"""The consumable loadout a character fights with, as plain data, and the stock
it carries for it (`docs/PLAN_consumable_utility.md` increment 5).

ONE AUTHORITY. `best_loadout.best_loadout` picks, per character and per fight,
the utility potions and the recovery food that maximise XP per second; the
player reads it once per cycle against the fight ahead and threads it on the
selection context (`SelectionContext.loadout`). Every consumable decision reads
that one value: the CRAFT_POTIONS guard brews and equips only its potions, a
fight step's prep carries only its potions and food, the fleet floor's
need is its use, and the keep authority holds its carry in the bag. A potion or
a food it does not name is never stocked by any of them.

Pure data plus the carry arithmetic, so the selection context can hold it
without importing the loop-rate machinery (which imports the context).

* CARRY — what the character takes into a run of fights: the units one fight
  uses × `CARRY_HORIZON_FIGHTS`. A utility slot holds at most
  `UTILITY_SLOT_MAX_STACK` units (the API's equip maximum), so a potion's carry
  is capped there. Food sits in the bag, so a food's carry is capped by what
  the bag can hold of it and, where the reader prices from held stock, by that
  stock (`food_carry`, Task 8c ruling C2-food): the uncapped horizon asked a
  recovery eating several units a fight for more than the bag could ever hold,
  so a nearly empty bag read full and the loop read `runnable=False`.
* ONE ROOM — the bag's room is shared by every food the recovery eats, so it is
  allocated jointly (`food_shares`): each food's share is its part of the room
  in proportion to the units one fight eats of it, the recovery's own plan, so
  no listing order and no code decides who gets the room. The loop's recovery
  never eats more of the foods a fight than that room holds
  (`loop_rate_core.recovery_choice`), so every food it eats has a share of at
  least one fight's units (`Formal.LoopRate.share_covers`)."""

from collections.abc import Sequence
from dataclasses import dataclass

from artifactsmmo_cli.ai.inventory_room import has_room
from artifactsmmo_cli.ai.thresholds import UTILITY_SLOT_MAX_STACK

CARRY_HORIZON_FIGHTS = 20
"""Fights one carried stock is sized for: the fights before the next bank visit,
when the bag can be topped up again. Measured over `learning.db` 2026-09-25 ..
2026-10-09 (1,356 runs of successful Fights between two bank actions — Withdraw,
Deposit or DepositAll — across the five characters): mean 20.2, median 5, p75
17, p90 48. The MEAN is the expected fights a carry must cover; a carry left
over is held stock, free for the next run (USER 2026-10-09, "free until used
up"), so the median would under-cover the long runs that matter. It equals the
fleet's banked horizon (`consumable_floor_core.REFILL_HORIZON_FIGHTS`), so each
character's banked share is one carry."""


@dataclass(frozen=True)
class ChosenLoadout:
    """The chosen loadout against `monster`: each utility potion it wears with
    the units one fight drinks, each food its recovery eats with the units one
    fight's recovery eats (only codes it uses, in the chooser's order), and
    `made_food`, the food that recovery eats when every unit must be MADE
    (held count 0, replacement price): the food worth producing (spec
    2026-10-13 section 1). Held food is eaten free; only `made_food` is stocked
    past what is held (`grind_heal_prep.heal_prep_goal` reads it), or asked of
    the fleet."""

    monster: str
    potions: tuple[tuple[str, int], ...]
    food: tuple[tuple[str, int], ...]
    made_food: tuple[tuple[str, int], ...]
    runnable: bool = True
    """Whether the bag has room for the fight's drops (spec 2026-10-18 §2.10,
    `LoopRate.runnable`). A pick that is not runnable is still the fight's
    loadout: the keep and the preps keep serving it, and the fight against
    `monster` is refused on this flag (`fight_room_license`). A party's pick
    counts no trips and always runs."""

    def potion_codes(self) -> frozenset[str]:
        """The utility potions the loadout wears."""
        return frozenset(code for code, _ in self.potions)

    def food_codes(self) -> frozenset[str]:
        """The foods the loadout's recovery eats."""
        return frozenset(code for code, _ in self.food)


def potion_carry(used_per_fight: int) -> int:
    """Units of a chosen potion to wear: one fight's use × the horizon, at most a
    full utility slot."""
    return min(used_per_fight * CARRY_HORIZON_FIGHTS, UTILITY_SLOT_MAX_STACK)


def food_shares(foods: Sequence[tuple[int, int]], slots_free: int, qty_free: int) -> tuple[int, ...]:
    """The bag's room for each of the loadout's foods, allocated jointly: one
    room for all of them (Task 8c ruling C2-food, fix round 1). `foods` holds,
    per food, the units one fight eats of it and the units of it the bag holds;
    `slots_free` and `qty_free` are the reader's bag less every other keep.

    The room is the foods' own units plus the free quantity (none past the cap). A food the bag
    holds a stack of grows on quantity alone; the foods it holds none of need a
    new stack each, and a bag without a free slot for every one of them takes
    none of them (`inventory_room.has_room`, the one slot and quantity model —
    which of them would get a short slot is no fact the bag knows). The foods
    admitted share the room in proportion to the units one fight eats of each,
    rounded down: the shares sum to at most the room, and a room that holds one
    fight's units of every admitted food gives each at least its fight
    (`Formal.LoopRate.shares_sum_le`, `share_covers`)."""
    qty = sum(bag for _, bag in foods) + max(0, qty_free)
    new_stacks = sum(1 for eaten, bag in foods if eaten > 0 and bag == 0)
    admits_new = has_room(new_stacks, 0, slots_free, qty)
    admitted = [eaten > 0 and (bag > 0 or admits_new) for eaten, bag in foods]
    total = sum(eaten for (eaten, _), yes in zip(foods, admitted, strict=True) if yes)
    return tuple(eaten * qty // total if yes else 0
                 for (eaten, _), yes in zip(foods, admitted, strict=True))


def food_carry(eaten_per_fight: int, room: int, stock: int | None) -> int:
    """Units of a chosen food to carry in the bag: the least of (a) one
    recovery's use × the horizon, (b) `room`, the bag's room for it
    (`food_shares`), and (c) `stock`, the units held or obtainable now (bag and
    bank) when the reader prices from held stock; `stock` is None when units
    past the held ones are made, so no stock bounds the carry. The ONE bound:
    the keep, the loop rate and the heal prep all read it."""
    carry = min(eaten_per_fight * CARRY_HORIZON_FIGHTS, room)
    return carry if stock is None else min(carry, stock)
