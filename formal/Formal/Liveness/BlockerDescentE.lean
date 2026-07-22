import Formal.Liveness.EMeasure
import Formal.Liveness.CycleStepE
import Formal.Liveness.UnconditionalDescent

/-! # BlockerDescentE — per-means `EMeasure` descent for the GEARED cycle

E-tower (C2b, `docs/PLAN_c2_composed_liveness.md`): every means selectable
below 50 under `perceptionRefreshE` strictly descends the 20-slot `EMeasure`.
The D-tower rows carry over (chore applies never touch the gear fields; the
gear latch slot moved BELOW `hpDeficit` because the inadequate-arming refresh
raises it on rest/chore cycles). New rows: the three-case `gearReview`
(open gap / gap exhausted / stale latch) and the fight rows re-proved against
the fight hp-loss + rollover gear re-arm layers.

Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.BlockerDescentE

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CumulativeProgress (b2n)
open Formal.Liveness.EMeasure
open Formal.Liveness.CycleStepD
open Formal.Liveness.CycleStepE

private theorem fires_of_ladder {s : State} {k : MeansKind}
    (h : productionLadder s = some k) : fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody
    rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- The geared cycle at a selected means, unfolded. -/
private theorem cycleStepE_some (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefreshE s) = some k) :
    cycleStepE s =
      rearmE k (perceptionRefreshE s)
        (gearProgress k
          (fightLoss k (perceptionRefreshE s)
            (partialClear k
              (pressureDeltaD k (perceptionRefreshE s)
                (cycleStep (perceptionRefreshE s)))))) := by
  unfold cycleStepE
  rw [hk]

/-! ## perceptionRefreshE field bridges — only the objective Bools and the
gear latch can move. -/

private theorem refreshE_phase (s : State) :
    (perceptionRefreshE s).taskLifecyclePhase = s.taskLifecyclePhase := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_progress (s : State) :
    (perceptionRefreshE s).taskProgress = s.taskProgress := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_total (s : State) :
    (perceptionRefreshE s).taskTotal = s.taskTotal := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_overstock (s : State) :
    (perceptionRefreshE s).hasOverstockItems = s.hasOverstockItems := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_selectBankDeposits (s : State) :
    (perceptionRefreshE s).selectBankDepositsNonempty = s.selectBankDepositsNonempty := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_sellable (s : State) :
    (perceptionRefreshE s).sellableInventoryNonempty = s.sellableInventoryNonempty := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_recyclable (s : State) :
    (perceptionRefreshE s).recyclableSurplusNonempty = s.recyclableSurplusNonempty := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_craftRelief (s : State) :
    (perceptionRefreshE s).craftReliefFires = s.craftReliefFires := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_craftPotions (s : State) :
    (perceptionRefreshE s).craftPotionsFires = s.craftPotionsFires := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_pending (s : State) :
    (perceptionRefreshE s).pendingItemsNonempty = s.pendingItemsNonempty := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_inventoryUsed (s : State) :
    (perceptionRefreshE s).inventoryUsed = s.inventoryUsed := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_inventoryMax (s : State) :
    (perceptionRefreshE s).inventoryMax = s.inventoryMax := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_hp (s : State) :
    (perceptionRefreshE s).hp = s.hp := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_maxHp (s : State) :
    (perceptionRefreshE s).maxHp = s.maxHp := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_overstockDebt (s : State) :
    (perceptionRefreshE s).overstockDebt = s.overstockDebt := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_depositDebt (s : State) :
    (perceptionRefreshE s).depositDebt = s.depositDebt := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_sellDebt (s : State) :
    (perceptionRefreshE s).sellDebt = s.sellDebt := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_gearGap (s : State) :
    (perceptionRefreshE s).gearGap = s.gearGap := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_adequate (s : State) :
    (perceptionRefreshE s).loadoutAdequate = s.loadoutAdequate := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

/-! ## Layer preservation micro-lemmas (gear fields through the E layers). -/

private theorem rearmE_eq_mint_of_no_levelup {k : MeansKind} {r st : State}
    (h : st.level = r.level) : rearmE k r st = rearmOnMint k r st := by
  unfold rearmE
  rw [if_neg]
  simp [h]

private theorem rearmOnMint_gearGap (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).gearGap = st.gearGap := by
  cases k <;> simp [rearmOnMint, choreRearm, dispatchesFight, apply_ite]

