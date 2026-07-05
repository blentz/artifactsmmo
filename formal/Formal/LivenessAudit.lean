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
import Formal.Liveness.LadderEval
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
import Formal.Liveness.ItemsTaskTermination
import Formal.Liveness.ItemsTaskRun
import Formal.Liveness.GameDataFixture
import Formal.Liveness.LevelFiftyReachable
import Formal.Liveness.ReducedReachability
import Formal.Liveness.NoWait
import Formal.Liveness.PerceptionInvariant
import Formal.Liveness.FightFairness
import Formal.Liveness.BlockerQuieting
import Formal.Liveness.BlockerMonotone
import Formal.Liveness.BlockerSelection
import Formal.Liveness.BootstrapReach
import Formal.Liveness.PerceptionRefresh
import Formal.Liveness.CycleStepP
import Formal.Liveness.LevelFiftyReachableP
import Formal.Liveness.BlockerSettled
import Formal.Liveness.SettledWitness
import Formal.Liveness.SettledReach
import Formal.Liveness.WarmupCleared
import Formal.Liveness.Leveling
import Formal.Liveness.FightReady
import Formal.Liveness.FightReadyReach
import Formal.Liveness.GearTierLeveling
import Formal.Liveness.WinnableGrounded
import Formal.Liveness.LifecycleBound
import Formal.Liveness.LifecycleBound2
import Formal.Liveness.LifecycleBound3
import Formal.Liveness.LifecycleBound4
import Formal.Liveness.LifecycleBound6
import Formal.Liveness.ApplyXpLevelPreservation
import Formal.Liveness.CycleStepCharacterization
import Formal.Liveness.XpMonotonicity
import Formal.Liveness.LifecycleBound7
import Formal.Liveness.GameDataInvariance
import Formal.Liveness.CategoryBBridge
import Formal.Liveness.PursueTaskSelection
import Formal.Liveness.InProgressDecidesWithSelection
import Formal.Liveness.InventorySemantics
import Formal.Liveness.EquipmentSemantics
import Formal.Liveness.PositionSemantics
import Formal.Liveness.GoldSemantics
import Formal.Liveness.SkillXpSemantics
import Formal.Liveness.RichApplyConsistency
import Formal.Liveness.LearningStoreBridge
import Formal.Liveness.MetaGoalDispatch
import Formal.Liveness.StateFieldGapSemantics
import Formal.Liveness.TaskPoolSemantics
import Formal.Liveness.TaskPoolTrajectory
import Formal.Liveness.StickySelect
import Formal.Liveness.ZombieFreedom
import Formal.Liveness.GatedArming
import Formal.Liveness.UnconditionalDescent
import Formal.Liveness.DeferFaithful
import Formal.Liveness.CycleStepDC
import Formal.Liveness.WitnessAcquirable
import Formal.Liveness.GearedDescent
import Formal.Liveness.CycleStepEC

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

-- Phase 23a — Tier 4 cumulative progress. The weaker-form headline
-- `cumulative_state_change_under_no_wait` was RETIRED (2026-06-29): audit-only,
-- subsumed by the Phase 23d-1 unrestricted headline.
open Formal.Liveness.CumulativeProgress
#print axioms cycleStepN_succ

-- Phase 23b — extended 14-tuple lex measure (`ExtMeasure`) machinery, used
-- for well-founded induction and still LIVE in `PerceptionInvariant`/`Plan`.
-- NOTE: the Phase 23b strong-form headline
-- `cumulative_progress_under_no_wait_restricted` was RETIRED (2026-06-29) —
-- it had no live proof dependents (audit-only) and is superseded WITHOUT the
-- trajectory restriction by the Phase 23d-1 unrestricted headline
-- `LifecycleBound7.lifecycle_progress_from_bounds_proven`. The shared lemmas
-- it consumed remain audited here.
#print axioms extMeasureLt_wellFounded
#print axioms cycleStep_level_ge
#print axioms progressMeans_decreases_extMeasure_or_advances_level

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
-- Item 1g-C: accept_cancel_loop_bound + lifecycle_progress_from_bounds
-- axioms DELETED; the bridge axiom discharged as
-- lifecycle_progress_from_bounds_proven (LifecycleBound7).
-- cumulative_progress_under_no_wait also deleted (axiom-using wrapper).
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

