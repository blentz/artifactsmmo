import Formal.Liveness.FightFairness
import Formal.Liveness.BlockerQuieting
import Formal.Liveness.CycleStepCharacterization
import Mathlib.Tactic

/-! # BlockerSettled — breaking the task-phase / composition circularity (O5.2)

The last 3 blockers (completeTask, taskCancel, lowYieldCancel) read the
non-monotone `taskLifecyclePhase`; they settle only once `objectiveStep` is
SELECTED (preempting the phase-advancing pursueTask/acceptTask), which itself needs
all blockers quiet — a circular coupling.

Break it with a SELF-PRESERVING `Settled` state that bundles every blocker's
clearing condition at once. At a `Settled` state ALL 14 blockers are quiet, so
`objectiveStep` is selected, so the cycle is a `.fight` — which preserves every
`Settled` field (fight touches only level/xp/bankAccessible/actionsAttempted, none
of which a blocker's clearing condition depends on adversely). Hence `Settled` is
`cycleStep`-invariant, and a single `Settled` state discharges the whole fairness
obligation `CombatObjectiveFairlyScheduled` — and thus level-50 reachability —
modulo only "the trajectory REACHES a Settled state" (the genuine transient).

NO new axioms (standard set + LIV-001 via the fight branch).
-/

namespace Formal.Liveness.BlockerSettled

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.FightFairness

/-- A fully-settled state: every `objectiveStepBlocker`'s firing condition is
    cleared, and a combat objective is active. The task lifecycle is parked at
    `.none`. -/
structure Settled (s : State) : Prop where
  overstock      : s.hasOverstockItems = false
  deposits       : s.selectBankDepositsNonempty = false
  gear           : s.gearReviewFires = false
  pending        : s.pendingItemsNonempty = false
  sellable       : s.sellableInventoryNonempty = false
  craft          : s.craftReliefFires = false
  recycleNonempty : s.recyclableSurplusNonempty = false
  hpFull         : s.hp = s.maxHp
  bank           : s.bankAccessible = true
  leveled        : s.level ≥ s.bankRequiredLevel
  phaseNone      : s.taskLifecyclePhase = .none
  objFires       : s.objectiveStepFires = true
  objFight       : s.objectiveStepIsFight = true

/-- At a `Settled` state every higher-priority blocker is quiet. -/
theorem Settled_blockers_quiet (s : State) (h : Settled s) :
    ∀ b ∈ objectiveStepBlockers, fires b s = false := by
  intro b hb
  fin_cases hb
  · simp only [fires, hpCriticalFires]
    rcases Nat.eq_zero_or_pos s.maxHp with hz | hpos
    · simp [hz]
    · have hlt : ¬ (CRITICAL_HP_DEN * s.hp < CRITICAL_HP_NUM * s.maxHp) := by
        rw [h.hpFull]; simp only [CRITICAL_HP_DEN, CRITICAL_HP_NUM]; omega
      simp [hlt]
  · simp [fires, restForCombatFires, h.hpFull]
  · simp [fires, bankUnlockFires, h.bank]
  · simp only [fires, reachUnlockLevelFires]
    have hge : ¬ (s.level < s.bankRequiredLevel) := by have := h.leveled; omega
    simp [hge]
  · simp [fires, discardCriticalFires, h.overstock]
  · simp [fires, ProductionLadder.craftReliefFires, h.craft]
  · simp [fires, recycleReliefFires, h.recycleNonempty]
  · simp [fires, sellReliefFires, h.sellable]
  · simp [fires, depositFullFires, h.deposits]
  · simp [fires, discardHighFires, h.overstock]
  · simp [fires, ProductionLadder.gearReviewFires, h.gear]
  · simp [fires, claimPendingFires, h.pending]
  · simp [fires, completeTaskFires, h.phaseNone]
  · simp [fires, sellPressuredFires, h.sellable]
  · simp [fires, lowYieldCancelFires, h.phaseNone]
  · simp [fires, taskCancelFires, h.phaseNone]

/-- At a `Settled` state the ladder selects `objectiveStep` (combat objective fires,
    all higher-priority means quiet). -/
theorem Settled_productionLadder (s : State) (h : Settled s) :
    productionLadder s = some .objectiveStep := by
  apply productionLadder_eq_objectiveStep_of_unblocked
  · simp [fires, ProductionLadder.objectiveStepFires, h.objFires]
  · exact Settled_blockers_quiet s h

/-- `Settled` is `cycleStep`-invariant: the selected combat objective makes the
    cycle a `.fight`, which preserves every `Settled` field. -/
theorem Settled_cycleStep (s : State) (h : Settled s) : Settled (cycleStep s) := by
  have hpl : productionLadder s = some .objectiveStep := Settled_productionLadder s h
  have hcs : cycleStep s = applyActionKind .fight s :=
    cycleStep_eq_fight_when_objectiveStepFight s hpl h.objFight
  rw [hcs]
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩
  · exact h.overstock
  · exact h.deposits
  · exact h.gear
  · exact h.pending
  · exact h.sellable
  · exact h.craft
  · -- recyclableSurplusNonempty: fight clears nothing in that field; it stays false.
    exact h.recycleNonempty
  · -- hp = maxHp (fight touches neither).
    exact h.hpFull
  · -- bankAccessible stays true.
    simp only [applyActionKind]; simp [h.bank]
  · -- level ≥ bankRequiredLevel: level non-decreasing, bankRequiredLevel untouched.
    simp only [applyActionKind]
    have := h.leveled
    split <;> omega
  · -- phase untouched = none.
    exact h.phaseNone
  · exact h.objFires
  · exact h.objFight

theorem Settled_cycleStepN :
    ∀ (n : Nat) (s : State), Settled s → Settled (cycleStepN n s)
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact Settled_cycleStepN n (cycleStep s) (Settled_cycleStep s h)

/-- **A single `Settled` state discharges the fairness obligation.** Since `Settled`
    is invariant, at EVERY future step the combat objective fires, is combat-typed,
    and is unblocked — exactly `CombatObjectiveFairlyScheduled`. -/
theorem combatScheduled_of_settled (s : State) (h : Settled s) :
    CombatObjectiveFairlyScheduled s := by
  intro N
  refine ⟨N, le_refl N, ?_, ?_, ?_⟩
  · have hN := Settled_cycleStepN N s h
    simp [fires, ProductionLadder.objectiveStepFires, hN.objFires]
  · exact (Settled_cycleStepN N s h).objFight
  · exact Settled_blockers_quiet (cycleStepN N s) (Settled_cycleStepN N s h)

/-- **End-to-end from a Settled state.** Config-positivity + a Settled state ⇒
    level 50. The whole `hfightFires` / blocker-transience tower collapses to one
    hypothesis: the trajectory reaches a `Settled` state. -/
theorem ai_reaches_level_fifty_of_settled (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (h : Settled s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  ai_reaches_level_fifty_from_fair_combat s htec hnec (combatScheduled_of_settled s h)

end Formal.Liveness.BlockerSettled