private theorem rearmOnMint_adequate (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).loadoutAdequate = st.loadoutAdequate := by
  cases k <;> simp [rearmOnMint, choreRearm, dispatchesFight, apply_ite]

private theorem gearProgress_gearGap_of_ne {k : MeansKind} (st : State)
    (hkne : k ≠ .gearReview) : (gearProgress k st).gearGap = st.gearGap := by
  cases k <;> first
    | rfl
    | exact absurd rfl hkne

private theorem gearProgress_adequate_of_ne {k : MeansKind} (st : State)
    (hkne : k ≠ .gearReview) :
    (gearProgress k st).loadoutAdequate = st.loadoutAdequate := by
  cases k <;> first
    | rfl
    | exact absurd rfl hkne

private theorem fightLoss_gearGap (k : MeansKind) (r st : State) :
    (fightLoss k r st).gearGap = st.gearGap := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

private theorem fightLoss_adequate (k : MeansKind) (r st : State) :
    (fightLoss k r st).loadoutAdequate = st.loadoutAdequate := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

private theorem partialClear_gearGap (k : MeansKind) (st : State) :
    (partialClear k st).gearGap = st.gearGap := by
  cases k <;> simp [partialClear, apply_ite]

private theorem partialClear_adequate (k : MeansKind) (st : State) :
    (partialClear k st).loadoutAdequate = st.loadoutAdequate := by
  cases k <;> simp [partialClear, apply_ite]

private theorem pressureDeltaD_gearGap (k : MeansKind) (r st : State) :
    (pressureDeltaD k r st).gearGap = st.gearGap := by
  cases k <;> simp [pressureDeltaD, apply_ite]

private theorem pressureDeltaD_adequate (k : MeansKind) (r st : State) :
    (pressureDeltaD k r st).loadoutAdequate = st.loadoutAdequate := by
  cases k <;> simp [pressureDeltaD, apply_ite]

private theorem apply_fight_gearGap (r : State) :
    (applyActionKind .fight r).gearGap = r.gearGap := rfl

private theorem apply_fight_adequate (r : State) :
    (applyActionKind .fight r).loadoutAdequate = r.loadoutAdequate := rfl

/-- Composite gear-gap preservation for a NON-rollover fight cycle. -/
private theorem cycleStepE_gearGap_fight (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefreshE s) = some k)
    (hkne : k ≠ .gearReview)
    (hcp : cycleStep (perceptionRefreshE s)
        = applyActionKind .fight (perceptionRefreshE s))
    (hfl : (applyActionKind .fight (perceptionRefreshE s)).level = s.level) :
    (cycleStepE s).gearGap = s.gearGap := by
  rw [cycleStepE_some s hk, hcp]
  rw [rearmE_eq_mint_of_no_levelup (by
    rw [gearProgress_level, fightLoss_level, partialClear_level,
      pressureDeltaD_level, hfl, perceptionRefreshE_level])]
  rw [rearmOnMint_gearGap, gearProgress_gearGap_of_ne _ hkne, fightLoss_gearGap,
    partialClear_gearGap, pressureDeltaD_gearGap, apply_fight_gearGap,
    refreshE_gearGap]

/-- Composite adequacy preservation for a NON-rollover fight cycle. -/
private theorem cycleStepE_adequate_fight (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefreshE s) = some k)
    (hkne : k ≠ .gearReview)
    (hcp : cycleStep (perceptionRefreshE s)
        = applyActionKind .fight (perceptionRefreshE s))
    (hfl : (applyActionKind .fight (perceptionRefreshE s)).level = s.level) :
    (cycleStepE s).loadoutAdequate = s.loadoutAdequate := by
  rw [cycleStepE_some s hk, hcp]
  rw [rearmE_eq_mint_of_no_levelup (by
    rw [gearProgress_level, fightLoss_level, partialClear_level,
      pressureDeltaD_level, hfl, perceptionRefreshE_level])]
  rw [rearmOnMint_adequate, gearProgress_adequate_of_ne _ hkne, fightLoss_adequate,
    partialClear_adequate, pressureDeltaD_adequate, apply_fight_adequate,
    refreshE_adequate]

/-! ## Chore + lifecycle rows (D-tower rows re-proved through the E layers). -/

