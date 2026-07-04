import Formal.Liveness.DMeasure
import Formal.Liveness.CycleStepD
import Formal.Liveness.UnconditionalDescent

/-! # BlockerDescentD — every below-50-selectable means strictly descends DMeasure

Brick D3 of `docs/PLAN_residual_closure.md`: the `BlockerDescent` per-means
descent re-proved over the defer-faithful, adversarially-re-arming cycle
(`cycleStepD`), against the 15-slot `DMeasure`. New rows vs the F-tower:
the synthetic `.objectiveStep` placeholder (slot 15) and `pursueTask`
(slot 4, defer window). The fight row absorbs the worst-case chore re-arm
(slots 5-12 raises are dominated by slots 1/2).

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}.
Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false
set_option linter.unusedSimpArgs false
set_option linter.unnecessarySeqFocus false
set_option linter.flexible false

namespace Formal.Liveness.BlockerDescentD

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CumulativeProgress (b2n)
open Formal.Liveness.DMeasure
open Formal.Liveness.CycleStepD

/-- A selected means fires (local copy of the `findSome?` extraction). -/
private theorem fires_of_ladder {s : State} {k : MeansKind}
    (h : productionLadder s = some k) : fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody
    rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- The defer-faithful cycle at a selected means, unfolded. -/
private theorem cycleStepD_some (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefreshD s) = some k) :
    cycleStepD s =
      rearmOnMint k (perceptionRefreshD s)
        (pressureDeltaD k (perceptionRefreshD s) (cycleStep (perceptionRefreshD s))) := by
  unfold cycleStepD
  rw [hk]

/-! ## perceptionRefreshD field bridges — only the two objective Bools move. -/

private theorem refreshD_phase (s : State) :
    (perceptionRefreshD s).taskLifecyclePhase = s.taskLifecyclePhase := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_progress (s : State) :
    (perceptionRefreshD s).taskProgress = s.taskProgress := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_total (s : State) :
    (perceptionRefreshD s).taskTotal = s.taskTotal := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_overstock (s : State) :
    (perceptionRefreshD s).hasOverstockItems = s.hasOverstockItems := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_selectBankDeposits (s : State) :
    (perceptionRefreshD s).selectBankDepositsNonempty = s.selectBankDepositsNonempty := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_sellable (s : State) :
    (perceptionRefreshD s).sellableInventoryNonempty = s.sellableInventoryNonempty := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_recyclable (s : State) :
    (perceptionRefreshD s).recyclableSurplusNonempty = s.recyclableSurplusNonempty := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_craftRelief (s : State) :
    (perceptionRefreshD s).craftReliefFires = s.craftReliefFires := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_craftPotions (s : State) :
    (perceptionRefreshD s).craftPotionsFires = s.craftPotionsFires := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_gearReview (s : State) :
    (perceptionRefreshD s).gearReviewFires = s.gearReviewFires := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_pending (s : State) :
    (perceptionRefreshD s).pendingItemsNonempty = s.pendingItemsNonempty := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_inventoryUsed (s : State) :
    (perceptionRefreshD s).inventoryUsed = s.inventoryUsed := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_inventoryMax (s : State) :
    (perceptionRefreshD s).inventoryMax = s.inventoryMax := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_hp (s : State) :
    (perceptionRefreshD s).hp = s.hp := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_maxHp (s : State) :
    (perceptionRefreshD s).maxHp = s.maxHp := by
  unfold perceptionRefreshD; split <;> rfl
private theorem refreshD_objectiveFires (s : State) :
    (perceptionRefreshD s).objectiveStepFires = true
    ∨ (perceptionRefreshD s).objectiveStepFires = s.objectiveStepFires := by
  unfold perceptionRefreshD; split
  · exact Or.inl rfl
  · exact Or.inr rfl


/-! ## Rest rows — slot 14 (`hpDeficit`). -/

