/-
  Formal.LivenessAudit

  Prints `#print axioms` for every theorem in `Formal/Liveness/`. Consumed by
  `formal/gate/check_axioms_liveness.sh`. Liveness theorems may depend on
  Mathlib's standard axiom set (see the gate script for the enumerated
  allow-list at the current Mathlib pin).

  Note: Phase 19b introduces the FIRST production-use liveness axiom,
  `Formal.Liveness.Measure.xpToNextLevel` (AXIOM-ID LIV-001 in
  `Formal/Liveness/Measure.lean`). The gate's allow-list explicitly permits
  this axiom; the manifest records it per theorem.

  Phase 19c expands the measure to 6 components and adds per-action
  progress lemmas for Gather / Deposit / Rest plus the `ProgressAction`
  headline. No new axioms beyond LIV-001.
-/
import Formal.Liveness.Placeholder
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.Measure
import Formal.Liveness.FightProgress
import Formal.Liveness.GatherProgress
import Formal.Liveness.DepositProgress
import Formal.Liveness.RestProgress
import Formal.Liveness.ProgressAction
import Formal.Liveness.MeansFiring
import Formal.Liveness.NoDeadlockV2
import Formal.Liveness.PlanAction
import Formal.Liveness.Plan
import Formal.Liveness.PlanExists
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Formal.Liveness.TaskInfeasibility
import Formal.Liveness.TaskCompleteReachable
import Formal.Liveness.SkillGapClosure
import Formal.Liveness.RecipeChainClosure
import Formal.Liveness.GameDataFixture
import Formal.Liveness.LevelFiftyReachable
import Formal.Liveness.LifecycleBound
import Formal.Liveness.LifecycleBound2
import Formal.Liveness.LifecycleBound3
import Formal.Liveness.LifecycleBound4
import Formal.Liveness.TaskPoolSemantics
import Formal.Liveness.TaskPoolTrajectory

open Formal.Liveness.Placeholder
open Formal.Liveness.Measure
open Formal.Liveness.FightProgress
open Formal.Liveness.GatherProgress
open Formal.Liveness.DepositProgress
open Formal.Liveness.RestProgress
open Formal.Liveness.ProgressAction
open Formal.Liveness.MeansFiring
open Formal.Liveness.NoDeadlockV2
open Formal.Liveness.PlanExists
open Formal.Liveness.CycleStep

-- Phase 19a sanity.
#print axioms mathlib_works

-- Phase 19b/c: Measure module.
#print axioms measureLt_wellFounded
#print axioms measureLt_of_levelDeficit_dec
#print axioms measureLt_of_xpDeficit_dec
#print axioms measureLt_of_skillXpDeficit_dec
#print axioms measureLt_of_bankPressure_dec
#print axioms measureLt_of_hpDeficit_dec
#print axioms toLexHex_lt_of_measureLt

-- Phase 19b: FightAction progress.
#print axioms fight_decreases_measure

-- Phase 19c: per-action progress lemmas.
#print axioms gather_decreases_measure
#print axioms deposit_decreases_measure
#print axioms rest_decreases_measure

-- Phase 19c: ProgressAction headline.
#print axioms step_decreases_measure

-- Phase 20b-v2: per-MeansKind firing → Phase-18 value > 0 lemmas.
#print axioms _fires_hpCritical_implies_restoreHp_positive
#print axioms _fires_bankUnlock_implies_unlockBank_positive
#print axioms _fires_reachUnlockLevel_implies_value_positive
#print axioms _fires_discardCritical_implies_discardOverstock_positive
#print axioms _fires_depositFull_implies_depositInventory_positive
#print axioms _fires_discardHigh_implies_discardOverstock_positive
#print axioms _fires_claimPending_implies_claimPending_positive
#print axioms _fires_completeTask_implies_completeTask_positive
#print axioms _fires_sellPressured_implies_sellInventory_positive
#print axioms _fires_lowYieldCancel_implies_lowYieldCancel_positive
#print axioms _fires_taskCancel_implies_taskCancel_positive
#print axioms _fires_pursueTask_implies_pursueTask_positive
#print axioms _fires_acceptTask_implies_acceptTask_positive
#print axioms _fires_taskExchange_implies_taskExchange_positive
#print axioms _fires_sellIdle_implies_sellInventory_positive
#print axioms _fires_bankExpand_implies_expandBank_positive
#print axioms _fires_wait_implies_wait_positive
#print axioms pursueTaskValueModel_positive_when_unsatisfied