theorem descendsE_hpCritical (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .hpCritical) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, hpCriticalFires, Bool.and_eq_true, decide_eq_true_eq,
    refreshE_hp, refreshE_maxHp] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .rest (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_hpDeficit_dec <;>
    simp only [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, if_false, Bool.false_eq_true, Bool.false_and, reduceIte,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
    first
      | rfl
      | (obtain ⟨hpos, hlt⟩ := hfire
         simp only [CRITICAL_HP_NUM, CRITICAL_HP_DEN] at hlt
         omega)


theorem descendsE_restForCombat (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .restForCombat) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, restForCombatFires, Bool.and_eq_true, decide_eq_true_eq,
    refreshE_hp, refreshE_maxHp] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .rest (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_hpDeficit_dec <;>
    simp only [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, if_false, Bool.false_eq_true, Bool.false_and, reduceIte,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
    first
      | rfl
      | (obtain ⟨_, hlt⟩ := hfire; omega)


/-- `recycleRelief` (→ `.recycle`) strictly descends. -/
theorem descendsE_recycleRelief (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .recycleRelief) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, recycleReliefFires, Bool.and_eq_true, refreshE_recyclable] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .recycle (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_recyclable_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, hfire.2,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]


/-- `craftRelief` (→ `.craft`) strictly descends. -/
theorem descendsE_craftRelief (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .craftRelief) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.craftReliefFires, refreshE_craftRelief] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .craft (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_craftRelief_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, hfire,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]


/-- `claimPending` (→ `.claimPendingItem`) strictly descends. -/
theorem descendsE_claimPending (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .claimPending) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, claimPendingFires, refreshE_pending] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .claimPendingItem (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_pending_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, hfire,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]


theorem descendsE_discardCritical (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .discardCritical) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, discardCriticalFires, Bool.and_eq_true, refreshE_overstock] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .deleteItem (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hdebt : s.overstockDebt = 0
  · apply eLt_of_overstock_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.1.1, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · apply eLt_of_overstockDebt_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.1.1, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
      omega


theorem descendsE_discardHigh (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .discardHigh) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, discardHighFires, Bool.and_eq_true, refreshE_overstock] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .deleteItem (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hdebt : s.overstockDebt = 0
  · apply eLt_of_overstock_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.1.1, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · apply eLt_of_overstockDebt_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.1.1, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
      omega


theorem descendsE_depositFull (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .depositFull) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, depositFullFires, Bool.and_eq_true, refreshE_selectBankDeposits] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .depositAll (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hdebt : s.depositDebt = 0
  · apply eLt_of_selectBankDeposits_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.2, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · apply eLt_of_depositDebt_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.2, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
      omega


theorem descendsE_sellPressured (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .sellPressured) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, sellPressuredFires, Bool.and_eq_true, refreshE_sellable] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .npcSell (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hdebt : s.sellDebt = 0
  · apply eLt_of_sellable_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.2, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · apply eLt_of_sellDebt_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.2, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
      omega


theorem descendsE_sellRelief (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .sellRelief) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, sellReliefFires, Bool.and_eq_true, refreshE_sellable] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .npcSell (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hdebt : s.sellDebt = 0
  · apply eLt_of_sellable_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.2, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · apply eLt_of_sellDebt_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hfire.2, hdebt,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
      omega


theorem descendsE_craftPotions (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .craftPotions) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.craftPotionsFires, refreshE_craftPotions] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .craft (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hrelief : s.craftReliefFires = true
  · apply eLt_of_craftRelief_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hrelief,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · rw [Bool.not_eq_true] at hrelief
    apply eLt_of_craftPotions_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hrelief, hfire,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]


theorem descendsE_taskCancel (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .taskCancel) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, taskCancelFires, Bool.and_eq_true, Bool.or_eq_true,
    decide_eq_true_eq, refreshE_phase] at hfire
  have hphase : s.taskLifecyclePhase ≠ .none := by
    rcases hfire.1 with h | h <;> (rw [h]; intro hc; cases hc)
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .taskCancel (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_phasePresent_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, hphase,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]


theorem descendsE_lowYieldCancel (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .lowYieldCancel) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, lowYieldCancelFires, Bool.and_eq_true,
    decide_eq_true_eq, refreshE_phase] at hfire
  have hphase : s.taskLifecyclePhase ≠ .none := by
    rw [hfire.1]; intro hc; cases hc
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .taskCancel (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_phasePresent_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, hphase,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]


