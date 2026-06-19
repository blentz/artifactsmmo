import Formal.Liveness.InventoryPressure

/-! # InventoryDynamics — Workstream A Phase-1 Brick 2: the faithful pressure layer

Brick 1 (`InventoryPressure`) proved the gate-direction lemmas from the EXISTING
fire predicates. This brick adds the missing FAITHFUL DYNAMICS: in the current
model `applyActionKind` PRESERVES `inventoryUsed` (Plan.lean:229/237/246 defer the
decrement; `.fight` never raises it), so inventory pressure is frozen — unfaithful
to the real bot, where fighting fills the bag and chores drain it.

`pressureDelta` is the per-means inventory-pressure update, to be composed AFTER a
cycle step (Brick 3's `cycleStepF`) exactly as `perceptionRefresh` composes before
one. It touches ONLY `inventoryUsed`, so every level/xp/hp/measure fact transfers
by `rfl` bridges (the `perceptionRefresh` playbook). The model:

* `objectiveStep` (the combat/objective FIGHT) loots → `+ DROP_BOUND` (capped);
* `claimPending` MINTS one item → `+ 1` (capped) — the Phase-0 wrinkle-1 producer;
* the pressure-reducers (deposit/discard/sell/craftRelief) DRAIN the bag → `0`;
* every other means leaves pressure unchanged.

This brick proves the foundational facts the transience argument (Brick 3+) and
the differential (Phase 2) consume: field-preservation, BOUNDED growth (no action
raises pressure by more than `DROP_BOUND`), and that each reducer clears pressure
to `0` (which, with Brick 1's `pressureGatedChores_quiet_of_low`, silences the
gated chores while `inventoryMax > 0`).

NOTE — the exact post-values are Phase-2 DIFFERENTIAL obligations, and the reducer
post-value `0` is LOAD-BEARING for the transience (`PressureTransience`): the
counting argument needs each drain to land STRICTLY BELOW the 85% threshold, and
models that as the extreme `0`. This is OPTIMISTIC, not conservative — production's
`depositFull` (deposit-all) plausibly empties the bag, but `discardHigh`/
`sellPressured`/`discardCritical`/`craftRelief` remove only specific items (a
PARTIAL drain). Modelling every reducer as `→ 0` overstates the drain, making
"low pressure next step" easier to prove. The differential investigation
(`docs/REVIEW_pressuredelta_differential.md`, 2026-06-19) FALSIFIED the claim that a
fired reducer drops pressure below 85%: production's discard removes only the EXCESS
above per-item caps (a bag of capped consumables/recipe-mats stays ≥ 85% and the
guard then goes SILENT), deposit keeps a large keep-set, sell targets only `free ≥ 5`
(≥ 85% for `inventoryMax > 33`), and craft batch-clamps. So `→ 0` is UNFAITHFUL, and
under a faithful partial drain the `PressureTransience` counting is FALSE — the real
bot can livelock at ≥ 85% (`[[project_inventory_profiles]]`'s full-of-useful-items
livelock). The honest fix (follow-on): weaken `pressureDelta` to the bounded partial
drain each action actually performs, replace `Drainability.DrainArmed` with
`EffectiveDrainArmed` (a reducer whose application drops below 85% fires), and
re-derive the counting — which then surfaces the livelock as its precise failure
precondition. The lemmas below are value-agnostic in `DROP_BOUND`.

Additive only — `applyActionKind`, `cycleStep`, and every existing proof are
untouched. Axioms ⊆ {propext, Quot.sound}. Liveness namespace — Mathlib allowed. -/

namespace Formal.Liveness.InventoryDynamics

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder

/-- Max item-slots a single fight/gather adds to the bag (the largest monster/
    resource drop stack). **Differential-pinned** (Phase 2 pins the exact catalog
    max); the value is provisional and every lemma in this module is agnostic to
    it beyond `DROP_BOUND ≥ 1` (needed only so the `+1` claim mint stays within
    the bound). -/
def DROP_BOUND : Nat := 8

/-- The per-means inventory-pressure update, applied AFTER the cycle's action.
    Touches ONLY `inventoryUsed`; capped at `inventoryMax` for the producers. -/
def pressureDelta (k : MeansKind) (s : State) : State :=
  match k with
  | .objectiveStep => { s with inventoryUsed := min s.inventoryMax (s.inventoryUsed + DROP_BOUND) }
  | .claimPending  => { s with inventoryUsed := min s.inventoryMax (s.inventoryUsed + 1) }
  | .depositFull | .discardCritical | .discardHigh | .sellPressured | .craftRelief =>
      { s with inventoryUsed := 0 }
  | _ => s

/-- The pressure-reducing means: each DRAINS the bag (modelled `inventoryUsed → 0`). -/
def isPressureReducer (k : MeansKind) : Bool :=
  match k with
  | .depositFull | .discardCritical | .discardHigh | .sellPressured | .craftRelief => true
  | _ => false

/-! ## Field-preservation bridges — `pressureDelta` touches only `inventoryUsed`,
so every other field transfers by `rfl` across all 23 means branches. These let
Brick 3 carry the descent / level-advance to the faithful cycle. -/

theorem pressureDelta_level (k : MeansKind) (s : State) :
    (pressureDelta k s).level = s.level := by cases k <;> rfl

theorem pressureDelta_xp (k : MeansKind) (s : State) :
    (pressureDelta k s).xp = s.xp := by cases k <;> rfl

theorem pressureDelta_hp (k : MeansKind) (s : State) :
    (pressureDelta k s).hp = s.hp := by cases k <;> rfl

theorem pressureDelta_maxHp (k : MeansKind) (s : State) :
    (pressureDelta k s).maxHp = s.maxHp := by cases k <;> rfl

theorem pressureDelta_inventoryMax (k : MeansKind) (s : State) :
    (pressureDelta k s).inventoryMax = s.inventoryMax := by cases k <;> rfl

theorem pressureDelta_bankRequiredLevel (k : MeansKind) (s : State) :
    (pressureDelta k s).bankRequiredLevel = s.bankRequiredLevel := by cases k <;> rfl

/-! ## Bounded growth — no means raises pressure by more than `DROP_BOUND`. The
combat/objective fight and the claim mint are the only producers; both are capped
and within the bound. This is proof-step 2 of the plan (the riser is bounded). -/

/-- **Bounded growth.** Every means leaves `inventoryUsed` at most `DROP_BOUND`
above its prior value — the single faithful fact that the riser (fight loot / claim
mint) is bounded, which bounds the chore burst between two combats. -/
theorem pressureDelta_inventoryUsed_le_add_bound (k : MeansKind) (s : State) :
    (pressureDelta k s).inventoryUsed ≤ s.inventoryUsed + DROP_BOUND := by
  cases k <;> simp only [pressureDelta, DROP_BOUND] <;> omega

/-! ## Reducers clear pressure — each drain empties the bag, so (with `Brick 1`)
the gated chores fall silent while `inventoryMax > 0`. -/

/-- Every pressure-reducer drains the bag to `0`. -/
theorem pressureDelta_reducer_clears {k : MeansKind} (h : isPressureReducer k = true)
    (s : State) : (pressureDelta k s).inventoryUsed = 0 := by
  cases k <;> simp_all [isPressureReducer, pressureDelta]

/-- After a reducer, all four pressure-gated chores are quiet (the drained bag is
    below every threshold while `inventoryMax > 0`). Bridges Brick-1's
    `pressureGatedChores_quiet_of_low` through the cleared pressure. -/
theorem pressureGatedChores_quiet_after_reducer {k : MeansKind}
    (h : isPressureReducer k = true) (s : State) (hmax : s.inventoryMax > 0) :
    discardCriticalFires (pressureDelta k s) = false
      ∧ discardHighFires (pressureDelta k s) = false
      ∧ depositFullFires (pressureDelta k s) = false
      ∧ sellPressuredFires (pressureDelta k s) = false := by
  apply InventoryPressure.pressureGatedChores_quiet_of_low
  rw [pressureDelta_reducer_clears h s, pressureDelta_inventoryMax]
  omega

end Formal.Liveness.InventoryDynamics
