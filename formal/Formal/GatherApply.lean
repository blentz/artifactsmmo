-- @concept: resources, items @property: safety
import Formal.InventoryRoom
/-
Formal model of the slot-bookkeeping core of
`src/artifactsmmo_cli/ai/actions/gathering.py`
(specifically `GatherAction.is_applicable` and `GatherAction.apply`).

The Python `apply` mints `+1` of `drop_item` into the inventory dict; the
planner-projected `inventory_used` therefore increases by exactly one per
chained `apply`. The planner re-checks `is_applicable` on every popped node
(`src/artifactsmmo_cli/ai/planner.py:122`), so the per-step precondition
`inventory_free >= MIN_FREE_SLOTS` is enforced on every step of a multi-step
gather chain.

`MIN_FREE_SLOTS = 3` in the Python (it is a buffer for the executed action,
which may produce ore + random bonus drops); the planner's projection only
mints `+1`, so the precondition is comfortably tight: with `MIN_FREE_SLOTS >=
1`, `apply` cannot mint past `inventory_max`. We bake the contract as `>= k`
for any `k >= 1` and instantiate `k = 3` for the production constant.

The pure cores live in
`src/artifactsmmo_cli/ai/actions/gather_apply_core.py`; the differential test
exercises `gather_apply_pure` / `gather_is_applicable_pure` against this Lean
model.

Lean core only — no mathlib. Nat arithmetic via `omega`.
-/

namespace Formal.GatherApply

/-- Minimal inventory projection: `used` is the current slot count and `cap`
is `inventory_max`. The actual item dictionary is irrelevant to the slot-
bookkeeping safety theorem; the diff test pins the per-key bookkeeping
separately. -/
structure Inv where
  used : Nat
  cap : Nat
  deriving Repr, DecidableEq

/-- `inventory_free`. Defined symmetrically to the Python property
`WorldState.inventory_free = inventory_max - inventory_used` (with `Nat`
truncating subtraction; the invariant `used ≤ cap` is the safety claim and
is maintained by `apply` when `is_applicable` held). -/
def free (i : Inv) : Nat := i.cap - i.used

/-- `MIN_FREE_SLOTS` — the production constant from `gathering.py`. -/
def MIN_FREE_SLOTS : Nat := 3

/-- The slot half of `GatherAction.is_applicable`: True iff at least `k` free
slots remain. -/
def isApplicable (i : Inv) (k : Nat) : Bool :=
  decide (k ≤ i.cap - i.used)

/-- Slot-aware `GatherAction.is_applicable`, mirroring the extended pure core
`gather_is_applicable_pure(inv, k, drop_item)`. The quantity floor
(`k ≤ cap - used`) is retained; when the drop is known (`hasDrop = true`) the
yielded stack must ALSO fit the per-slot cap via `InventoryRoom.hasRoom` — a
NEW drop code needs a free slot (`newStacks = 1`), growing a held code does not
(`newStacks = 0`). `hasDrop = false` recovers the quantity-only `isApplicable`
(the `drop_item = None` caller path). `qtyFree = cap - used`, `slotsFree =
slotsMax - slotsUsed`, `addedQty = 1` (the planner mints exactly one). -/
def isApplicableSlot (i : Inv) (k : Nat) (hasDrop : Bool)
    (newStacks slotsUsed slotsMax : Int) : Bool :=
  decide (k ≤ i.cap - i.used) &&
    (if hasDrop then
        InventoryRoom.hasRoom newStacks 1 (slotsMax - slotsUsed) ((i.cap : Int) - i.used)
      else true)

/-- Planner-projection of `GatherAction.apply` over inventory slots: mint
exactly one item, leaving `cap` unchanged. The pure core's item-dict bookkeeping
is exercised by the differential test; only the slot count matters here. -/
def apply (i : Inv) : Inv := { i with used := i.used + 1 }

/-! ### Contracts. -/

/-- `is_applicable` lower-bound: a successful check guarantees the claimed
slot floor. -/
theorem is_applicable_imp_free_ge (i : Inv) (k : Nat) :
    isApplicable i k = true → k ≤ i.cap - i.used := by
  intro h
  simp [isApplicable] at h
  exact h

/-- **Per-step safety**: under the production precondition (`k ≥ 1`) and a
passing `is_applicable` check, `apply` never overflows the inventory cap. -/
theorem apply_inventory_safe (i : Inv) (k : Nat) (hk : 1 ≤ k)
    (h : isApplicable i k = true) :
    (apply i).used ≤ i.cap := by
  have hfree := is_applicable_imp_free_ge i k h
  -- k ≤ cap - used, k ≥ 1, Nat subtraction: cap - used ≥ 1 ⇒ used + 1 ≤ cap
  simp [apply]
  omega

