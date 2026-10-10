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
  is capped there; food sits in the bag and is not capped."""

from dataclasses import dataclass

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
    the units one fight drinks, and each food its recovery eats with the units
    one fight's recovery eats (only codes it uses, in the chooser's order)."""

    monster: str
    potions: tuple[tuple[str, int], ...]
    food: tuple[tuple[str, int], ...]

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


def food_carry(eaten_per_fight: int) -> int:
    """Units of a chosen food to carry in the bag: one recovery's use × the
    horizon."""
    return eaten_per_fight * CARRY_HORIZON_FIGHTS
