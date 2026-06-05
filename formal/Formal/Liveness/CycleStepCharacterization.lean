import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.ApplyXpLevelPreservation
import Formal.Liveness.LifecycleBound6
import Mathlib.Tactic

/-! # CycleStepCharacterization — Item 1g-B2 sub-step

When `productionLadder s = some .bankUnlock` or `.reachUnlockLevel`,
`cycleStep s = applyActionKind .fight s`. Combined with the
preservation lemmas, this lets us characterize xp/level changes per
cycleStep position by which ladder slot fires.

NO new axioms.
-/

namespace Formal.Liveness.CycleStepCharacterization

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.ApplyXpLevelPreservation
open Formal.Liveness.LifecycleBound6

/-- When ladder fires `.bankUnlock`, `cycleStep` applies `.fight`. -/
theorem cycleStep_eq_fight_when_bankUnlock (s : State)
    (h : productionLadder s = some .bankUnlock) :
    cycleStep s = applyActionKind .fight s := by
  unfold cycleStep
  rw [h]
  rfl

/-- When ladder fires `.reachUnlockLevel`, `cycleStep` applies `.fight`. -/
theorem cycleStep_eq_fight_when_reachUnlockLevel (s : State)
    (h : productionLadder s = some .reachUnlockLevel) :
    cycleStep s = applyActionKind .fight s := by
  unfold cycleStep
  rw [h]
  rfl

/-- Combined: when ladder fires either fight-driving means,
    `cycleStep` applies `.fight`. -/
theorem cycleStep_eq_fight_when_fightFires (s : State)
    (h : productionLadder s = some .bankUnlock
         ∨ productionLadder s = some .reachUnlockLevel) :
    cycleStep s = applyActionKind .fight s := by
  cases h with
  | inl h => exact cycleStep_eq_fight_when_bankUnlock s h
  | inr h => exact cycleStep_eq_fight_when_reachUnlockLevel s h

/-- When ladder doesn't fire `.bankUnlock`/`.reachUnlockLevel`/`.completeTask`,
    `cycleStep s` preserves both `level` and `xp`. Uses the planFor table:
    every other ladder slot maps to an ActionKind that's not `.fight`
    and not `.completeTask`. -/
theorem cycleStep_xp_level_preserved_when_no_fight_no_complete (s : State)
    (h : productionLadder s ≠ some .bankUnlock
         ∧ productionLadder s ≠ some .reachUnlockLevel
         ∧ productionLadder s ≠ some .completeTask) :
    (cycleStep s).level = s.level ∧ (cycleStep s).xp = s.xp := by
  unfold cycleStep
  obtain ⟨hbu, hru, hct⟩ := h
  -- Case-split on productionLadder s; rule out the fight-driving cases.
  cases hpl : productionLadder s with
  | none => exact ⟨rfl, rfl⟩
  | some k =>
    -- The remaining ladder slots: hpCritical, discardCritical, depositFull,
    -- discardHigh, claimPending, sellPressured, lowYieldCancel, taskCancel,
    -- objectiveStep, pursueTask, acceptTask, taskExchange, sellIdle,
    -- bankExpand, wait.
    -- planFor maps each to a non-fight, non-completeTask action.
    cases k with
    | hpCritical =>
      show (applyActionKind .rest s).level = s.level
            ∧ (applyActionKind .rest s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | bankUnlock => rw [hpl] at hbu; exact absurd rfl hbu
    | reachUnlockLevel => rw [hpl] at hru; exact absurd rfl hru
    | discardCritical =>
      show (applyActionKind .deleteItem s).level = s.level
            ∧ (applyActionKind .deleteItem s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | craftRelief =>
      -- planFor .craftRelief = [.craft]; applyActionKind .craft preserves
      -- level and xp (bumps craftableSlots + skillXpDelta only).
      show (applyActionKind .craft s).level = s.level
            ∧ (applyActionKind .craft s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | depositFull =>
      show (applyActionKind .depositAll s).level = s.level
            ∧ (applyActionKind .depositAll s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | discardHigh =>
      show (applyActionKind .deleteItem s).level = s.level
            ∧ (applyActionKind .deleteItem s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | claimPending =>
      show (applyActionKind .claimPendingItem s).level = s.level
            ∧ (applyActionKind .claimPendingItem s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | completeTask => rw [hpl] at hct; exact absurd rfl hct
    | sellPressured =>
      show (applyActionKind .npcSell s).level = s.level
            ∧ (applyActionKind .npcSell s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | lowYieldCancel =>
      show (applyActionKind .taskCancel s).level = s.level
            ∧ (applyActionKind .taskCancel s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | taskCancel =>
      show (applyActionKind .taskCancel s).level = s.level
            ∧ (applyActionKind .taskCancel s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | objectiveStep =>
      show (applyActionKind .objectiveStep s).level = s.level
            ∧ (applyActionKind .objectiveStep s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | pursueTask =>
      show (applyActionKind .taskTrade s).level = s.level
            ∧ (applyActionKind .taskTrade s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | acceptTask =>
      show (applyActionKind .acceptTask s).level = s.level
            ∧ (applyActionKind .acceptTask s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | taskExchange =>
      show (applyActionKind .taskExchange s).level = s.level
            ∧ (applyActionKind .taskExchange s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | sellIdle =>
      show (applyActionKind .npcSell s).level = s.level
            ∧ (applyActionKind .npcSell s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | bankExpand =>
      show (applyActionKind .buyBankExpansion s).level = s.level
            ∧ (applyActionKind .buyBankExpansion s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | wait =>
      show (applyActionKind .wait s).level = s.level
            ∧ (applyActionKind .wait s).xp = s.xp
      exact ⟨rfl, rfl⟩

end Formal.Liveness.CycleStepCharacterization
