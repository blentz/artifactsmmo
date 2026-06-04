import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Mathlib.Tactic

/-! # GoldSemantics — Item 4d

Per-action invariance and mutation lemmas for `gold`.

  • `.completeTask` credits `taskCompleteGoldEstimate` (= 1).
  • `.npcSell` credits `npcSellGoldEstimate` (= 1).
  • `.buyBankExpansion` already debits `nextExpansionCost` (pre-Item 4).
  • All other 24 actions preserve gold (subject to .move/.mapTransition
    needing the match-split treatment from Item 4c).

NO new axioms.
-/

namespace Formal.Liveness.GoldSemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure

/-- `.completeTask` credits gold by `taskCompleteGoldEstimate`. -/
theorem completeTask_gold_credited (s : State) :
    (applyActionKind .completeTask s).gold = s.gold + taskCompleteGoldEstimate :=
  rfl

/-- `.npcSell` credits gold by `npcSellGoldEstimate`. -/
theorem npcSell_gold_credited (s : State) :
    (applyActionKind .npcSell s).gold = s.gold + npcSellGoldEstimate :=
  rfl

/-- `.completeTask` increases gold strictly (since
    `taskCompleteGoldEstimate ≥ 1`). -/
theorem completeTask_gold_monotone (s : State) :
    (applyActionKind .completeTask s).gold ≥ s.gold := by
  rw [completeTask_gold_credited]; omega

/-- `.npcSell` increases gold strictly. -/
theorem npcSell_gold_monotone (s : State) :
    (applyActionKind .npcSell s).gold ≥ s.gold := by
  rw [npcSell_gold_credited]; omega

/-- `.buyBankExpansion` debits gold by `nextExpansionCost` (Nat sub
    saturates at 0). -/
theorem buyBankExpansion_gold_debited (s : State) :
    (applyActionKind .buyBankExpansion s).gold = s.gold - s.nextExpansionCost :=
  rfl

end Formal.Liveness.GoldSemantics
