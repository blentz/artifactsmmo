import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.LifecycleBound
import Formal.Liveness.LifecycleBound2
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Mathlib.Tactic

/-! # LifecycleBound3 — Item 1e: structural composition for level advance

Composes the structural building blocks (Items 1a/c/d) into a real
level-advance argument that doesn't depend on the
`lifecycle_progress_from_bounds` axiom for the same shape — under
finite-step composition.

The argument:
  1. `bounded_plan_reaches_complete` (Item 1c): finite K-step plan
     reaches `phase = .complete`.
  2. `lifecycle_progress_from_bounds_step` (Item 1e in
     LIV003Decomposition): one more `.completeTask` grants +10 xp.
  3. K+1-step plan reaches a state with strictly higher xp.

The level-rollover composition (xp → level when xp ≥ xpToNextLevel
level) is supplied by `applyActionKind .fight`'s rollover branch in
Plan.lean (Phase 21c), but composing it with completeTask's +10 grant
requires modeling the cumulative xp accumulation across multiple
completions. That's bounded by `(xpToNextLevel level) / 10` completions
per level advance.

This module ships the xp-grant theorem at K+1 steps (the structural
piece). The full ceil-iteration-to-level-up remains as a deferred
arithmetic composition (manageable in a future phase).

NO new axioms.
-/

namespace Formal.Liveness.LifecycleBound3

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.LifecycleBound
open Formal.Liveness.LifecycleBound2
open Formal.Liveness.LIV003Decomposition

/-! ## Composition: K+1-step plan grants xp -/

/-- For any state with feasible task in progress, the
    K+1 = (taskTotal - taskProgress) + 1 step plan (K `.taskTrade` +
    1 `.completeTask`) reaches a state with xp = s.xp + 10. -/
theorem bounded_plan_plus_complete_grants_xp (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (hFeas : s.taskFeasibleProjected = true) :
    let K := s.taskTotal - s.taskProgress
    let plan : Plan := List.replicate K .taskTrade ++ [.completeTask]
    (applyPlan plan s).xp = s.xp + taskCompleteXpEstimate := by
  -- Step 1: apply K .taskTrade reaches phase = .complete.
  set K := s.taskTotal - s.taskProgress with hKDef
  set tradePlan : Plan := List.replicate K .taskTrade with htDef
  have hTradePhase :
      (applyPlan tradePlan s).taskLifecyclePhase = TaskLifecyclePhase.complete :=
    Formal.Liveness.TaskCompleteReachable.taskComplete_reachable s hCode hTot hLT
  -- Step 2: the trade chain preserves xp (taskTrade doesn't grant xp).
  have hTradeXp : (applyPlan tradePlan s).xp = s.xp := by
    -- Prove via induction: each .taskTrade preserves xp.
    have aux : ∀ n t, (applyPlan (List.replicate n .taskTrade) t).xp = t.xp := by
      intro n
      induction n with
      | zero => intro t; simp [applyPlan]
      | succ k ih =>
        intro t
        show (applyPlan (.taskTrade :: List.replicate k .taskTrade) t).xp = t.xp
        rw [applyPlan_cons, ih]
        rfl
    rw [htDef, aux]
  -- Step 3: apply .completeTask grants +10 xp (Item 1e step lemma).
  have hSplit : applyPlan (tradePlan ++ [.completeTask]) s
              = applyActionKind .completeTask (applyPlan tradePlan s) := by
    simp [applyPlan, List.foldl_append]
  show (applyPlan (tradePlan ++ [.completeTask]) s).xp
        = s.xp + taskCompleteXpEstimate
  rw [hSplit]
  rw [lifecycle_progress_from_bounds_step (applyPlan tradePlan s) hTradePhase]
  rw [hTradeXp]

/-! ## Existential level-advance witness -/

/-- Existence of a plan that grants xp. The follow-up xp/level rollover
    composition (via .fight rollover or cumulative completeTask grants
    until xp ≥ xpToNextLevel level) is left for Item 1f. -/
theorem feasible_task_grants_xp (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (hFeas : s.taskFeasibleProjected = true) :
    ∃ plan : Plan,
      (applyPlan plan s).xp ≥ s.xp + taskCompleteXpEstimate := by
  refine ⟨List.replicate (s.taskTotal - s.taskProgress) .taskTrade
            ++ [.completeTask], ?_⟩
  rw [bounded_plan_plus_complete_grants_xp s hCode hTot hLT hFeas]

end Formal.Liveness.LifecycleBound3
