-- These arrived transitively via the retired FightFairness import (removed
-- 2026-07-20 with the superseded capstone tower); named directly now.
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # BlockerQuieting — one-step transience of the objectiveStep blockers (O5.2)

The transience mechanism underneath `BlockersQuietInfinitelyOften`: each
`objectiveStepBlocker`'s `planFor` action CLEARS its own firing condition, so the
blocker cannot fire two cycles in a row. Proven here per blocker
(`<blocker>_quiet_after_firing`): `productionLadder s = some b ⇒ fires b (cycleStep s) = false`.

Coverage: 15 of the 17 blockers. `reachUnlockLevel` and `gearReview` are excluded —
their `.fight` does NOT one-step-quiet them, and for the same reason, because since
wave 4 they map to the SAME production goal (`ReachUnlockLevelGoal`).
`reachUnlockLevel` fires repeatedly until `level` reaches `bankRequiredLevel`;
`gearReview` fires while `regear_level_up` holds, which production clears only when
the level-up changes the horizon reading — a later cycle, not this step. Boundedness
for both is a DESCENT argument (`descends_fight` at `levelDeficit`/`xpDeficit`), not
one-step quieting.

These are the building blocks for the full `BlockersQuietInfinitelyOften`: combined
with flag-monotonicity (no `applyActionKind` re-arms the opaque flags / `hp` / `level`
/ `bankAccessible`) they bound total blocker firings. The task-phase blockers
(`completeTask`, `taskCancel`, `lowYieldCancel`) re-arm only via the task lifecycle,
which a persistent combat objective preempts (`pursueTask` sits after `objectiveStep`).

NO new axioms (standard set + LIV-001 via the fight branch).
-/

namespace Formal.Liveness.BlockerQuieting

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress

/-- A selected means fires (extracted from the `findSome?` characterisation of
    `productionLadder`). Local copy of the `private` helper in CycleStep /
    CumulativeProgress. -/
private theorem fires_of_ladder {s : State} {k : MeansKind}
    (h : productionLadder s = some k) : fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody
    rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- `discardCritical` dispatches `deleteItem`, clearing `hasOverstockItems`. -/
theorem discardCritical_quiet_after_firing (s : State)
    (h : productionLadder s = some .discardCritical) :
    fires .discardCritical (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .deleteItem s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, discardCriticalFires, applyActionKind]

/-- `discardHigh` dispatches `deleteItem`, clearing `hasOverstockItems`. -/
theorem discardHigh_quiet_after_firing (s : State)
    (h : productionLadder s = some .discardHigh) :
    fires .discardHigh (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .deleteItem s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, discardHighFires, applyActionKind]

/-- `craftRelief` dispatches `craft`, clearing `craftReliefFires`. -/
theorem craftRelief_quiet_after_firing (s : State)
    (h : productionLadder s = some .craftRelief) :
    fires .craftRelief (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .craft s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, craftReliefFires, applyActionKind]

/-- `depositFull` dispatches `depositAll`, clearing `selectBankDepositsNonempty`. -/
theorem depositFull_quiet_after_firing (s : State)
    (h : productionLadder s = some .depositFull) :
    fires .depositFull (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .depositAll s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, depositFullFires, applyActionKind]

-- `gearReview_quiet_after_firing` was DELETED in wave 4 and not replaced. It
-- claimed the rung clears its own flag by firing, which was true when the
-- witness was `.optimizeLoadout`. The witness is now `.fight` (the guard maps to
-- `ReachUnlockLevelGoal`), and a fight does not touch `gearReviewFires` — nor
-- does production clear `regear_level_up` on the fight itself. The theorem would
-- now be FALSE, so it is gone rather than restated; `descends_gearReview` in
-- `BlockerDescent` carries the boundedness instead.

/-- `claimPending` dispatches `claimPendingItem`, clearing `pendingItemsNonempty`. -/
theorem claimPending_quiet_after_firing (s : State)
    (h : productionLadder s = some .claimPending) :
    fires .claimPending (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .claimPendingItem s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, claimPendingFires, applyActionKind]

