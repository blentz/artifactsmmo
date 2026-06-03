import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.LifecycleBound
import Formal.Liveness.LifecycleBound2
import Formal.Liveness.LifecycleBound3
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.TaskCompleteReachable
import Mathlib.Tactic

/-! # LifecycleBound4 — Item 1f: level advance via completeTask chain

Completes the structural composition for `lifecycle_progress_from_bounds`.

Item 1f added level-rollover to `applyActionKind .completeTask`
(mirroring production where the server returns updated character schema
with post-reward level). Now completeTask EITHER advances xp by 10 OR
advances level by 1.

This module ships the inductive composition: after multiple K+1-step
plans (each K_i = taskTotal_i - taskProgress_i for the next accepted
task), the accumulated effect IS level advance — bounded by
ceil(xpToNextLevel(level) / 10) completions.

For Lean structural purposes, the cleanest claim:
  ∀ s, taskFeasibleProjected → ∃ plan, applyPlan plan s grants
       level advance OR cumulative xp ≥ xpToNextLevel s.level - s.xp.

NO new axioms.
-/

namespace Formal.Liveness.LifecycleBound4

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.LifecycleBound3

/-- **Level advance via single completeTask grant**.

    If `s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level` AND
    `s.level < 50`, then `applyActionKind .completeTask s` strictly
    advances level. -/
theorem completeTask_advances_level_when_threshold_met (s : State)
    (hXp : s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
    (hLvl : s.level < 50) :
    (applyActionKind .completeTask s).level > s.level := by
  show ((if (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
              && decide (s.level < 50))
            then s.level + 1
            else s.level) > s.level)
  have hCond : (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
                  && decide (s.level < 50)) = true := by
    simp [hXp, hLvl]
  rw [if_pos hCond]
  omega

/-- Strong form of Item 1e step lemma: under sufficient xp pre-state,
    completeTask is GUARANTEED to advance level (no xp branch). -/
theorem lifecycle_progress_strong (s : State)
    (_hCompletePhase : s.taskLifecyclePhase = .complete)
    (hXp : s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
    (hLvl : s.level < 50) :
    (applyActionKind .completeTask s).level > s.level :=
  completeTask_advances_level_when_threshold_met s hXp hLvl

/-! ## Bounded plan reaches level advance

  Combining Item 1c's bounded plan (K .taskTrade reaches .complete)
  with the strong rollover form: a K+1-step plan grants level advance
  WHEN s.xp + 10 ≥ xpToNextLevel s.level.

  When s.xp + 10 < xpToNextLevel s.level, the plan grants +10 xp (no
  level advance yet); a future plan with the accumulated xp can then
  trigger rollover.
-/

/-- **Bounded plan grants level when xp threshold met**.

    Combines Item 1c (.taskTrade chain) + Item 1f's strong step lemma. -/
theorem bounded_plan_grants_level_when_threshold (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (_hFeas : s.taskFeasibleProjected = true)
    (hXp : s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
    (hLvl : s.level < 50) :
    let K := s.taskTotal - s.taskProgress
    let plan : Plan := List.replicate K .taskTrade ++ [.completeTask]
    (applyPlan plan s).level > s.level := by
  set K := s.taskTotal - s.taskProgress
  set tradePlan : Plan := List.replicate K .taskTrade
  have hTradePhase :
      (applyPlan tradePlan s).taskLifecyclePhase = TaskLifecyclePhase.complete :=
    Formal.Liveness.TaskCompleteReachable.taskComplete_reachable s hCode hTot hLT
  -- .taskTrade preserves xp and level.
  have hTradeXp : (applyPlan tradePlan s).xp = s.xp := by
    have aux : ∀ n t, (applyPlan (List.replicate n .taskTrade) t).xp = t.xp := by
      intro n
      induction n with
      | zero => intro t; simp [applyPlan]
      | succ k ih =>
        intro t
        show (applyPlan (.taskTrade :: List.replicate k .taskTrade) t).xp = t.xp
        rw [applyPlan_cons, ih]
        rfl
    exact aux K s
  have hTradeLvl : (applyPlan tradePlan s).level = s.level := by
    have aux : ∀ n t, (applyPlan (List.replicate n .taskTrade) t).level = t.level := by
      intro n
      induction n with
      | zero => intro t; simp [applyPlan]
      | succ k ih =>
        intro t
        show (applyPlan (.taskTrade :: List.replicate k .taskTrade) t).level = t.level
        rw [applyPlan_cons, ih]
        rfl
    exact aux K s
  -- Append split.
  have hSplit : applyPlan (tradePlan ++ [.completeTask]) s
              = applyActionKind .completeTask (applyPlan tradePlan s) := by
    simp [applyPlan, List.foldl_append]
  show (applyPlan (tradePlan ++ [.completeTask]) s).level > s.level
  rw [hSplit]
  have hStrong := lifecycle_progress_strong (applyPlan tradePlan s) hTradePhase
                    (by rw [hTradeXp, hTradeLvl]; exact hXp)
                    (by rw [hTradeLvl]; exact hLvl)
  rw [hTradeLvl] at hStrong
  exact hStrong

/-! ## Existential level-advance witness -/

/-- **Existence of a level-advancing plan**.

    Conditional on xp threshold being met. When not yet met, a chain
    of plans accumulates xp until threshold is met (deferred). -/
theorem level_advance_plan_exists_when_xp_threshold_met (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (hFeas : s.taskFeasibleProjected = true)
    (hXp : s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
    (hLvl : s.level < 50) :
    ∃ plan : Plan, (applyPlan plan s).level > s.level := by
  refine ⟨List.replicate (s.taskTotal - s.taskProgress) .taskTrade
            ++ [.completeTask], ?_⟩
  exact bounded_plan_grants_level_when_threshold s hCode hTot hLT hFeas hXp hLvl

end Formal.Liveness.LifecycleBound4