theorem descendsD_hpCritical (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .hpCritical) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, hpCriticalFires, Bool.and_eq_true, decide_eq_true_eq,
    refreshD_hp, refreshD_maxHp] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .rest (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_hpDeficit_dec <;>
    simp only [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, if_false, Bool.false_eq_true, reduceIte,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp] <;>
    first
      | rfl
      | (obtain ⟨hpos, hlt⟩ := hfire
         simp only [CRITICAL_HP_NUM, CRITICAL_HP_DEN] at hlt
         omega)

theorem descendsD_restForCombat (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .restForCombat) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, restForCombatFires, Bool.and_eq_true, decide_eq_true_eq,
    refreshD_hp, refreshD_maxHp] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .rest (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_hpDeficit_dec <;>
    simp only [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, if_false, Bool.false_eq_true, reduceIte,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp] <;>
    first
      | rfl
      | (obtain ⟨_, hlt⟩ := hfire; omega)


/-- `discardCritical` (→ `.deleteItem`) strictly descends. -/
theorem descendsD_discardCritical (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .discardCritical) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, discardCriticalFires, Bool.and_eq_true, refreshD_overstock] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .deleteItem (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_overstock_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire.1.1,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `discardHigh` (→ `.deleteItem`) strictly descends. -/
theorem descendsD_discardHigh (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .discardHigh) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, discardHighFires, Bool.and_eq_true, refreshD_overstock] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .deleteItem (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_overstock_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire.1.1,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `depositFull` (→ `.depositAll`) strictly descends. -/
theorem descendsD_depositFull (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .depositFull) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, depositFullFires, Bool.and_eq_true, refreshD_selectBankDeposits] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .depositAll (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_selectBankDeposits_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire.2,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `sellPressured` (→ `.npcSell`) strictly descends. -/
theorem descendsD_sellPressured (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .sellPressured) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, sellPressuredFires, Bool.and_eq_true, refreshD_sellable] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .npcSell (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_sellable_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire.2,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `sellRelief` (→ `.npcSell`) strictly descends. -/
theorem descendsD_sellRelief (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .sellRelief) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, sellReliefFires, Bool.and_eq_true, refreshD_sellable] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .npcSell (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_sellable_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire.2,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `recycleRelief` (→ `.recycle`) strictly descends. -/
theorem descendsD_recycleRelief (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .recycleRelief) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, recycleReliefFires, Bool.and_eq_true, refreshD_recyclable] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .recycle (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_recyclable_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire.2,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `craftRelief` (→ `.craft`) strictly descends. -/
theorem descendsD_craftRelief (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .craftRelief) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.craftReliefFires, refreshD_craftRelief] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .craft (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_craftRelief_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `gearReview` (→ `.optimizeLoadout`) strictly descends. -/
theorem descendsD_gearReview (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .gearReview) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.gearReviewFires, refreshD_gearReview] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .optimizeLoadout (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_gearReview_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `claimPending` (→ `.claimPendingItem`) strictly descends. -/
theorem descendsD_claimPending (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .claimPending) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, claimPendingFires, refreshD_pending] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .claimPendingItem (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_pending_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hfire,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-- `craftPotions` (→ `.craft`, clears BOTH craft flags): descends at
    `craftReliefFlag` when that latch was armed, else at `craftPotionsFlag`. -/
theorem descendsD_craftPotions (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .craftPotions) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.craftPotionsFires, refreshD_craftPotions] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .craft (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hrelief : s.craftReliefFires = true
  · apply dLt_of_craftRelief_dec <;>
      simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
        applyActionKind, hrelief,
        refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]
  · rw [Bool.not_eq_true] at hrelief
    apply dLt_of_craftPotions_dec <;>
      simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
        applyActionKind, hrelief, hfire,
        refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]


/-! ## Task-lifecycle rows — slot 3 (`phasePresent`). -/

/-- `taskCancel` (→ `.taskCancel`) strictly descends at `phasePresent`. -/
theorem descendsD_taskCancel (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .taskCancel) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, taskCancelFires, Bool.and_eq_true, Bool.or_eq_true,
    decide_eq_true_eq, refreshD_phase] at hfire
  have hphase : s.taskLifecyclePhase ≠ .none := by
    rcases hfire.1 with h | h <;> (rw [h]; intro hc; cases hc)
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .taskCancel (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_phasePresent_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hphase,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]

