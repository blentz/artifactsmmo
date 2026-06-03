import Formal.Liveness.LifecycleBound
import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.RecipeChainClosure
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.TaskCompleteReachable
import Mathlib.Tactic

/-! # LifecycleBound2 — Item 1c: bounded reach `.complete` via plan

Continues the structural discharge of `accept_cancel_loop_bound` by
exhibiting an EXPLICIT plan that reaches `.complete` from any feasible
.accepted/.inProgress state. The plan is bounded by `taskTotal -
taskProgress` — a finite Nat function of the state.

The original `accept_cancel_loop_bound` axiom is universally quantified
over `cycleStepN`, claiming `∃ K, ∃ j ≤ K, phase = .complete` for any
function satisfying the cycleStepN recursion laws. For the SPECIFIC
cycleStep we have (CycleStep.lean), the unrefined `taskCancelFires` is
over-eager (fires on every .accepted state), so the axiom is genuinely
FALSE in our model.

This phase provides the structural bound that DOES hold (via
.taskTrade chain, not cycleStep iteration). Item 1d will refine
cycleStep itself to use the feasibility-gated predicates, then drop
the axiom.

NO new axioms.
-/

namespace Formal.Liveness.LifecycleBound2

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable
open Formal.Liveness.LifecycleBound

/-! ## Plan-bound to `.complete` -/

/-- **Bounded plan reaches `.complete`**.

    The witness plan is `List.replicate K .taskTrade` where K =
    `taskTotal - taskProgress`. The plan length is bounded by taskTotal
    (a finite Nat). Under feasibility, this is the structural analog of
    `accept_cancel_loop_bound`'s `∃ j ≤ ..., phase = .complete` claim.

    Connection to the original axiom: the axiom quantifies over
    `cycleStepN j`, which iterates `cycleStep` — but our cycleStep under
    unrefined `taskCancelFires` doesn't actually advance from .accepted
    to .complete. This theorem uses the planFor-equivalent witness
    DIRECTLY (`.taskTrade` chain) rather than going through cycleStep.

    The K bound is concrete (taskTotal - taskProgress) rather than
    `(taskPoolFinite + 1) * (lowYieldSampleThreshold + 1)`. Under
    feasibility, the true bound is the simpler one. -/
theorem bounded_plan_reaches_complete (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (_hFeas : s.taskFeasibleProjected = true) :
    ∃ K, ∃ plan : Plan,
      plan.length = K ∧
      K ≤ s.taskTotal ∧
      (applyPlan plan s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  refine ⟨s.taskTotal - s.taskProgress,
          List.replicate (s.taskTotal - s.taskProgress) .taskTrade,
          ?_, ?_, ?_⟩
  · simp [List.length_replicate]
  · omega
  · exact taskComplete_reachable s hCode hTot hLT

/-- Existential form parameterized over taskPoolFinite — the axiom-shape
    version. Connects to the structural witness. -/
theorem bounded_plan_within_pool (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal)
    (hFeas : s.taskFeasibleProjected = true)
    (hPool : s.taskTotal ≤ Formal.Liveness.LIV003Decomposition.taskPoolFinite) :
    ∃ K, ∃ plan : Plan,
      plan.length = K ∧
      K ≤ Formal.Liveness.LIV003Decomposition.taskPoolFinite ∧
      (applyPlan plan s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  obtain ⟨K, plan, hLen, hKLT, hPhase⟩ :=
    bounded_plan_reaches_complete s hCode hTot hLT hFeas
  refine ⟨K, plan, hLen, ?_, hPhase⟩
  omega

/-! ## Connection to Phase 23d-8 recipe-chain closure -/

/-- For ANY recipe-chain task (where prerequisites may need K_gather
    .gather + K_craft .craft before the .taskTrade chain), a bounded
    plan reaches `.complete`. Connects 23d-8's
    `recipe_then_complete_reachable` with 1c's bound.

    This is the strongest existential we can extract structurally
    without refining cycleStep itself. -/
theorem recipe_chain_bounded (r : Formal.Liveness.RecipeChainClosure.Recipe)
    (s : State)
    (hCode : s.taskCode.isSome = true)
    (hTot : s.taskTotal > 0)
    (hLT : s.taskProgress < s.taskTotal) :
    ∃ K, ∃ plan : Plan,
      plan.length = K ∧
      (applyPlan plan s).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  -- Compose Phase 23d-8 recipe_then_complete_reachable.
  obtain ⟨K_gather, K_craft, K_trade, hPhase⟩ :=
    Formal.Liveness.RecipeChainClosure.recipe_then_complete_reachable
      r s hCode hTot hLT
  refine ⟨K_gather + K_craft + K_trade,
          List.replicate K_gather .gather
            ++ List.replicate K_craft .craft
            ++ List.replicate K_trade .taskTrade,
          ?_, hPhase⟩
  simp [List.length_replicate, List.length_append]
  omega

end Formal.Liveness.LifecycleBound2
