import Formal.StepDispatch
import Formal.Extracted.MinGathers

/-!
# Extracted bridges, part 6 (P3d): MinGathers.

`min_gathers.py` is the planner's pure gather lower bound — the
`UpgradeEquipmentGoal.is_plannable` unreachability gate and the Piece-C
`gather_step_target` feasibility router both decide on it. The hand model
`Formal.StepDispatch.minGathers` was aligned to the Python threaded-CONSUME
semantics in P3d (the P2c ShoppingList fidelity gap — a constant-credit hand
model double-credits shared stock on DAG recipes — closed for `min_gathers`),
and both sides share the extracted encoding (String items, Int quantities,
insertion-ordered association-list dicts), so the bridge is a plain pointwise
equality over ALL inputs — trees and DAGs alike — proved by structural
induction on the fuel. Every `Formal.StepDispatch` gather-cost theorem
(flat raw cost, the `gatherTarget_*` soundness trio's cost premises)
transfers to the extracted def through it.

No sorry/admit, no new axioms; core-only (safety-module convention).
-/

namespace Extracted.Bridges

/-- The extracted dict read IS the hand `Formal.ShoppingList.getD` (same
equations; the hand `minGathers` shares the ShoppingList dict encoding). -/
private theorem mg_dictGetD_eq {α : Type} (m : List (String × α))
    (k : String) (d : α) :
    Extracted.MinGathers._dictGetD m k d = Formal.ShoppingList.getD m k d := by
  induction m with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    simp only [Extracted.MinGathers._dictGetD, Formal.ShoppingList.getD, ih]

/-- The extracted dict update IS the hand `Formal.ShoppingList.setD` (same
equations). -/
private theorem mg_dictSet_eq {α : Type} (m : List (String × α))
    (k : String) (v : α) :
    Extracted.MinGathers._dictSet m k v = Formal.ShoppingList.setD m k v := by
  induction m with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    simp only [Extracted.MinGathers._dictSet, Formal.ShoppingList.setD, ih]

/-- BRIDGE (universal): the extracted `_min_gathers` equals the hand
`Formal.StepDispatch.minGathers` for EVERY fuel, item, quantity, recipe
environment and threaded `(total, owned)` state — tree or DAG alike. -/
theorem min_gathers_node_bridge :
    ∀ (fuel : Nat) (item : String) (qty : Int)
      (recipes : List (String × List (String × Int)))
      (state : Int × List (String × Int)),
      Extracted.MinGathers._min_gathers fuel item qty recipes state
        = Formal.StepDispatch.minGathers fuel item qty recipes state := by
  intro fuel
  induction fuel with
  | zero => intro item qty recipes state; rfl
  | succ n ih =>
    intro item qty recipes state
    simp only [Extracted.MinGathers._min_gathers, Formal.StepDispatch.minGathers,
      mg_dictGetD_eq, mg_dictSet_eq, ih, decide_eq_true_eq,
      Int.ofNat_eq_natCast, Int.natCast_eq_zero]

/-- BRIDGE (universal): the extracted `min_gathers` IS the hand
`Formal.StepDispatch.minGathersCount` on every input — the seeded-fuel,
zero-total API both `gather_step_target` and the `is_plannable` gate call.
Every hand gather-cost theorem transfers to the extracted def. -/
theorem min_gathers_bridge (item : String) (qty : Int)
    (recipes : List (String × List (String × Int)))
    (owned : List (String × Int)) :
    Extracted.MinGathers.min_gathers item qty recipes owned
      = Formal.StepDispatch.minGathersCount item qty recipes owned := by
  show (Extracted.MinGathers._min_gathers
        (Int.toNat ((Int.ofNat (List.length recipes)) + 1)) item qty recipes
        (0, owned)).1
    = (Formal.StepDispatch.minGathers (recipes.length + 1) item qty recipes
        (0, owned)).1
  rw [show Int.toNat ((Int.ofNat (List.length recipes)) + 1)
      = List.length recipes + 1 by rw [Int.ofNat_eq_natCast]; omega]
  rw [min_gathers_node_bridge]

/-- THE flat-gather contract, restated on the EXTRACTED definition: a RAW
(empty/absent recipe) step with no holdings costs exactly its quantity —
the budget-feasible FLAT gather the deepest-step route relies on. -/
theorem min_gathers_raw_unowned_extracted (item : String) (qty : Nat)
    (recipes : List (String × List (String × Int)))
    (hraw : (Formal.ShoppingList.getD recipes item []).length = 0) :
    Extracted.MinGathers.min_gathers item (qty : Int) recipes [] = (qty : Int) := by
  rw [min_gathers_bridge]
  unfold Formal.StepDispatch.minGathersCount
  exact Formal.StepDispatch.minGathers_raw_unowned recipes.length item qty
    recipes hraw

/-- The DAG double-credit witness pinned on the EXTRACTED def: 2 banked ore
shared by two parents cover only ONE branch — 2 real gathers remain (the
constant-credit model said 0). Kernel-checks that the extracted image carries
the consume accounting. -/
example :
    Extracted.MinGathers.min_gathers "sword" 1
        [("sword", [("a", 1), ("b", 1)]), ("a", [("ore", 2)]), ("b", [("ore", 2)])]
        [("ore", 2)]
      = 2 := by decide

end Extracted.Bridges
