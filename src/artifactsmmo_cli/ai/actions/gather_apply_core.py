"""Pure core for `GatherAction.is_applicable` / `.apply` inventory bookkeeping.

This module isolates the minimal transition GatherAction performs on the
inventory: the planner-side mint of `+1` of `drop_item`, and the slot-availability
precondition (`inventory_free >= MIN_FREE_SLOTS`).

Two levels of assurance cover these cores, and they cover DIFFERENT things.

The Lean module `formal/Formal/GatherApply.lean` proves FOUR contracts, all of
them over `Inv := {used : Nat, cap : Nat}` (GatherApply.lean:35). That structure
has NO item dictionary, so nothing below about `item_count` is proved there —
the Lean file says so itself at line 195 ("the per-key item-dict bookkeeping is
exercised by the Python unit tests"). What Lean proves:

* `gather_is_applicable_pure(inv, k, drop_item)` returns True iff `max - used
  >= k` AND (when `drop_item` is known) the drop fits the slot cap: a NEW drop
  code needs a free slot, growing a held code does not (`inventory_room.has_room`).
  The slot rule is proved over a `hasDrop : Bool`, not over the code itself.
* `gather_apply_pure(inv, code)` produces an inventory whose `used = used + 1`
  and `max` unchanged (`applyN_used`, `applyN_cap`).
* SAFETY: `gather_is_applicable_pure(inv, k) and k >= 1` implies the post-state
  satisfies `used' <= max` (the planner cannot mint past `inventory_max` in one
  step), and chaining `n` applies starting from `inventory_free >= n` preserves
  `used <= max` for the entire chain (`chain_safe`).
* `gather_apply_batch_pure(inv, drop_item, qty)` mints `qty` in one step with
  `used' = min(used + qty, cap)` (`gather_apply_batch_used`), bounded by
  `gather_apply_batch_le_cap` and agreeing with the singleton at `qty = 1`
  (`gather_apply_batch_one`). SAFETY is this function's OWN break-on-full loop,
  not a caller-side bound: it cannot mint past `cap` for ANY `qty`, including
  one far larger than the free quantity (`gather_apply_batch_huge_qty_witness`).

The PER-KEY dictionary behaviour is pinned by tests, not by the kernel — that
`item_count[drop_item]` rises by exactly the minted amount and every other entry
is preserved bit-for-bit, for both the singleton and the batch. See
`tests/test_ai/test_gather_apply_core.py` (`test_apply_batch_mints_exactly_qty`,
`test_apply_batch_preserves_other_entries`, `test_other_items_preserved`) and
`formal/diff/test_gather_apply_diff.py`, which binds the singleton to the Lean
oracle over the used/cap projection.

`gather_batch_size_pure(inv, demand, drop_item)` is a separate sizing aid and is
NOT a safety mechanism — it reports how much of `demand` currently has room
(`min(demand, cap - used)`, or 0 when a NEW code has no free slot), reusing
`gather_is_applicable_pure`'s slot rule via `inventory_room.has_room`. It
answers a question about the CURRENT state, so a caller that runs ONCE per plan
(rather than per node) must not let its 0 stand as a final answer — see
`intermediate_batch.size_closure_gather`, which floors it at 1 while demand
remains precisely so a full bag cannot delete the gather from the whole search.

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
    """Units of `drop_item` a caller may currently REQUEST from a batched gather.

    `min(demand, quantity headroom)`, or 0 when the drop needs a NEW stack and
    no slot is free — reusing `gather_is_applicable_pure`'s slot rule via the
    shared `has_room` (a new code needs a free slot, growing a held code does
    not), rather than open-coding the same predicate a second time. This is a
    SIZING AID, not the source of `gather_apply_batch_pure`'s cap safety: that
    safety comes from `gather_apply_batch_pure`'s own break-on-full loop, which
    holds for ANY `qty` regardless of what this function returns.
    """
    if demand <= 0:
        return 0
    new_stacks = 0 if drop_item in inv.item_count else 1
    slots_free = inv.slots_max - inv.slots_used
    qty_free = inv.cap - inv.used
    if not has_room(new_stacks, added_qty=0, slots_free=slots_free, qty_free=qty_free):
        return 0
    return max(0, min(demand, qty_free))


def gather_apply_batch_pure(inv: GatherInv, drop_item: str, qty: int) -> GatherInv:
    """Mint `qty` of `drop_item`, BREAKING when full so the planner never mints
    past `cap` — the same fold-with-break shape as `apply_monster_drops_pure`.
    `qty = 1` is `gather_apply_pure` exactly."""
    for _ in range(max(0, qty)):
        if inv.used >= inv.cap:
            break
        inv = gather_apply_pure(inv, drop_item)
    return inv