theorem descendsE_completeTask (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .completeTask) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, completeTaskFires, decide_eq_true_eq, refreshE_phase] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .completeTask (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hwill : (decide ((perceptionRefreshE s).xp + taskCompleteXpEstimate ≥
      xpToNextLevel (perceptionRefreshE s).level)
      && decide ((perceptionRefreshE s).level < 50)) = true
  · have hlvl : s.level < 50 := by
      have := hwill
      simp only [Bool.and_eq_true, decide_eq_true_eq, perceptionRefreshE_level] at this
      exact this.2
    have hfl : (applyActionKind .completeTask (perceptionRefreshE s)).level
        = (perceptionRefreshE s).level + 1 := by
      simp only [applyActionKind]; rw [if_pos hwill]
    apply eLt_of_levelDeficit_dec
    simp only [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      if_false, Bool.false_eq_true, Bool.false_and, reduceIte, hfl,
      perceptionRefreshE_level]
    omega
  · have hphase : s.taskLifecyclePhase ≠ .none := by
      rw [hfire]; intro h; cases h
    have hfl : (applyActionKind .completeTask (perceptionRefreshE s)).level
        = (perceptionRefreshE s).level := by
      simp only [applyActionKind]; rw [if_neg hwill]
    have hfx : (applyActionKind .completeTask (perceptionRefreshE s)).xp
        = (perceptionRefreshE s).xp := by
      simp only [applyActionKind]; rw [if_neg hwill]
      simp [taskCompleteXpEstimate]
    have hph : (applyActionKind .completeTask (perceptionRefreshE s)).taskLifecyclePhase
        = .none := by
      simp only [applyActionKind]
    have hwillP : ¬(xpToNextLevel s.level ≤ s.xp ∧ s.level < 50) := by
      simpa [Bool.and_eq_true, decide_eq_true_eq, ge_iff_le, taskCompleteXpEstimate,
        perceptionRefreshE_level, perceptionRefreshE_xp] using hwill
    apply eLt_of_phasePresent_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD, applyActionKind, hwillP, hphase, taskCompleteXpEstimate,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]

/-! ## The gearReview row — three cases: open gap, gap exhausted, stale latch. -/

theorem descendsE_gearReview (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .gearReview) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.gearReviewFires] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .optimizeLoadout (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hgap : s.gearGap = 0
  · by_cases hadq : s.loadoutAdequate = true
    · -- Stale latch: the refresh only arms when INADEQUATE, so the latch was
      -- already set in `s`; the optimize apply clears it — slot `gearReviewFlag`.
      have hlatch : s.gearReviewFires = true := by
        by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
        · have harm : perceptionRefreshE s = s := by
            unfold perceptionRefreshE
            rw [if_pos hc, if_pos hadq]
          rw [harm] at hfire
          exact hfire
        · have hid : perceptionRefreshE s = s := by
            unfold perceptionRefreshE
            rw [if_neg hc]
          rw [hid] at hfire
          exact hfire
      apply eLt_of_gearReview_dec <;>
        simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
          applyActionKind, hgap, hadq, hlatch,
          refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
    · -- Gap exhausted, inadequate: this cycle RESTORES adequacy — slot 3.
      have hadq' : s.loadoutAdequate = false := Bool.eq_false_iff.mpr hadq
      apply eLt_of_inadequacy_dec <;>
        simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
          applyActionKind, hgap, hadq',
          refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp]
  · -- Open gap: one gear step closes — slot 2.
    apply eLt_of_gearGap_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
        applyActionKind, hgap,
        refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
      omega

/-! ## Fight rows — rollover pays slot 1 (dominating the gear re-arm and the
hp loss); accumulation pays slot 4 with the gear fields provably untouched. -/