-- Phase 20e-v2 step 2: unconditional no-deadlock headline (replaces the
-- retracted Phase 20c-v2 conditional `productionLadder_total_under_invariants`
-- now that production has WaitGoal as a last-resort, always-firing means).
#print axioms productionLadder_ne_none_of_fires
#print axioms productionLadder_total
#print axioms exists_firing_means

-- Phase 21a: plan-existence lemmas for trivial firing means.
#print axioms plan_exists_for_hpCritical
#print axioms plan_exists_for_claimPending
#print axioms plan_exists_for_completeTask
#print axioms plan_exists_for_acceptTask
#print axioms plan_exists_for_taskExchange
#print axioms plan_exists_for_taskCancel
#print axioms plan_exists_for_bankExpand
#print axioms plan_exists_for_wait

-- Phase 21b: plan-existence lemmas for the moderate-difficulty single-step
-- firing means (state model collapses MoveTo prefix into the trailing
-- action's effects on the firing-predicate-visible fields).
#print axioms plan_exists_for_discardCritical
#print axioms plan_exists_for_discardHigh
#print axioms plan_exists_for_depositFull
#print axioms plan_exists_for_sellPressured
#print axioms plan_exists_for_sellIdle
#print axioms plan_exists_for_lowYieldCancel

-- Phase 21c: Fight-based plan-existence lemmas. Both extend
-- `applyActionKind .fight` to model (a) bank-unlock achievement flip
-- and (b) xp/level rollover (the latter making `applyActionKind` and
-- `applyPlan` noncomputable via dependency on the axiomatic
-- `Formal.Liveness.Measure.xpToNextLevel`, AXIOM-ID LIV-001).
#print axioms plan_exists_for_bankUnlock
#print axioms plan_exists_for_reachUnlockLevel

-- Phase 21d-1: final Tier-3 plan-existence lemmas. `.taskTrade` collapses
-- multi-trade delivery into one step (pursueTask). `.objectiveStep` is a
-- synthetic placeholder ActionKind (NOT a production Action subclass) —
-- see PlanAction.lean docstring for the honest disclosure.
#print axioms plan_exists_for_pursueTask
#print axioms plan_exists_for_objectiveStep

-- Phase 22a: cycle-loop infrastructure (Tier 4 scaffold). `cycleStep`
-- composes productionLadder + planFor + applyActionKind into one cycle's
-- pure transition; `cycleStep_progress_or_waits` is the progress-or-wait
-- headline connecting Phase 20's no-deadlock with Phase 21's plan-exists.
#print axioms planFor_ne_nil
#print axioms cycleStep_total
#print axioms cycleStep_progress_or_waits

-- Phase 23a — Tier 4 cumulative progress (weaker form).
open Formal.Liveness.CumulativeProgress
#print axioms cycleStepN_succ
#print axioms cumulative_state_change_under_no_wait

-- Phase 23b — Tier 4 strong form: level strictly advances under no-wait +
-- progress-means trajectory restriction. Uses an extended 14-tuple lex
-- measure (`ExtMeasure`) for well-founded induction. See
-- `Formal/Liveness/CumulativeProgress.lean` docstring for honest
-- disclosure of the 5 deferred task-lifecycle MeansKinds.
#print axioms extMeasureLt_wellFounded
#print axioms cycleStep_level_ge
#print axioms progressMeans_decreases_extMeasure_or_advances_level
#print axioms cumulative_progress_under_no_wait_restricted

-- Phase 23d-1 — LIV-003 fat axiom REFACTORED into three smaller pieces.
-- The OLD `cumulative_progress_lifecycle_axiom` has been DELETED; the
-- unrestricted headline `cumulative_progress_under_no_wait` now depends on
-- the smaller decomposed axioms in `Formal.Liveness.LIV003Decomposition`:
--   • LIV-003a — THEOREM `taskAccepted_implies_cancelOrPursueFires`
--     (provable; no axiom)
--   • LIV-003b — `lowYieldSampleThreshold`, `_pos`,
--     `inProgress_decides_within_threshold`
--   • LIV-003c — `taskPoolFinite`, `_pos`, `accept_cancel_loop_bound`
--   • LIV-003-bridge — `lifecycle_progress_from_bounds` (narrow
--     composition residual replacing the fat axiom)
-- See `Formal/Liveness/LIV003Decomposition.lean` for the full disclosure.
open Formal.Liveness.LIV003Decomposition
#print axioms taskAccepted_implies_cancelOrPursueFires
#print axioms taskInProgress_implies_cancelOrPursueFires
#print axioms taskActive_implies_cancelOrPursueFires
-- Phase 23d-5: `lowYieldSampleThreshold(_pos)` relocated to
-- `Formal.Liveness.ProductionLadder` so the production firing predicate
-- and the abstract theorem share the SAME opaque constant.
#print axioms Formal.Liveness.ProductionLadder.lowYieldSampleThreshold
#print axioms Formal.Liveness.ProductionLadder.lowYieldSampleThreshold_pos
#print axioms inProgress_decides_within_threshold
#print axioms taskPoolFinite
#print axioms taskPoolFinite_pos
#print axioms accept_cancel_loop_bound
#print axioms lifecycle_progress_from_bounds
#print axioms cumulative_progress_under_no_wait
#print axioms accepted_state_decides_cancel_or_pursue

-- Phase 23d-3 — LIV-003a STRONG FORM: feasibility-grounded bridge.
-- `taskInfeasible` packages a Phase-13 feasibility witness with the
-- gating phase condition; the structural bridge to `taskCancelFires`
-- requires NO new axioms. The decision-level companions compose
-- Phase-13 `TaskDecision.combat_or_no_history_pivots` at the Liveness
-- abstraction. See `Formal/Liveness/TaskInfeasibility.lean` for the
-- full disclosure.
open Formal.Liveness.TaskInfeasibility
#print axioms taskInfeasible_implies_taskCancelFires
#print axioms taskInfeasible_implies_taskCancelFires_headline
#print axioms taskInfeasible_implies_pursueTaskFires
#print axioms combatGate_implies_pivot_decision
#print axioms noHistory_implies_pivot_decision
#print axioms vpc_below_threshold_implies_pivot

-- Phase 23d-6b: TaskComplete reachability via .taskTrade replication.
open Formal.Liveness.TaskCompleteReachable
#print axioms taskTrade_progress_succ
#print axioms taskTrade_total_preserved
#print axioms replicate_taskTrade_progress
#print axioms replicate_taskTrade_total
#print axioms taskTrade_step_reaches_complete
#print axioms taskComplete_reachable
#print axioms taskComplete_reachable_exists

-- Phase 23d-7: SkillGapClosure — chain .gather to satisfy skill prerequisite,
-- then .taskTrade to reach .complete. Closes Part C of Phase 23d-6.
open Formal.Liveness.SkillGapClosure
#print axioms gather_skill_succ
#print axioms replicate_gather_skill_progress
#print axioms skill_prerequisite_reachable
#print axioms skill_gap_then_complete_reachable

-- Phase 23d-8: RecipeChainClosure — chain .gather + .craft + .taskTrade
-- reaches .complete for items tasks needing crafted output. Closes the
-- recipe-chain gap deferred in Phase 23d-7.
open Formal.Liveness.RecipeChainClosure
#print axioms craft_advances_slots_succ
#print axioms replicate_craft_slots
#print axioms recipe_produces_item
#print axioms recipe_then_complete_reachable

-- Phase 24: GameDataFixture — concrete recipe-chain instance demonstrating
-- the Phase 23d-8 universal theorem produces a finite plan on a real-shaped
-- game-data instance (iron_ore → iron_bar → iron_sword chain).
open Formal.Liveness.GameDataFixture
#print axioms snapshotCapturedAt
#print axioms allRecipes
#print axioms snapshot_recipe_count
#print axioms live_first_recipe_completable

-- Phase 25: LevelFiftyReachable — TIER 5 CAPSTONE. Iterates Phase 23c-3c's
-- cumulative_progress_under_no_wait 49 times to prove level-50 reachability
-- from any state with GlobalInvariants.
open Formal.Liveness.LevelFiftyReachable
#print axioms cycleStepN_add
#print axioms globalInvariants_step
#print axioms level_advances_once
#print axioms ai_reaches_level_fifty_aux
#print axioms ai_reaches_level_fifty
#print axioms ai_reaches_level_fifty_from_spawn

-- Item 1a: LifecycleBound — refined taskCancelFires gated on
-- taskFeasibleProjected. Lifecycle reaches .complete under feasibility.
open Formal.Liveness.LifecycleBound
#print axioms taskCancelFiresRefined_inactive_when_feasible
#print axioms taskCancelFiresRefined_inactive_when_feasible_inProgress
#print axioms taskTrade_preserves_feasible
#print axioms replicate_taskTrade_preserves_feasible
#print axioms lifecycle_reaches_complete_when_feasible

-- Item 1c: LifecycleBound2 — bounded plan reaches .complete under
-- feasibility. Structural witness for the original
-- accept_cancel_loop_bound axiom's existential.
open Formal.Liveness.LifecycleBound2
#print axioms bounded_plan_reaches_complete
#print axioms bounded_plan_within_pool
#print axioms recipe_chain_bounded

-- Item 1e: LifecycleBound3 — K+1-step plan grants +10 xp via completeTask.
-- Structural composition piece for level-advance argument.
open Formal.Liveness.LifecycleBound3
#print axioms bounded_plan_plus_complete_grants_progress
#print axioms feasible_task_grants_progress
open Formal.Liveness.LIV003Decomposition
#print axioms lifecycle_progress_from_bounds_step

-- Item 1f: LifecycleBound4 — bounded plan grants level advance when xp
-- threshold met. Composes Item 1c bounded plan + Item 1f rollover step.
open Formal.Liveness.LifecycleBound4
#print axioms completeTask_advances_level_when_threshold_met
#print axioms lifecycle_progress_strong
#print axioms bounded_plan_grants_level_when_threshold
#print axioms level_advance_plan_exists_when_xp_threshold_met

-- Item 1g-A2: TaskPoolSemantics local lemmas. Behavioural basis for the
-- pigeonhole bound on accept-cancel cycles (∀ trajectory, cancel count
-- bounded by |taskPool|). The trajectory-level theorem ships in a
-- follow-up sub-item.
open Formal.Liveness.TaskPoolSemantics
#print axioms acceptTask_preserves_seen
#print axioms acceptTask_preserves_pool
#print axioms acceptTask_taskCode_eq
#print axioms taskCancel_seen_cons
#print axioms taskCancel_seen_none
#print axioms taskCancel_preserves_pool
#print axioms taskCancel_seen_length_le_succ

-- Item 1g-A3: trajectory-level pool/seen lemmas. Per-action + cycleStep
-- monotonicity and length bounds; iterated bounds on cycleStepN.
open Formal.Liveness.TaskPoolTrajectory
#print axioms applyActionKind_pool_invariant
#print axioms applyActionKind_seen_length_monotone
#print axioms applyActionKind_seen_length_le_succ
#print axioms cycleStep_pool_invariant
#print axioms cycleStep_seen_length_monotone
#print axioms cycleStep_seen_length_le_succ
#print axioms cycleStepN_pool_invariant
#print axioms cycleStepN_seen_length_le_add
