"""Overheal-aware consumable selection. The legacy `_best_consumable` picked the
MAX-`hp_restore` consumable UNCONDITIONALLY, so a small deficit + a big potion
overheals, the UseConsumable cost hits its 100.0 overheal sentinel, and the
planner inserts a spurious Rest. This pure core fixes that: among usable items it
picks the one that best FITS the deficit.

Among inventory items with `qty > 0` and `hp_restore > 0`, choose the lex-argmin on
the key `(overheal_flag, waste, minus_coverage, code)`:

* `overheal_flag = 1 if restore > deficit else 0`  — a fitting item always beats an
  overhealing one (the fit-preference that kills the spurious Rest).
* `waste = (restore - deficit) if overheal else 0`  — when every item overheals,
  take the SMALLEST overshoot.
* `minus_coverage = -restore`  — among fitters, take the LARGEST restore (fewest
  future heals).
* `code`  — deterministic final tiebreak (string order).

Pure: no I/O. This is the differential target proved in
`formal/Formal/ConsumableSelection.lean` over `Int`.
"""

from collections.abc import Mapping

from artifactsmmo_cli.ai.game_data import ItemStats


def _key(code: str, restore: int, deficit: int) -> tuple[int, int, int, str]:
    overheal = restore > deficit
    overheal_flag = 1 if overheal else 0
    waste = (restore - deficit) if overheal else 0
    return (overheal_flag, waste, -restore, code)


def select_consumable(
    inventory: dict[str, int], item_stats: Mapping[str, ItemStats], deficit: int
) -> tuple[str, int] | None:
    """Return `(item_code, hp_restore)` for the lex-argmin usable consumable, or
    `None` when no inventory item has `qty > 0` and `hp_restore > 0`."""
    best: tuple[str, int] | None = None
    best_key: tuple[int, int, int, str] | None = None
    for code, qty in inventory.items():
        if qty <= 0:
            continue
        stats = item_stats.get(code)
        if stats is None or stats.hp_restore <= 0:
            continue
        k = _key(code, stats.hp_restore, deficit)
        if best_key is None or k < best_key:
            best_key = k
            best = (code, stats.hp_restore)
    return best