theorem descendsE_fight (s : State) (hlvl : s.level < 50)
    (hfire : productionLadder (perceptionRefreshE s) = some .bankUnlock
        ∨ productionLadder (perceptionRefreshE s) = some .reachUnlockLevel
        ∨ (productionLadder (perceptionRefreshE s) = some .objectiveStep
            ∧ (perceptionRefreshE s).objectiveStepIsFight = true)) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hcp : cycleStep (perceptionRefreshE s)
      = applyActionKind .fight (perceptionRefreshE s) :=
    cycleStep_eq_fight_when_fightCycleFires (perceptionRefreshE s) hfire
  have hFl : (cycleStepE s).level
      = (applyActionKind .fight (perceptionRefreshE s)).level := by
    rw [cycleStepE_level, hcp]
  have hFx : (cycleStepE s).xp
      = (applyActionKind .fight (perceptionRefreshE s)).xp := by
    rw [cycleStepE_xp, hcp]
  have hrl : (perceptionRefreshE s).level = s.level := perceptionRefreshE_level s
  have hrx : (perceptionRefreshE s).xp = s.xp := perceptionRefreshE_xp s
  have hk : ∃ k, k ≠ MeansKind.gearReview
      ∧ productionLadder (perceptionRefreshE s) = some k := by
    rcases hfire with h | h | ⟨h, _⟩
    · exact ⟨.bankUnlock, by decide, h⟩
    · exact ⟨.reachUnlockLevel, by decide, h⟩
    · exact ⟨.objectiveStep, by decide, h⟩
  obtain ⟨k, hkne, hksel⟩ := hk
  by_cases hwill : s.xp + 10 ≥ xpToNextLevel s.level
  · have hcond : (decide ((perceptionRefreshE s).xp + 10 ≥
          xpToNextLevel (perceptionRefreshE s).level)
          && decide ((perceptionRefreshE s).level < 50)) = true := by
      rw [hrl, hrx, decide_eq_true_eq.mpr hwill, decide_eq_true_eq.mpr hlvl]; rfl
    have hfl : (applyActionKind .fight (perceptionRefreshE s)).level = s.level + 1 := by
      simp only [applyActionKind]; rw [if_pos hcond, hrl]
    apply eLt_of_levelDeficit_dec
    simp only [eMeasure, hFl, hfl]
    omega
  · have hcond : (decide ((perceptionRefreshE s).xp + 10 ≥
          xpToNextLevel (perceptionRefreshE s).level)
          && decide ((perceptionRefreshE s).level < 50)) = false := by
      rw [hrl, hrx]
      simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
      exact Or.inl hwill
    have hfl : (applyActionKind .fight (perceptionRefreshE s)).level = s.level := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrl]
    have hfx : (applyActionKind .fight (perceptionRefreshE s)).xp = s.xp + 10 := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrx]
    have hGg := cycleStepE_gearGap_fight s hksel hkne hcp hfl
    have hAd := cycleStepE_adequate_fight s hksel hkne hcp hfl
    apply eLt_of_xpDeficit_dec
    · simp only [eMeasure, hFl, hfl]
    · simp only [eMeasure, hGg]
    · simp only [eMeasure, hAd]
    · simp only [eMeasure, hFl, hfl, hFx, hfx]
      omega

/-! ## Prefix machinery for the two refresh-armed rows. -/

/-- The blocker prefix up to (excluding) `.objectiveStep`. -/
private def gearScanPrefix : List MeansKind :=
  [.hpCritical, .restForCombat, .bankUnlock, .reachUnlockLevel,
   .discardCritical, .craftRelief, .recycleRelief, .sellRelief, .depositFull,
   .discardHigh, .gearReview, .craftPotions, .claimPending, .completeTask,
   .sellPressured, .lowYieldCancel, .taskCancel]

private theorem blockerPrefix_split :
    Formal.Liveness.UnconditionalDescent.blockerPrefix
      = gearScanPrefix ++ [.objectiveStep] := rfl

/-- Selection = `.objectiveStep` forces every EARLIER prefix means quiet — in
    particular the gear latch (it precedes the objective in the ladder). -/
