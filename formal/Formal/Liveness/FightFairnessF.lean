import Formal.Liveness.LevelFiftyReachableF
import Formal.Liveness.PressureBurst

/-! # FightFairnessF — Workstream A Phase-1 Brick 3d-c (reduction): `hfightFiresF`
from the REDUCED residual.

`LevelFiftyReachableF.ai_reaches_level_fiftyF` reaches level 50 for the faithful
cycle MODULO `hfightFiresF` (the fight fires infinitely often on the refreshed
selection states). This module discharges `hfightFiresF` down to the **reduced
residual** `ReducedResidualF`, via the fight-side local dichotomy
(`PressureBurst.productionLadder_eq_objectiveStep_of_low_pressure`).

## The shrink this brick mechanizes

`FightFairnessP.BlockersQuietBelowCapInfinitelyOftenP` (the `cycleStepP` residual)
required all FOURTEEN `objectiveStepBlockers` quiet i.o. — an UNFAITHFUL assumption,
because along `cycleStepP` the four pressure-gated chores were silently frozen
(inventory never filled). `cycleStepF` MODELS the filling, so its residual replaces
the four pressure-gated chores with a concrete, checkable pressure condition:

  `ReducedResidualF` = i.o. (below cap ∧ inventory pressure LOW ∧ the TEN
  `nonPressureBlockers` quiet).

`hfightFiresF_of_reduced` proves this residual discharges `hfightFiresF`: at a
reduced-residual position, low pressure silences the four pressure-gated chores
(Brick 1), so with the ten non-pressure blockers quiet the fight-side dichotomy
selects the combat objective, and `perceptionRefresh` arms `objectiveStepIsFight`
below the cap.

## The residual is HONEST, not yet fully discharged

`ReducedResidualF` STILL CARRIES a low-pressure conjunct — this brick does NOT yet
prove pressure dips low infinitely often. That bounded-burst transience (each drain
resets pressure to 0, each fill is ≤ `DROP_BOUND`, claim fuel is finite) is the
REMAINING sub-piece, to be discharged from `Drainability.RuntimeInvariant` + the
ten-blocker quiet. This brick's job is the precise REDUCTION: it pins the residual
to exactly "low pressure ∧ ten quiet i.o.", the smallest honest gap.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed. -/

namespace Formal.Liveness.FightFairnessF

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFLeveling
open Formal.Liveness.LevelFiftyReachableF
open Formal.Liveness.PressureBurst

/-- **The reduced fight-firing residual for the faithful cycle.** Infinitely often
    the trajectory is below the cap, the refreshed selection state has LOW inventory
    pressure (below the binding 85% threshold), and the TEN `nonPressureBlockers`
    are quiet on it. The four pressure-gated chores are NOT in the obligation — low
    pressure silences them (Brick 1). This is the honest faithful residual that
    replaces the `cycleStepP` capstone's unfaithful 14-blocker assumption. The
    low-pressure conjunct is itself discharged (from `RuntimeInvariant` + the
    bounded-burst dynamics) in the remaining sub-piece. -/
def ReducedResidualF (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
    (cycleStepFN k s).level < 50
    ∧ 100 * (perceptionRefresh (cycleStepFN k s)).inventoryUsed
        < 85 * (perceptionRefresh (cycleStepFN k s)).inventoryMax
    ∧ (∀ b ∈ nonPressureBlockers, fires b (perceptionRefresh (cycleStepFN k s)) = false)

/-- **The reduction.** `ReducedResidualF` discharges `hfightFiresF`. At each reduced
    -residual position, the fight-side dichotomy selects the combat objective (low
    pressure quiets the four pressure-gated chores, the ten non-pressure blockers are
    quiet by hypothesis, and `perceptionRefresh` arms the objective below the cap),
    and the committed objective is combat-typed (`perceptionRefresh` arms
    `objectiveStepIsFight`). -/
theorem hfightFiresF_of_reduced (s : State) (h : ReducedResidualF s) :
    hfightFiresF s := by
  intro N
  obtain ⟨k, hkN, hlt, hlow, hquiet⟩ := h N
  refine ⟨k, hkN, Or.inr (Or.inr ⟨?_, ?_⟩)⟩
  · -- The objective is armed below the cap, on the refreshed selection state.
    have hobj : fires .objectiveStep (perceptionRefresh (cycleStepFN k s)) = true := by
      simp only [fires, ProductionLadder.objectiveStepFires]
      exact perceptionRefresh_objectiveStepFires (cycleStepFN k s) hlt
    -- Low pressure + ten non-pressure quiet + objective armed ⇒ ladder fights.
    exact productionLadder_eq_objectiveStep_of_low_pressure
      (perceptionRefresh (cycleStepFN k s)) hlow hobj hquiet
  · -- The committed objective is combat-typed (perceptionRefresh arms it).
    exact perceptionRefresh_objectiveStepIsFight (cycleStepFN k s) hlt

/-! ## The faithful capstone, fed by the reduced residual -/

/-- **Faithful level-50 reachability from the reduced residual.** Bundles the
    `hfightFiresF` discharge: given the three non-degeneracy invariants and the
    reduced residual `ReducedResidualF` (the ten non-pressure blockers quiet AND
    pressure low, below cap, i.o.), the faithful cycle reaches level 50. This is the
    cleanest honest statement of the residual set the faithful capstone rests on —
    NO unfaithful 14-blocker assumption, NO measure, modulo LIV-001 and the
    low-pressure-transience sub-piece carried inside `ReducedResidualF`. -/
theorem ai_reaches_level_fiftyF_of_reduced (s : State)
    (hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) ≠ some .wait)
    (hex : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .taskExchange →
                (perceptionRefresh (cycleStepFN k s)).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankExpand →
                (perceptionRefresh (cycleStepFN k s)).nextExpansionCost > 0)
    (hr : ReducedResidualF s) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  ai_reaches_level_fiftyF s ⟨hnowait, hex, hbe, hfightFiresF_of_reduced s hr⟩

end Formal.Liveness.FightFairnessF
