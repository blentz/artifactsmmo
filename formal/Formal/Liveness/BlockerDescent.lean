import Formal.Liveness.FMeasure
import Formal.Liveness.CycleStepCharacterization

/-! # BlockerDescent — every below-50-selectable means strictly descends FMeasure

Brick 3 of `docs/PLAN_l50_unconditional_descent.md`: one descent lemma per means
the production ladder can select below level 50 (the 17 `objectiveStepBlockers`
rows ahead of `.objectiveStep` in `allInLadderOrder`, plus the armed
`.objectiveStep` fight itself). Brick 4 (`UnconditionalDescent.lean`) closes the
case analysis into `cycleStepF_descends_below_fifty` and the hypothesis-free
capstone.

Proof shape, uniform across the chore rows:
1. the selected means FIRES on the refreshed state (`fires_of_ladder`);
2. `cycleStepF s = pressureDelta k (applyActionKind a (perceptionRefresh s))`
   where `planFor k = [a]`;
3. `perceptionRefresh` is `fMeasure`-invariant (it touches only the two
   objective Bools, which are deliberately not in the tuple), so the goal
   reduces to a descent against `fMeasure (perceptionRefresh s)`;
4. the apply CLEARS the quantity the firing required (flag latch / lifecycle
   phase / hp deficit), giving the strict slot, and `{s with …}` preservation
   plus `pressureDelta`'s inventory-only footprint give the higher-slot
   equalities.

Fight rows (`bankUnlock` / `reachUnlockLevel` / armed `objectiveStep`) re-prove
the `LevelingDescent.cycleStepF_fight_descends` rollover/accumulate split
against slots 1/2 of the richer tuple.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}.
Liveness namespace — Mathlib allowed. -/

set_option linter.dupNamespace false

namespace Formal.Liveness.BlockerDescent

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.CycleStepF
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CumulativeProgress (b2n)
open Formal.Liveness.FMeasure

/-- A selected means fires (extracted from the `findSome?` characterisation of
    `productionLadder`). Local copy of the `private` helper in CycleStep /
    CumulativeProgress / BlockerQuieting. -/
private theorem fires_of_ladder {s : State} {k : MeansKind}
    (h : productionLadder s = some k) : fires k s = true := by
  unfold productionLadder at h
  rw [List.findSome?_eq_some_iff] at h
  obtain ⟨_pre, x, _suf, _hl, hbody, _hpre_none⟩ := h
  by_cases hfire : fires x s = true
  · simp [hfire] at hbody
    rw [← hbody]; exact hfire
  · simp [hfire] at hbody

/-- `perceptionRefresh` is `fMeasure`-invariant: it mutates only
    `objectiveStepFires`/`objectiveStepIsFight`, neither of which is a tuple
    slot (the deliberate design choice of `FMeasure`). -/
theorem fMeasure_perceptionRefresh (s : State) :
    fMeasure (perceptionRefresh s) = fMeasure s := by
  unfold perceptionRefresh
  split <;> rfl

/-- The faithful cycle at a selected means, unfolded:
    refresh-select-apply then the means' pressure adjustment. -/
private theorem cycleStepF_some (s : State) {k : MeansKind}
    (hk : productionLadder (perceptionRefresh s) = some k) :
    cycleStepF s = pressureDelta k (cycleStep (perceptionRefresh s)) := by
  unfold cycleStepF
  rw [hk]
  rfl

/-! ## Rest rows — slot 13 (`hpDeficit`), strict because the fires require
`hp < maxHp` and the apply sets `hp := maxHp`. -/

/-- `hpCritical` (→ `.rest`) strictly descends `FMeasure` at `hpDeficit`. -/
theorem descends_hpCritical (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .hpCritical) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, hpCriticalFires, Bool.and_eq_true, decide_eq_true_eq] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .rest (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_hpDeficit_dec <;>
    simp only [fMeasure, pressureDelta, applyActionKind] <;>
    first
      | rfl
      | (obtain ⟨hpos, hlt⟩ := hfire
         simp only [CRITICAL_HP_NUM, CRITICAL_HP_DEN] at hlt
         omega)

/-- `restForCombat` (→ `.rest`) strictly descends `FMeasure` at `hpDeficit`. -/
theorem descends_restForCombat (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .restForCombat) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, restForCombatFires, Bool.and_eq_true, decide_eq_true_eq] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .rest (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_hpDeficit_dec <;>
    simp only [fMeasure, pressureDelta, applyActionKind] <;>
    first
      | rfl
      | (obtain ⟨_, hlt⟩ := hfire; omega)

/-! ## Flag-latch chore rows — strict at the row's own flag slot (fires require
the flag `true`; the apply clears it), all higher slots preserved by the
`{s with …}` update + `pressureDelta`'s inventory-only footprint. -/

