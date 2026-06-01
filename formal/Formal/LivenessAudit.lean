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