/-- Same theorem instantiated at the production constant `MIN_FREE_SLOTS = 3`. -/
theorem apply_inventory_safe_prod (i : Inv) (h : isApplicable i MIN_FREE_SLOTS = true) :
    (apply i).used ≤ i.cap :=
  apply_inventory_safe i MIN_FREE_SLOTS (by decide) h

/-! ### Slot-aware contracts (mirror `gather_is_applicable_pure(inv, k, drop_item)`). -/

/-- The slot-aware check still implies the quantity floor (first conjunct): a
passing `isApplicableSlot` guarantees the same `k ≤ cap - used` the quantity-only
`isApplicable` did. The slot term is strictly additive. -/
theorem isApplicableSlot_imp_free_ge (i : Inv) (k : Nat) (hasDrop : Bool)
    (newStacks slotsUsed slotsMax : Int)
    (h : isApplicableSlot i k hasDrop newStacks slotsUsed slotsMax = true) :
    k ≤ i.cap - i.used := by
  unfold isApplicableSlot at h
  simp only [Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.1

/-- **Per-step mint safety still holds** under the slot-aware check: a passing
gather (with `k ≥ 1`) cannot mint past the inventory cap. Reduces to the
existing `apply_inventory_safe` via the retained quantity floor. -/
theorem apply_inventory_safe_slot (i : Inv) (k : Nat) (hk : 1 ≤ k) (hasDrop : Bool)
    (newStacks slotsUsed slotsMax : Int)
    (h : isApplicableSlot i k hasDrop newStacks slotsUsed slotsMax = true) :
    (apply i).used ≤ i.cap := by
  have hfree := isApplicableSlot_imp_free_ge i k hasDrop newStacks slotsUsed slotsMax h
  simp only [apply]
  omega

/-- **Per-step slot safety**: a passing gather of a KNOWN drop cannot create a
stack past the slot cap — `newStacks` distinct new stacks always fit the free
slot budget (`newStacks ≤ slotsMax - slotsUsed`). For a NEW drop
(`newStacks = 1`) this witnesses a free slot; for a held drop
(`newStacks = 0`) it is trivially satisfied. -/
theorem isApplicableSlot_slot_safe (i : Inv) (k : Nat)
    (newStacks slotsUsed slotsMax : Int)
    (h : isApplicableSlot i k true newStacks slotsUsed slotsMax = true) :
    newStacks ≤ slotsMax - slotsUsed := by
  unfold isApplicableSlot InventoryRoom.hasRoom at h
  simp only [if_true, Bool.and_eq_true, decide_eq_true_eq] at h
  omega

/-- Witness: a NEW drop (`newStacks = 1`) at 0 free slots is BLOCKED even though
quantity has ample room (`cap - used = 104`). Mirrors the Python slot-exhaustion
test `test_gather_blocked_when_new_drop_needs_slot_but_none_free`. -/
theorem isApplicableSlot_new_drop_no_slot_witness :
    isApplicableSlot { used := 20, cap := 124 } 1 true 1 20 20 = false := by decide

/-- Witness: growing a HELD drop (`newStacks = 0`) at 0 free slots is ALLOWED
(quantity permitting). Mirrors the Python test
`test_gather_allowed_when_drop_grows_held_stack_with_no_free_slot`. -/
theorem isApplicableSlot_held_drop_no_slot_witness :
    isApplicableSlot { used := 20, cap := 124 } 1 true 0 20 20 = true := by decide

/-- Iterated `apply`. -/
def applyN : Inv → Nat → Inv
  | i, 0 => i
  | i, n + 1 => apply (applyN i n)

/-- `applyN` increases `used` by exactly `n`. -/
theorem applyN_used (i : Inv) (n : Nat) : (applyN i n).used = i.used + n := by
  induction n with
  | zero => simp [applyN]
  | succ m ih => simp [applyN, apply, ih]; omega

/-- `applyN` preserves `cap`. -/
theorem applyN_cap (i : Inv) (n : Nat) : (applyN i n).cap = i.cap := by
  induction n with
  | zero => simp [applyN]
  | succ m ih => simp [applyN, apply, ih]

/-- **Chain safety**: if the starting state has at least `n` free slots, then
after `n` chained `apply`s the inventory still has `used ≤ cap`. This is the
per-chain invariant the planner depends on (the planner's per-pop
`is_applicable` re-check at `planner.py:122` enforces the per-step `k ≥
MIN_FREE_SLOTS` precondition, but even under the weaker per-step `k ≥ 1`
precondition the chain stays in-band). -/
theorem chain_safe (i : Inv) (n : Nat) (hwf : i.used ≤ i.cap)
    (h : n ≤ i.cap - i.used) :
    (applyN i n).used ≤ i.cap := by
  rw [applyN_used]
  omega

/-- Witness: non-vacuous chain safety — a state with 3 free slots admits 3
chained applies without overflow. Pins production constant `MIN_FREE_SLOTS = 3`
as a real, reachable witness (not an unreachable-hypothesis dodge). -/
theorem chain_safe_min_free_witness :
    let i : Inv := { used := 5, cap := 8 }
    (applyN i 3).used ≤ i.cap := by
  decide

/-- Witness: `is_applicable` holds at the boundary `used = cap - k`. -/
theorem is_applicable_boundary_witness :
    isApplicable { used := 5, cap := 8 } 3 = true := by decide

/-- Witness: `is_applicable` fails one slot below the boundary. -/
theorem is_applicable_off_boundary_witness :
    isApplicable { used := 6, cap := 8 } 3 = false := by decide

/-! ### Batched mint (mirror `gather_apply_batch_pure` / `gather_batch_size_pure`
in `gather_apply_core.py`). Only the slot count matters here, exactly as for
`apply`/`applyN` above; the per-key item-dict bookkeeping is exercised by the
Python unit tests. -/