/-- `sellPressured` dispatches `npcSell`, clearing `sellableInventoryNonempty`. -/
theorem sellPressured_quiet_after_firing (s : State)
    (h : productionLadder s = some .sellPressured) :
    fires .sellPressured (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .npcSell s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, sellPressuredFires, applyActionKind]

/-- `completeTask` dispatches `completeTask`, resetting the lifecycle phase to
    `.none` (so the `.complete` firing condition fails). -/
theorem completeTask_quiet_after_firing (s : State)
    (h : productionLadder s = some .completeTask) :
    fires .completeTask (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .completeTask s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, completeTaskFires, applyActionKind]

/-- `taskCancel` dispatches `taskCancel`, resetting the phase to `.none`. -/
theorem taskCancel_quiet_after_firing (s : State)
    (h : productionLadder s = some .taskCancel) :
    fires .taskCancel (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .taskCancel s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, taskCancelFires, applyActionKind]

/-- `lowYieldCancel` dispatches `taskCancel`, resetting the phase to `.none`
    (the `.inProgress` firing condition fails). -/
theorem lowYieldCancel_quiet_after_firing (s : State)
    (h : productionLadder s = some .lowYieldCancel) :
    fires .lowYieldCancel (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .taskCancel s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, lowYieldCancelFires, applyActionKind]

/-- `restForCombat` dispatches `rest`, restoring `hp := maxHp` (the `hp < maxHp`
    firing condition fails). -/
theorem restForCombat_quiet_after_firing (s : State)
    (h : productionLadder s = some .restForCombat) :
    fires .restForCombat (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .rest s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]; simp [fires, restForCombatFires, applyActionKind]

/-- `hpCritical` dispatches `rest`, restoring `hp := maxHp` (so `hp/maxHp` is no
    longer below the critical fraction). -/
theorem hpCritical_quiet_after_firing (s : State)
    (h : productionLadder s = some .hpCritical) :
    fires .hpCritical (cycleStep s) = false := by
  have hcs : cycleStep s = applyActionKind .rest s := by
    unfold cycleStep; rw [h]; rfl
  rw [hcs]
  simp only [fires, hpCriticalFires, applyActionKind]
  -- post hp = maxHp: `DEN * maxHp < NUM * maxHp` is false (DEN > NUM > 0), and
  -- when maxHp = 0 the first conjunct is false.
  rcases Nat.eq_zero_or_pos s.maxHp with hz | hp
  · simp [hz]
  · have : ¬ (CRITICAL_HP_DEN * s.maxHp < CRITICAL_HP_NUM * s.maxHp) := by
      simp only [CRITICAL_HP_DEN, CRITICAL_HP_NUM]; omega
    simp [this]

/-- `bankUnlock` dispatches `.fight`, which (under the bank-unlock firing
    conditions) flips `bankAccessible := true`, so `bankUnlock`'s `¬bankAccessible`
    condition fails next cycle. -/
theorem bankUnlock_quiet_after_firing (s : State)
    (h : productionLadder s = some .bankUnlock) :
    fires .bankUnlock (cycleStep s) = false := by
  have hfire : fires .bankUnlock s = true := fires_of_ladder h
  have hcs : cycleStep s = applyActionKind .fight s := by
    unfold cycleStep; rw [h]; rfl
  -- The fight's `unlockMonsterReady` guard is exactly `bankUnlockFires s`, true
  -- here, so the post-state has `bankAccessible = true`.
  have hready : (s.bankUnlockMonsterPresent && !s.bankAccessible
                  && decide (s.xp ≤ s.initialXp)
                  && (decide (s.unlockMonsterLevel = 0)
                      || decide (s.level + 1 ≥ s.unlockMonsterLevel))) = true := by
    have := hfire; simp only [fires, bankUnlockFires] at this; exact this
  have hba : (applyActionKind .fight s).bankAccessible = true := by
    simp only [applyActionKind]; simp [hready]
  rw [hcs]
  simp only [fires, bankUnlockFires]
  rw [hba]; simp

end Formal.Liveness.BlockerQuieting