/-- `lowYieldCancel` (→ `.taskCancel`) strictly descends at `phasePresent`. -/
theorem descendsD_lowYieldCancel (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .lowYieldCancel) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, lowYieldCancelFires, Bool.and_eq_true,
    decide_eq_true_eq, refreshD_phase] at hfire
  have hphase : s.taskLifecyclePhase ≠ .none := by
    rw [hfire.1]; intro hc; cases hc
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .taskCancel (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply dLt_of_phasePresent_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, hphase,
      refreshD_phase, refreshD_progress, refreshD_total, refreshD_overstock,
      refreshD_selectBankDeposits, refreshD_sellable, refreshD_recyclable,
      refreshD_craftRelief, refreshD_craftPotions, refreshD_gearReview,
      refreshD_pending, refreshD_inventoryUsed, refreshD_inventoryMax,
      refreshD_hp, refreshD_maxHp,
      perceptionRefreshD_level, perceptionRefreshD_xp]

/-- `completeTask` (→ `.completeTask`): `levelDeficit` in the degenerate
    rollover branch, else `phasePresent` (the xp grant is 0). -/
theorem descendsD_completeTask (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .completeTask) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, completeTaskFires, decide_eq_true_eq, refreshD_phase] at hfire
  rw [cycleStepD_some s hk]
  have hcs : cycleStep (perceptionRefreshD s) =
      applyActionKind .completeTask (perceptionRefreshD s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hwill : (decide ((perceptionRefreshD s).xp + taskCompleteXpEstimate ≥
      xpToNextLevel (perceptionRefreshD s).level)
      && decide ((perceptionRefreshD s).level < 50)) = true
  · have hlvl : s.level < 50 := by
      have := hwill
      simp only [Bool.and_eq_true, decide_eq_true_eq, perceptionRefreshD_level] at this
      exact this.2
    have hfl : (applyActionKind .completeTask (perceptionRefreshD s)).level
        = (perceptionRefreshD s).level + 1 := by
      simp only [applyActionKind]; rw [if_pos hwill]
    apply dLt_of_levelDeficit_dec
    simp only [dMeasure, rearmOnMint, dispatchesFight, choreRearm, pressureDeltaD,
      if_false, Bool.false_eq_true, reduceIte, hfl, perceptionRefreshD_level]
    omega
  · have hphase : s.taskLifecyclePhase ≠ .none := by
      rw [hfire]; intro h; cases h
    have hfl : (applyActionKind .completeTask (perceptionRefreshD s)).level
        = (perceptionRefreshD s).level := by
      simp only [applyActionKind]; rw [if_neg hwill]
    have hfx : (applyActionKind .completeTask (perceptionRefreshD s)).xp
        = (perceptionRefreshD s).xp := by
      simp only [applyActionKind]; rw [if_neg hwill]
      simp [taskCompleteXpEstimate]
    have hph : (applyActionKind .completeTask (perceptionRefreshD s)).taskLifecyclePhase
        = .none := by
      simp only [applyActionKind]
    apply dLt_of_phasePresent_dec
    · simp [dMeasure, rearmOnMint, dispatchesFight, choreRearm, pressureDeltaD, hfl,
        perceptionRefreshD_level]
    · simp [dMeasure, rearmOnMint, dispatchesFight, choreRearm, pressureDeltaD, hfl, hfx,
        perceptionRefreshD_level, perceptionRefreshD_xp]
    · simp [dMeasure, rearmOnMint, dispatchesFight, choreRearm, pressureDeltaD, hph, hphase]


/-! ## Fight row — slots 1/2 dominate the worst-case re-arm, the loot fill,
and the armed flag. -/

/-- A fight cycle strictly descends `DMeasure` at `levelDeficit`/`xpDeficit`.
    Mirror of `BlockerDescent.descends_fight` with the D-bridges. -/
theorem descendsD_fight (s : State) (hlvl : s.level < 50)
    (hfire : productionLadder (perceptionRefreshD s) = some .bankUnlock
        ∨ productionLadder (perceptionRefreshD s) = some .reachUnlockLevel
        ∨ (productionLadder (perceptionRefreshD s) = some .objectiveStep
            ∧ (perceptionRefreshD s).objectiveStepIsFight = true)) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  have hcp : cycleStep (perceptionRefreshD s)
      = applyActionKind .fight (perceptionRefreshD s) :=
    cycleStep_eq_fight_when_fightCycleFires (perceptionRefreshD s) hfire
  have hFl : (cycleStepD s).level
      = (applyActionKind .fight (perceptionRefreshD s)).level := by
    rw [cycleStepD_level, hcp]
  have hFx : (cycleStepD s).xp
      = (applyActionKind .fight (perceptionRefreshD s)).xp := by
    rw [cycleStepD_xp, hcp]
  have hrl : (perceptionRefreshD s).level = s.level := perceptionRefreshD_level s
  have hrx : (perceptionRefreshD s).xp = s.xp := perceptionRefreshD_xp s
  by_cases hwill : s.xp + 10 ≥ xpToNextLevel s.level
  · have hcond : (decide ((perceptionRefreshD s).xp + 10 ≥ xpToNextLevel (perceptionRefreshD s).level)
                  && decide ((perceptionRefreshD s).level < 50)) = true := by
      rw [hrl, hrx, decide_eq_true_eq.mpr hwill, decide_eq_true_eq.mpr hlvl]; rfl
    have hfl : (applyActionKind .fight (perceptionRefreshD s)).level = s.level + 1 := by
      simp only [applyActionKind]; rw [if_pos hcond, hrl]
    apply dLt_of_levelDeficit_dec
    simp only [dMeasure, hFl, hfl]
    omega
  · have hcond : (decide ((perceptionRefreshD s).xp + 10 ≥ xpToNextLevel (perceptionRefreshD s).level)
                  && decide ((perceptionRefreshD s).level < 50)) = false := by
      rw [hrl, hrx]
      simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
      exact Or.inl hwill
    have hfl : (applyActionKind .fight (perceptionRefreshD s)).level = s.level := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrl]
    have hfx : (applyActionKind .fight (perceptionRefreshD s)).xp = s.xp + 10 := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrx]
    apply dLt_of_xpDeficit_dec
    · simp only [dMeasure, hFl, hfl]
    · simp only [dMeasure, hFl, hfl, hFx, hfx]
      omega


