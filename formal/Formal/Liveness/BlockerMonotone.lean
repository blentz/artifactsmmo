import Formal.Liveness.BlockerQuieting
import Formal.Liveness.LifecycleBound6
import Mathlib.Tactic

/-! # BlockerMonotone — permanent quieting of the opaque-flag blockers (O5.2)

Increment 6 (`BlockerQuieting`) proved each blocker quiets the cycle AFTER it
fires. This module lifts that to PERMANENT quieting for the six opaque-flag
blockers: their firing flag is only ever set `false` by `applyActionKind` (never
`true` — verified against `Plan.lean`), so once clear it stays clear along the
whole `cycleStepN` trajectory, and the blocker never fires again.

`<flag>_false_cycleStepN` — monotonicity; `<blocker>_quiet_forever_of_flag` — the
blocker is quiet at every future step once its flag is false.

Flags covered: `hasOverstockItems` (discardCritical + discardHigh),
`selectBankDepositsNonempty` (depositFull), `gearReviewFires` (gearReview),
`pendingItemsNonempty` (claimPending), `sellableInventoryNonempty` (sellPressured),
`craftReliefFires` (craftRelief).

NO new axioms (standard set + LIV-001 via the cycleStep fight branch).
-/

namespace Formal.Liveness.BlockerMonotone

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.BlockerQuieting

/-! ## hasOverstockItems (discardCritical, discardHigh) -/

theorem hasOverstockItems_false_apply (a : ActionKind) (s : State)
    (h : s.hasOverstockItems = false) :
    (applyActionKind a s).hasOverstockItems = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem hasOverstockItems_false_cycleStep (s : State)
    (h : s.hasOverstockItems = false) :
    (cycleStep s).hasOverstockItems = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact hasOverstockItems_false_apply _ s h

theorem hasOverstockItems_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.hasOverstockItems = false →
      (cycleStepN n s).hasOverstockItems = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact hasOverstockItems_false_cycleStepN n (cycleStep s)
        (hasOverstockItems_false_cycleStep s h)

/-- Once overstock is clear, `discardCritical` never fires again. -/
theorem discardCritical_quiet_forever (s : State) (h : s.hasOverstockItems = false)
    (n : Nat) : fires .discardCritical (cycleStepN n s) = false := by
  simp [fires, discardCriticalFires, hasOverstockItems_false_cycleStepN n s h]

/-- Once overstock is clear, `discardHigh` never fires again. -/
theorem discardHigh_quiet_forever (s : State) (h : s.hasOverstockItems = false)
    (n : Nat) : fires .discardHigh (cycleStepN n s) = false := by
  simp [fires, discardHighFires, hasOverstockItems_false_cycleStepN n s h]

/-! ## selectBankDepositsNonempty (depositFull) -/

theorem selectBankDeposits_false_apply (a : ActionKind) (s : State)
    (h : s.selectBankDepositsNonempty = false) :
    (applyActionKind a s).selectBankDepositsNonempty = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem selectBankDeposits_false_cycleStep (s : State)
    (h : s.selectBankDepositsNonempty = false) :
    (cycleStep s).selectBankDepositsNonempty = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact selectBankDeposits_false_apply _ s h

theorem selectBankDeposits_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.selectBankDepositsNonempty = false →
      (cycleStepN n s).selectBankDepositsNonempty = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact selectBankDeposits_false_cycleStepN n (cycleStep s)
        (selectBankDeposits_false_cycleStep s h)

/-- Once the deposit set is empty, `depositFull` never fires again. -/
theorem depositFull_quiet_forever (s : State)
    (h : s.selectBankDepositsNonempty = false) (n : Nat) :
    fires .depositFull (cycleStepN n s) = false := by
  simp [fires, depositFullFires, selectBankDeposits_false_cycleStepN n s h]

/-! ## gearReviewFires (gearReview) -/

theorem gearReviewFires_false_apply (a : ActionKind) (s : State)
    (h : s.gearReviewFires = false) :
    (applyActionKind a s).gearReviewFires = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem gearReviewFires_false_cycleStep (s : State) (h : s.gearReviewFires = false) :
    (cycleStep s).gearReviewFires = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact gearReviewFires_false_apply _ s h

theorem gearReviewFires_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.gearReviewFires = false →
      (cycleStepN n s).gearReviewFires = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact gearReviewFires_false_cycleStepN n (cycleStep s)
        (gearReviewFires_false_cycleStep s h)

