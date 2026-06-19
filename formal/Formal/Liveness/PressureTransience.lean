import Formal.Liveness.PressureDrain
import Formal.Liveness.FightFairnessF
import Formal.Liveness.CycleStepFIteration

/-! # PressureTransience — Workstream A Phase-1 Brick 3d-c (counting): close
`ReducedResidualF`'s low-pressure conjunct from the local dichotomy.

The local dichotomy is complete (fight side `PressureBurst`, drain side
`PressureDrain`). This module does the bounded-burst COUNTING that turns it into the
`ReducedResidualF` the faithful capstone needs: from the genuine scheduling residual
(`TenQuietPairsBelowCapInfinitelyOften` — the ten non-pressure blockers quiet on two
CONSECUTIVE refreshed selection states, below the cap, infinitely often) plus
`Drainability.RuntimeInvariant` and the capacity non-degeneracy invariant, it proves
`FightFairnessF.ReducedResidualF`.

## Why a quiet PAIR resolves the coincidence

`ReducedResidualF` needs a position that is BOTH low-pressure AND ten-quiet, i.o. A
single ten-quiet position may be high-pressure; the drain then fires but only the
NEXT position is low — which need not be ten-quiet. A quiet PAIR `(k, k+1)` closes
the gap: if pressure is low at `k`, `k` is the witness; if high, `RuntimeInvariant`
arms a drain channel, the drain step (`cycleStepF_drains_when_pressured_armed_tenQuiet`)
empties the bag, so `k+1` is low-pressure — AND ten-quiet by the pair. Either way a
witness exists. The pair residual is still PURELY about the ten non-pressure blockers
(the honest scheduling residual); it asks they be quiet in runs of length two, which
is what genuine transience (a blocker's clear lasts more than an instant) delivers.

This discharges the low-pressure conjunct WITHOUT assuming it — the faithful win.
What remains a residual is exactly: the ten non-pressure blockers quiet i.o. (pairs)
+ drainability when pressured + positive capacity — all honest, checkable
properties, NO inventory-composition fabrication.

## SOUNDNESS BOUNDARY (adversarial review, 2026-06-19)

This argument is LOAD-BEARING on `InventoryDynamics.pressureDelta` modelling every
reducer as `inventoryUsed → 0` (the high-pressure branch does `rw [hdrain]` with
`hdrain : (cycleStepFN (k+1) s).inventoryUsed = 0`, then `omega`). That `→ 0` is
OPTIMISTIC, not conservative: production's `depositFull` plausibly empties the bag,
but `discardHigh`/`sellPressured`/`discardCritical`/`craftRelief` remove only
specific items (a PARTIAL drain). The transience needs each drain to land STRICTLY
BELOW 85%; `→ 0` is the extreme that trivially satisfies it. The differential investigation
(`docs/REVIEW_pressuredelta_differential.md`, 2026-06-19) FALSIFIED the `→ 0` claim:
production's discard removes only the EXCESS above per-item caps, deposit keeps a
large keep-set, sell targets only `free ≥ 5`, craft batch-clamps — NONE guarantees
post-pressure < 85%, and discard/deposit can go SILENT while still pressured. So this
counting is sound for the `→ 0`-drain MODEL but the model is UNFAITHFUL: under the
real partial drains the conclusion "k+1 is low-pressure" FAILS, and the bot can
livelock at ≥ 85% (`[[project_inventory_profiles]]`). The honest residual is therefore
stronger than `DrainArmed` — call it `EffectiveDrainArmed` (a reducer whose
application actually drops below 85% fires i.o.) — and it is a runtime property
production does NOT guarantee. "Reaches level 50" here is a statement about the
`→ 0`-drain model, NOT an unconditional real-bot guarantee. Follow-on: weaken
`pressureDelta`, swap in `EffectiveDrainArmed`, re-derive — surfacing the livelock as
the precise failure precondition.

Local `perceptionRefresh` bridges (inventoryUsed/Max, hasOverstockItems,
sellableInventoryNonempty) are proved inline — `perceptionRefresh` touches only the
two objective Bools, so each is `split <;> rfl`.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed. -/

namespace Formal.Liveness.PressureTransience

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration
open Formal.Liveness.Drainability
open Formal.Liveness.PressureBurst
open Formal.Liveness.PressureDrain
open Formal.Liveness.FightFairnessF

/-! ## `perceptionRefresh` inventory/flag bridges (touches only objective Bools) -/

theorem pr_inventoryUsed (s : State) :
    (perceptionRefresh s).inventoryUsed = s.inventoryUsed := by
  unfold perceptionRefresh; split <;> rfl

theorem pr_inventoryMax (s : State) :
    (perceptionRefresh s).inventoryMax = s.inventoryMax := by
  unfold perceptionRefresh; split <;> rfl

theorem pr_overstock (s : State) :
    (perceptionRefresh s).hasOverstockItems = s.hasOverstockItems := by
  unfold perceptionRefresh; split <;> rfl

theorem pr_sellable (s : State) :
    (perceptionRefresh s).sellableInventoryNonempty = s.sellableInventoryNonempty := by
  unfold perceptionRefresh; split <;> rfl

/-! ## The scheduling residual: ten-quiet on two consecutive refreshed states -/

/-- **The honest scheduling residual.** Infinitely often, two CONSECUTIVE refreshed
    selection states `perceptionRefresh (cycleStepFN k s)` and `…(k+1)…` are both
    below the cap with the ten `nonPressureBlockers` quiet. Purely about the ten
    non-pressure blockers (the four pressure-gated chores are handled by the pressure
    dynamics); asking quietness in runs of length two is what genuine blocker
    transience supplies. -/
def TenQuietPairsBelowCapInfinitelyOften (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
    (cycleStepFN k s).level < 50
    ∧ (∀ b ∈ nonPressureBlockers, fires b (perceptionRefresh (cycleStepFN k s)) = false)
    ∧ (cycleStepFN (k+1) s).level < 50
    ∧ (∀ b ∈ nonPressureBlockers, fires b (perceptionRefresh (cycleStepFN (k+1) s)) = false)

/-! ## The counting: quiet pairs + drainability + capacity ⇒ ReducedResidualF -/

/-- **Close the low-pressure conjunct.** From the quiet-pair scheduling residual,
    `RuntimeInvariant` (drainability when pressured), and the positive-capacity
    invariant, `ReducedResidualF` holds — the low-pressure conjunct is DISCHARGED, not
    assumed. At a quiet pair: low pressure at `k` ⇒ `k` witnesses; high pressure at
    `k` ⇒ the drain empties the bag so `k+1` is low-pressure and (by the pair)
    ten-quiet, witnessing. -/
theorem reducedResidual_of_tenQuietPairs (s : State)
    (hcap : ∀ k, (cycleStepFN k s).inventoryMax > 0)
    (hri : RuntimeInvariant cycleStepFN s)
    (htqp : TenQuietPairsBelowCapInfinitelyOften s) :
    ReducedResidualF s := by
  intro N
  obtain ⟨k, hkN, hlt_k, hq_k, hlt_k1, hq_k1⟩ := htqp N
  by_cases hlow : 100 * (perceptionRefresh (cycleStepFN k s)).inventoryUsed
                    < 85 * (perceptionRefresh (cycleStepFN k s)).inventoryMax
  · -- Low pressure at k: k is the witness.
    exact ⟨k, hkN, hlt_k, hlow, hq_k⟩
  · -- High pressure at k: drain ⇒ k+1 low-pressure ∧ ten-quiet (by the pair).
    refine ⟨k+1, le_trans hkN (Nat.le_succ k), hlt_k1, ?_, hq_k1⟩
    have hUu := pr_inventoryUsed (cycleStepFN k s)
    have hUm := pr_inventoryMax (cycleStepFN k s)
    -- Pressured on the pre-refresh state (perceptionRefresh preserves inventory).
    have hpres_pre : Pressured (cycleStepFN k s) := by
      unfold Pressured
      simp only [DISCARD_HIGH_DEN, DISCARD_HIGH_NUM]
      rw [hUu, hUm] at hlow
      omega
    have harmed_pre : DrainArmed (cycleStepFN k s) := hri k ⟨hpres_pre, hcap k⟩
    -- Bridge Pressured / DrainArmed / capacity to the refreshed selection state.
    have hpres_r : Pressured (perceptionRefresh (cycleStepFN k s)) := by
      unfold Pressured at hpres_pre ⊢; rw [hUu, hUm]; exact hpres_pre
    have harmed_r : DrainArmed (perceptionRefresh (cycleStepFN k s)) := by
      unfold DrainArmed at harmed_pre ⊢
      rw [pr_overstock, pr_sellable]; exact harmed_pre
    have hmax_r : (perceptionRefresh (cycleStepFN k s)).inventoryMax > 0 := by
      rw [hUm]; exact hcap k
    -- The drain empties the bag at step k+1.
    have hdrain : (cycleStepFN (k+1) s).inventoryUsed = 0 := by
      rw [cycleStepFN_succ_outer k s]
      exact cycleStepF_drains_when_pressured_armed_tenQuiet (cycleStepFN k s)
        hpres_r hmax_r harmed_r hq_k
    -- So the refreshed state at k+1 is low-pressure (capacity positive).
    rw [pr_inventoryUsed, pr_inventoryMax, hdrain]
    have := hcap (k+1)
    omega

/-! ## The faithful capstone, fed by the honest residual set -/

/-- **Faithful level-50 reachability from the honest residual set.** The faithful
    cycle reaches level 50 from: the three non-degeneracy invariants, the quiet-pair
    scheduling residual, `RuntimeInvariant`, and positive capacity — with the
    low-pressure transience PROVEN, not assumed. This is the honest faithful capstone:
    no unfaithful 14-blocker assumption, no measure, modulo LIV-001 and these
    checkable runtime properties. -/
theorem ai_reaches_level_fiftyF_of_tenQuietPairs (s : State)
    (hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) ≠ some .wait)
    (hex : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .taskExchange →
                (perceptionRefresh (cycleStepFN k s)).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankExpand →
                (perceptionRefresh (cycleStepFN k s)).nextExpansionCost > 0)
    (hcap : ∀ k, (cycleStepFN k s).inventoryMax > 0)
    (hri : RuntimeInvariant cycleStepFN s)
    (htqp : TenQuietPairsBelowCapInfinitelyOften s) :
    ∃ k, (cycleStepFN k s).level ≥ 50 :=
  ai_reaches_level_fiftyF_of_reduced s hnowait hex hbe
    (reducedResidual_of_tenQuietPairs s hcap hri htqp)

end Formal.Liveness.PressureTransience
