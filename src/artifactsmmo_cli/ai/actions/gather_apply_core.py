"""Pure core for `GatherAction.is_applicable` / `.apply` inventory bookkeeping.

This module isolates the minimal transition GatherAction performs on the
inventory: the planner-side mint of `+1` of `drop_item`, and the slot-availability
precondition (`inventory_free >= MIN_FREE_SLOTS`).

The Lean module `formal/Formal/GatherApply.lean` proves three contracts on
these pure cores:

* `gather_is_applicable_pure(inv, k, drop_item)` returns True iff `max - used
  >= k` AND (when `drop_item` is known) the drop fits the slot cap: a NEW drop
  code needs a free slot, growing a held code does not (`inventory_room.has_room`).
* `gather_apply_pure(inv, code)` produces an inventory whose `used = used + 1`,
  `max` unchanged, and `item_count[code]` incremented by 1 (all other entries
  preserved).
* SAFETY: `gather_is_applicable_pure(inv, k) and k >= 1` implies the post-state
  satisfies `used' <= max` (the planner cannot mint past `inventory_max` in one
  step), and chaining `n` applies starting from `inventory_free >= n` preserves
  `used <= max` for the entire chain.
* `gather_apply_batch_pure(inv, drop_item, qty)` mints `qty` of `drop_item` in
  one step: `used' = min(used + qty, cap)`, `item_count[drop_item]` rises by
  the same amount, all other entries preserved. `gather_batch_size_pure(inv,
  demand, drop_item)` bounds `qty` so this can never mint past `cap` for any
  `qty`, including a batch far larger than the free quantity.

The planner (`src/artifactsmmo_cli/ai/planner.py`:122) re-checks
`is_applicable(node.state, ...)` on every node it pops, so chained `apply`s in
a plan ALWAYS see a fresh applicability check at each step. The safety theorem
applies per step; the chain safety is therefore a corollary of `is_applicable`
being a slot-floor.
"""
from collections.abc import Mapping
from dataclasses import dataclass, replace

from artifactsmmo_cli.ai.inventory_room import has_room


@dataclass(frozen=True)
class GatherInv:
    """Minimal projection of `WorldState` that `GatherAction.apply` reads."""

    used: int                       # sum of inventory values (inventory_used)
    cap: int                        # inventory_max
    item_count: Mapping[str, int]   # inventory dict
    slots_used: int = 0             # distinct stacks held (inventory_slots_used)
    slots_max: int = 0              # slot cap (inventory_slots_max)


def gather_is_applicable_pure(inv: GatherInv, min_free: int,
                              drop_item: str | None = None) -> bool:
    """Gathering is applicable iff there is room for the yielded drop under BOTH
    the quantity floor (`min_free`) and the slot cap. A gather yields the ore
    plus possible bonus drops; `min_free` remains the quantity floor. When
    `drop_item` is known, gathering a NEW code (not in `item_count`) also needs
    a free slot; gathering more of a held code does not.

    `drop_item=None` preserves the old quantity-only behavior for callers that
    do not resolve the drop.
    """
    if (inv.cap - inv.used) < min_free:
        return False
    if drop_item is None:
        return True
    new_stacks = 0 if drop_item in inv.item_count else 1
    slots_free = inv.slots_max - inv.slots_used
    qty_free = inv.cap - inv.used
    return has_room(new_stacks, added_qty=1, slots_free=slots_free, qty_free=qty_free)


def gather_apply_pure(inv: GatherInv, drop_item: str) -> GatherInv:
    """Mint `+1` of `drop_item` into the inventory.

    `used` increases by exactly one; `cap` is unchanged; `item_count[drop_item]`
    increases by one; all other entries are preserved bit-for-bit. Note: this
    function is the bookkeeping the planner uses for projected states; it does
    NOT itself enforce `is_applicable` — the planner does (planner.py:122).
    """
    new_counts = dict(inv.item_count)
    new_counts[drop_item] = new_counts.get(drop_item, 0) + 1
    return replace(inv, used=inv.used + 1, item_count=new_counts)


def apply_monster_drops_pure(inv: GatherInv, drops: tuple[str, ...]) -> GatherInv:
    """Mint one of each `drops` code into the inventory, BREAKING when full so the
    planner never mints past `cap`. Models the loot a kill yields (the planner's
    projected state for `FightAction.apply`). Proved in
    formal/Formal/MonsterDropApply.lean: counts never decrease (monotone), and
    when every drop fits (`used + len(drops) <= cap`) each drop's count rises by
    its multiplicity — so a `needed:N` goal over a monster drop is reachable."""
    for drop_item in drops:
        if inv.used >= inv.cap:
            break
        inv = gather_apply_pure(inv, drop_item)
    return inv


def gather_batch_size_pure(inv: GatherInv, demand: int, drop_item: str) -> int:
    """Units of `drop_item` one batched gather may mint NOW.

    `min(demand, quantity headroom)`, or 0 when the drop needs a NEW stack and
    no slot is free. The slot test matches `gather_is_applicable_pure`'s: a new
    code needs a free slot, growing a held code does not. Bounding by
    `cap - used` is what makes `gather_apply_batch_pure` unable to mint past
    `inventory_max`.
    """
    if demand <= 0:
        return 0
    if drop_item not in inv.item_count and (inv.slots_max - inv.slots_used) < 1:
        return 0
    return max(0, min(demand, inv.cap - inv.used))


def gather_apply_batch_pure(inv: GatherInv, drop_item: str, qty: int) -> GatherInv:
    """Mint `qty` of `drop_item`, BREAKING when full so the planner never mints
    past `cap` — the same fold-with-break shape as `apply_monster_drops_pure`.
    `qty = 1` is `gather_apply_pure` exactly."""
    for _ in range(max(0, qty)):
        if inv.used >= inv.cap:
            break
        inv = gather_apply_pure(inv, drop_item)
    return inv