/-! ## The two D-only rows: placeholder + pursueTask. -/

/-- A stale-armed objective Bool with `objectiveStepIsFight = false` can only
    survive INSIDE the defer window (arming would have set both Bools); the
    dispatched synthetic placeholder clears it — slot 15, no loot, no re-arm. -/
theorem descendsD_placeholder (s : State)
    (hk : productionLadder (perceptionRefreshD s) = some .objectiveStep)
    (hisF : (perceptionRefreshD s).objectiveStepIsFight = false) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  -- The refresh must have been the identity (arming sets isFight := true).
  have hcond : (decide (s.level < 50) && !(deferGate s)) = false := by
    by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
    · exfalso
      have : (perceptionRefreshD s).objectiveStepIsFight = true := by
        unfold perceptionRefreshD; rw [if_pos hc]
      rw [this] at hisF; cases hisF
    · rwa [Bool.not_eq_true] at hc
  have heq : perceptionRefreshD s = s := by
    unfold perceptionRefreshD
    rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
  have hk0 : productionLadder s = some .objectiveStep := by rwa [heq] at hk
  have his0 : s.objectiveStepIsFight = false := by rwa [heq] at hisF
  have hfire := fires_of_ladder hk0
  simp only [fires, ProductionLadder.objectiveStepFires] at hfire
  rw [cycleStepD_some s hk, heq]
  have hcs : cycleStep s = applyActionKind .objectiveStep s := by
    unfold cycleStep
    rw [hk0]
    simp [planFor, his0]
  rw [hcs]
  apply dLt_of_objectiveStepFlag_dec <;>
    simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      applyActionKind, his0, hfire]

/-- `pursueTask` is selectable only inside the defer window (outside it the
    armed `objectiveStep` precedes it); the gate certifies `progress < total`,
    so the task trade strictly descends `taskCycles`. -/
