import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.PursueTaskSelection
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.MeansKind
import Mathlib.Tactic

/-! # InProgressDecidesWithSelection — Item 3c

Reformulates `inProgress_decides_within_threshold` to replace the
`hpursue` trajectory hypothesis with the discharged
`pursueSelectionConditions` bundle from Item 3a/3b.

Both forms coexist:
  • Original `inProgress_decides_within_threshold` in
    `LIV003Decomposition` (takes `hpursue` directly).
  • New `inProgress_decides_within_threshold_with_selection_conditions`
    in this module (takes `pursueSelectionConditions` instead).

The new form lets downstream consumers establish the lifecycle bound
WITHOUT axiom-shaped trajectory hypotheses — they pass the structural
selection conditions and the new theorem internally invokes
`hpursue_under_conditions` to satisfy the old `hpursue` shape.

NO new axioms.
-/

namespace Formal.Liveness.InProgressDecidesWithSelection

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.LIV003Decomposition
open Formal.Liveness.PursueTaskSelection

/-- **Item 3c**: replaces `hpursue` with `pursueSelectionConditions`. -/
theorem inProgress_decides_within_threshold_with_selection_conditions
    (s : State) (cycleStepN : Nat → State → State)
    (hsucc : ∀ n s', cycleStepN (n+1) s' = cycleStepN n (cycleStep s'))
    (hzero : ∀ s', cycleStepN 0 s' = s')
    (hphase : s.taskLifecyclePhase = .inProgress)
    (hPursueConds : ∀ (s' : State), s'.taskLifecyclePhase = .inProgress →
                    pursueSelectionConditions s')
    (hattempts_init :
      s.actionsAttempted ≤ lowYieldSampleThreshold) :
    ∃ k ≤ lowYieldSampleThreshold,
      ProductionLadder.lowYieldCancelFires (cycleStepN k s) = true
      ∨ (cycleStepN k s).taskLifecyclePhase = .complete := by
  -- Derive the old hpursue shape from the bundle via 3b.
  have hpursue : ∀ s' : State, s'.taskLifecyclePhase = .inProgress →
                  cycleStep s' = applyActionKind .taskTrade s' := by
    intro s' hphase'
    exact hpursue_under_conditions s' hphase' (hPursueConds s' hphase')
  -- Apply the original theorem.
  exact inProgress_decides_within_threshold
          s cycleStepN hsucc hzero hphase hpursue hattempts_init

end Formal.Liveness.InProgressDecidesWithSelection
