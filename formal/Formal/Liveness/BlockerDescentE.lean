import Formal.Liveness.EMeasure
import Formal.Liveness.CycleStepE
import Formal.Liveness.UnconditionalDescent

/-! # BlockerDescentE — per-means `EMeasure` descent for the GEARED cycle

E-tower (C2b, `docs/PLAN_c2_composed_liveness.md`): every means selectable
below 50 under `perceptionRefreshE` strictly descends the 23-slot `EMeasure`.
The D-tower rows carry over (chore applies never touch the gear fields). New
rows: the fight rows re-proved against the fight hp-loss + rollover gear re-arm
layers, and the gear objective step. (The `gearReview` latch and its row were
retired in Phase 4-3b.)

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
private theorem refreshE_geCancel (s : State) :
    (perceptionRefreshE s).geCancelTargetsNonempty = s.geCancelTargetsNonempty := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_supplyDemand (s : State) :
    (perceptionRefreshE s).supplyDemand = s.supplyDemand := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_supplyAsymmetric (s : State) :
    (perceptionRefreshE s).supplyAsymmetric = s.supplyAsymmetric := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl
private theorem refreshE_currencyTurnIn (s : State) :
    (perceptionRefreshE s).currencyTurnInActive = s.currencyTurnInActive := by
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

private theorem rearmOnMint_level (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).level = st.level := by
  unfold rearmOnMint turnInRearm choreRearm; split
  · rfl
  · cases k <;> first | rfl | (dsimp only; split <;> rfl)

private theorem rearmOnMint_gearGap (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).gearGap = st.gearGap := by
  unfold rearmOnMint turnInRearm choreRearm; split
  · rfl
  · cases k <;> first | rfl | (dsimp only; split <;> rfl)

private theorem rearmOnMint_adequate (k : MeansKind) (r st : State) :
    (rearmOnMint k r st).loadoutAdequate = st.loadoutAdequate := by
  unfold rearmOnMint turnInRearm choreRearm; split
  · rfl
  · cases k <;> first | rfl | (dsimp only; split <;> rfl)

-- WAVE 4 RE-HOME: `gearProgress` runs on the non-combat OBJECTIVE STEP, so
-- "this step makes no gear progress" is "the rung is not the objective step, OR
-- it is and that step is a FIGHT" — the two arms `gearProgress` keeps disjoint.
private theorem gearProgress_gearGap_of_notGear {k : MeansKind} (st : State)
    (h : k ≠ .objectiveStep ∨ st.objectiveStepIsFight = true) :
    (gearProgress k st).gearGap = st.gearGap := by
  cases k <;> try rfl
  case objectiveStep =>
    rcases h with h | h
    · exact absurd rfl h
    · unfold gearProgress; simp [h]

private theorem gearProgress_adequate_of_notGear {k : MeansKind} (st : State)
    (h : k ≠ .objectiveStep ∨ st.objectiveStepIsFight = true) :
    (gearProgress k st).loadoutAdequate = st.loadoutAdequate := by
  cases k <;> try rfl
  case objectiveStep =>
    rcases h with h | h
    · exact absurd rfl h
    · unfold gearProgress; simp [h]

-- WAVE 4: `gearProgress` now reads `objectiveStepIsFight` off the state it is
-- applied to, which is the INNER composed state, so the fight-cycle composites
-- need that field carried through the layers below it. None of them touch it.
-- WAVE 4: a non-combat objective step is the GEAR step, so `gearProgress` can
-- move `gearGap` (slot 2) or `loadoutAdequate` (slot 3) — both ABOVE
-- `objectiveStepFlag`. Every caller therefore needs to know which of the three
-- things it did, and this is the exhaustive split.
private theorem gearProgress_objectiveStep_cases (st : State)
    (hisF : st.objectiveStepIsFight = false) :
    gearProgress .objectiveStep st = st
    ∨ (gearProgress .objectiveStep st).gearGap < st.gearGap
    ∨ ((gearProgress .objectiveStep st).gearGap = st.gearGap
        ∧ (gearProgress .objectiveStep st).loadoutAdequate = true
        ∧ st.loadoutAdequate = false) := by
  unfold gearProgress
  rw [if_neg (by rw [hisF]; exact Bool.false_ne_true)]
  by_cases hp : st.gearCycleProductive = true
  · rw [if_neg (by simp [hp])]
    by_cases hz : st.gearGap = 0
    · rw [if_pos hz]
      -- Already adequate means the update is the IDENTITY, which is arm 1;
      -- only a genuine false -> true restores adequacy and descends.
      by_cases ha : st.loadoutAdequate = true
      · exact Or.inl (by rw [← ha])
      · exact Or.inr (Or.inr ⟨rfl, rfl, by simpa using ha⟩)
    · rw [if_neg hz]
      exact Or.inr (Or.inl (by simp; omega))
  · rw [if_pos (by simp [Bool.not_eq_true] at hp ⊢; exact hp)]
    exact Or.inl rfl

