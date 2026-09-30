import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.TaskCompleteReachable
import Formal.Liveness.LadderEval
import Mathlib.Tactic

/-! # Skill-gap closure — Phase 23d-7 (hand-written)

User mandate (2026-06-01):
> on an unlimited planning budget, the algorithm should see all tasks
> as feasible, because any task blocked by skill level can be planned
> for by gaining relevant xp or skill-xp to reach the pre-requisite
> skill or level required to progress the task.

Closes Part C of Phase 23d-6: when a task's prerequisites are NOT met
(`trackedSkillLevel < targetSkillLevel`), the planner can chain the grind's
earning legs (`.gather`) to close the skill gap, then chain `.taskTrade`
actions to complete the task.

Phase 2d-L2: a leg pays skill XP, not a level. `.gather` pays `skillLegXp`
(≥ 1, the `SkillXpPositive` gate) against the per-level needs
(`Measure.grantSkillXp`), so the gap closes after at most the XP owed
(`skillDeficit`) earning legs, and the band invariant (`SkillBand`) turns
"nothing owed" into "the target level is reached".

Two-stage K-step plan:
  K_skill   = `skillDeficit`            `.gather` steps (earning legs)
  K_complete = `taskTotal - taskProgress` `.taskTrade` steps

Total K = K_skill + K_complete, finite.

NO new axioms. Pure structural composition of:
- `.gather`'s apply (`grantSkillXp`: pays `skillLegXp`, rolls levels over).
- Phase 23d-6's `taskComplete_reachable` (`.taskTrade` chain).
-/

namespace Formal.Liveness.SkillGapClosure

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable

/-! ## Per-step preservation under `.gather` -/

/-- `.gather` pays `skillLegXp`: the XP owed falls by that much. -/
theorem gather_skill_pays (s : State) :
    (applyActionKind .gather s).skillDeficit = s.skillDeficit - s.skillLegXp := by
  show (grantSkillXp s s.skillLegXp).skillDeficit = _
  exact grantSkillXp_deficit s s.skillLegXp

/-- `.gather` keeps the skill fields in band. -/
theorem gather_band (s : State) (h : s.SkillBand) : (applyActionKind .gather s).SkillBand := by
  show (grantSkillXp s s.skillLegXp).SkillBand
  exact grantSkillXp_band s s.skillLegXp h

/-- `.gather` keeps what a leg pays. -/
theorem gather_legXp_preserved (s : State) :
    (applyActionKind .gather s).skillLegXp = s.skillLegXp := by
  rfl

/-- `.gather` preserves `targetSkillLevel`. -/
theorem gather_targetSkillLevel_preserved (s : State) :
    (applyActionKind .gather s).targetSkillLevel = s.targetSkillLevel := by
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

/-- K `.gather` steps lower the XP owed by K legs' pay, keep the band and
    keep what a leg pays. -/
theorem replicate_gather_skill_progress :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).skillDeficit = s.skillDeficit - n * s.skillLegXp ∧
      (applyPlan (List.replicate n .gather) s).skillLegXp = s.skillLegXp ∧
      (s.SkillBand → (applyPlan (List.replicate n .gather) s).SkillBand) := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).skillDeficit = _ ∧
      (applyPlan (.gather :: List.replicate k .gather) s).skillLegXp = _ ∧
      (s.SkillBand → (applyPlan (.gather :: List.replicate k .gather) s).SkillBand)
    rw [applyPlan_cons]
    obtain ⟨hd, hl, hb⟩ := ih (applyActionKind .gather s)
    refine ⟨?_, ?_, fun h => hb (gather_band s h)⟩
    · rw [hd, gather_legXp_preserved, gather_skill_pays, Nat.add_mul, Nat.one_mul]; omega
    · rw [hl, gather_legXp_preserved]

