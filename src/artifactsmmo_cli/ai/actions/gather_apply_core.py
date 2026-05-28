"""Pure core for `GatherAction.is_applicable` / `.apply` inventory bookkeeping.

This module isolates the minimal transition GatherAction performs on the
inventory: the planner-side mint of `+1` of `drop_item`, and the slot-availability
precondition (`inventory_free >= MIN_FREE_SLOTS`).

The Lean module `formal/Formal/GatherApply.lean` proves three contracts on
these pure cores:

* `gather_is_applicable_pure(inv, k)` returns True iff `max - used >= k`.
* `gather_apply_pure(inv, code)` produces an inventory whose `used = used + 1`,
  `max` unchanged, and `item_count[code]` incremented by 1 (all other entries
  preserved).
* SAFETY: `gather_is_applicable_pure(inv, k) and k >= 1` implies the post-state
  satisfies `used' <= max` (the planner cannot mint past `inventory_max` in one
  step), and chaining `n` applies starting from `inventory_free >= n` preserves
  `used <= max` for the entire chain.

The planner (`src/artifactsmmo_cli/ai/planner.py`:122) re-checks
`is_applicable(node.state, ...)` on every node it pops, so chained `apply`s in
a plan ALWAYS see a fresh applicability check at each step. The safety theorem
applies per step; the chain safety is therefore a corollary of `is_applicable`
being a slot-floor.
"""
from dataclasses import dataclass, replace
from collections.abc import Mapping


@dataclass(frozen=True)
class GatherInv:
    """Minimal projection of `WorldState` that `GatherAction.apply` reads."""

    used: int                       # sum of inventory values (inventory_used)
    cap: int                        # inventory_max
    item_count: Mapping[str, int]   # inventory dict


def gather_is_applicable_pure(inv: GatherInv, min_free: int) -> bool:
    """True iff inventory has `min_free` slots available.

    Mirrors the slot half of `GatherAction.is_applicable` (the skill-level half
    is orthogonal and lives in `is_applicable` itself).
    """
    return (inv.cap - inv.used) >= min_free


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
