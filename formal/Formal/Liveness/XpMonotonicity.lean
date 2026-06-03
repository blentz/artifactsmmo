import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.ApplyXpLevelPreservation
import Formal.Liveness.CycleStepCharacterization
import Formal.Liveness.LifecycleBound6
import Formal.Liveness.PlanExists
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # XpMonotonicity — Item 1g-B2 sub-step 3

Under constant-level trajectories (where `(cycleStep s).level = s.level`,
the precondition for our contradiction proof), xp is non-decreasing.

Ships two key lemmas:
  • `cycleStep_xp_ge_when_level_eq` — single-step xp monotonicity.
  • `cycleStepN_xp_ge_when_level_eq` — iterated xp monotonicity.

Foundation for `xp_accumulates_under_no_level_advance` (next sub-step).

NO new axioms.
-/

namespace Formal.Liveness.XpMonotonicity

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.ApplyXpLevelPreservation
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.LifecycleBound6
open Formal.Liveness.PlanExists
open Formal.Liveness.CumulativeProgress

/-- Right-side recurrence: `cycleStepN (n+1) s = cycleStep (cycleStepN n s)`.
    Derived from `cycleStepN_add` with `m := n, n := 1`. -/
theorem cycleStepN_succ_outer (n : Nat) (s : State) :
    cycleStepN (n+1) s = cycleStep (cycleStepN n s) := by
  rw [show n + 1 = n + 1 from rfl]
  rw [cycleStepN_add n 1 s]
  show cycleStepN 1 (cycleStepN n s) = cycleStep (cycleStepN n s)
  rw [cycleStepN_succ 0 (cycleStepN n s), cycleStepN_zero]

/-- `.fight` xp lower-bound: when no rollover (level unchanged),
    `xp = s.xp + 10`. -/
theorem fight_xp_eq_add_ten_when_level_eq (s : State)
    (h : (applyActionKind .fight s).level = s.level) :
    (applyActionKind .fight s).xp = s.xp + 10 := by
  -- From fight semantics: if willLevel then xp:=0, level:=s.level+1
  --                       else xp:=s.xp+10, level:=s.level.
  -- Hypothesis rules out willLevel=true (else level=s.level+1 ≠ s.level).
  by_cases hwill : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                     && decide (s.level < 50)) = true
  · -- Rollover branch: level := s.level + 1.
    exfalso
    have hlvl : (applyActionKind .fight s).level = s.level + 1 := by
      simp only [applyActionKind]
      rw [if_pos hwill]
    rw [hlvl] at h
    omega
  · -- Non-rollover branch: xp := s.xp + 10.
    simp only [applyActionKind]
    rw [if_neg hwill]

/-- `.completeTask` xp lower-bound under XP=0: when no level change,
    xp is preserved (= s.xp). -/
theorem completeTask_xp_eq_when_level_eq (s : State)
    (h : (applyActionKind .completeTask s).level = s.level) :
    (applyActionKind .completeTask s).xp = s.xp := by
  by_cases hwill : (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
                     && decide (s.level < 50)) = true
  · exfalso
    have hlvl : (applyActionKind .completeTask s).level = s.level + 1 := by
      simp only [applyActionKind]
      rw [if_pos hwill]
    rw [hlvl] at h
    omega
  · simp only [applyActionKind]
    rw [if_neg hwill]
    show s.xp + taskCompleteXpEstimate = s.xp
    show s.xp + 0 = s.xp
    omega

/-- Per-action xp non-decreasing under constant-level constraint. -/
theorem applyActionKind_xp_ge_when_level_eq (k : ActionKind) (s : State)
    (h : (applyActionKind k s).level = s.level) :
    (applyActionKind k s).xp ≥ s.xp := by
  cases k with
  | fight =>
    rw [fight_xp_eq_add_ten_when_level_eq s h]
    omega
  | completeTask =>
    rw [completeTask_xp_eq_when_level_eq s h]
  | _ =>
    rw [applyActionKind_xp_preserved_except_fight_completeTask _ _
          (by intro contra; cases contra)
          (by intro contra; cases contra)]

/-- Single-step xp monotonicity under constant level. -/
theorem cycleStep_xp_ge_when_level_eq (s : State)
    (h : (cycleStep s).level = s.level) :
    (cycleStep s).xp ≥ s.xp := by
  unfold cycleStep at h ⊢
  split at h
  · -- productionLadder = none → cycleStep = s.
    omega
  · rename_i k _
    split at h
    · -- planFor returns [] → cycleStep = s. Impossible by planFor_ne_nil
      -- but split handles it.
      omega
    · rename_i a _ _
      exact applyActionKind_xp_ge_when_level_eq a s h

/-- Iterated xp monotonicity under constant level across the WHOLE
    prefix. If level is constant at every position from 0 to n, then
    xp is monotone non-decreasing. -/
theorem cycleStepN_xp_ge_when_level_eq_throughout (s : State) (n : Nat)
    (h : ∀ k ≤ n, (cycleStepN k s).level = s.level) :
    (cycleStepN n s).xp ≥ s.xp := by
  induction n with
  | zero =>
    rw [cycleStepN_zero]
  | succ k ih =>
    have hsucc_lvl_orig : (cycleStepN (k+1) s).level = s.level := h (k+1) (Nat.le_refl _)
    have hk_lvl : (cycleStepN k s).level = s.level := h k (Nat.le_succ _)
    -- Rewrite the (k+1) form via cycleStepN_succ_outer.
    rw [cycleStepN_succ_outer k s] at hsucc_lvl_orig
    -- Now hsucc_lvl_orig : (cycleStep (cycleStepN k s)).level = s.level.
    have hstep_lvl :
        (cycleStep (cycleStepN k s)).level = (cycleStepN k s).level := by
      rw [hsucc_lvl_orig, hk_lvl]
    have hstep_xp :
        (cycleStep (cycleStepN k s)).xp ≥ (cycleStepN k s).xp :=
      cycleStep_xp_ge_when_level_eq (cycleStepN k s) hstep_lvl
    have hk_xp := ih (fun j hj => h j (Nat.le_succ_of_le hj))
    rw [cycleStepN_succ_outer k s]
    omega

end Formal.Liveness.XpMonotonicity
