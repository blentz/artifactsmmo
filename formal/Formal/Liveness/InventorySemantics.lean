import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Mathlib.Tactic

/-! # InventorySemantics — Item 4a

Helper `invCount` and per-action invariance/mutation lemmas for the
new `inventoryItems` field added in Item 4a.

  • `invCount inv code` — total count of `code` across the list of
    `(code, count)` pairs (multiple entries summed). Mirrors the
    production-side `state.inventory.get(code, 0)`.
  • `applyActionKind_inventory_invariant_except_gather` — every
    action except `.gather` preserves `inventoryItems`.
  • `gather_invCount_unchanged_for_other_codes` — `.gather` only
    bumps the gatherTarget's entry; unrelated codes are unchanged.
  • `gather_invCount_increments_target` — when gatherTarget = some c,
    `.gather` increments `invCount _ c` by exactly 1.

NO new axioms.
-/

namespace Formal.Liveness.InventorySemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure

/-- Total count of `code` across the `(code, count)` pair list.
    Uses direct recursion to enable straightforward induction proofs. -/
def invCount : List (String × Nat) → String → Nat
  | [], _ => 0
  | (c, n) :: rest, code =>
    if c = code then n + invCount rest code else invCount rest code

@[simp] theorem invCount_nil (code : String) : invCount [] code = 0 := rfl

theorem invCount_cons_match (code : String) (n : Nat)
    (rest : List (String × Nat)) :
    invCount ((code, n) :: rest) code = n + invCount rest code := by
  show (if code = code then n + invCount rest code else invCount rest code)
       = n + invCount rest code
  simp

theorem invCount_cons_mismatch (code other : String) (n : Nat)
    (rest : List (String × Nat)) (h : code ≠ other) :
    invCount ((code, n) :: rest) other = invCount rest other := by
  show (if code = other then n + invCount rest other else invCount rest other)
       = invCount rest other
  simp [h]

/-- Every action EXCEPT `.gather` preserves `inventoryItems`. -/
theorem applyActionKind_inventory_invariant_except_gather
    (k : ActionKind) (s : State) (hne : k ≠ .gather) :
    (applyActionKind k s).inventoryItems = s.inventoryItems := by
  cases k with
  | gather => exact absurd rfl hne
  | _ => rfl

/-- `.gather` with no gatherTarget preserves inventory. -/
theorem gather_inventory_when_none (s : State)
    (h : s.gatherTarget = none) :
    (applyActionKind .gather s).inventoryItems = s.inventoryItems := by
  show (match s.gatherTarget with
        | some code => (code, 1) :: s.inventoryItems
        | none => s.inventoryItems) = s.inventoryItems
  rw [h]

/-- `.gather` with gatherTarget = some c cons-prepends `(c, 1)`. -/
theorem gather_inventory_when_some (s : State) (c : String)
    (h : s.gatherTarget = some c) :
    (applyActionKind .gather s).inventoryItems = (c, 1) :: s.inventoryItems := by
  show (match s.gatherTarget with
        | some code => (code, 1) :: s.inventoryItems
        | none => s.inventoryItems) = (c, 1) :: s.inventoryItems
  rw [h]

/-- `.gather` increments the target's invCount by exactly 1. -/
theorem gather_invCount_increments_target (s : State) (c : String)
    (h : s.gatherTarget = some c) :
    invCount (applyActionKind .gather s).inventoryItems c
    = invCount s.inventoryItems c + 1 := by
  rw [gather_inventory_when_some s c h]
  rw [invCount_cons_match]
  omega

/-- `.gather` doesn't change invCount for codes other than the target. -/
theorem gather_invCount_unchanged_for_other_codes (s : State) (c other : String)
    (htgt : s.gatherTarget = some c) (hne : c ≠ other) :
    invCount (applyActionKind .gather s).inventoryItems other
    = invCount s.inventoryItems other := by
  rw [gather_inventory_when_some s c htgt]
  exact invCount_cons_mismatch c other 1 s.inventoryItems hne

end Formal.Liveness.InventorySemantics