-- Only the `.objectiveStep` apply arm is missing; the layer lemmas already exist.
private theorem apply_objectiveStep_productive (r : State) :
    (applyActionKind .objectiveStep r).gearCycleProductive = r.gearCycleProductive := rfl

private theorem fightLoss_isFight (k : MeansKind) (r st : State) :
    (fightLoss k r st).objectiveStepIsFight = st.objectiveStepIsFight := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

private theorem partialClear_isFight (k : MeansKind) (st : State) :
    (partialClear k st).objectiveStepIsFight = st.objectiveStepIsFight := by
  cases k <;> simp [partialClear, apply_ite]

private theorem pressureDeltaD_isFight (k : MeansKind) (r st : State) :
    (pressureDeltaD k r st).objectiveStepIsFight = st.objectiveStepIsFight := by
  cases k <;> simp [pressureDeltaD, apply_ite]

private theorem apply_fight_isFight (r : State) :
    (applyActionKind .fight r).objectiveStepIsFight = r.objectiveStepIsFight := by
  simp only [applyActionKind]

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

/-! ### `gearCycleProductive` preservation (increment 4).

The productivity observation is carried by the state and touched by NOTHING in
the cycle — every layer is a `{ s with ... }` update over other fields. These
lemmas let the descent rows transport `hprodc` (stated about `s`) through the
composed post-apply state that `gearProgress` actually sees. -/

private theorem refreshE_productive (s : State) :
    (perceptionRefreshE s).gearCycleProductive = s.gearCycleProductive := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

private theorem fightLoss_productive (k : MeansKind) (r st : State) :
    (fightLoss k r st).gearCycleProductive = st.gearCycleProductive := by
  unfold fightLoss
  split
  · split <;> rfl
  · rfl

private theorem partialClear_productive (k : MeansKind) (st : State) :
    (partialClear k st).gearCycleProductive = st.gearCycleProductive := by
  cases k <;> simp [partialClear, apply_ite]

private theorem pressureDeltaD_productive (k : MeansKind) (r st : State) :
    (pressureDeltaD k r st).gearCycleProductive = st.gearCycleProductive := by
  cases k <;> simp [pressureDeltaD, apply_ite]

private theorem apply_optimizeLoadout_productive (r : State) :
    (applyActionKind .optimizeLoadout r).gearCycleProductive
      = r.gearCycleProductive := rfl

-- `applyActionKind .objectiveStep` only clears the fires flag, so every slot the
-- gear branch reasons about passes straight through it.
private theorem apply_objectiveStep_gearGap (r : State) :
    (applyActionKind .objectiveStep r).gearGap = r.gearGap := rfl

private theorem apply_objectiveStep_adequate (r : State) :
    (applyActionKind .objectiveStep r).loadoutAdequate = r.loadoutAdequate := rfl

private theorem apply_objectiveStep_level (r : State) :
    (applyActionKind .objectiveStep r).level = r.level := rfl

private theorem apply_fight_gearGap (r : State) :
    (applyActionKind .fight r).gearGap = r.gearGap := rfl

private theorem apply_fight_adequate (r : State) :
    (applyActionKind .fight r).loadoutAdequate = r.loadoutAdequate := rfl

