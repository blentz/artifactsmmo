import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.LifecycleBound
import Formal.Liveness.LifecycleBound2
import Formal.Liveness.LifecycleBound3
import Formal.Liveness.LifecycleBound4
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.PlanExists
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # LifecycleBound6 — Item 1g-B2 level-monotonicity infrastructure

Infrastructure for the trajectory-level discharge of
`lifecycle_progress_from_bounds`. Ships:

  • `cycleStepN_level_ge` — level non-decreasing across iterated cycleStep
    (lifting `cycleStep_level_ge` from CumulativeProgress).

The full discharge of `lifecycle_progress_from_bounds` is deferred
to next sub-item — the fight-count accumulation argument across
the hfightFires hypothesis requires careful primitive recursion
that doesn't fit cleanly in a single commit.

NO new axioms.
-/

namespace Formal.Liveness.LifecycleBound6

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.LIV003Decomposition

/-! ## Iterated level monotonicity -/

/-- Iterated cycleStep preserves the level-non-decreasing invariant. -/
theorem cycleStepN_level_ge (s : State) (n : Nat) :
    (cycleStepN n s).level ≥ s.level := by
  induction n generalizing s with
  | zero => rw [cycleStepN_zero]
  | succ k ih =>
    rw [cycleStepN_succ]
    have h1 : (cycleStep s).level ≥ s.level := cycleStep_level_ge s
    have h2 : (cycleStepN k (cycleStep s)).level ≥ (cycleStep s).level :=
      ih (cycleStep s)
    omega

end Formal.Liveness.LifecycleBound6