-- Obligation-5 O5.1: hnowait discharged HONESTLY (a task means always fires
-- before .wait; NOT the .wait fall-through).
open Formal.Liveness.NoWait in
#print axioms task_means_always_fires
open Formal.Liveness.NoWait in
#print axioms productionLadder_ne_wait
-- Obligation-5: hnowait + hex/hbe discharged; GlobalInvariants reduced to
-- {hperc, hfightFires} + spawn config-positivity.
open Formal.Liveness.ReducedReachability in
#print axioms ai_reaches_level_fifty_config_positive

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

-- Item 1g-B2: level monotonicity across iterated cycleStep.
open Formal.Liveness.LifecycleBound6
#print axioms cycleStepN_level_ge

-- Item 1g-B2: per-action xp/level preservation under XP=0 fix.
open Formal.Liveness.ApplyXpLevelPreservation
#print axioms applyActionKind_level_preserved_except_fight_completeTask
#print axioms applyActionKind_xp_preserved_except_fight_completeTask
#print axioms completeTask_level_preserved_when_no_rollover
#print axioms completeTask_xp_preserved_when_no_rollover

-- Item 1g-B2 step2: cycleStep characterization per ladder slot.
open Formal.Liveness.CycleStepCharacterization
#print axioms cycleStep_eq_fight_when_bankUnlock
#print axioms cycleStep_eq_fight_when_reachUnlockLevel
#print axioms cycleStep_eq_fight_when_fightFires
#print axioms cycleStep_xp_level_preserved_when_no_fight_no_complete

-- Item 1g-B2 step3: xp monotonicity under constant level.
open Formal.Liveness.XpMonotonicity
#print axioms fight_xp_eq_add_ten_when_level_eq
#print axioms completeTask_xp_eq_when_level_eq
#print axioms applyActionKind_xp_ge_when_level_eq
#print axioms cycleStep_xp_ge_when_level_eq
#print axioms cycleStepN_xp_ge_when_level_eq_throughout
#print axioms cycleStepN_succ_outer

-- Item 1g-B2 core: lifecycle_progress_from_bounds discharged as THEOREM.
open Formal.Liveness.LifecycleBound7
#print axioms xp_accumulates_when_level_constant
#print axioms lifecycle_progress_from_bounds_proven

-- Item 2b: GlobalInvariants Category A propagation.
open Formal.Liveness.GameDataInvariance
#print axioms applyActionKind_taskExchangeMinCoins_invariant
#print axioms applyActionKind_nextExpansionCost_invariant
#print axioms cycleStep_taskExchangeMinCoins_invariant
#print axioms cycleStep_nextExpansionCost_invariant
#print axioms cycleStepN_taskExchangeMinCoins_invariant
#print axioms cycleStepN_nextExpansionCost_invariant
#print axioms hex_propagation
#print axioms hbe_propagation

-- Item 2c: Category B safety bridge anchors.
open Formal.Liveness.CategoryBBridge
#print axioms hnowait_safety_anchor
#print axioms hfightFires_safety_anchor

-- Item 3a/3b: pursueTask ladder selection conditions + headline.
open Formal.Liveness.PursueTaskSelection
#print axioms productionLadder_eq_pursueTask
#print axioms cycleStep_eq_taskTrade
#print axioms pursueTaskFires_when_inProgress
#print axioms hpursue_under_conditions

-- Item 3c: bundle-form headline.
open Formal.Liveness.InProgressDecidesWithSelection
#print axioms inProgress_decides_within_threshold_with_selection_conditions

-- Item 4a: inventory composition semantics.
open Formal.Liveness.InventorySemantics
#print axioms invCount_nil
#print axioms invCount_cons_match
#print axioms invCount_cons_mismatch
#print axioms applyActionKind_inventory_invariant_except_gather
#print axioms gather_inventory_when_none
#print axioms gather_inventory_when_some
#print axioms gather_invCount_increments_target
#print axioms gather_invCount_unchanged_for_other_codes

