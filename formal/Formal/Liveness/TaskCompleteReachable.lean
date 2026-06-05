import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Mathlib.Tactic

set_option linter.unusedSimpArgs false
set_option linter.unusedVariables false

/-! # TaskComplete reachability — Phase 23d-6 (hand-written)

Proves: for any state with an accepted (or in-progress) task and
strictly-positive remaining progress, applying `.taskTrade` to that
state `K = taskTotal - taskProgress` times reaches phase `.complete`.

This is the user-mandated structural claim (2026-06-01):
> "mathematically, the planner should be able to be proven capable
> of reaching the TaskComplete outcome."

Witness is **explicit**: `K = s.taskTotal - s.taskProgress`. Proof is
structural — no axiom dependency beyond what `.taskTrade`'s apply
already carries. NOT a k=0 trivial witness — K is strictly positive
under the precondition `taskProgress < taskTotal`.

Scope this phase (Part B per Phase 23d-6 brief):
- Reach `.complete` via `.taskTrade` replication, assuming
  prerequisites already satisfied (sufficient inventory, sufficient
  skill).
- Skill-gap closure (Part C — chain of skill-progressing actions
  before TaskTrade) deferred to Phase 23d-7. Requires per-skill XP
  counters in State.
-/

namespace Formal.Liveness.TaskCompleteReachable

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase

/-! ## Helper lemmas: per-step preservation under `.taskTrade` -/

/-- `.taskTrade` advances `taskProgress` by exactly 1. -/
theorem taskTrade_progress_succ (s : State) :
    (applyActionKind .taskTrade s).taskProgress = s.taskProgress + 1 := by
  rfl

/-- `.taskTrade` preserves `taskTotal`. -/
theorem taskTrade_total_preserved (s : State) :
    (applyActionKind .taskTrade s).taskTotal = s.taskTotal := by
  rfl

/-- `.taskTrade` preserves `taskCode`. -/
theorem taskTrade_code_preserved (s : State) :
    (applyActionKind .taskTrade s).taskCode = s.taskCode := by
  rfl

/-! ## Replicate-application lemmas -/

/-- Apply `K` `.taskTrade` steps and the resulting `taskProgress` is
    `s.taskProgress + K`. -/
theorem replicate_taskTrade_progress :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .taskTrade) s).taskProgress
        = s.taskProgress + n := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    -- replicate (k+1) a = a :: replicate k a
    show (applyPlan (.taskTrade :: List.replicate k .taskTrade) s).taskProgress
           = s.taskProgress + (k + 1)
    rw [applyPlan_cons]
    rw [ih (applyActionKind .taskTrade s)]
    rw [taskTrade_progress_succ]
    omega

/-- Apply `K` `.taskTrade` steps and `taskTotal` is preserved. -/
theorem replicate_taskTrade_total :
    ∀ (n : Nat) (s : State),
      (applyPlan (List.replicate n .taskTrade) s).taskTotal
        = s.taskTotal := by
  intro n
  induction n with
  | zero =>
    intro s
    simp [applyPlan]
  | succ k ih =>
    intro s
    show (applyPlan (.taskTrade :: List.replicate k .taskTrade) s).taskTotal
           = s.taskTotal
    rw [applyPlan_cons]
    rw [ih (applyActionKind .taskTrade s)]
    rw [taskTrade_total_preserved]

/-! ## Per-step completion -/

/-- Single `.taskTrade` application that lands the state at exactly
    `taskProgress + 1 = taskTotal` reaches `.complete`. -/
