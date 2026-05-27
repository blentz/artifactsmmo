"""Pure upgrade-selection cores extracted from UpgradeEquipmentGoal.

These are store/game_data-free value objects and functions: callers build
`UpgradeCandidate`s from game_data and call these to rank/select. The semantics
mirror the original goal exactly:

* `best_by_value`: pick the higher-VALUE of an inventory pick vs a craftable
  pick; on a tie the inventory pick wins (`>=`), since equipping an owned item
  is cheaper than crafting.
* `craftable_key` / `inventory_key`: the lexicographic argmax sort keys with
  `item_code` (not slot) as the final field. Distinct item_codes never compare
  equal (the winning ITEM is unique); the same item mapped to multiple slots
  yields same-code candidates that DO compare equal, resolved first-wins by list
  order.
* `best_by_key`: deterministic argmax — the first candidate whose key strictly
  exceeds the running best, scanning in list order (matching the original
  `if key > best_key` loop); ties are kept first-wins.

The model is proved in `formal/Formal/UpgradeSelection.lean`.
"""

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class UpgradeCandidate:
    """A single equipment-upgrade pick, pre-resolved from game_data."""

    item_code: str
    value: float        # equip_value (attack + resistance + hp_restore; integer-valued)
    level: int
    craft_level: int
    relevant: bool      # relevant tool/skill for the active task
    fills_empty: bool   # target slot currently empty


def best_by_value(inv: UpgradeCandidate | None,
                  craft: UpgradeCandidate | None) -> UpgradeCandidate | None:
    """Higher-VALUE of an inventory pick and a craftable pick; tie -> inventory.

    Mirrors `UpgradeEquipmentGoal._best_by_value`: prefer the owned (inventory)
    item only on a tie, since equipping it is cheaper than crafting.
    """
    if inv is None:
        return craft
    if craft is None:
        return inv
    return inv if inv.value >= craft.value else craft


def craftable_key(c: UpgradeCandidate) -> tuple[int, int, float, int, str]:
    """Lexicographic sort key for craftable candidates:
    (relevant, fills_empty, value, -craft_level, item_code)."""
    return (int(c.relevant), int(c.fills_empty), c.value, -c.craft_level, c.item_code)


def inventory_key(c: UpgradeCandidate) -> tuple[int, float, int, str]:
    """Lexicographic sort key for inventory candidates:
    (relevant, value, level, item_code)."""
    return (int(c.relevant), c.value, c.level, c.item_code)


def best_by_key(cands: list[UpgradeCandidate],
                key: Callable[[UpgradeCandidate], tuple]) -> UpgradeCandidate | None:
    """Deterministic argmax: the candidate whose `key` is greatest, scanning in
    list order. Matches the original `if key > best_key` loop — the FIRST
    candidate to strictly exceed the running best is taken, and a later equal key
    never displaces it. Distinct item_codes (the final key field) give a unique
    max-key item; same-code candidates (one item, multiple slots) tie and the
    FIRST in list order wins (first-wins)."""
    best: UpgradeCandidate | None = None
    best_key: tuple | None = None
    for c in cands:
        k = key(c)
        if best_key is None or k > best_key:
            best, best_key = c, k
    return best