private theorem gearReview_quiet_of_objectiveStep {r : State}
    (hk : productionLadder r = some .objectiveStep) :
    r.gearReviewFires = false := by
  unfold productionLadder at hk
  rw [Formal.Liveness.UnconditionalDescent.ladder_split,
    List.findSome?_append] at hk
  cases hpre : (Formal.Liveness.UnconditionalDescent.blockerPrefix).findSome?
      (fun k => if fires k r then some k else none) with
  | none =>
      exfalso
      rw [hpre, Option.none_or] at hk
      rw [List.findSome?_eq_some_iff] at hk
      obtain ⟨pre, x, suf, hl, hbody, _⟩ := hk
      by_cases hf : fires x r = true
      · simp only [hf, if_true] at hbody
        have hx : x = .objectiveStep := Option.some.inj hbody
        have hxmem : x ∈ Formal.Liveness.UnconditionalDescent.discretionaryTail := by
          rw [hl]
          exact List.mem_append_right _ List.mem_cons_self
        rw [hx] at hxmem
        revert hxmem
        decide
      · simp [hf] at hbody
  | some k' =>
      rw [hpre] at hk
      simp only [Option.some_or] at hk
      have hk' : k' = .objectiveStep := Option.some.inj hk
      rw [hk'] at hpre
      rw [blockerPrefix_split, List.findSome?_append] at hpre
      cases hpre2 : gearScanPrefix.findSome?
          (fun k => if fires k r then some k else none) with
      | some k'' =>
          exfalso
          rw [hpre2] at hpre
          simp only [Option.some_or] at hpre
          have hkk : k'' = .objectiveStep := Option.some.inj hpre
          rw [List.findSome?_eq_some_iff] at hpre2
          obtain ⟨pre, x, suf, hl, hbody, _⟩ := hpre2
          by_cases hf : fires x r = true
          · simp only [hf, if_true] at hbody
            have hx : x = k'' := Option.some.inj hbody
            have hxmem : x ∈ gearScanPrefix := by
              rw [hl]
              exact List.mem_append_right _ List.mem_cons_self
            rw [hx, hkk] at hxmem
            revert hxmem
            decide
          · simp [hf] at hbody
      | none =>
          rw [List.findSome?_eq_none_iff] at hpre2
          have h := hpre2 .gearReview (by decide)
          by_cases hf : fires .gearReview r = true
          · rw [if_pos hf] at h; cases h
          · simpa [fires, ProductionLadder.gearReviewFires,
              Bool.not_eq_true] using hf

/-! ## The two refresh-shaped rows: placeholder + pursueTask. -/

/-- A stale-armed objective Bool with `isFight = false` survives only when the
    refresh was the identity: adequate arming sets `isFight`, inadequate
    arming sets the gear latch (which would outrank the objective). -/
theorem descendsE_placeholder (s : State) (hArms : AdequateArmsFightAt s)
    (hk : productionLadder (perceptionRefreshE s) = some .objectiveStep)
    (hisF : (perceptionRefreshE s).objectiveStepIsFight = false) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hquietG : (perceptionRefreshE s).gearReviewFires = false :=
    gearReview_quiet_of_objectiveStep hk
  have hcond : (decide (s.level < 50) && !(deferGate s)) = false := by
    by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
    · exfalso
      by_cases hadq : s.loadoutAdequate = true
      · have hgd : deferGate s = false := by
          by_contra hne
          rw [Bool.not_eq_false] at hne
          simp [hne] at hc
        have hlt : s.level < 50 := by
          by_contra hne
          simp [hne] at hc
        have : (perceptionRefreshE s).objectiveStepIsFight = true := by
          unfold perceptionRefreshE
          rw [if_pos hc, if_pos hadq]
          exact (hArms hlt hgd hadq).2
        rw [this] at hisF; cases hisF
      · have : (perceptionRefreshE s).gearReviewFires = true := by
          unfold perceptionRefreshE
          rw [if_pos hc, if_neg hadq]
        rw [this] at hquietG; cases hquietG
    · rwa [Bool.not_eq_true] at hc
  have heq : perceptionRefreshE s = s := by
    unfold perceptionRefreshE
    rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
  have hk0 : productionLadder s = some .objectiveStep := by rwa [heq] at hk
  have his0 : s.objectiveStepIsFight = false := by rwa [heq] at hisF
  have hfire := fires_of_ladder hk0
  simp only [fires, ProductionLadder.objectiveStepFires] at hfire
  rw [cycleStepE_some s hk, heq]
  have hcs : cycleStep s = applyActionKind .objectiveStep s := by
    unfold cycleStep
    rw [hk0]
    simp [planFor, his0]
  rw [hcs]
  apply eLt_of_objectiveStepFlag_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, his0, hfire]

/-- `pursueTask` is selectable only inside the defer window: outside it the
    refresh arms the objective (adequate) or the gear latch (inadequate), and
    BOTH outrank it. The gate certifies work remains — `taskCycles` descends. -/
