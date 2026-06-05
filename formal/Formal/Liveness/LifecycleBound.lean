import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.TaskCompleteReachable
import Mathlib.Tactic

/-! # Lifecycle bound (Perimeter Item 1a partial discharge)

Refines `taskCancelFires` to be conditional on `taskFeasibleProjected`
(NEW State field). When `taskFeasibleProjected = true`, the refined
taskCancel doesn't fire — mirroring production's
`task_decision == PURSUE` semantics — which lets the lifecycle progress
toward `.complete` via `.taskTrade`.

This is the structural piece for discharging `accept_cancel_loop_bound`.
The discharge proceeds in stages:
  1a (this module): refined `taskCancelFires_refined`. Step lemmas
                    showing per-cycleStep behavior under feasibility.
  1b: bounded reach `.complete` under feasibility.
  1c: discharge `accept_cancel_loop_bound` conditionally.
  1d: discharge `lifecycle_progress_from_bounds` via 1c + LIV-002.
  1e: drop both axioms from allow-list.

NO new axioms. Pure structural step lemma.
-/

namespace Formal.Liveness.LifecycleBound

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable

/-- Refined taskCancel firing predicate: production's
    `task_decision == PIVOT` only triggers when learning store indicates
    infeasibility. The Lean abstraction gates on
    `taskFeasibleProjected`: false = PIVOT (cancel fires), true = PURSUE
    (cancel inactive). -/
def taskCancelFiresRefined (s : State) : Bool :=
  (decide (s.taskLifecyclePhase = .accepted)
   || decide (s.taskLifecyclePhase = .inProgress))
  && !s.taskFeasibleProjected

/-- Step lemma: under feasibility, refined cancel doesn't fire from
    `.accepted`. Establishes that taskCancelFires_refined does not
    block the .accepted → .complete trajectory. -/
theorem taskCancelFiresRefined_inactive_when_feasible (s : State)
    (_hAccepted : s.taskLifecyclePhase = .accepted)
    (hFeas : s.taskFeasibleProjected = true) :
    taskCancelFiresRefined s = false := by
  show ((decide (s.taskLifecyclePhase = .accepted)
         || decide (s.taskLifecyclePhase = .inProgress))
        && !s.taskFeasibleProjected) = false
  rw [hFeas]
  simp

/-- Step lemma: same for `.inProgress`. -/
theorem taskCancelFiresRefined_inactive_when_feasible_inProgress (s : State)
    (_hInProgress : s.taskLifecyclePhase = .inProgress)
    (hFeas : s.taskFeasibleProjected = true) :
    taskCancelFiresRefined s = false := by
  show ((decide (s.taskLifecyclePhase = .accepted)
         || decide (s.taskLifecyclePhase = .inProgress))
        && !s.taskFeasibleProjected) = false
  rw [hFeas]
  simp

/-- `.taskTrade` preserves `taskFeasibleProjected`. (The action neither
    consumes nor updates the learning-store-derived flag — production's
    task_decision is recomputed each cycle, but for the Lean structural
    claim we treat the flag as a state-carried invariant.) -/
theorem taskTrade_preserves_feasible (s : State) :
    (applyActionKind .taskTrade s).taskFeasibleProjected
      = s.taskFeasibleProjected := by
  rfl

/-- K-step `.taskTrade` preserves `taskFeasibleProjected`. -/
theorem replicate_taskTrade_preserves_feasible :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .taskTrade) s).taskFeasibleProjected
        = s.taskFeasibleProjected := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show ((applyPlan (.taskTrade :: List.replicate k .taskTrade) s)).taskFeasibleProjected = s.taskFeasibleProjected
    rw [applyPlan_cons]
    rw [ih (applyActionKind .taskTrade s)]
    rw [taskTrade_preserves_feasible]

/-- **Lifecycle bound under feasibility**.

    For any state with an accepted/in-progress task and
    `taskFeasibleProjected = true`, the K-step `.taskTrade` chain (where
    K = taskTotal - taskProgress) reaches `phase = .complete`. The
    refined taskCancelFiresRefined does NOT fire throughout (feasibility
    is preserved by `.taskTrade`).

    Composes Phase 23d-6's `taskComplete_reachable` (which already
    proves the `.complete` reach) with the feasibility-preservation
    lemma above. -/
theorem lifecycle_reaches_complete_when_feasible (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (_hFeas : s.taskFeasibleProjected = true) :
    let s' := applyPlan (List.replicate (s.taskTotal - s.taskProgress) .taskTrade) s
    s'.taskLifecyclePhase = TaskLifecyclePhase.complete
    ∧ s'.taskFeasibleProjected = s.taskFeasibleProjected := by
  refine ⟨taskComplete_reachable s hCode hTot hLT, ?_⟩
  exact replicate_taskTrade_preserves_feasible _ s

end Formal.Liveness.LifecycleBound
