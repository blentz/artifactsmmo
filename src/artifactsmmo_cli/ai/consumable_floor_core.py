"""Pure core: the fleet's consumable floor (Phase 5-2c-iii-c-2 #5,
`docs/PLAN_task_value.md` §10; proved model `formal/Formal/ConsumableFloor.lean`,
differential `formal/diff/test_consumable_floor_diff.py`).

USER 2026-10-07: "Fishing feeds Cooking, Cooking feeds HP recovery or provides
stat bonuses. Both cases require pre-emptive crafting of an available supply.
The fleet can collectively maintain a minimum supply in the bank."

* `tier_pick`: the TIER-APPROPRIATE consumable — the best restore usable at the
  character's level, even if a skill cannot make it yet (that skill demand is
  the seesaw, USER "Tier-appropriate"); a tie goes to the higher level, then
  catalogue order (never the code's spelling).
* `fleet_deficit`: the floor is fleet size × the per-character target (USER).
* `publish_share`: each character publishes ⌈deficit / fleet⌉ on the demand
  board, which SUMS rows across characters.
"""

from collections.abc import Sequence


def tier_pick(char_level: int, candidates: Sequence[tuple[int, int]]) -> int | None:
    """Index of the best `(level, restore)` candidate usable at `char_level`."""
    best: tuple[int, tuple[int, int]] | None = None
    for index, (level, restore) in enumerate(candidates):
        if level > char_level or restore <= 0:
            continue
        if best is None or (restore, level) > (best[1][1], best[1][0]):
            best = (index, (level, restore))
    return None if best is None else best[0]


def fleet_deficit(target: int, fleet: int, stock: int) -> int:
    return max(0, target * fleet - stock)


def publish_share(deficit: int, fleet: int) -> int:
    return -(-deficit // fleet)
