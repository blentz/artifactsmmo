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

/-- `gearReview` (→ `.optimizeLoadout`) strictly descends at `gearReviewFlag`. -/
theorem descends_gearReview (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .gearReview) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, ProductionLadder.gearReviewFires] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .optimizeLoadout (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_gearReview_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hfire]

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

/-! ## Task-lifecycle rows — slot 3 (`phasePresent`): the fires require a
non-`.none` phase, the applies all reset it to `.none`. `completeTask` grants
NO xp (`taskCompleteXpEstimate = 0`, server-verified — `Measure.lean:440`), so
its rollover branch fires only from an already-over-threshold xp state; both
branches are handled. -/

/-- `completeTask` (→ `.completeTask`) strictly descends: at `levelDeficit` in
    the (degenerate, `xp` already ≥ threshold) rollover branch, else at
    `phasePresent` (`.complete → .none`, level/xp unchanged since the xp grant
    is zero). -/
theorem descends_completeTask (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .completeTask) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, completeTaskFires, decide_eq_true_eq] at hfire
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .completeTask (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  by_cases hwill : (decide ((perceptionRefresh s).xp + taskCompleteXpEstimate ≥
      xpToNextLevel (perceptionRefresh s).level)
      && decide ((perceptionRefresh s).level < 50)) = true
  · -- Rollover: level + 1 with level < 50 — slot 1 strict.
    have hlvl : (perceptionRefresh s).level < 50 := by
      have := hwill
      simp only [Bool.and_eq_true, decide_eq_true_eq] at this
      exact this.2
    have hfl : (applyActionKind .completeTask (perceptionRefresh s)).level
        = (perceptionRefresh s).level + 1 := by
      simp only [applyActionKind]; rw [if_pos hwill]
    apply fLt_of_levelDeficit_dec
    simp only [fMeasure, pressureDelta, hfl]
    omega
  · -- No rollover: level/xp unchanged (xp grant is 0) — slot 3 strict.
    have hphase : (perceptionRefresh s).taskLifecyclePhase ≠ .none := by
      rw [hfire]; intro h; cases h
    have hfl : (applyActionKind .completeTask (perceptionRefresh s)).level
        = (perceptionRefresh s).level := by
      simp only [applyActionKind]; rw [if_neg hwill]
    have hfx : (applyActionKind .completeTask (perceptionRefresh s)).xp
        = (perceptionRefresh s).xp := by
      simp only [applyActionKind]; rw [if_neg hwill]
      simp [taskCompleteXpEstimate]
    have hph : (applyActionKind .completeTask (perceptionRefresh s)).taskLifecyclePhase
        = .none := by
      simp only [applyActionKind]
    apply fLt_of_phasePresent_dec
    · simp only [fMeasure, pressureDelta, hfl]
    · simp only [fMeasure, pressureDelta, hfl, hfx]
    · simp [fMeasure, pressureDelta, hph, hphase]

/-- `taskCancel` (→ `.taskCancel`) strictly descends at `phasePresent`. -/
theorem descends_taskCancel (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .taskCancel) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, taskCancelFires, Bool.and_eq_true, Bool.or_eq_true,
    decide_eq_true_eq] at hfire
  have hphase : (perceptionRefresh s).taskLifecyclePhase ≠ .none := by
    rcases hfire.1 with h | h <;> (rw [h]; intro hc; cases hc)
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .taskCancel (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_phasePresent_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hphase]

/-- `lowYieldCancel` (→ `.taskCancel`) strictly descends at `phasePresent`. -/
theorem descends_lowYieldCancel (s : State)
    (hk : productionLadder (perceptionRefresh s) = some .lowYieldCancel) :
    fMeasureLt (fMeasure (cycleStepF s)) (fMeasure s) := by
  have hfire := fires_of_ladder hk
  simp only [fires, lowYieldCancelFires, Bool.and_eq_true,
    decide_eq_true_eq] at hfire
  have hphase : (perceptionRefresh s).taskLifecyclePhase ≠ .none := by
    rw [hfire.1]; intro hc; cases hc
  rw [cycleStepF_some s hk, ← fMeasure_perceptionRefresh s]
  have hcs : cycleStep (perceptionRefresh s) =
      applyActionKind .taskCancel (perceptionRefresh s) := by
    unfold cycleStep; rw [hk]; rfl
  rw [hcs]
  apply fLt_of_phasePresent_dec <;>
    simp [fMeasure, pressureDelta, applyActionKind, hphase]

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