-- Item 4b: equipment composition semantics.
open Formal.Liveness.EquipmentSemantics
#print axioms equipAt_nil
#print axioms equipAt_cons_match
#print axioms equipAt_cons_mismatch
#print axioms applyActionKind_equipment_invariant_except_equipment_actions
#print axioms equip_equipment_when_none
#print axioms equip_equipment_when_some
#print axioms equip_equipAt_target
#print axioms unequip_equipment_when_none
#print axioms unequip_equipment_when_some

-- Item 4c: position semantics.
open Formal.Liveness.PositionSemantics
#print axioms applyActionKind_posX_invariant_except_move_actions
#print axioms applyActionKind_posY_invariant_except_move_actions
#print axioms move_pos_when_none
#print axioms move_pos_when_some
#print axioms mapTransition_pos_when_none
#print axioms mapTransition_pos_when_some

-- Item 4d: gold reward semantics.
open Formal.Liveness.GoldSemantics
#print axioms completeTask_gold_credited
#print axioms npcSell_gold_credited
#print axioms completeTask_gold_monotone
#print axioms npcSell_gold_monotone
#print axioms buyBankExpansion_gold_debited

-- Item 4e/5: per-skill XP semantics.
open Formal.Liveness.SkillXpSemantics
#print axioms skillXp_nil
#print axioms skillXp_cons_match
#print axioms skillXp_cons_mismatch
#print axioms applyActionKind_skillXp_invariant_except_gather_craft
#print axioms gather_skillXp_when_none
#print axioms gather_skillXp_when_some
#print axioms gather_skillXp_increments_target
#print axioms craft_skillXp_when_none
#print axioms craft_skillXp_when_some
#print axioms craft_skillXp_increments_target

-- Item 4f: scalar↔rich consistency preservation.
open Formal.Liveness.RichApplyConsistency
#print axioms gather_inventoryUsed_invariant
#print axioms gather_inventoryMax_invariant
#print axioms craft_inventoryUsed_invariant
#print axioms equip_inventoryUsed_invariant
#print axioms unequip_inventoryUsed_invariant
#print axioms move_inventoryUsed_invariant
#print axioms gather_projectedSkillXpDelta_advances
#print axioms completeTask_inventoryUsed_invariant
#print axioms npcSell_inventoryUsed_invariant

-- Item 6a/6b: LearningStore bridge to TaskDecision.
open Formal.Liveness.LearningStoreBridge
#print axioms taskCancelFires_when_PIVOT
#print axioms taskCancelFires_false_when_PURSUE
#print axioms ls_pivots_on_combat_or_no_history
#print axioms ls_pursues_on_req_none

-- Item 7: MetaGoal dispatch + .objectiveStep discharge.
open Formal.Liveness.MetaGoalDispatch
#print axioms dispatch_reachCharLevel
#print axioms dispatch_reachSkillLevel
#print axioms dispatch_obtainItem
#print axioms applyDispatch_reachCharLevel
#print axioms applyDispatch_reachSkillLevel
#print axioms applyDispatch_obtainItem

-- Item 8: state field gap closure invariance.
open Formal.Liveness.StateFieldGapSemantics
#print axioms applyActionKind_skillLevels_invariant
#print axioms applyActionKind_bankItemsCatalog_invariant
#print axioms applyActionKind_bankGold_invariant
#print axioms applyActionKind_pendingItemCodes_invariant
#print axioms applyActionKind_npcStock_invariant
#print axioms applyActionKind_eventSpawns_invariant

-- Task 1 (tasks-termination): items-task keepSet/batchK conformance models.
-- Core-only (no Mathlib); listed here so the liveness axiom gate covers them.
open Formal.Liveness.ItemsTaskTermination
#print axioms keepSet_contains_task_item
#print axioms keepSet_contains_recipe_inputs
#print axioms batchK_ge_one
#print axioms batchK_le_remaining

-- tasks-termination follow-up: ItemsTaskRun — the inventory-COUPLED run
-- model that supersedes the collapsed-trade concern. `trade` REQUIRES and
-- CONSUMES one held task item to advance progress (the coupling the rejected
-- capstone lacked); `held_accounts` proves the whole run consumes EXACTLY the
-- items obtained (no free progress). Core-only; axiom-clean.
open Formal.Liveness.ItemsTaskRun
#print axioms trade_consumes
#print axioms trade_stuck_without_held
#print axioms trade_stuck_at_total
#print axioms run_total
#print axioms applyRun_total
#print axioms applyRun_cons
#print axioms replicate_trade_accounts
#print axioms replicate_trade_progress_of_room
#print axioms obtain_then_trades_reach
#print axioms obtain_then_trades_reach_exists
#print axioms held_accounts