theorem taskTrade_step_reaches_complete (s : State)
    (hTot : s.taskTotal > 0)
    (hEq : s.taskProgress + 1 ≥ s.taskTotal) :
    (applyActionKind .taskTrade s).taskLifecyclePhase = .complete := by
  -- Unfold .taskTrade application. The phase is computed as:
  --   if s.taskTotal = 0 then s.taskLifecyclePhase
  --   else if (s.taskProgress + 1) ≥ s.taskTotal then .complete else .inProgress
  show (if s.taskTotal = 0 then s.taskLifecyclePhase
        else if (s.taskProgress + 1) ≥ s.taskTotal then .complete
        else .inProgress) = .complete
  have hNonZero : s.taskTotal ≠ 0 := Nat.pos_iff_ne_zero.mp hTot
  rw [if_neg hNonZero, if_pos hEq]

/-! ## Headline -/

/-- **TaskComplete reachability**.

    For any state with a non-empty task and remaining work, applying
    `.taskTrade` `K = taskTotal - taskProgress` times reaches
    `phase = .complete`.

    Witness is **explicit**: `K = s.taskTotal - s.taskProgress > 0`.
    No new axioms; pure structural proof from Phase 23d-5's refined
    `.taskTrade` apply.

    User mandate (2026-06-01):
    > "mathematically, the planner should be able to be proven
    > capable of reaching the TaskComplete outcome."
-/
theorem taskComplete_reachable (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal) :
    (applyPlan (List.replicate (s.taskTotal - s.taskProgress) .taskTrade) s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  -- Let K = taskTotal - taskProgress, strictly positive.
  set K := s.taskTotal - s.taskProgress with hKdef
  have hKpos : K > 0 := by
    show s.taskTotal - s.taskProgress > 0
    omega
  -- K = m + 1 for some m. Decompose replicate (m+1) = replicate m ++ [last].
  obtain ⟨m, hm⟩ : ∃ m, K = m + 1 := ⟨K - 1, by omega⟩
  rw [hm]
  -- replicate (m+1) a = replicate m a ++ [a]
  have hRepEq : List.replicate (m + 1) (ActionKind.taskTrade)
              = List.replicate m .taskTrade ++ [.taskTrade] :=
    List.replicate_succ' (n := m) (a := ActionKind.taskTrade)
  rw [hRepEq]
  -- applyPlan (xs ++ [a]) s = applyActionKind a (applyPlan xs s)
  have hSplit : applyPlan
      (List.replicate m .taskTrade ++ [ActionKind.taskTrade]) s
        = applyActionKind .taskTrade
            (applyPlan (List.replicate m .taskTrade) s) := by
    simp [applyPlan, List.foldl_append]
  rw [hSplit]
  -- Define sM = state after m .taskTrade steps.
  set sM := applyPlan (List.replicate m .taskTrade) s with hsMdef
  -- sM.taskProgress = s.taskProgress + m
  have hProg : sM.taskProgress = s.taskProgress + m := by
    rw [hsMdef, replicate_taskTrade_progress]
  -- sM.taskTotal = s.taskTotal
  have hTotEq : sM.taskTotal = s.taskTotal := by
    rw [hsMdef, replicate_taskTrade_total]
  -- Apply the per-step completion lemma to sM.
  apply taskTrade_step_reaches_complete sM
  · rw [hTotEq]; exact hTot
  · rw [hProg, hTotEq]
    -- s.taskProgress + m + 1 ≥ s.taskTotal
    -- We have K = m + 1, K = s.taskTotal - s.taskProgress.
    -- So m + 1 = s.taskTotal - s.taskProgress, hence m = s.taskTotal - s.taskProgress - 1.
    -- s.taskProgress + m + 1 = s.taskTotal (when s.taskProgress < s.taskTotal).
    omega

/-! ## Corollary — existential form -/

/-- Existential restatement: ∃ K, K-step plan reaches `.complete`. -/
theorem taskComplete_reachable_exists (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal) :
    ∃ K : Nat,
      (applyPlan (List.replicate K .taskTrade) s).taskLifecyclePhase
        = .complete :=
  ⟨s.taskTotal - s.taskProgress,
   taskComplete_reachable s hCode hTot hLT⟩

end Formal.Liveness.TaskCompleteReachable