theorem descendsD_pursueTask (s : State) (hlvl : s.level < 50)
    (hk : productionLadder (perceptionRefreshD s) = some .pursueTask) :
    dMeasureLt (dMeasure (cycleStepD s)) (dMeasure s) := by
  -- objectiveStep is quiet on the refreshed state (it precedes pursueTask).
  have hquiet : (perceptionRefreshD s).objectiveStepFires = false := by
    have hk' := hk
    unfold productionLadder at hk'
    rw [Formal.Liveness.UnconditionalDescent.ladder_split,
      List.findSome?_append] at hk'
    cases hpre : (Formal.Liveness.UnconditionalDescent.blockerPrefix).findSome?
        (fun k => if fires k (perceptionRefreshD s) then some k else none) with
    | some k' =>
        exfalso
        rw [hpre] at hk'
        simp only [Option.some_or] at hk'
        have hk'' := Option.some.inj hk'
        rw [List.findSome?_eq_some_iff] at hpre
        obtain ⟨pre, x, suf, hl, hbody, _⟩ := hpre
        by_cases hf : fires x (perceptionRefreshD s) = true
        · simp only [hf, if_true] at hbody
          have hx : x = .pursueTask := (Option.some.inj hbody).trans hk''
          have hxmem : x ∈ Formal.Liveness.UnconditionalDescent.blockerPrefix := by
            rw [hl]
            exact List.mem_append_right _ (List.mem_cons_self)
          rw [hx] at hxmem
          revert hxmem
          decide
        · simp [hf] at hbody
    | none =>
        rw [List.findSome?_eq_none_iff] at hpre
        have h : (if fires .objectiveStep (perceptionRefreshD s) = true
            then some MeansKind.objectiveStep else none)
            = (none : Option MeansKind) :=
          hpre .objectiveStep (by decide)
        by_cases hf : fires .objectiveStep (perceptionRefreshD s) = true
        · rw [if_pos hf] at h; cases h
        · simpa [fires, ProductionLadder.objectiveStepFires,
            Bool.not_eq_true] using hf
  -- Hence the refresh did NOT arm: below 50 that forces the gate to hold.
  have hcond : (decide (s.level < 50) && !(deferGate s)) = false := by
    by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
    · exfalso
      have : (perceptionRefreshD s).objectiveStepFires = true := by
        unfold perceptionRefreshD; rw [if_pos hc]
      rw [this] at hquiet; cases hquiet
    · rwa [Bool.not_eq_true] at hc
  have hgate : deferGate s = true := by
    rcases Bool.and_eq_false_iff.mp hcond with h | h
    · exact absurd (decide_eq_true_eq.mpr hlvl) (by rw [h]; exact Bool.false_ne_true)
    · simpa using h
  have heq : perceptionRefreshD s = s := by
    unfold perceptionRefreshD
    rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
  have hk0 : productionLadder s = some .pursueTask := by rwa [heq] at hk
  -- The gate's conjuncts: task active + work remaining.
  have hg := hgate
  simp only [deferGate, Bool.and_eq_true, decide_eq_true_eq] at hg
  obtain ⟨⟨_hdefer, hpursue⟩, hprog⟩ := hg
  have hphase : s.taskLifecyclePhase ≠ .none := by
    simp only [pursueTaskFires, Bool.or_eq_true, decide_eq_true_eq] at hpursue
    rcases hpursue with h | h <;> (rw [h]; intro hc; cases hc)
  have htot : s.taskTotal ≠ 0 := by omega
  rw [cycleStepD_some s hk, heq]
  have hcs : cycleStep s = applyActionKind .taskTrade s := by
    unfold cycleStep; rw [hk0]; rfl
  rw [hcs]
  have hpost : (applyActionKind .taskTrade s).taskLifecyclePhase ≠ .none := by
    simp only [applyActionKind]
    rw [if_neg htot]
    split <;> (intro hc; cases hc)
  apply dLt_of_taskCycles_dec
  · simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD, applyActionKind]
  · simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD, applyActionKind]
  · simp [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD, hpost, hphase]
  · simp only [dMeasure, rearmOnMint, dispatchesFight, pressureDeltaD,
      if_false, Bool.false_eq_true, reduceIte, applyActionKind]
    omega

end Formal.Liveness.BlockerDescentD
