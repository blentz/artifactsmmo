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

  Phase 20a adds Reachable, StateRegions, and RegionFiring modules.
  No new axioms beyond LIV-001 are introduced.

  Phase 20b adds the NoDeadlock headline (strong + Reachable corollary).
  No new axioms beyond LIV-001.
-/
import Formal.Liveness.Placeholder
import Formal.Liveness.Measure
import Formal.Liveness.FightProgress
import Formal.Liveness.GatherProgress
import Formal.Liveness.DepositProgress
import Formal.Liveness.RestProgress
import Formal.Liveness.ProgressAction
import Formal.Liveness.Reachable
import Formal.Liveness.StateRegions
import Formal.Liveness.RegionFiring
import Formal.Liveness.NoDeadlock

open Formal.Liveness.Placeholder
open Formal.Liveness.Measure
open Formal.Liveness.FightProgress
open Formal.Liveness.GatherProgress
open Formal.Liveness.DepositProgress
open Formal.Liveness.RestProgress
open Formal.Liveness.ProgressAction
open Formal.Liveness.Reachable
open Formal.Liveness.StateRegions
open Formal.Liveness.RegionFiring
open Formal.Liveness.NoDeadlock

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

-- Phase 20a: Reachable closure.
#print axioms spawn_reachable

-- Phase 20a: StateRegions exhaustiveness and per-region characterisation.
#print axioms regions_exhaustive
#print axioms regionOf_criticalHP
#print axioms regionOf_pendingItems
#print axioms regionOf_taskComplete
#print axioms regionOf_noTask
#print axioms regionOf_inventoryFull
#print axioms regionOf_levelBlocker
#print axioms regionOf_bankLockedFightable

-- Phase 20a: Per-region firing-goal witnesses.
#print axioms region_criticalHP_fires_restoreHP
#print axioms region_pendingItemsWaiting_fires_claimPending
#print axioms region_taskComplete_fires_completeTask
#print axioms region_noTask_fires_acceptTask
#print axioms region_inventoryFull_fires_discardOverstock
#print axioms region_levelBlocker_fires_reachUnlockLevel
#print axioms region_bankLockedFightable_fires_unlockBank
#print axioms region_progressNeeded_fires_pursueTask

-- Phase 20b: NoDeadlock headline (strong + Reachable corollary).
#print axioms no_deadlock_strong
#print axioms no_deadlock_reachable