/-- Composite gear-gap preservation for a NON-rollover fight cycle. -/
private theorem cycleStepE_gearGap_fight (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefreshE s) = some k)
    (hkne : k ≠ .objectiveStep
        ∨ (perceptionRefreshE s).objectiveStepIsFight = true)
    (hcp : cycleStep (perceptionRefreshE s)
        = applyActionKind .fight (perceptionRefreshE s))
    (hfl : (applyActionKind .fight (perceptionRefreshE s)).level = s.level) :
    (cycleStepE s).gearGap = s.gearGap := by
  rw [cycleStepE_some s hk, hcp]
  rw [rearmE_eq_mint_of_no_levelup (by
    rw [gearProgress_level, fightLoss_level, partialClear_level,
      pressureDeltaD_level, hfl, perceptionRefreshE_level])]
  have hinner : (fightLoss k (perceptionRefreshE s)
      (partialClear k (pressureDeltaD k (perceptionRefreshE s)
        (applyActionKind .fight (perceptionRefreshE s))))).objectiveStepIsFight
      = (perceptionRefreshE s).objectiveStepIsFight := by
    rw [fightLoss_isFight, partialClear_isFight, pressureDeltaD_isFight,
      apply_fight_isFight]
  rw [rearmOnMint_gearGap, gearProgress_gearGap_of_notGear _ (by
      rcases hkne with h | h
      · exact Or.inl h
      · exact Or.inr (by rw [hinner]; exact h)), fightLoss_gearGap,
    partialClear_gearGap, pressureDeltaD_gearGap, apply_fight_gearGap,
    refreshE_gearGap]

/-- Composite adequacy preservation for a NON-rollover fight cycle. -/
private theorem cycleStepE_adequate_fight (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefreshE s) = some k)
    (hkne : k ≠ .objectiveStep
        ∨ (perceptionRefreshE s).objectiveStepIsFight = true)
    (hcp : cycleStep (perceptionRefreshE s)
        = applyActionKind .fight (perceptionRefreshE s))
    (hfl : (applyActionKind .fight (perceptionRefreshE s)).level = s.level) :
    (cycleStepE s).loadoutAdequate = s.loadoutAdequate := by
  rw [cycleStepE_some s hk, hcp]
  rw [rearmE_eq_mint_of_no_levelup (by
    rw [gearProgress_level, fightLoss_level, partialClear_level,
      pressureDeltaD_level, hfl, perceptionRefreshE_level])]
  have hinner : (fightLoss k (perceptionRefreshE s)
      (partialClear k (pressureDeltaD k (perceptionRefreshE s)
        (applyActionKind .fight (perceptionRefreshE s))))).objectiveStepIsFight
      = (perceptionRefreshE s).objectiveStepIsFight := by
    rw [fightLoss_isFight, partialClear_isFight, pressureDeltaD_isFight,
      apply_fight_isFight]
  rw [rearmOnMint_adequate, gearProgress_adequate_of_notGear _ (by
      rcases hkne with h | h
      · exact Or.inl h
      · exact Or.inr (by rw [hinner]; exact h)), fightLoss_adequate,
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


/-- `geCancel` (→ `.geCancelOrder`) strictly descends at `geCancelFlag` (the
    fire-and-lose GE_CANCEL guard, above `objectiveStepFlag`). -/
theorem descendsE_geCancel (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .geCancel) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, geCancelFires, refreshE_geCancel] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .geCancelOrder (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply eLt_of_geCancel_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, hfire,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate, refreshE_geCancel, refreshE_supplyDemand,
      perceptionRefreshE_level, perceptionRefreshE_xp]


private theorem refreshE_bankItemsCount (s : State) :
    (perceptionRefreshE s).bankItemsCount = s.bankItemsCount := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

private theorem refreshE_bankCapacity (s : State) :
    (perceptionRefreshE s).bankCapacity = s.bankCapacity := by
  unfold perceptionRefreshE
  split
  · split <;> rfl
  · rfl

set_option maxRecDepth 8000 in
/-- `bankExpand` (→ `.buyBankExpansion`) strictly descends at `bankExpandSlot`
    (2026-09-13). Directly below `currencyTurnInFlag` and above the two
    perception-raised slots. -/
