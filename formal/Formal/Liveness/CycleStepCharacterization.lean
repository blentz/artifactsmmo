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

/-- O5.2 (2026-06-16): when ladder fires `.objectiveStep` AND the objective step
    is a COMBAT step (`objectiveStepIsFight`), `cycleStep` applies `.fight` — the
    faithful general char-leveling path (production `ReachCharLevel` meta-goal /
    combat objectives). `planFor .objectiveStep` routes to `[.fight]`. -/
theorem cycleStep_eq_fight_when_objectiveStepFight (s : State)
    (h : productionLadder s = some .objectiveStep)
    (hf : s.objectiveStepIsFight = true) :
    cycleStep s = applyActionKind .fight s := by
  unfold cycleStep
  rw [h]
  simp [planFor, hf]

/-- O5.2 combined fight-firing: bank-bootstrap OR a combat objective.
    This is the SATISFIABLE fight predicate — `objectiveStep`-with-`isFight`
    fires while `level < 50` (OBJECTIVE_STEP at ladder idx 14, before the
    discretionary task means), so the leveling trajectory is realizable, unlike
    the bank-bootstrap-only disjunction (which retires after unlock). -/
theorem cycleStep_eq_fight_when_fightCycleFires (s : State)
    (h : productionLadder s = some .bankUnlock
         ∨ productionLadder s = some .reachUnlockLevel
         ∨ (productionLadder s = some .objectiveStep
             ∧ s.objectiveStepIsFight = true)) :
    cycleStep s = applyActionKind .fight s := by
  rcases h with h | h | ⟨h, hf⟩
  · exact cycleStep_eq_fight_when_bankUnlock s h
  · exact cycleStep_eq_fight_when_reachUnlockLevel s h
  · exact cycleStep_eq_fight_when_objectiveStepFight s h hf

/-- When ladder doesn't fire `.bankUnlock`/`.reachUnlockLevel` (and any firing
    `.objectiveStep` is neither a combat step nor a met task's turn-in),
    `cycleStep s` preserves both `level` and `xp`. Uses the planFor table: every
    other ladder slot maps to an ActionKind that's not `.fight` and not
    `.completeTask`.

    RESTATED Phase 5-2c-iii-c-2 #6: the `≠ some .completeTask` conjunct went
    with the COMPLETE_TASK rung; the turn-in it excluded is now the objective
    step's dispatch on a met task alone (Bool unarmed, phase `.complete`), so
    the `.objectiveStep` conjunct excludes that dispatch instead.

    O5.2 (2026-06-16): the `objectiveStep`-is-fight guard is now explicit — a
    combat objective DOES advance level/xp (the faithful general leveling path),
    so the "no level/xp change" claim is true exactly when it is a placeholder. -/
