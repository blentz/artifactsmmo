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

NOTE (2026-06-19) — `pressureDelta` survives ONLY as the faithful inventory layer of
the `cycleStepF` definition; the non-vacuous reach-50
(`LevelingDescent.cycleStepF_reaches_fifty_of_fights`) uses it via its level/xp
PRESERVATION (`pressureDelta_level`/`_xp`), NOT its reducer post-value. The reducer
`→ 0` is therefore NO LONGER load-bearing for any live proof: the i.o.-fairness
transience tower that depended on it was REMOVED as vacuous. The differential
investigation (`docs/REVIEW_pressuredelta_differential.md`) had already shown `→ 0` is
UNFAITHFUL anyway (production reducers remove only a bounded subset — discard the
excess above per-item caps, deposit minus a keep-set, sell down to 5 free — so a bag of
capped items can stay ≥ 85% and livelock, the `[[project_inventory_profiles]]` bug now
fixed by the production last-resort deposit). The lemmas below are value-agnostic in
`DROP_BOUND`; the reducer-clears lemmas are retained as harmless inventory facts.

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
      -- CORRECTED 2026-07-22: reducers make NO drain claim. See the note below.
      s
  | _ => s

/-- The pressure-reducing means. NOTE (2026-07-22): this is a CLASSIFICATION of
    which means production intends as reducers. It no longer carries any claim
    about how much they actually drain — see the note on `pressureDelta`. -/
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

/-! ## Reducers make NO drain claim — RETIRED 2026-07-22

`pressureDelta` used to model every reducer as `inventoryUsed := 0`, and two
lemmas here — `pressureDelta_reducer_clears` and
`pressureGatedChores_quiet_after_reducer` — read that off. Both are DELETED,
because the premise is false about production.

`docs/REVIEW_pressuredelta_differential.md` (2026-06-19) drove all five reducers
and found NONE drops the bag below the 85% watermark: DISCARD removes only the
excess above per-item caps (a capped bag stays >=85% and the guard then goes
SILENT), DEPOSIT keeps a large keep-set, SELL targets `free >= 5`, CRAFT
batch-clamps. The honest replacement built at the time
(`EffectiveDrainTransience.lean`, lifting the drain to an explicit
`EffectiveDrainArmed` residual) was deleted as COLLATERAL in the vacuous-tower
removal `c7c658ab`, and the `-> 0` model it had replaced survived it.

The model now makes no drain claim at all: a reducer leaves `inventoryUsed`
alone. That is PESSIMISTIC — production usually does remove something — which is
the safe direction for a reachability argument.

Nothing is lost. No descent row consumes the `bankPressure` slot; it appears in
`EMeasure` only as an equality premise for higher slots, so reducer rows descend
via their latch/debt components and the pressure value is lex-dominated either
way. The chore latches are handled by `CycleStepD.partialClear` (debt-counted
re-arms), which is the mechanism that actually models a reducer needing several
batches — and, unlike the `-> 0` drain, it is honest about that.

What remains assumed is `DEBT_CAP`: the number of re-arm rounds a chore can take
before its latch clears. That bound is where the real full-of-useful-items
livelock (`project_inventory_profiles`) would show up, and it is an opaque
worst-case constant, not a proven one. -/

end Formal.Liveness.InventoryDynamics
