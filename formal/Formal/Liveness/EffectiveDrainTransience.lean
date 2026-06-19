import Formal.Liveness.FightFairnessF
import Formal.Liveness.PressureTransience

/-! # EffectiveDrainTransience — Workstream A Phase-1 Brick 3d-c (HONEST fix): the
truthful transience, resting on `EffectiveDrainArmed` instead of the falsified
`→ 0`-drain model.

The differential investigation (`docs/REVIEW_pressuredelta_differential.md`)
FALSIFIED `InventoryDynamics.pressureDelta`'s `reducer → 0`: production's reducers
remove only a bounded subset (discard = excess above per-item caps; deposit = bank-
eligible minus a keep-set; sell = down to 5 free slots; craft = net units), so NONE
guarantees post-pressure < 85%, and the bot can livelock at ≥ 85%
(`[[project_inventory_profiles]]`). The `PressureTransience` counting that derived
"k+1 is low-pressure" from `inventoryUsed = 0` is therefore sound only for the
unfaithful `→ 0` model.

This module gives the HONEST replacement. It does NOT model the partial-drain
arithmetic (which needs per-item caps + game data); instead it lifts the
effective-drain to an EXPLICIT runtime residual `EffectiveDrainArmed` — "when
pressured (and the reducer is selectable: ten non-pressure blockers quiet, below
cap), the NEXT cycle lands strictly below 85%" — and re-derives `ReducedResidualF`
from it with ZERO dependence on `pressureDelta`, the `→ 0` value, or
`Drainability.RuntimeInvariant`.

`EffectiveDrainArmed` is the honest residual: it is precisely "the bot effectively
drains when pressured", the property the differential showed production does NOT
guarantee. Where it FAILS is exactly the full-of-useful-items livelock — the proof
now NAMES that failure precondition instead of hiding it behind `→ 0`. The coincidence
work is still real (the quiet-PAIR provides it); `EffectiveDrainArmed` alone does not
give `ReducedResidualF`.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed. -/

namespace Formal.Liveness.EffectiveDrainTransience

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepF
open Formal.Liveness.PressureBurst
open Formal.Liveness.FightFairnessF
open Formal.Liveness.PressureTransience

/-- **The honest effective-drain residual.** Whenever a refreshed selection state is
    pressured (≥ 85%), below the cap, and the ten `nonPressureBlockers` are quiet (so a
    reducer is actually selectable), the NEXT cycle's refreshed selection state lands
    strictly below 85%. This is the truthful abstraction of "an effective drain fires":
    it asserts the OUTCOME (pressure actually drops below the watermark) rather than
    assuming, as the `→ 0` model did, that every reducer empties the bag. Production
    does NOT guarantee this — discard removes only excess-above-caps, etc. — so
    `EffectiveDrainArmed` is exactly the runtime property whose FAILURE is the
    full-of-useful-items livelock. -/
def EffectiveDrainArmed (s : State) : Prop :=
  ∀ k,
    (85 * (perceptionRefresh (cycleStepFN k s)).inventoryMax
        ≤ 100 * (perceptionRefresh (cycleStepFN k s)).inventoryUsed
     ∧ (cycleStepFN k s).level < 50
     ∧ (∀ b ∈ nonPressureBlockers, fires b (perceptionRefresh (cycleStepFN k s)) = false))
    → 100 * (perceptionRefresh (cycleStepFN (k+1) s)).inventoryUsed
        < 85 * (perceptionRefresh (cycleStepFN (k+1) s)).inventoryMax

/-- **The honest counting.** From the quiet-pair scheduling residual and
    `EffectiveDrainArmed`, `ReducedResidualF` holds — WITHOUT the `→ 0` model,
    `pressureDelta`, or `RuntimeInvariant`. At a quiet pair `(k, k+1)`: low pressure at
    `k` ⇒ `k` witnesses; high pressure at `k` ⇒ (the pair gives ten-quiet, the residual
    gives the effective drain) `k+1` is low-pressure and ten-quiet, witnessing. The
    quiet PAIR still does the coincidence work; `EffectiveDrainArmed` supplies the
    honest drop that the falsified `→ 0` model used to fabricate. -/
theorem reducedResidual_of_effectiveDrain (s : State)
    (hed : EffectiveDrainArmed s)
    (htqp : TenQuietPairsBelowCapInfinitelyOften s) :
    ReducedResidualF s := by
  intro N
  obtain ⟨k, hkN, hlt_k, hq_k, hlt_k1, hq_k1⟩ := htqp N
  by_cases hlow : 100 * (perceptionRefresh (cycleStepFN k s)).inventoryUsed
                    < 85 * (perceptionRefresh (cycleStepFN k s)).inventoryMax
  · -- Low pressure at k: k witnesses directly.
    exact ⟨k, hkN, hlt_k, hlow, hq_k⟩
  · -- High pressure at k: the effective-drain residual lands k+1 low-pressure;
    -- the quiet PAIR supplies ten-quiet at k+1.
    push Not at hlow
    exact ⟨k+1, le_trans hkN (Nat.le_succ k), hlt_k1, hed k ⟨hlow, hlt_k, hq_k⟩, hq_k1⟩

/-- **The HONEST faithful capstone.** The faithful cycle reaches level 50 from the
    non-degeneracy invariants, the quiet-pair scheduling residual, and
    `EffectiveDrainArmed` — modulo LIV-001 and NO `→ 0`-drain fiction. Contrast
    `PressureTransience.ai_reaches_level_fiftyF_of_tenQuietPairs`, which used the
    falsified `→ 0` model: this version rests on the honest, production-not-guaranteed
    `EffectiveDrainArmed`, so its residual NAMES the full-of-useful-items livelock as
    the precise precondition under which the bot can fail to reach 50. -/
theorem ai_reaches_level_fiftyF_of_effectiveDrain (s : State)
    (hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) ≠ some .wait)
    (hex : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .taskExchange →
                (perceptionRefresh (cycleStepFN k s)).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankExpand →
                (perceptionRefresh (cycleStepFN k s)).nextExpansionCost > 0)
    (hed : EffectiveDrainArmed s)
    (htqp : TenQuietPairsBelowCapInfinitelyOften s) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  ai_reaches_level_fiftyF_of_reduced s hnowait hex hbe
    (reducedResidual_of_effectiveDrain s hed htqp)

end Formal.Liveness.EffectiveDrainTransience