/-- `discardCritical` (→ `.deleteItem`) strictly descends at `overstockFlag`. -/
theorem descends_discardCritical (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .discardCritical) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, discardCriticalFires, Bool.and_eq_true] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .deleteItem (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_overstock_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire.1.1]

/-- `discardHigh` (→ `.deleteItem`) strictly descends at `overstockFlag`. -/
theorem descends_discardHigh (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .discardHigh) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, discardHighFires, Bool.and_eq_true] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .deleteItem (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_overstock_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire.1.1]

/-- `depositFull` (→ `.depositAll`) strictly descends at
    `selectBankDepositsFlag`. -/
theorem descends_depositFull (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .depositFull) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, depositFullFires, Bool.and_eq_true] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .depositAll (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_selectBankDeposits_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire.2]

/-- `sellPressured` (→ `.npcSell`) strictly descends at `sellableFlag`. -/
theorem descends_sellPressured (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .sellPressured) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, sellPressuredFires, Bool.and_eq_true] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .npcSell (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_sellable_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire.2]

/-- `sellRelief` (→ `.npcSell`) strictly descends at `sellableFlag`. -/
theorem descends_sellRelief (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .sellRelief) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, sellReliefFires, Bool.and_eq_true] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .npcSell (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_sellable_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire.2]

/-- `recycleRelief` (→ `.recycle`) strictly descends at `recyclableFlag`. -/
theorem descends_recycleRelief (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .recycleRelief) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, recycleReliefFires, Bool.and_eq_true] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .recycle (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_recyclable_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire.2]

/-- `geCancel` (→ `.geCancelOrder`) strictly descends at `geCancelFlag`. The
    fire-and-lose GE_CANCEL guard: `.geCancelOrder` clears only
    `geCancelTargetsNonempty`, so every higher slot is unchanged and the bottom
    slot strictly drops. -/
theorem descends_geCancel (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .geCancel) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, geCancelFires] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .geCancelOrder (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_geCancel_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire]

set_option maxRecDepth 8000 in
/-- `bankExpand` (→ `.buyBankExpansion`) strictly descends at `bankExpandSlot`
    (2026-09-13). Bottom of the cascade, like `geCancel`:
    `.buyBankExpansion` changes only `gold` (down) and `bankCapacity` (up), and
    neither appears in the FMeasure tuple above this slot.

    The strictness is arithmetic rather than a flag flip. Firing gives
    `FILL_DEN * items ≥ FILL_NUM * capacity`, so the slot
    `(FILL_DEN * items + 1) - FILL_NUM * capacity` is at least 1; the buy leaves
    `items` alone and adds `bankExpansionSlots` to `capacity`, so the subtrahend
    grows by `bankExpansionSlots * FILL_NUM` and the saturating difference
    strictly drops. This holds for ANY trigger ratio, which is the point — at
    the 75% trigger a single buy no longer always clears the threshold, so the
    fire-and-lose flag shape the other bottom slots use would not have worked
    here. -/
theorem descends_bankExpand (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .bankExpand) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, bankExpandFires, Bool.and_eq_true, decide_eq_true_eq] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .buyBankExpansion (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  -- The fill conjunct is what makes the slot non-zero before the buy, and omega
  -- needs it as a literal inequality in context.
  have hfill : 100 * (perceptionRefresh s).bankItemsCount
      ≥ 75 * (perceptionRefresh s).bankCapacity := by
    have hd := hfire.1.1.2
    simpa [ProductionLadder.BANK_EXPAND_FILL_DEN,
           ProductionLadder.BANK_EXPAND_FILL_NUM] using hd
  apply fLt_of_bankExpand_dec <;>
    simp only [fMeasure, pressureDelta, applyActionKind, bankExpansionSlots,
               ProductionLadder.BANK_EXPAND_FILL_DEN,
               ProductionLadder.BANK_EXPAND_FILL_NUM] <;>
    first
      | rfl
      | omega

/-- `craftRelief` (→ `.craft`) strictly descends at `craftReliefFlag`. -/
theorem descends_craftRelief (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .craftRelief) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.craftReliefFires] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .craft (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_craftRelief_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire]