-- O5.2 keystone (2026-06-16): the perception invariant `xp < xpToNextLevel level`
-- (while level<50) is `cycleStep`-preserved, so a single spawn fact propagates to
-- every reachable state — the honest discharge mechanism for the fight-progress
-- `hperc` hypothesis (mirrors GameDataInvariance's hex/hbe discharge). Unblocks
-- routing a general char-leveling fight through `objectiveStep` (O5.2).
open Formal.Liveness.PerceptionInvariant
#print axioms applyActionKind_preserves_XpInBand
#print axioms cycleStep_preserves_XpInBand
#print axioms cycleStepN_preserves_XpInBand
#print axioms spawn_XpInBand

-- O5.2 fairness reduction (2026-06-16): hfightFires reduces to the precise runtime
-- Prop CombatObjectiveFairlyScheduled (a combat objective active+unblocked
-- infinitely often). Selection mechanics + the reduction + end-to-end level-50
-- reachability from spawn config-positivity + fairness, all proven.
open Formal.Liveness.FightFairness
#print axioms productionLadder_eq_objectiveStep_of_unblocked
#print axioms hfightFires_of_combat_scheduled
#print axioms ai_reaches_level_fifty_from_fair_combat
#print axioms combat_scheduled_of_persistent_and_quiet
#print axioms ai_reaches_level_fifty_from_persistent_combat

-- O5.2 blocker one-step quieting (2026-06-16): each objectiveStepBlocker's planFor
-- action clears its own firing condition, so it cannot fire two cycles in a row
-- (13 of 14; reachUnlockLevel is gap-bounded instead). Building blocks for
-- BlockersQuietInfinitelyOften.
open Formal.Liveness.BlockerQuieting
#print axioms discardCritical_quiet_after_firing
#print axioms discardHigh_quiet_after_firing
#print axioms craftRelief_quiet_after_firing
#print axioms depositFull_quiet_after_firing
#print axioms gearReview_quiet_after_firing
#print axioms claimPending_quiet_after_firing
#print axioms sellPressured_quiet_after_firing
#print axioms completeTask_quiet_after_firing
#print axioms taskCancel_quiet_after_firing
#print axioms lowYieldCancel_quiet_after_firing
#print axioms restForCombat_quiet_after_firing
#print axioms hpCritical_quiet_after_firing
#print axioms bankUnlock_quiet_after_firing

-- O5.2 blocker PERMANENT quieting (2026-06-16): the 6 opaque flags are only ever
-- cleared (never re-armed) by applyActionKind, so once false they stay false along
-- cycleStepN — lifting one-step quieting to "the blocker never fires again". 7 of
-- the 14 blockers handled to permanent quieting.
open Formal.Liveness.BlockerMonotone
#print axioms discardCritical_quiet_forever
#print axioms discardHigh_quiet_forever
#print axioms depositFull_quiet_forever
#print axioms gearReview_quiet_forever
#print axioms claimPending_quiet_forever
#print axioms sellPressured_quiet_forever
#print axioms craftRelief_quiet_forever
#print axioms hpCritical_quiet_forever
#print axioms restForCombat_quiet_forever
#print axioms bankUnlock_quiet_forever
#print axioms reachUnlockLevel_quiet_forever

-- O5.2 Settled state (2026-06-16): breaks the task-phase/composition circularity.
-- A self-preserving Settled state has all 14 blockers quiet ⇒ objectiveStep selected
-- ⇒ cycle is a fight ⇒ Settled preserved. So a single Settled state discharges
-- CombatObjectiveFairlyScheduled and level-50 reachability; only "reach a Settled
-- state" (the transient) remains.
open Formal.Liveness.BlockerSettled
#print axioms Settled_blockers_quiet
#print axioms Settled_cycleStep
#print axioms combatScheduled_of_settled
#print axioms ai_reaches_level_fifty_of_settled

-- O5.2 anti-vacuity (2026-06-16): Settled is satisfiable (settledWitness), and the
-- witness discharges config-positivity + Settled, giving a CONCRETE hypothesis-free
-- (modulo LIV-001) level-50 reachability — the non-vacuous payoff of the O5.2 work.
open Formal.Liveness.SettledWitness
#print axioms settledWitness_isSettled
#print axioms settledWitness_reaches_fifty

-- O5.2 reach frontier (2026-06-16): reach_fifty_of_eventually_settled reduces the
-- whole obligation to ∃K Settled (config-pos is cycleStepN-invariant). And
-- Settled_unreachable_without_perception PROVES the O5.4 frontier: the pure model
-- never sets objectiveStepFires true, so reaching Settled requires perception to
-- supply the combat objective — not model-producible.
open Formal.Liveness.SettledReach
#print axioms reach_fifty_of_eventually_settled
#print axioms Settled_unreachable_without_perception

-- O5.2 warm-up brick 1 (2026-06-16): MechCleared bundles the 9 cycleStep-monotone
-- clearing conditions (the Settled core sans phase + perception); proven invariant by
-- composing the incr 7-9 monotonicity lemmas, and bridged to Settled.
open Formal.Liveness.WarmupCleared
#print axioms MechCleared_cycleStep
#print axioms settled_of_mechCleared

-- O5.2 warm-up brick 2 (2026-06-16): Leveling — the REACHABLE steady state
-- (MechCleared + parked task + perception). Weaker than Settled (no phase=.none, so a
-- feasible accepted task qualifies), self-preserving via the objectiveStep→fight cycle,
-- and discharges CombatObjectiveFairlyScheduled + level-50 reachability.
open Formal.Liveness.Leveling
#print axioms Leveling_blockers_quiet
#print axioms Leveling_cycleStep
#print axioms combatScheduled_of_leveling
#print axioms ai_reaches_level_fifty_of_leveling

-- O5.2 gear-tier decouple (2026-06-16): FightReady is the bank-INDEPENDENT leveling
-- invariant (non-fight blockers quiet + combat objective; NO bankAccessible /
-- level≥bankRequiredLevel). The selected means is always a FIGHT (bankUnlock /
-- reachUnlockLevel / objectiveStep), so reach-50 holds at every level<50 via gear-tier
-- combat, not gated on the level-44 bank unlock.
open Formal.Liveness.FightReady
#print axioms productionLadder_fight_of_fightReady
#print axioms FightReady_cycleStep
#print axioms hfightFires_of_fightReady
#print axioms ai_reaches_level_fifty_of_fightReady

-- O5.2 gear-tier part 2 (2026-06-17): WinnableAcrossBand (the gear-tier guarantee — a
-- winnable XP-positive monster exists at every level the char actually reaches, 1≤L<50)
-- grounds combat-target existence via the proven picker headline, hence grounds
-- objectiveStepFires/IsFight. Brick 2 closed a vacuity trap: the earlier ∀-Int form is
-- unsatisfiable for any finite catalog (xpPos fades at high L), so it is now band-
-- restricted and SATISFIABILITY-witnessed. The opaque-bool BINDING + the catalog
-- derivation of WinnableAcrossBand are the named O5.4 residual.
open Formal.Liveness.GearTierLeveling
#print axioms winnableAcrossBand_satisfiable
#print axioms combatTargetExists_of_gearTier
#print axioms combatObjective_live_below_fifty

-- Task 4 (2026-06-20): WinnableAcrossBand DISCHARGED over the live catalog via a
-- per-level witness table. The combat verdict is kernel `decide`d over
-- production-projected scalars (differential-pinned by
-- formal/diff/test_winnable_witness_diff.py); no native_decide, no new axioms.
open Formal.Liveness.WinnableGrounded
#print axioms winnableAcrossBand_grounded

-- Perception-refresh Brick 3 (2026-06-18): the combat objective is ARMED along the
-- refreshed trajectory. At every step k with level<50, the state the refreshed cycle
-- SELECTS on — perceptionRefresh (cycleStepPN k s) — has objectiveStepFires AND
-- objectiveStepIsFight true (immediate from Brick 1). This OVERTURNS the frontier
-- (SettledReach.objectiveStepFires_false_cycleStepN: the pure transition never sets it):
-- perceptionRefresh re-arms per-cycle what cycleStep clears. Discharges the objective-
-- committed half of hfightFires once restated over cycleStepP (Brick 4).
open Formal.Liveness.CycleStepP
#print axioms cycleStepP_objectiveStepFires_armed
#print axioms cycleStepP_objectiveStepIsFight_armed
#print axioms cycleStepP_objective_armed_overturns_frontier

-- Perception-refresh Brick 2 (2026-06-18): the refreshed bootstrap window reaches
-- bankRequiredLevel in-model (cycleStepPN analog of B-0's reaches_bankRequiredLevel).
#print axioms cycleStepP_reaches_bankRequiredLevel

-- Perception-refresh helpers (2026-06-18): the REUSABLE cycleStepP iteration +
-- monotonicity laws consumed by CycleStepFIteration. The vacuous cycleStepP level-50
-- capstone (GlobalInvariantsP / ai_reaches_level_fiftyP) and its hfightFiresP engine
-- were REMOVED 2026-06-19 (ResidualVacuity kernel-proved them vacuous — see
-- LevelFiftyReachableP's removal note; the non-vacuous replacement is
-- LevelingDescent.cycleStepF_reaches_fifty_of_fights).
open Formal.Liveness.LevelFiftyReachableP
#print axioms cycleStepPN_add
#print axioms cycleStepPN_succ_outer
#print axioms cycleStepPN_level_ge
#print axioms cycleStepPN_xp_ge_when_level_eq_throughout

-- StickySelect / ZombieFreedom (Tier-2 sticky progress-gated release; no infinite
-- zombie hold). `no_infinite_sticky_hold` uses ONLY the standard axiom set; the
-- measure instantiation `no_infinite_zombie_below_fifty` additionally inherits the
-- pre-existing measure axiom LIV-001 (`Measure.xpToNextLevel`) — NO new axioms.
open Formal.Liveness.StickySelect
#print axioms sticky_requires_progress
#print axioms sticky_progress_safe
#print axioms released_picks_top
#print axioms no_infinite_sticky_hold
open Formal.Liveness.ZombieFreedom
#print axioms no_infinite_zombie_below_fifty
open Formal.Liveness.GatedArming
#print axioms gatedArming_eq_top_of_released
#print axioms arming_false_of_held_nonfight
#print axioms no_infinite_zombie_suppression

-- Unconditional descent (2026-07-04): the hquiet (blockers-quiet) residual of
-- ai_reaches_fifty_grounded is DISCHARGED. FMeasure (13-slot cycleStepF-tailored
-- lex tuple; perceptionRefresh-invariant by construction) descends strictly on
-- EVERY below-50 faithful cycle — per-means over the 18-element ladder prefix
-- (BlockerDescent), closed by the prefix/none case analysis (the armed
-- objectiveStep makes the discretionary tail unreachable below the cap). The
-- capstone ai_reaches_fifty_unconditional is HYPOTHESIS-FREE: no hquiet, no
-- hspawn, no fairness residual — axioms are the standard set + LIV-001 only.
-- Honesty perimeter: FMeasure module docstring +
-- docs/PLAN_l50_unconditional_descent.md (opaque-Bool fidelity, items-task
-- defer-case, single-action chore semantics).
open Formal.Liveness.FMeasure
#print axioms fMeasureLt_wellFounded
#print axioms exists_level_ge_of_fdescent
#print axioms cycleStepF_reaches_fifty_of_fdescent
#print axioms fdescent_hyp_satisfiable_with_goal
open Formal.Liveness.BlockerDescent
#print axioms fMeasure_perceptionRefresh
#print axioms descends_fight
#print axioms descends_completeTask
#print axioms descends_claimPending
open Formal.Liveness.UnconditionalDescent
#print axioms ladder_mem_blockerPrefix
#print axioms ladder_some_below_fifty
#print axioms cycleStepF_descends_below_fifty
#print axioms ai_reaches_fifty_unconditional

-- Residual closure (2026-07-04, docs/PLAN_residual_closure.md): the
-- defer-faithful, adversarially-re-arming capstone. cycleStepD models the
-- items-task LONG-HAUL DEFER window (residual 3: arming gated on
-- itemsTaskDeferActive; inside the window the cycle pursues the items task,
-- descending taskCycles) and worst-cases chore re-arming (residual 4, fight
-- direction: EVERY fight re-arms ALL 8 chore latches; reach-50 still holds —
-- flags are lex-dominated by the fight's level/xp descent). The synthetic
-- placeholder row (stale-armed objective Bool inside the window) descends the
-- new objectiveStepFlag slot with dispatch-keyed loot (pressureDeltaD).
-- HYPOTHESIS-FREE; axioms = standard + LIV-001.
open Formal.Liveness.DMeasure
#print axioms dMeasureLt_wellFounded
#print axioms exists_level_ge_of_ddescent
open Formal.Liveness.BlockerDescentD
#print axioms descendsD_fight
#print axioms descendsD_placeholder
#print axioms descendsD_pursueTask
#print axioms descendsD_completeTask
open Formal.Liveness.DeferFaithful
#print axioms ladder_mem_pursuePrefix
#print axioms ladderD_some_below_fifty
#print axioms cycleStepD_descends_below_fifty
#print axioms ai_reaches_fifty_defer_faithful

-- Phase B2 (2026-07-04, docs/PLAN_c2_composed_liveness.md): the COMPUTABLE
-- mirror of the defer-faithful cycle. cycleStepDC (xpNext : Nat) is a
-- byte-for-byte clone of the noncomputable cycle with LIV-001's value passed
-- as data; the equality theorems are rfl-shaped, so ANY drift between clone
-- and source breaks the build — the anti-drift guarantee is the kernel. The
-- oracle's cycle_step_d entry evaluates the mirror for the trace-lockstep
-- harness (diff/trace_lockstep.py), which feeds the server's REAL max_xp per
-- cycle — the axiom replaced by observed data at every replayed step.
open Formal.Liveness.CycleStepDC
#print axioms applyActionKindC_eq
#print axioms planForC_eq
#print axioms cycleStepC_eq
#print axioms cycleStepDC_eq

-- C1b (2026-07-04, docs/PLAN_c2_composed_liveness.md): the witness gear is
-- provably OBTAINABLE — the Task-3/corner-3 acquirability residual of
-- WinnableGrounded discharged against the live fixture. Certificate pattern:
-- python computes acquirableCert, the KERNEL verifies its closure property
-- (certClosed) — a wrong cert cannot prove. acquirableWitness = the SAME
-- production sweep restricted to the cert pool: rows still WIN
-- (acquirable_rows_winnable), loadouts ⊆ cert, and coverage holds at every
-- band level with an EMPTY frontier (post-P1 multi-drop closure — the level-38
-- wall dissolved; acquirableFrontier_empty pins it).
open Formal.Liveness.WitnessAcquirable
#print axioms certClosed
#print axioms acquirable_loadouts_in_cert
#print axioms acquirable_rows_winnable
#print axioms acquirable_covers_band
#print axioms acquirableFrontier_empty

-- C2b/C2c (2026-07-04, docs/PLAN_c2_composed_liveness.md): the E-tower — the
-- geared cycle. perceptionRefreshE credits fight xp ONLY behind adequate gear
-- (the gap-1 combat-outcome fix the trace phases measured); inadequate states
-- take gear-progress cycles (finite discharge grounded offline by the EMPTY
-- acquirable frontier, WitnessAcquirable); fights cost FIGHT_LOSS_BOUND hp
-- (B1-measured 270) with death→respawn; rollovers adversarially reset gear +
-- every chore latch/debt. ai_reaches_fifty_geared is HYPOTHESIS-FREE: axioms
-- must be std + xpToNextLevel (LIV-001) ONLY.
open Formal.Liveness.GearedDescent
#print axioms cycleStepE_descends_below_fifty
#print axioms ai_reaches_fifty_geared

-- E-mirror binding (oracle `cycle_step_e` stands on this; rfl-chain on the
-- Phase-B2 clone, so mirror and model cannot drift silently).
#print axioms Formal.Liveness.CycleStepEC.cycleStepEC_eq