/-- Once the gear-review latch is clear, `gearReview` never fires again. -/
theorem gearReview_quiet_forever (s : State) (h : s.gearReviewFires = false) (n : Nat) :
    fires .gearReview (cycleStepN n s) = false := by
  simp [fires, ProductionLadder.gearReviewFires, gearReviewFires_false_cycleStepN n s h]

/-! ## pendingItemsNonempty (claimPending) -/

theorem pendingItems_false_apply (a : ActionKind) (s : State)
    (h : s.pendingItemsNonempty = false) :
    (applyActionKind a s).pendingItemsNonempty = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem pendingItems_false_cycleStep (s : State) (h : s.pendingItemsNonempty = false) :
    (cycleStep s).pendingItemsNonempty = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact pendingItems_false_apply _ s h

theorem pendingItems_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.pendingItemsNonempty = false →
      (cycleStepN n s).pendingItemsNonempty = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact pendingItems_false_cycleStepN n (cycleStep s)
        (pendingItems_false_cycleStep s h)

/-- Once pending items are claimed, `claimPending` never fires again. -/
theorem claimPending_quiet_forever (s : State) (h : s.pendingItemsNonempty = false)
    (n : Nat) : fires .claimPending (cycleStepN n s) = false := by
  simp [fires, claimPendingFires, pendingItems_false_cycleStepN n s h]

/-! ## sellableInventoryNonempty (sellPressured) -/

theorem sellable_false_apply (a : ActionKind) (s : State)
    (h : s.sellableInventoryNonempty = false) :
    (applyActionKind a s).sellableInventoryNonempty = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem sellable_false_cycleStep (s : State) (h : s.sellableInventoryNonempty = false) :
    (cycleStep s).sellableInventoryNonempty = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact sellable_false_apply _ s h

theorem sellable_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.sellableInventoryNonempty = false →
      (cycleStepN n s).sellableInventoryNonempty = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact sellable_false_cycleStepN n (cycleStep s)
        (sellable_false_cycleStep s h)

/-- Once nothing is sellable, `sellPressured` never fires again. -/
theorem sellPressured_quiet_forever (s : State)
    (h : s.sellableInventoryNonempty = false) (n : Nat) :
    fires .sellPressured (cycleStepN n s) = false := by
  simp [fires, sellPressuredFires, sellable_false_cycleStepN n s h]

/-! ## craftReliefFires (craftRelief) -/

theorem craftReliefFires_false_apply (a : ActionKind) (s : State)
    (h : s.craftReliefFires = false) :
    (applyActionKind a s).craftReliefFires = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem craftReliefFires_false_cycleStep (s : State) (h : s.craftReliefFires = false) :
    (cycleStep s).craftReliefFires = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact craftReliefFires_false_apply _ s h

theorem craftReliefFires_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.craftReliefFires = false →
      (cycleStepN n s).craftReliefFires = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact craftReliefFires_false_cycleStepN n (cycleStep s)
        (craftReliefFires_false_cycleStep s h)

/-- Once the craft-relief latch is clear, `craftRelief` never fires again. -/
theorem craftRelief_quiet_forever (s : State) (h : s.craftReliefFires = false) (n : Nat) :
    fires .craftRelief (cycleStepN n s) = false := by
  simp [fires, craftReliefFires, craftReliefFires_false_cycleStepN n s h]

/-! ## hp = maxHp (hpCritical, restForCombat) — `hp` is only restored, never reduced -/

theorem hp_eq_maxHp_apply (a : ActionKind) (s : State) (h : s.hp = s.maxHp) :
    (applyActionKind a s).hp = (applyActionKind a s).maxHp := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem hp_eq_maxHp_cycleStep (s : State) (h : s.hp = s.maxHp) :
    (cycleStep s).hp = (cycleStep s).maxHp := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact hp_eq_maxHp_apply _ s h

theorem hp_eq_maxHp_cycleStepN :
    ∀ (n : Nat) (s : State), s.hp = s.maxHp → (cycleStepN n s).hp = (cycleStepN n s).maxHp
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact hp_eq_maxHp_cycleStepN n (cycleStep s) (hp_eq_maxHp_cycleStep s h)

/-- Once hp is full, `hpCritical` never fires again (`hp/maxHp` is not below the
    critical fraction when `hp = maxHp`). -/