/-- K `.gather` steps preserve `targetSkillLevel`. -/
theorem replicate_gather_targetSkillLevel :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .gather) s).targetSkillLevel = s.targetSkillLevel := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.gather :: List.replicate k .gather) s).targetSkillLevel
           = s.targetSkillLevel
    rw [applyPlan_cons]
    rw [ih (applyActionKind .gather s)]
    rw [gather_targetSkillLevel_preserved]

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

    With the skill fields in band and a leg that earns, applying
    `K_skill = skillDeficit` earning legs (`.gather`) brings
    `trackedSkillLevel` to at least `targetSkillLevel` (skill prerequisite
    satisfied), while preserving all task fields and `targetSkillLevel`. -/
theorem skill_prerequisite_reachable (s : State)
    (hband : s.SkillBand) (hleg : 0 < s.skillLegXp) :
    let s' := applyPlan (List.replicate s.skillDeficit .gather) s
    s'.trackedSkillLevel ≥ s.targetSkillLevel ∧
    s'.targetSkillLevel = s.targetSkillLevel ∧
    s'.taskCode = s.taskCode ∧
    s'.taskProgress = s.taskProgress ∧
    s'.taskTotal = s.taskTotal := by
  set K_skill := s.skillDeficit with hKdef
  have htarget := replicate_gather_targetSkillLevel K_skill s
  refine ⟨?_, htarget, ?_, ?_, ?_⟩
  · obtain ⟨hd, _, hb⟩ := replicate_gather_skill_progress K_skill s
    have hzero : (applyPlan (List.replicate K_skill .gather) s).skillDeficit = 0 := by
      rw [hd]
      have : K_skill ≤ K_skill * s.skillLegXp := Nat.le_mul_of_pos_right _ hleg
      omega
    have := (skillDeficit_zero_iff _ (hb hband)).mp hzero
    rw [htarget] at this
    exact this
  · exact replicate_gather_taskCode K_skill s
  · exact replicate_gather_taskProgress K_skill s
  · exact replicate_gather_taskTotal K_skill s

/-! ## End-to-end bridge: skill-gap closure + task completion -/

/-- **Any task with skill gap is completable via finite plan**.

    For any state with (1) an accepted/in-progress task with remaining
    work and (2) a skill prerequisite gap, the K-step plan
    `K_skill .gather` ++ `K_complete .taskTrade` reaches `phase = .complete`.

    Witness: K_skill = `skillDeficit` (the earning legs),
             K_complete = `taskTotal - taskProgress`.
    Total K = K_skill + K_complete, finite. -/
theorem skill_gap_then_complete_reachable (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (_hSkillGap : s.trackedSkillLevel < s.targetSkillLevel) :
    ∃ (K_skill K_complete : Nat),
      (applyPlan
        ((List.replicate K_skill .gather) ++ (List.replicate K_complete .taskTrade))
        s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  -- Build the two stages.
  set K_skill := s.skillDeficit with hSkillDef
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

/-! ## Non-vacuity: the band and a paying leg are satisfiable -/

-- Level 3 toward 5, 4 XP into level 3 whose need is 10, level 4 needs 12,
-- a leg pays 3: 18 XP owed, so six legs close the gap.
private def grindWitness : State :=
  { Formal.Liveness.LadderEval.inertLadderState with
    trackedSkillLevel := 3
    targetSkillLevel := 5
    trackedSkillXp := 4
    skillXpNeeds := [10, 12]
    skillLegXp := 3 }

example : grindWitness.skillDeficit = 18 := by rfl
example : grindWitness.SkillBand := by
  refine ⟨rfl, ?_, ?_⟩
  · intro n hn
    simp only [grindWitness, List.mem_cons, List.not_mem_nil, or_false] at hn
    rcases hn with rfl | rfl <;> decide
  · intro n h
    simp only [grindWitness, List.head?_cons, Option.some.injEq] at h
    subst h; decide
example : (applyPlan (List.replicate 6 .gather) grindWitness).trackedSkillLevel = 5 := by rfl

end Formal.Liveness.SkillGapClosure
