import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Mathlib.Tactic

/-! # TaskPoolSemantics — Item 1g-A2 local lemmas

Local behavioural lemmas for the new pool semantics added in
`Plan.applyActionKind`:

  • `.acceptTask`  — picks the first `taskPool` code not in
    `taskCodesSeen`; falls back to `acceptTaskPlaceholderCode`.
  • `.taskCancel`  — cons-prepends the current `taskCode` onto
    `taskCodesSeen` (no-op if `taskCode = none`).

These four lemmas form the local-step basis for the trajectory-level
pigeonhole bound (Item 1g-A2 main theorem, deferred to next sub-item).

NO new axioms.
-/

namespace Formal.Liveness.TaskPoolSemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure

/-- `.acceptTask` does NOT mutate `taskCodesSeen`. -/
theorem acceptTask_preserves_seen (s : State) :
    (applyActionKind .acceptTask s).taskCodesSeen = s.taskCodesSeen := rfl

/-- `.acceptTask` does NOT mutate `taskPool`. -/
theorem acceptTask_preserves_pool (s : State) :
    (applyActionKind .acceptTask s).taskPool = s.taskPool := rfl

/-- `.acceptTask` picks the first fresh `taskPool` code when one exists.
    Reduces to `List.find?` semantics on the predicate
    `decide (¬ c ∈ taskCodesSeen)`. -/
theorem acceptTask_taskCode_eq (s : State) :
    (applyActionKind .acceptTask s).taskCode
    = some ((s.taskPool.find? (fun c => decide (¬ (c ∈ s.taskCodesSeen)))).getD
              acceptTaskPlaceholderCode) := rfl

/-- `.taskCancel` cons-prepends the current `taskCode` (when present)
    onto `taskCodesSeen`. -/
theorem taskCancel_seen_cons (s : State) (c : String)
    (hc : s.taskCode = some c) :
    (applyActionKind .taskCancel s).taskCodesSeen = c :: s.taskCodesSeen := by
  show (match s.taskCode with
        | some c' => c' :: s.taskCodesSeen
        | none => s.taskCodesSeen) = c :: s.taskCodesSeen
  rw [hc]

/-- `.taskCancel` with no active task leaves `taskCodesSeen` unchanged. -/
theorem taskCancel_seen_none (s : State) (hc : s.taskCode = none) :
    (applyActionKind .taskCancel s).taskCodesSeen = s.taskCodesSeen := by
  show (match s.taskCode with
        | some c' => c' :: s.taskCodesSeen
        | none => s.taskCodesSeen) = s.taskCodesSeen
  rw [hc]

/-- `.taskCancel` does NOT mutate `taskPool`. -/
theorem taskCancel_preserves_pool (s : State) :
    (applyActionKind .taskCancel s).taskPool = s.taskPool := rfl

/-- Length of `taskCodesSeen` grows by at most 1 across a `.taskCancel`. -/
theorem taskCancel_seen_length_le_succ (s : State) :
    (applyActionKind .taskCancel s).taskCodesSeen.length
      ≤ s.taskCodesSeen.length + 1 := by
  cases hc : s.taskCode with
  | none =>
    rw [taskCancel_seen_none s hc]; omega
  | some c =>
    rw [taskCancel_seen_cons s c hc]
    simp

end Formal.Liveness.TaskPoolSemantics
