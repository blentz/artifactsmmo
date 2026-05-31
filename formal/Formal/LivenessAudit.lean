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

open Formal.Liveness.Placeholder
open Formal.Liveness.Measure
open Formal.Liveness.FightProgress
open Formal.Liveness.GatherProgress
open Formal.Liveness.DepositProgress
open Formal.Liveness.RestProgress
open Formal.Liveness.ProgressAction
open Formal.Liveness.MeansFiring
open Formal.Liveness.NoDeadlockV2

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
#print axioms pursueTaskValueModel_positive_when_unsatisfied

-- Phase 20c-v2: no-deadlock headline.
#print axioms productionLadder_ne_none_of_fires
#print axioms productionLadder_total_under_invariants
#print axioms exists_firing_means_under_invariants
