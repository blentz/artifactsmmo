import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.TaskPoolSemantics
import Mathlib.Tactic

/-! # TaskPoolTrajectory — Item 1g-A3 trajectory-level lemmas

Lifts `TaskPoolSemantics`'s per-action lemmas to whole trajectories:

  • `applyActionKind_pool_invariant` — every action preserves `taskPool`.
  • `applyActionKind_seen_length_monotone` — `taskCodesSeen.length` is
    non-decreasing across any action.
  • `applyActionKind_seen_length_le_succ` — `taskCodesSeen.length` grows
    by at most 1 per action.
  • `cycleStep_pool_invariant`, `cycleStep_seen_length_monotone`,
    `cycleStep_seen_length_le_succ` — same properties on `cycleStep`.
  • `cycleStepN_pool_invariant`, `cycleStepN_seen_length_le_add` —
    iterated cycleStep bounds.

These are the per-step bounds used by the pigeonhole argument in
Item 1g-A4 to prove `accept_cancel_loop_bound_proven`.

NO new axioms.
-/

namespace Formal.Liveness.TaskPoolTrajectory

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.CycleStep
open Formal.Liveness.TaskPoolSemantics

/-- Every `applyActionKind` action preserves `taskPool`. -/
theorem applyActionKind_pool_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).taskPool = s.taskPool := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).taskPool = s.taskPool
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).taskPool = s.taskPool
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- `taskCodesSeen.length` is non-decreasing across any action. -/
theorem applyActionKind_seen_length_monotone (k : ActionKind) (s : State) :
    s.taskCodesSeen.length ≤ (applyActionKind k s).taskCodesSeen.length := by
  cases k with
  | taskCancel =>
    -- Only taskCancel mutates seen; the new is c :: old or old.
    show s.taskCodesSeen.length
          ≤ (match s.taskCode with
             | some c => c :: s.taskCodesSeen
             | none => s.taskCodesSeen).length
    cases hc : s.taskCode with
    | none => simp
    | some c => simp
  | move =>
    show s.taskCodesSeen.length
          ≤ (match s.moveTarget with
             | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
             | none => s).taskCodesSeen.length
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show s.taskCodesSeen.length
          ≤ (match s.moveTarget with
             | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
             | none => s).taskCodesSeen.length
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- `taskCodesSeen.length` grows by at most 1 per action. -/
theorem applyActionKind_seen_length_le_succ (k : ActionKind) (s : State) :
    (applyActionKind k s).taskCodesSeen.length ≤ s.taskCodesSeen.length + 1 := by
  cases k with
  | taskCancel => exact taskCancel_seen_length_le_succ s
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).taskCodesSeen.length ≤ s.taskCodesSeen.length + 1
    cases s.moveTarget <;> (show s.taskCodesSeen.length ≤ s.taskCodesSeen.length + 1; omega)
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).taskCodesSeen.length ≤ s.taskCodesSeen.length + 1
    cases s.moveTarget <;> (show s.taskCodesSeen.length ≤ s.taskCodesSeen.length + 1; omega)
  | _ =>
    -- All other actions preserve seen exactly.
    show s.taskCodesSeen.length ≤ s.taskCodesSeen.length + 1
    omega

/-! ## cycleStep lifts -/

/-- `cycleStep` preserves `taskPool`. -/
theorem cycleStep_pool_invariant (s : State) :
    (cycleStep s).taskPool = s.taskPool := by
  unfold cycleStep
  split
  · rfl
  · rename_i k _
    split
    · rfl
    · rename_i a _ _
      exact applyActionKind_pool_invariant a s

/-- `cycleStep` is monotone on `taskCodesSeen.length`. -/
theorem cycleStep_seen_length_monotone (s : State) :
    s.taskCodesSeen.length ≤ (cycleStep s).taskCodesSeen.length := by
  unfold cycleStep
  split
  · exact Nat.le_refl _
  · split
    · exact Nat.le_refl _
    · rename_i a _ _
      exact applyActionKind_seen_length_monotone a s

/-- `cycleStep` grows `taskCodesSeen.length` by at most 1. -/
theorem cycleStep_seen_length_le_succ (s : State) :
    (cycleStep s).taskCodesSeen.length ≤ s.taskCodesSeen.length + 1 := by
  unfold cycleStep
  split
  · omega
  · split
    · omega
    · rename_i a _ _
      exact applyActionKind_seen_length_le_succ a s

/-! ## Iterated bounds

  Stated against an abstract `cycleStepN` matching `accept_cancel_loop_bound`'s
  axiom signature: a function with the recurrence
  `cycleStepN (n+1) s' = cycleStepN n (cycleStep s')` and `cycleStepN 0 s = s`.
  These bounds carry to any concrete instance. -/

/-- Iterated `cycleStep` preserves `taskPool`. -/
theorem cycleStepN_pool_invariant
    (cycleStepN : Nat → State → State)
    (hsucc : ∀ n s', cycleStepN (n+1) s' = cycleStepN n (cycleStep s'))
    (hzero : ∀ s', cycleStepN 0 s' = s')
    (s : State) (n : Nat) :
    (cycleStepN n s).taskPool = s.taskPool := by
  induction n generalizing s with
  | zero =>
    rw [hzero]
  | succ k ih =>
    rw [hsucc, ih]
    exact cycleStep_pool_invariant s

/-- Iterated `cycleStep` bounds `taskCodesSeen.length` growth by `n`. -/
theorem cycleStepN_seen_length_le_add
    (cycleStepN : Nat → State → State)
    (hsucc : ∀ n s', cycleStepN (n+1) s' = cycleStepN n (cycleStep s'))
    (hzero : ∀ s', cycleStepN 0 s' = s')
    (s : State) (n : Nat) :
    (cycleStepN n s).taskCodesSeen.length ≤ s.taskCodesSeen.length + n := by
  induction n generalizing s with
  | zero =>
    rw [hzero]; omega
  | succ k ih =>
    rw [hsucc]
    have h1 := ih (cycleStep s)
    have h2 : (cycleStep s).taskCodesSeen.length ≤ s.taskCodesSeen.length + 1 :=
      cycleStep_seen_length_le_succ s
    omega

end Formal.Liveness.TaskPoolTrajectory
