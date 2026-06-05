import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.TaskCompleteReachable
import Mathlib.Tactic

set_option linter.unusedSimpArgs false
set_option linter.unusedVariables false

/-! # Skill-gap closure — Phase 23d-7 (hand-written)

User mandate (2026-06-01):
> on an unlimited planning budget, the algorithm should see all tasks
> as feasible, because any task blocked by skill level can be planned
> for by gaining relevant xp or skill-xp to reach the pre-requisite
> skill or level required to progress the task.

Closes Part C of Phase 23d-6: when a task's prerequisites are NOT met
(`projectedSkillXpDelta < targetSkillXp`), the planner can chain
`.gather` actions to close the skill gap, then chain `.taskTrade`
actions to complete the task.

Two-stage K-step plan:
  K_skill   = `targetSkillXp - projectedSkillXpDelta` `.gather` steps
  K_complete = `taskTotal - taskProgress`             `.taskTrade` steps

Total K = K_skill + K_complete. Finite under the precondition that
both gaps are bounded.

NO new axioms. Pure structural composition of:
- Phase 23d-7's `.gather` apply (advances `projectedSkillXpDelta` by 1).
- Phase 23d-6's `taskComplete_reachable` (`.taskTrade` chain).
-/

namespace Formal.Liveness.SkillGapClosure

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable

/-! ## Per-step preservation under `.gather` -/

/-- `.gather` advances `projectedSkillXpDelta` by 1. -/
theorem gather_skill_succ (s : State) :
    (applyActionKind .gather s).projectedSkillXpDelta
      = s.projectedSkillXpDelta + 1 := by
  rfl

/-- `.gather` preserves `targetSkillXp`. -/
theorem gather_targetSkillXp_preserved (s : State) :
    (applyActionKind .gather s).targetSkillXp = s.targetSkillXp := by
  rfl

/-- `.gather` preserves `taskCode`. -/
theorem gather_taskCode_preserved (s : State) :
    (applyActionKind .gather s).taskCode = s.taskCode := by
  rfl

/-- `.gather` preserves `taskProgress`. -/
theorem gather_taskProgress_preserved (s : State) :
    (applyActionKind .gather s).taskProgress = s.taskProgress := by
  rfl

/-- `.gather` preserves `taskTotal`. -/
theorem gather_taskTotal_preserved (s : State) :
    (applyActionKind .gather s).taskTotal = s.taskTotal := by
  rfl

/-- `.gather` preserves `taskLifecyclePhase`. -/
theorem gather_phase_preserved (s : State) :
    (applyActionKind .gather s).taskLifecyclePhase = s.taskLifecyclePhase := by
  rfl

/-! ## Replicate-application lemmas -/

/-- K `.gather` steps advance `projectedSkillXpDelta` by exactly K. -/
theorem replicate_gather_skill_progress :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).projectedSkillXpDelta
        = s.projectedSkillXpDelta + n := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).projectedSkillXpDelta
           = s.projectedSkillXpDelta + (k + 1)
    rw [applyPlan_cons]
    rw [ih (applyActionKind .gather s)]
    rw [gather_skill_succ]
    omega

/-- K `.gather` steps preserve `targetSkillXp`. -/
theorem replicate_gather_targetSkillXp :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).targetSkillXp = s.targetSkillXp := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).targetSkillXp
           = s.targetSkillXp
    rw [applyPlan_cons]
    rw [ih (applyActionKind .gather s)]
    rw [gather_targetSkillXp_preserved]

/-- K `.gather` steps preserve `taskCode`. -/
theorem replicate_gather_taskCode :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).taskCode = s.taskCode := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).taskCode
           = s.taskCode
    rw [applyPlan_cons]
    rw [ih (applyActionKind .gather s)]
    rw [gather_taskCode_preserved]

/-- K `.gather` steps preserve `taskProgress`. -/
theorem replicate_gather_taskProgress :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).taskProgress = s.taskProgress := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).taskProgress
           = s.taskProgress
    rw [applyPlan_cons]
    rw [ih (applyActionKind .gather s)]
    rw [gather_taskProgress_preserved]

/-- K `.gather` steps preserve `taskTotal`. -/
theorem replicate_gather_taskTotal :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).taskTotal = s.taskTotal := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).taskTotal
           = s.taskTotal
    rw [applyPlan_cons]
    rw [ih (applyActionKind .gather s)]
    rw [gather_taskTotal_preserved]