theorem descendsE_pursueTask (s : State) (hArms : AdequateArmsFightAt s) (hlvl : s.level < 50)
    (hk : productionLadder (perceptionRefreshE s) = some .pursueTask) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hprefix_none :
      (Formal.Liveness.UnconditionalDescent.blockerPrefix).findSome?
        (fun k => if fires k (perceptionRefreshE s) then some k else none)
      = none := by
    have hk' := hk
    unfold productionLadder at hk'
    rw [Formal.Liveness.UnconditionalDescent.ladder_split,
      List.findSome?_append] at hk'
    cases hpre : (Formal.Liveness.UnconditionalDescent.blockerPrefix).findSome?
        (fun k => if fires k (perceptionRefreshE s) then some k else none) with
    | some k' =>
        exfalso
        rw [hpre] at hk'
        simp only [Option.some_or] at hk'
        have hk'' := Option.some.inj hk'
        rw [List.findSome?_eq_some_iff] at hpre
        obtain ⟨pre, x, suf, hl, hbody, _⟩ := hpre
        by_cases hf : fires x (perceptionRefreshE s) = true
        · simp only [hf, if_true] at hbody
          have hx : x = .pursueTask := (Option.some.inj hbody).trans hk''
          have hxmem : x ∈ Formal.Liveness.UnconditionalDescent.blockerPrefix := by
            rw [hl]
            exact List.mem_append_right _ List.mem_cons_self
          rw [hx] at hxmem
          revert hxmem
          decide
        · simp [hf] at hbody
    | none => rfl
  rw [List.findSome?_eq_none_iff] at hprefix_none
  have hquietO : (perceptionRefreshE s).objectiveStepFires = false := by
    have h := hprefix_none .objectiveStep (by decide)
    by_cases hf : fires .objectiveStep (perceptionRefreshE s) = true
    · rw [if_pos hf] at h; cases h
    · simpa [fires, ProductionLadder.objectiveStepFires,
        Bool.not_eq_true] using hf
  have hquietG : (perceptionRefreshE s).gearReviewFires = false := by
    have h := hprefix_none .gearReview (by decide)
    by_cases hf : fires .gearReview (perceptionRefreshE s) = true
    · rw [if_pos hf] at h; cases h
    · simpa [fires, ProductionLadder.gearReviewFires,
        Bool.not_eq_true] using hf
  have hcond : (decide (s.level < 50) && !(deferGate s)) = false := by
    by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
    · exfalso
      by_cases hadq : s.loadoutAdequate = true
      · have hgd : deferGate s = false := by
          by_contra hne
          rw [Bool.not_eq_false] at hne
          simp [hne] at hc
        have hlt : s.level < 50 := by
          by_contra hne
          simp [hne] at hc
        have : (perceptionRefreshE s).objectiveStepFires = true := by
          unfold perceptionRefreshE
          rw [if_pos hc, if_pos hadq]
          exact (hArms hlt hgd hadq).1
        rw [this] at hquietO; cases hquietO
      · have : (perceptionRefreshE s).gearReviewFires = true := by
          unfold perceptionRefreshE
          rw [if_pos hc, if_neg hadq]
        rw [this] at hquietG; cases hquietG
    · rwa [Bool.not_eq_true] at hc
  have hgate : deferGate s = true := by
    rcases Bool.and_eq_false_iff.mp hcond with h | h
    · exact absurd (decide_eq_true_eq.mpr hlvl) (by rw [h]; exact Bool.false_ne_true)
    · simpa using h
  have heq : perceptionRefreshE s = s := by
    unfold perceptionRefreshE
    rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
  have hk0 : productionLadder s = some .pursueTask := by rwa [heq] at hk
  have hg := hgate
  simp only [deferGate, Bool.and_eq_true, decide_eq_true_eq] at hg
  obtain ⟨⟨_hdefer, hpursue⟩, hprog⟩ := hg
  have hphase : s.taskLifecyclePhase ≠ .none := by
    simp only [pursueTaskFires, Bool.or_eq_true, decide_eq_true_eq] at hpursue
    rcases hpursue with h | h <;> (rw [h]; intro hc; cases hc)
  have htot : s.taskTotal ≠ 0 := by omega
  rw [cycleStepE_some s hk, heq]
  have hcs : cycleStep s = applyActionKind .taskTrade s := by
    unfold cycleStep; rw [hk0]; rfl
  rw [hcs]
  have hpost : (applyActionKind .taskTrade s).taskLifecyclePhase ≠ .none := by
    simp only [applyActionKind]
    rw [if_neg htot]
    split <;> (intro hc; cases hc)
  apply eLt_of_taskCycles_dec
  · simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD, applyActionKind]
  · simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD, applyActionKind]
  · simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD, applyActionKind]
  · simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD, applyActionKind]
  · simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD, hpost, hphase]
  · simp only [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      if_false, Bool.false_eq_true, Bool.false_and, reduceIte, applyActionKind]
    omega

end Formal.Liveness.BlockerDescentE