theorem descendsE_bankExpand (s : State)
    (hk : productionLadder (perceptionRefreshE s) = some .bankExpand) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, bankExpandFires, Bool.and_eq_true, decide_eq_true_eq] at hfire
  rw [cycleStepE_some s hk]
  have hcs : cycleStep (perceptionRefreshE s) =
      applyActionKind .buyBankExpansion (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  have hfill : 100 * s.bankItemsCount ≥ 75 * s.bankCapacity := by
    have hd := hfire.1.1.2
    simpa [ProductionLadder.BANK_EXPAND_FILL_DEN,
           ProductionLadder.BANK_EXPAND_FILL_NUM,
           refreshE_bankItemsCount, refreshE_bankCapacity] using hd
  apply eLt_of_bankExpand_dec <;>
    simp [eMeasure, rearmE, rearmOnMint, dispatchesFight, gearProgress, fightLoss, partialClear, pressureDeltaD,
      applyActionKind, bankExpansionSlots,
      ProductionLadder.BANK_EXPAND_FILL_DEN, ProductionLadder.BANK_EXPAND_FILL_NUM,
      refreshE_phase, refreshE_progress, refreshE_total, refreshE_overstock,
      refreshE_selectBankDeposits, refreshE_sellable, refreshE_recyclable,
      refreshE_craftRelief, refreshE_craftPotions, refreshE_pending,
      refreshE_inventoryUsed, refreshE_inventoryMax, refreshE_hp, refreshE_maxHp,
      refreshE_overstockDebt, refreshE_depositDebt, refreshE_sellDebt,
      refreshE_gearGap, refreshE_adequate, refreshE_geCancel, refreshE_supplyDemand,
      refreshE_currencyTurnIn,
      refreshE_bankItemsCount, refreshE_bankCapacity,
      perceptionRefreshE_level, perceptionRefreshE_xp] <;>
    omega

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


/-! ## The fight row. -/


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
  -- WAVE 4: the excluded rung is the GEAR objective step. Every member of the
  -- fight family is either not the objective step at all, or is one whose
  -- `objectiveStepIsFight` is true — which is exactly `gearProgress`'s guard.
  have hk : ∃ k, (k ≠ MeansKind.objectiveStep
        ∨ (perceptionRefreshE s).objectiveStepIsFight = true)
      ∧ productionLadder (perceptionRefreshE s) = some k := by
    rcases hfire with h | h | ⟨h, hf⟩
    · exact ⟨.bankUnlock, Or.inl (by decide), h⟩
    · exact ⟨.reachUnlockLevel, Or.inl (by decide), h⟩
    · exact ⟨.objectiveStep, Or.inr hf, h⟩
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
   .geCancel,
   .discardCritical, .craftRelief, .recycleRelief, .sellRelief, .depositFull,
   .discardHigh, .craftPotions, .sellPressured, .claimPending, .bankExpand]

private theorem blockerPrefix_split :
    Formal.Liveness.UnconditionalDescent.blockerPrefix
      = gearScanPrefix ++ [.objectiveStep] := rfl

/-! ## The refresh-shaped row: placeholder. (The `pursueTask` row retired with
    the PURSUE_TASK rung, Phase 5-2c-iii-c-2 #4.) -/