/-! ## Skill-gap closure headline -/

/-- **Skill prerequisite closable**.

    Applying `K_skill = targetSkillXp - projectedSkillXpDelta`
    `.gather` steps brings `projectedSkillXpDelta` to at least
    `targetSkillXp` (skill prerequisite satisfied), while preserving
    all task fields and `targetSkillXp`. -/
theorem skill_prerequisite_reachable (s : State)
    (hSkillGap : s.projectedSkillXpDelta < s.targetSkillXp) :
    let s' := applyPlan (List.replicate (s.targetSkillXp - s.projectedSkillXpDelta) .gather) s
    s'.projectedSkillXpDelta ≥ s.targetSkillXp ∧
    s'.targetSkillXp = s.targetSkillXp ∧
    s'.taskCode = s.taskCode ∧
    s'.taskProgress = s.taskProgress ∧
    s'.taskTotal = s.taskTotal := by
  set K_skill := s.targetSkillXp - s.projectedSkillXpDelta with hKdef
  refine ⟨?_, ?_, ?_, ?_, ?_⟩
  · -- projectedSkillXpDelta after K_skill gathers = original + K_skill
    rw [replicate_gather_skill_progress K_skill s]
    -- K_skill = targetSkillXp - projectedSkillXpDelta, and gap > 0, so sum ≥ targetSkillXp
    omega
  · exact replicate_gather_targetSkillXp K_skill s
  · exact replicate_gather_taskCode K_skill s
  · exact replicate_gather_taskProgress K_skill s
  · exact replicate_gather_taskTotal K_skill s

/-! ## End-to-end bridge: skill-gap closure + task completion -/

/-- **Any task with skill gap is completable via finite plan**.

    For any state with (1) an accepted/in-progress task with remaining
    work and (2) a skill prerequisite gap, the K-step plan
    `K_skill .gather` ++ `K_complete .taskTrade` reaches `phase = .complete`.

    Witness: K_skill = `targetSkillXp - projectedSkillXpDelta`,
             K_complete = `taskTotal - taskProgress`.
    Total K = K_skill + K_complete, finite. -/
theorem skill_gap_then_complete_reachable (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (hSkillGap : s.projectedSkillXpDelta < s.targetSkillXp) :
    ∃ (K_skill K_complete : Nat),
      (applyPlan
        ((List.replicate K_skill .gather) ++ (List.replicate K_complete .taskTrade))
        s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  -- Build the two stages.
  set K_skill := s.targetSkillXp - s.projectedSkillXpDelta with hSkillDef
  set K_complete := s.taskTotal - s.taskProgress with hCompleteDef
  refine ⟨K_skill, K_complete, ?_⟩
  -- Split applyPlan over append: applyPlan (xs ++ ys) s = applyPlan ys (applyPlan xs s).
  have hSplit :
      applyPlan (List.replicate K_skill .gather ++ List.replicate K_complete .taskTrade) s
        = applyPlan (List.replicate K_complete .taskTrade)
            (applyPlan (List.replicate K_skill .gather) s) := by
    simp [applyPlan, List.foldl_append]
  rw [hSplit]
  -- Let s' = state after K_skill gathers.
  set s' := applyPlan (List.replicate K_skill .gather) s with hsdef
  -- s'.taskCode/Progress/Total preserved from s.
  have hCode' : s'.taskCode.isSome = true := by
    rw [hsdef, replicate_gather_taskCode]
    exact hCode
  have hTot' : s'.taskTotal > 0 := by
    rw [hsdef, replicate_gather_taskTotal]
    exact hTot
  have hProg' : s'.taskProgress = s.taskProgress := by
    rw [hsdef, replicate_gather_taskProgress]
  have hTot'_eq : s'.taskTotal = s.taskTotal := by
    rw [hsdef, replicate_gather_taskTotal]
  have hLT' : s'.taskProgress < s'.taskTotal := by
    rw [hProg', hTot'_eq]; exact hLT
  -- K_complete = s.taskTotal - s.taskProgress = s'.taskTotal - s'.taskProgress.
  have hKEq : K_complete = s'.taskTotal - s'.taskProgress := by
    rw [hProg', hTot'_eq, hCompleteDef]
  rw [hKEq]
  -- Apply taskComplete_reachable to s'.
  exact taskComplete_reachable s' hCode' hTot' hLT'

end Formal.Liveness.SkillGapClosure
