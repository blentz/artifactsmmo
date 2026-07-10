-- @concept: inventory, slot-room @property: safety
/-
Formal model of the slot+quantity inventory-room core of
`src/artifactsmmo_cli/ai/inventory_room.py` (`has_room`).

The game enforces BOTH a per-slot cap and a total-quantity cap: a NEW distinct
stack needs a free slot AND quantity headroom, while GROWING a held stack
(`newStacks = 0`) needs only quantity headroom. The Python core is

    def has_room(new_stacks, added_qty, slots_free, qty_free) -> bool:
        return new_stacks <= slots_free and added_qty <= qty_free

mirrored below over `Int` (the differential harness in
`formal/diff/test_inventory_room_diff.py` binds `has_room` to `hasRoom`).

Lean core only — no mathlib. Integer arithmetic via `omega`.
-/

namespace InventoryRoom

/-- A stack-creating action fits iff it has a free slot per new stack AND
    quantity headroom. Mirrors Python `has_room`. -/
def hasRoom (newStacks addedQty slotsFree qtyFree : Int) : Bool :=
  decide (newStacks ≤ slotsFree) && decide (addedQty ≤ qtyFree)

/-- No free slot for a new stack -> blocked, regardless of quantity room.
    The slot conjunct alone forces the result to `false`. -/
theorem hasRoom_false_of_no_slot (newStacks addedQty slotsFree qtyFree : Int)
    (h : newStacks > slotsFree) : hasRoom newStacks addedQty slotsFree qtyFree = false := by
  unfold hasRoom
  have hns : ¬ (newStacks ≤ slotsFree) := by omega
  simp [hns]

/-- No quantity room -> blocked, regardless of slots.
    The quantity conjunct alone forces the result to `false`. -/
theorem hasRoom_false_of_no_qty (newStacks addedQty slotsFree qtyFree : Int)
    (h : addedQty > qtyFree) : hasRoom newStacks addedQty slotsFree qtyFree = false := by
  unfold hasRoom
  have hq : ¬ (addedQty ≤ qtyFree) := by omega
  simp [hq]

/-- Grow-stack (`newStacks = 0`) ignores the slot cap: as long as the quantity
    fits and there is a nonnegative slot count, room is granted regardless of
    how tight the slot budget is. -/
theorem hasRoom_grow_ignores_slots (addedQty qtyFree slotsFree : Int)
    (hq : addedQty ≤ qtyFree) (hs : (0:Int) ≤ slotsFree) :
    hasRoom 0 addedQty slotsFree qtyFree = true := by
  unfold hasRoom
  simp [hq, hs]

/-! ### Non-vacuous witnesses (grounding the independence theorems on reachable
    states — see [[feedback_zero_vacuousness]]). -/

/-- Witness: a new stack with a free slot and quantity room is admitted. -/
theorem hasRoom_both_room_witness :
    hasRoom 1 5 2 10 = true := by decide

/-- Witness: a new stack blocked purely by the slot cap (qty would fit). -/
theorem hasRoom_no_slot_witness :
    hasRoom 2 5 1 10 = false := by decide

/-- Witness: blocked purely by the quantity cap (a free slot exists). -/
theorem hasRoom_no_qty_witness :
    hasRoom 1 11 5 10 = false := by decide

/-- Witness: growing a held stack past a full slot budget still fits. -/
theorem hasRoom_grow_full_slots_witness :
    hasRoom 0 5 0 10 = true := by decide

end InventoryRoom
