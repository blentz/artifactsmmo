import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.MeansKind
import Mathlib.Tactic

/-! # PursueTaskSelection — Item 3a/b

The `hpursue` hypothesis in
`Formal.Liveness.LIV003Decomposition.inProgress_decides_within_threshold`
asserts:

    ∀ s', s'.taskLifecyclePhase = .inProgress →
          cycleStep s' = applyActionKind .taskTrade s'

That is the strongest form: at every `.inProgress` state, the production
ladder picks `.pursueTask` (which maps to `.taskTrade`). In production,
this only holds when no higher-priority means fires.

This module:

  • 3a — defines `pursueSelectionConditions s`: the predicate bundle
    asserting that NO ladder slot above `.pursueTask` fires on `s`.
  • 3b — proves `productionLadder s = some .pursueTask` whenever
    `pursueSelectionConditions s` holds AND `pursueTaskFires s = true`.
  • Item 3 corollary: `cycleStep s = applyActionKind .taskTrade s`
    when the conditions hold (i.e., the same conclusion as `hpursue`).

NO new axioms.
-/

namespace Formal.Liveness.PursueTaskSelection

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep

/-- Item 3a: bundle predicate. None of the 13 ladder slots above
    `.pursueTask` fires (12 original + `.craftRelief` added between
    `.discardCritical` and `.depositFull`). -/
def pursueSelectionConditions (s : State) : Prop :=
  hpCriticalFires s = false
  ∧ bankUnlockFires s = false
  ∧ reachUnlockLevelFires s = false
  ∧ discardCriticalFires s = false
  ∧ craftReliefFires s = false
  ∧ depositFullFires s = false
  ∧ discardHighFires s = false
  ∧ claimPendingFires s = false
  ∧ completeTaskFires s = false
  ∧ sellPressuredFires s = false
  ∧ lowYieldCancelFires s = false
  ∧ taskCancelFires s = false
  ∧ objectiveStepFires s = false

/-- Item 3b: under `pursueSelectionConditions` plus `pursueTaskFires`,
    the ladder picks `.pursueTask`. -/
theorem productionLadder_eq_pursueTask
    (s : State)
    (hConds : pursueSelectionConditions s)
    (hPursue : pursueTaskFires s = true) :
    productionLadder s = some .pursueTask := by
  unfold productionLadder
  -- allInLadderOrder = [.hpCritical, .bankUnlock, .reachUnlockLevel,
  --   .discardCritical, .depositFull, .discardHigh, .claimPending,
  --   .completeTask, .sellPressured, .lowYieldCancel, .taskCancel,
  --   .objectiveStep, .pursueTask, .acceptTask, .taskExchange,
  --   .sellIdle, .bankExpand, .wait]
  show MeansKind.allInLadderOrder.findSome?
        (fun k => if fires k s then some k else none)
      = some .pursueTask
  obtain ⟨h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13⟩ := hConds
  simp only [MeansKind.allInLadderOrder, List.findSome?,
             fires, h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13,
             hPursue, if_true]
  rfl

/-- Item 3 corollary: under the conditions, `cycleStep` applies
    `.taskTrade`. This is the same conclusion as the `hpursue`
    hypothesis. -/
theorem cycleStep_eq_taskTrade
    (s : State)
    (hConds : pursueSelectionConditions s)
    (hPursue : pursueTaskFires s = true) :
    cycleStep s = applyActionKind .taskTrade s := by
  unfold cycleStep
  rw [productionLadder_eq_pursueTask s hConds hPursue]
  rfl

/-- At `.inProgress` phase, `pursueTaskFires` is true (by Phase 23c-3b's
    `pursueTaskFires := decide (phase ∈ {.accepted, .inProgress})`
    definition mirror). -/
theorem pursueTaskFires_when_inProgress (s : State)
    (hPhase : s.taskLifecyclePhase = .inProgress) :
    pursueTaskFires s = true := by
  unfold pursueTaskFires
  rw [hPhase]
  rfl

/-- Item 3 headline: at `.inProgress` with selection conditions,
    `cycleStep` applies `.taskTrade`. Specialises `cycleStep_eq_taskTrade`
    to a state-phase precondition more convenient for the `hpursue`
    discharge. -/
theorem hpursue_under_conditions
    (s : State)
    (hPhase : s.taskLifecyclePhase = .inProgress)
    (hConds : pursueSelectionConditions s) :
    cycleStep s = applyActionKind .taskTrade s :=
  cycleStep_eq_taskTrade s hConds (pursueTaskFires_when_inProgress s hPhase)

end Formal.Liveness.PursueTaskSelection