theorem hpCritical_quiet_forever (s : State) (h : s.hp = s.maxHp) (n : Nat) :
    fires .hpCritical (cycleStepN n s) = false := by
  have he := hp_eq_maxHp_cycleStepN n s h
  simp only [fires, hpCriticalFires]
  rcases Nat.eq_zero_or_pos (cycleStepN n s).maxHp with hz | hp
  · simp [hz]
  · have : ¬ (CRITICAL_HP_DEN * (cycleStepN n s).hp < CRITICAL_HP_NUM * (cycleStepN n s).maxHp) := by
      rw [he]; simp only [CRITICAL_HP_DEN, CRITICAL_HP_NUM]; omega
    simp [this]

/-- Once hp is full, `restForCombat` never fires again (`hp < maxHp` fails). -/
theorem restForCombat_quiet_forever (s : State) (h : s.hp = s.maxHp) (n : Nat) :
    fires .restForCombat (cycleStepN n s) = false := by
  have he := hp_eq_maxHp_cycleStepN n s h
  simp only [fires, restForCombatFires]
  have : ¬ ((cycleStepN n s).hp < (cycleStepN n s).maxHp) := by rw [he]; omega
  simp [this]

/-! ## bankAccessible (bankUnlock) — only ever flipped true, never back -/

theorem bankAccessible_apply (a : ActionKind) (s : State) (h : s.bankAccessible = true) :
    (applyActionKind a s).bankAccessible = true := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case fight => simp only [applyActionKind]; simp [h]
  all_goals exact h

theorem bankAccessible_cycleStep (s : State) (h : s.bankAccessible = true) :
    (cycleStep s).bankAccessible = true := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact bankAccessible_apply _ s h

theorem bankAccessible_cycleStepN :
    ∀ (n : Nat) (s : State), s.bankAccessible = true → (cycleStepN n s).bankAccessible = true
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact bankAccessible_cycleStepN n (cycleStep s) (bankAccessible_cycleStep s h)

/-- Once the bank is unlocked, `bankUnlock` never fires again (`¬bankAccessible`
    fails). -/
theorem bankUnlock_quiet_forever (s : State) (h : s.bankAccessible = true) (n : Nat) :
    fires .bankUnlock (cycleStepN n s) = false := by
  simp [fires, bankUnlockFires, bankAccessible_cycleStepN n s h]

/-! ## reachUnlockLevel — `level` monotone up, `bankRequiredLevel` invariant -/

theorem bankRequiredLevel_apply (a : ActionKind) (s : State) :
    (applyActionKind a s).bankRequiredLevel = s.bankRequiredLevel := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> rfl
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> rfl
  all_goals rfl

theorem bankRequiredLevel_cycleStep (s : State) :
    (cycleStep s).bankRequiredLevel = s.bankRequiredLevel := by
  unfold cycleStep
  split
  · rfl
  · split
    · rfl
    · exact bankRequiredLevel_apply _ s

theorem bankRequiredLevel_cycleStepN :
    ∀ (n : Nat) (s : State), (cycleStepN n s).bankRequiredLevel = s.bankRequiredLevel
  | 0, _ => rfl
  | n + 1, s => by
      rw [cycleStepN_succ, bankRequiredLevel_cycleStepN n (cycleStep s),
          bankRequiredLevel_cycleStep s]

/-- Once `level` reaches `bankRequiredLevel`, `reachUnlockLevel` never fires again
    (`level < bankRequiredLevel` fails; `level` only increases, the config is
    invariant). -/
theorem reachUnlockLevel_quiet_forever (s : State)
    (h : s.level ≥ s.bankRequiredLevel) (n : Nat) :
    fires .reachUnlockLevel (cycleStepN n s) = false := by
  have hlvl : (cycleStepN n s).level ≥ s.level :=
    Formal.Liveness.LifecycleBound6.cycleStepN_level_ge s n
  have hbrl : (cycleStepN n s).bankRequiredLevel = s.bankRequiredLevel :=
    bankRequiredLevel_cycleStepN n s
  simp only [fires, reachUnlockLevelFires]
  have hge : ¬ ((cycleStepN n s).level < (cycleStepN n s).bankRequiredLevel) := by
    rw [hbrl]; omega
  simp [hge]

end Formal.Liveness.BlockerMonotone
