"""Realizability check for a multi-slot loadout vs available inventory + equipment.

A loadout `{slot: code | None}` is REALIZABLE iff every chosen item code C
appears in the loadout at most as many times as the character can physically
provide: the number of unequipped (spare) copies in `inventory[C]` plus the
number of slots currently holding C in `current_equipment` (those will be
returned to inventory by the unequip half of a swap).

This is the post-`pick_loadout` invariant. `OptimizeLoadoutAction.apply`
asserts it indirectly via the per-slot `cur >= 1` check on the inventory
decrement; if `pick_loadout` ever returns a loadout that fails realizability,
the apply assertion fires (no more silent `pop(code, None)` tolerance).

Pure module — no I/O, no game state. The formal target lives here so the Lean
model can mirror the exact arithmetic.
"""
from collections.abc import Mapping


def ownership(code: str, inventory: Mapping[str, int],
              current_equipment: Mapping[str, str | None]) -> int:
    """Physical count of item `code` the character holds.

    spare copies in inventory + slots currently holding `code` (those slots'
    items return to inventory on unequip, so they're available for re-equip
    in another slot during the same swap plan).
    """
    n = inventory.get(code, 0)
    for equipped in current_equipment.values():
        if equipped == code:
            n += 1
    return n


def is_realizable(loadout: Mapping[str, str | None],
                  inventory: Mapping[str, int],
                  current_equipment: Mapping[str, str | None]) -> bool:
    """A loadout is realizable iff, for every non-None code C, the number of
    loadout slots holding C does not exceed `ownership(C, inv, equip)`.

    The post-pick_loadout loadout MUST satisfy this; the apply assertion in
    `OptimizeLoadoutAction.apply` is the runtime contract.
    """
    demand: dict[str, int] = {}
    for code in loadout.values():
        if code is None:
            continue
        demand[code] = demand.get(code, 0) + 1
    for code, count in demand.items():
        if count > ownership(code, inventory, current_equipment):
            return False
    return True