/-- `craftPotions` (→ `.craft`, which clears BOTH craft flags) strictly
    descends: at `craftReliefFlag` when that latch was also armed, else at
    `craftPotionsFlag` with `craftReliefFlag` unchanged (`false → false`). -/
theorem descends_craftPotions (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .craftPotions) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.craftPotionsFires] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .craft (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hrelief : (perceptionRefresh s).craftReliefFires = true
  · apply fLt_of_craftRelief_dec <;>
      simp [fMeasure, pressureDelta, applyActionKind, hrelief]
  · rw [Bool.not_eq_true] at hrelief
    apply fLt_of_craftPotions_dec <;>
      simp [fMeasure, pressureDelta, applyActionKind, hrelief, hfire]


/-- `claimPending` (→ `.claimPendingItem`) strictly descends at `pendingFlag` —
    the claim's `+1` inventory mint lands at `bankPressure` (slot 12), lex-BELOW
    the pending latch, exactly the ordering the tuple was built for. -/
theorem descends_claimPending (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .claimPending) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, claimPendingFires] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .claimPendingItem (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_pending_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire]

/-! ## Fight rows — slots 1/2, the `LevelingDescent.cycleStepF_fight_descends`
rollover/accumulate split re-proved against the richer tuple. -/

/-- A faithful FIGHT cycle strictly descends `FMeasure` at `levelDeficit`
    (rollover) or `xpDeficit` (accumulate) — the loot fill (`bankPressure`) and
    every flag change sit lex-below and are dominated. Mirror of
    `LevelingDescent.cycleStepF_fight_descends`. -/
theorem descends_fight (s : State) (hlvl : s.level < 50)
    (hfire : productionLadder (perceptionRefresh s) = some .bankUnlock
        ∨ productionLadder (perceptionRefresh s) = some .reachUnlockLevel
        ∨ (productionLadder (perceptionRefresh s) = some .objectiveStep
            ∧ (perceptionRefresh s).objectiveStepIsFight = true)) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hcp : cycleStepP s = applyActionKind .fight (perceptionRefresh s) := by
    show cycleStep (perceptionRefresh s) = applyActionKind .fight (perceptionRefresh s)
    exact cycleStep_eq_fight_when_fightCycleFires (perceptionRefresh s) hfire
  have hFl : (cycleStepF s).level = (applyActionKind .fight (perceptionRefresh s)).level := by
    rw [cycleStepF_level, hcp]
  have hFx : (cycleStepF s).xp = (applyActionKind .fight (perceptionRefresh s)).xp := by
    rw [cycleStepF_xp, hcp]
  have hrl : (perceptionRefresh s).level = s.level := perceptionRefresh_level s
  have hrx : (perceptionRefresh s).xp = s.xp := perceptionRefresh_xp s
  by_cases hwill : s.xp + 10 ≥ xpToNextLevel s.level
  · -- Rollover: slot 1 strict.
    have hcond : (decide ((perceptionRefresh s).xp + 10 ≥ xpToNextLevel (perceptionRefresh s).level)
                  && decide ((perceptionRefresh s).level < 50)) = true := by
      rw [hrl, hrx, decide_eq_true_eq.mpr hwill, decide_eq_true_eq.mpr hlvl]; rfl
    have hfl : (applyActionKind .fight (perceptionRefresh s)).level = s.level + 1 := by
      simp only [applyActionKind]; rw [if_pos hcond, hrl]
    apply fLt_of_levelDeficit_dec
    simp only [fMeasure, hFl, hfl]
    omega
  · -- Accumulate: slot 1 equal, slot 2 strict.
    have hcond : (decide ((perceptionRefresh s).xp + 10 ≥ xpToNextLevel (perceptionRefresh s).level)
                  && decide ((perceptionRefresh s).level < 50)) = false := by
      rw [hrl, hrx]
      simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
      exact Or.inl hwill
    have hfl : (applyActionKind .fight (perceptionRefresh s)).level = s.level := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrl]
    have hfx : (applyActionKind .fight (perceptionRefresh s)).xp = s.xp + 10 := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrx]
    apply fLt_of_xpDeficit_dec
    · simp only [fMeasure, hFl, hfl]
    · simp only [fMeasure, hFl, hfl, hFx, hfx]
      omega

end Formal.Liveness.BlockerDescent