/-- The task-work branch of the non-combat objective step (Phase 5-2c-iii-c-2
    #4, replacing the retired `pursueTask` row). The refreshed Bool is unarmed,
    so the refresh was the identity (both arming branches set it) — below 50
    that forces the defer gate, which certifies an active phase with work
    remaining. The step fired on the held task and dispatches `.taskTrade`.
    The gear layer may additionally close a gap (slot 2) or restore adequacy
    (slot 3); otherwise `taskCycles` (slot 7) strictly descends. -/
theorem descendsE_taskWork (s : State) (hArms : AdequateArmsFightAt s)
    (hlvl : s.level < 50)
    (hk : productionLadder (perceptionRefreshE s) = some .objectiveStep)
    (hisF : (perceptionRefreshE s).objectiveStepIsFight = false)
    (hofR : (perceptionRefreshE s).objectiveStepFires = false) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  have hcond : (decide (s.level < 50) && !(deferGate s)) = false := by
    by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
    · exfalso
      by_cases hadq : s.loadoutAdequate = true
      · have hgd : deferGate s = false := by
          by_contra hne
          rw [Bool.not_eq_false] at hne
          simp [hne] at hc
        have : (perceptionRefreshE s).objectiveStepFires = true := by
          unfold perceptionRefreshE
          rw [if_pos hc, if_pos hadq]
          exact (hArms hlvl hgd hadq).1
        rw [this] at hofR; cases hofR
      · have : (perceptionRefreshE s).objectiveStepFires = true := by
          unfold perceptionRefreshE
          rw [if_pos hc, if_neg hadq]
        rw [this] at hofR; cases hofR
    · rwa [Bool.not_eq_true] at hc
  have hgate : deferGate s = true := by
    rcases Bool.and_eq_false_iff.mp hcond with h | h
    · exact absurd (decide_eq_true_eq.mpr hlvl) (by rw [h]; exact Bool.false_ne_true)
    · simpa using h
  have heq : perceptionRefreshE s = s := by
    unfold perceptionRefreshE
    rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
  have hk0 : productionLadder s = some .objectiveStep := by rwa [heq] at hk
  have his0 : s.objectiveStepIsFight = false := by rwa [heq] at hisF
  have hof0 : s.objectiveStepFires = false := by rwa [heq] at hofR
  have hg := hgate
  simp only [deferGate, Bool.and_eq_true, decide_eq_true_eq] at hg
  obtain ⟨⟨_hdefer, hactive⟩, hprog⟩ := hg
  have hphase : s.taskLifecyclePhase ≠ .none := by
    simp only [Formal.Liveness.Plan.phaseActive, Bool.or_eq_true,
      decide_eq_true_eq] at hactive
    rcases hactive with h | h <;> (rw [h]; intro hc; cases hc)
  -- The gate's active phase is not `.complete`: no met-task turn-in here.
  have hnc : s.taskLifecyclePhase ≠ .complete := by
    simp only [Formal.Liveness.Plan.phaseActive, Bool.or_eq_true,
      decide_eq_true_eq] at hactive
    rcases hactive with h | h <;> (rw [h]; intro hc; cases hc)
  have htot : s.taskTotal ≠ 0 := by omega
  rw [cycleStepE_some s hk, heq]
  have hcs : cycleStep s = applyActionKind .taskTrade s := by
    unfold cycleStep; rw [hk0]; simp [planFor, his0, hof0, hnc, hphase]
  rw [hcs]
  have hpost : (applyActionKind .taskTrade s).taskLifecyclePhase ≠ .none := by
    simp only [applyActionKind]
    rw [if_neg htot]
    split <;> (intro hc; cases hc)
  have hchain : fightLoss .objectiveStep s (partialClear .objectiveStep
      (pressureDeltaD .objectiveStep s (applyActionKind .taskTrade s)))
      = applyActionKind .taskTrade s := by
    simp [fightLoss, partialClear, pressureDeltaD, dispatchesFight, his0]
  rw [hchain]
  have htIF : (applyActionKind .taskTrade s).objectiveStepIsFight = false := by
    simp [applyActionKind, his0]
  have htL : (applyActionKind .taskTrade s).level = s.level := by simp [applyActionKind]
  have htG : (applyActionKind .taskTrade s).gearGap = s.gearGap := by simp [applyActionKind]
  have htA : (applyActionKind .taskTrade s).loadoutAdequate = s.loadoutAdequate := by
    simp [applyActionKind]
  have hLV : (gearProgress .objectiveStep (applyActionKind .taskTrade s)).level = s.level := by
    rw [gearProgress_level, htL]
  rw [rearmE_eq_mint_of_no_levelup hLV]
  rcases gearProgress_objectiveStep_cases _ htIF with hid | hlt | ⟨heq2, hadq, hpre⟩
  · -- The gear layer moved nothing: the task trade descends `taskCycles`.
    rw [hid]
    have hmint : rearmOnMint .objectiveStep s (applyActionKind .taskTrade s)
        = applyActionKind .taskTrade s := by
      simp [rearmOnMint, dispatchesFight, his0,
        turnInRearm_of_not_turnIn (applyActionKind .taskTrade s) (Or.inr hnc)]
    rw [hmint]
    apply eLt_of_taskCycles_dec
    · simp [eMeasure, applyActionKind]
    · simp [eMeasure, applyActionKind]
    · simp [eMeasure, applyActionKind]
    · simp [eMeasure, applyActionKind]
    · simp [eMeasure, hpost, hphase]
    · simp only [eMeasure, applyActionKind]
      omega
  · -- A gap closed: slot 2.
    apply eLt_of_gearGap_dec
    · simp [eMeasure, rearmOnMint_level, hLV]
    · simp only [eMeasure, rearmOnMint_gearGap]
      rw [htG] at hlt; exact hlt
  · -- Gap was zero and adequacy is restored: slot 3, with slot 2 equal.
    apply eLt_of_inadequacy_dec
    · simp [eMeasure, rearmOnMint_level, hLV]
    · simp only [eMeasure, rearmOnMint_gearGap]; rw [heq2, htG]
    · simp only [eMeasure, rearmOnMint_adequate]
      rw [hadq, ← htA, hpre]
      simp [b2n]

/-- A non-combat objective step. TWO ways to reach it since wave 4, and they
    descend at different slots.

    Before wave 4 there was one: a STALE armed Bool surviving an identity
    refresh, because the inadequate branch armed the gear LATCH, which would
    outrank the objective. Increment 4.2b moved gear acquisition into the
    resolution graph, so `perceptionRefreshE`'s inadequate branch now arms THIS
    step (non-combat) instead — that is the gear chain, and it is the case the
    E measure's `gearGap` slot exists for.

      * inadequate refresh -> the GEAR step: `gearProgress` closes one gap
        (slot 2) or restores adequacy at zero (slot 3).
      * identity refresh   -> the stale arm: descends at `objectiveStepFlag`. -/
theorem descendsE_placeholder (s : State) (hArms : AdequateArmsFightAt s)
    (hGear : GearCycleMakesProgressAt s) (hlvl : s.level < 50)
    (hk : productionLadder (perceptionRefreshE s) = some .objectiveStep)
    (hisF : (perceptionRefreshE s).objectiveStepIsFight = false) :
    eMeasureLt (eMeasure (cycleStepE s)) (eMeasure s) := by
  by_cases hofR : (perceptionRefreshE s).objectiveStepFires = true
  swap
  · exact descendsE_taskWork s hArms hlvl hk hisF (Bool.eq_false_iff.mpr hofR)
  have hcs : cycleStep (perceptionRefreshE s)
      = applyActionKind .objectiveStep (perceptionRefreshE s) := by
    unfold cycleStep; rw [hk]; simp [planFor, hisF, hofR]
  -- The state `gearProgress` sees, and the two facts the split needs about it.
  have hIF : (fightLoss .objectiveStep (perceptionRefreshE s)
      (partialClear .objectiveStep
        (pressureDeltaD .objectiveStep (perceptionRefreshE s)
          (applyActionKind .objectiveStep (perceptionRefreshE s))))).objectiveStepIsFight
      = false := by
    rw [fightLoss_isFight, partialClear_isFight, pressureDeltaD_isFight]
    exact hisF
  have hGG : (fightLoss .objectiveStep (perceptionRefreshE s)
      (partialClear .objectiveStep
        (pressureDeltaD .objectiveStep (perceptionRefreshE s)
          (applyActionKind .objectiveStep (perceptionRefreshE s))))).gearGap
      = s.gearGap := by
    rw [fightLoss_gearGap, partialClear_gearGap, pressureDeltaD_gearGap,
      apply_objectiveStep_gearGap, refreshE_gearGap]
  have hAD : (fightLoss .objectiveStep (perceptionRefreshE s)
      (partialClear .objectiveStep
        (pressureDeltaD .objectiveStep (perceptionRefreshE s)
          (applyActionKind .objectiveStep (perceptionRefreshE s))))).loadoutAdequate
      = s.loadoutAdequate := by
    rw [fightLoss_adequate, partialClear_adequate, pressureDeltaD_adequate,
      apply_objectiveStep_adequate, refreshE_adequate]
  have hLV : (gearProgress .objectiveStep
      (fightLoss .objectiveStep (perceptionRefreshE s)
        (partialClear .objectiveStep
          (pressureDeltaD .objectiveStep (perceptionRefreshE s)
            (applyActionKind .objectiveStep (perceptionRefreshE s)))))).level
      = (perceptionRefreshE s).level := by
    rw [gearProgress_level, fightLoss_level, partialClear_level,
      pressureDeltaD_level, apply_objectiveStep_level]
  rcases gearProgress_objectiveStep_cases _ hIF with hid | hlt | ⟨heq, hadq, hpre⟩
  · -- The gear layer moved nothing. That is only possible on an IDENTITY
    -- refresh, and proving so is where `GearCycleMakesProgressAt` earns its
    -- place: an ARMED refresh means `loadoutAdequate = false`, and a productive
    -- cycle with an open gap or a restorable adequacy always moves something.
    -- An armed-but-unproductive cycle is precisely the livelock that hypothesis
    -- rules out — so this branch is the stale arm, and the pre-wave-4 proof
    -- applies verbatim.
    have hprod : (fightLoss .objectiveStep (perceptionRefreshE s)
        (partialClear .objectiveStep
          (pressureDeltaD .objectiveStep (perceptionRefreshE s)
            (applyActionKind .objectiveStep
              (perceptionRefreshE s))))).gearCycleProductive
        = s.gearCycleProductive := by
      rw [fightLoss_productive, partialClear_productive, pressureDeltaD_productive,
        apply_objectiveStep_productive, refreshE_productive]
    have heq : perceptionRefreshE s = s := by
      by_cases hc : (decide (s.level < 50) && !(deferGate s)) = true
      · by_cases hadq : s.loadoutAdequate = true
        · unfold perceptionRefreshE; rw [if_pos hc, if_pos hadq]
        · exfalso
          have hgd : deferGate s = false := by
            by_contra hne
            rw [Bool.not_eq_false] at hne
            simp [hne] at hc
          have hlt : s.level < 50 := by
            by_contra hne
            simp [hne] at hc
          have hp : s.gearCycleProductive = true :=
            hGear hlt hgd (by simpa using hadq)
          -- Unproductive is refuted; so the identity must have come from the
          -- gap-zero-already-adequate arm, which contradicts `hadq`.
          have hAdIn : (fightLoss .objectiveStep (perceptionRefreshE s)
              (partialClear .objectiveStep
                (pressureDeltaD .objectiveStep (perceptionRefreshE s)
                  (applyActionKind .objectiveStep
                    (perceptionRefreshE s))))).loadoutAdequate = false := by
            rw [hAD]; simpa using hadq
          rw [hp] at hprod
          unfold gearProgress at hid
          rw [if_neg (by rw [hIF]; exact Bool.false_ne_true),
            if_neg (by simp [hprod])] at hid
          by_cases hz : (fightLoss .objectiveStep (perceptionRefreshE s)
              (partialClear .objectiveStep
                (pressureDeltaD .objectiveStep (perceptionRefreshE s)
                  (applyActionKind .objectiveStep
                    (perceptionRefreshE s))))).gearGap = 0
          · rw [if_pos hz] at hid
            have := congrArg State.loadoutAdequate hid
            simp at this
            rw [this] at hAdIn; cases hAdIn
          · rw [if_neg hz] at hid
            have := congrArg State.gearGap hid
            simp at this
            omega
      · unfold perceptionRefreshE
        rw [if_neg hc]
    have hk0 : productionLadder s = some .objectiveStep := by rwa [heq] at hk
    have his0 : s.objectiveStepIsFight = false := by rwa [heq] at hisF
    have hfire : s.objectiveStepFires = true := by rwa [heq] at hofR
    rw [heq] at hid
    rw [cycleStepE_some s hk, heq]
    have hcs0 : cycleStep s = applyActionKind .objectiveStep s := by
      unfold cycleStep; rw [hk0]; simp [planFor, his0, hfire]
    rw [hcs0, hid]
    apply eLt_of_objectiveStepFlag_dec <;>
      simp [eMeasure, rearmE, rearmOnMint, choreRearm, dispatchesFight,
        fightLoss, partialClear, pressureDeltaD,
        applyActionKind, his0, hfire, refreshE_geCancel,
        turnInRearm_of_not_turnIn _ (Or.inl hfire)]
  · -- A gap closed: slot 2.
    rw [cycleStepE_some s hk, hcs, rearmE_eq_mint_of_no_levelup hLV]
    apply eLt_of_gearGap_dec
    · simp [eMeasure, rearmOnMint_level, hLV, perceptionRefreshE_level]
    · simp only [eMeasure, rearmOnMint_gearGap]
      rw [hGG] at hlt; exact hlt
  · -- Gap was zero and adequacy is restored: slot 3, with slot 2 equal.
    rw [cycleStepE_some s hk, hcs, rearmE_eq_mint_of_no_levelup hLV]
    apply eLt_of_inadequacy_dec
    · simp [eMeasure, rearmOnMint_level, hLV, perceptionRefreshE_level]
    · simp only [eMeasure, rearmOnMint_gearGap]; rw [heq, hGG]
    · simp only [eMeasure, rearmOnMint_adequate]
      rw [hadq, ← hAD, hpre]
      simp [b2n]

end Formal.Liveness.BlockerDescentE