/-- Iterated `apply` that BREAKS the moment the inventory is full, mirroring
the Python `gather_apply_batch_pure`'s fold-with-break: of the `n` requested
steps, each one first checks whether `used ≥ cap` and stops (returning the
current state unchanged) the instant it is, exactly like
`apply_monster_drops_pure`'s loop. -/
def applyBatch : Inv → Nat → Inv
  | i, 0 => i
  | i, n + 1 => if i.used ≥ i.cap then i else applyBatch (apply i) n

/-- **Batched mint is capped**: from a well-formed inventory (`used ≤ cap`,
the invariant `apply_inventory_safe`/`chain_safe` maintain), `n` batched
applies land exactly at `min (used + n) cap` — the break neither overshoots
nor stops early while room remains. -/
theorem gather_apply_batch_used (i : Inv) (n : Nat) (hwf : i.used ≤ i.cap) :
    (applyBatch i n).used = min (i.used + n) i.cap := by
  induction n generalizing i with
  | zero => simp [applyBatch]; omega
  | succ m ih =>
    unfold applyBatch
    split
    · next h => omega
    · next h =>
      have hwf' : (apply i).used ≤ (apply i).cap := by simp only [apply]; omega
      have := ih (apply i) hwf'
      simp only [apply] at this ⊢
      omega

/-- **Batch of one is the unbatched mint**: with room for at least one more
item (the precondition every real caller of `apply` already establishes via
`is_applicable`), a single batched step agrees with `apply` exactly —
`gather_apply_batch_pure(inv, code, 1) == gather_apply_pure(inv, code)`. -/
theorem gather_apply_batch_one (i : Inv) (h : i.used < i.cap) :
    applyBatch i 1 = apply i := by
  have hne : ¬ i.used ≥ i.cap := by omega
  simp [applyBatch, hne]

/-- **SAFETY**: the batched mint never exceeds `cap`, for ANY `qty` — including
a demand far larger than the free quantity. Starting from a well-formed
inventory, the break in `applyBatch` (not the caller pre-sizing `qty`) is what
makes this hold for an arbitrarily large `n`. -/
theorem gather_apply_batch_le_cap (i : Inv) (n : Nat) (hwf : i.used ≤ i.cap) :
    (applyBatch i n).used ≤ i.cap := by
  rw [gather_apply_batch_used i n hwf]
  exact Nat.min_le_right _ _

/-- Witness: a demand (`n = 50`) far larger than the headroom (`cap - used =
2`) still lands exactly at `cap`, never past it. Grounds `gather_apply_batch_
le_cap` on a reachable, non-vacuous instance rather than an unreachable
hypothesis. -/
theorem gather_apply_batch_huge_qty_witness :
    let i : Inv := { used := 18, cap := 20 }
    (applyBatch i 50).used = 20 := by decide

end Formal.GatherApply