theorem cycleStep_xp_level_preserved_when_no_fight_no_complete (s : State)
    (h : productionLadder s ≠ some .bankUnlock
         ∧ productionLadder s ≠ some .reachUnlockLevel
         ∧ (productionLadder s = some .objectiveStep →
              s.objectiveStepIsFight = false
              ∧ (s.objectiveStepFires = true
                 ∨ s.taskLifecyclePhase ≠ .complete))) :
    (cycleStep s).level = s.level ∧ (cycleStep s).xp = s.xp := by
  unfold cycleStep
  obtain ⟨hbu, hru, hof⟩ := h
  -- Case-split on productionLadder s; rule out the fight-driving cases.
  cases hpl : productionLadder s with
  | none => exact ⟨rfl, rfl⟩
  | some k =>
    -- The remaining ladder slots: hpCritical, discardCritical, depositFull,
    -- discardHigh, claimPending, sellPressured,
    -- objectiveStep, sellIdle,
    -- bankExpand, wait.
    -- planFor maps each to a non-fight, non-completeTask action.
    cases k with
    | hpCritical =>
      show (applyActionKind .rest s).level = s.level
            ∧ (applyActionKind .rest s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | restForCombat =>
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
    | geCancel =>
      -- planFor .geCancel = [.geCancelOrder]; applyActionKind .geCancelOrder
      -- preserves level and xp (clears geCancelTargetsNonempty only).
      show (applyActionKind .geCancelOrder s).level = s.level
            ∧ (applyActionKind .geCancelOrder s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | recycleRelief =>
      -- planFor .recycleRelief = [.recycle]; applyActionKind .recycle preserves
      -- level and xp (clears recyclableSurplusNonempty only).
      show (applyActionKind .recycle s).level = s.level
            ∧ (applyActionKind .recycle s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | sellRelief =>
      -- planFor .sellRelief = [.npcSell]; applyActionKind .npcSell preserves
      -- level and xp (clears sellableInventoryNonempty only).
      show (applyActionKind .npcSell s).level = s.level
            ∧ (applyActionKind .npcSell s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | maintainConsumables =>
      -- PLAN #6a: planFor .maintainConsumables = [.craft], same as craftRelief.
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
    | craftPotions =>
      -- planFor .craftPotions = [.craft], same as craftRelief.
      show (applyActionKind .craft s).level = s.level
            ∧ (applyActionKind .craft s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | claimPending =>
      show (applyActionKind .claimPendingItem s).level = s.level
            ∧ (applyActionKind .claimPendingItem s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | sellPressured =>
      show (applyActionKind .npcSell s).level = s.level
            ∧ (applyActionKind .npcSell s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | objectiveStep =>
      obtain ⟨hisf', hnct⟩ := hof hpl
      show (match (if s.objectiveStepIsFight then [ActionKind.fight]
                    else if s.objectiveStepFires then [ActionKind.objectiveStep]
                    else if s.taskLifecyclePhase = TaskLifecyclePhase.TaskLifecyclePhase.complete then [ActionKind.completeTask]
                    else if s.taskLifecyclePhase = TaskLifecyclePhase.TaskLifecyclePhase.none then
                      (if s.currencyTurnInActive then [ActionKind.npcBuy] else [ActionKind.gather])
                    else [ActionKind.taskTrade]) with
              | [] => s | a :: _ => applyActionKind a s).level = s.level
            ∧ (match (if s.objectiveStepIsFight then [ActionKind.fight]
                    else if s.objectiveStepFires then [ActionKind.objectiveStep]
                    else if s.taskLifecyclePhase = TaskLifecyclePhase.TaskLifecyclePhase.complete then [ActionKind.completeTask]
                    else if s.taskLifecyclePhase = TaskLifecyclePhase.TaskLifecyclePhase.none then
                      (if s.currencyTurnInActive then [ActionKind.npcBuy] else [ActionKind.gather])
                    else [ActionKind.taskTrade]) with
              | [] => s | a :: _ => applyActionKind a s).xp = s.xp
      rw [if_neg (by simp [hisf'])]
      by_cases hosf : s.objectiveStepFires = true
      · rw [if_pos hosf]; exact ⟨rfl, rfl⟩
      · rw [if_neg hosf]
        have hnc : s.taskLifecyclePhase ≠ .complete := by
          rcases hnct with h | h
          · exact absurd h hosf
          · exact h
        -- Phase 5-2c-iv: the fleet step's `.npcBuy` / `.gather` preserve
        -- character level and xp, like the task work's `.taskTrade`.
        rw [if_neg hnc]
        by_cases hpn : s.taskLifecyclePhase = .none
        · rw [if_pos hpn]
          by_cases hcur : s.currencyTurnInActive = true
          · rw [if_pos hcur]; exact ⟨rfl, rfl⟩
          · rw [if_neg hcur]; exact ⟨rfl, rfl⟩
        · rw [if_neg hpn]; exact ⟨rfl, rfl⟩
    | sellIdle =>
      show (applyActionKind .npcSell s).level = s.level
            ∧ (applyActionKind .npcSell s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | recycleSurplus =>
      show (applyActionKind .recycle s).level = s.level
            ∧ (applyActionKind .recycle s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | drainBankJunk =>
      show (applyActionKind .withdrawItem s).level = s.level
            ∧ (applyActionKind .withdrawItem s).xp = s.xp
      exact ⟨rfl, rfl⟩
    | geBid =>
      show (applyActionKind .gePostBuyOrder s).level = s.level
            ∧ (applyActionKind .gePostBuyOrder s).xp = s.xp
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
