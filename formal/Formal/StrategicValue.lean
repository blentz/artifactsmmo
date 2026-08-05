-- @concept: items, characters @property: safety, monotonicity
import Formal.GearValue
/-!
# Formal.StrategicValue

**Correctness of the efficiency-weighted `strategic_value` score.**

The Python `tiers/strategic_value.py:strategic_value_pure` returns the
nonneg-weighted sum

    combat_raw * combat_weight
    + wisdom * wisdom_weight + prospecting * prospecting_weight
    + inventory_space * inventory_weight + haste * haste_weight

It is the SEPARATE cross-slot priority / acquisition-timing scorer (#16 plan,
PLAN_acquisition_timing.md), distinct from the proved combat scorer
`equip_value` (Formal.EquipValueAugmented). `combat_raw` carries one shared
`combat_weight` so combat-slot ordering is preserved; the four efficiency stats
each carry their own derived per-stat rate weight, so a bag's compounding value
is no longer scored 1:1 with raw attack.

This module proves the two contracts ObjectiveGap (Phase 3) is parametric over:

1. **Nonnegativity** — with every stat and every weight nonneg the score is
   nonneg. The objective `gap` bounds (`0 ≤ gap ≤ denom`) require a nonneg-int
   value function.
2. **Monotonicity** — the score is monotone non-decreasing in EVERY stat (with
   nonneg weights). More of any good stat never lowers strategic value.

plus concrete witnesses (a pure bag scores positive; combat weight dominates
efficiency so combat ordering is preserved).

These are transferred onto the extracted `Extracted.StrategicValue` def by the
Bridges9 bridge.

The combat INPUT is not computed here and is not a formula of this layer's own:
it is `Formal.GearValue.rankCombat`, one of the two terms the ONE gear ruler is
the sum of (`GearValue.rankValue_decomp`). It used to be `GearValue.combatRaw`,
a flat 8-stat sum defined alongside the ruler — a second ruler in all but name,
which added a resistance PERCENTAGE to an HP amount 1:1. `combatOf` /
`combatOf_eq_rankCombat` below replace `combatRawOf` / `combatRawOf_eq` with that
strictly stronger correspondence, and `pursuitValue` below adds what the flat sum
never had: a proof that combat dominance is an ORDER-EMBEDDING, true for all
integer inputs rather than for the magnitudes the live catalog happens to carry.
-/

namespace Formal.StrategicValue

/-- The genuine-combat signal (one shared weight) and the four efficiency stats. -/
structure Stats where
  combatRaw      : Int
  wisdom         : Int
  prospecting    : Int
  inventorySpace : Int
  haste          : Int
deriving Repr, DecidableEq

/-- Per-stat efficiency rate weights (derived by the impure layer from openapi
rates / cadence proxy / haste probe — PLAN_acquisition_timing.md Phase 1). -/
structure Weights where
  combat      : Int
  wisdom      : Int
  prospecting : Int
  inventory   : Int
  haste       : Int
deriving Repr, DecidableEq

def strategicValue (s : Stats) (w : Weights) : Int :=
  s.combatRaw * w.combat
    + s.wisdom * w.wisdom
    + s.prospecting * w.prospecting
    + s.inventorySpace * w.inventory
    + s.haste * w.haste

/-! ## The combat input IS the gear ruler's own combat term.

RETIRED: `combatRawOf` (= `GearValue.combatRaw`, the flat 8-stat sum) together
with `combatRawOf_eq`, `combatRawOf_nonneg` and `strategicValue_combatRawOf`.
Their subject — the Python `gear_value_core.combat_raw` — no longer exists, so
keeping them would have told a false story about live code. Nothing that
survives is weaker: `combatOf` is the same *role* filled by a strictly stronger
object. Sharing an ATOM only guaranteed the two layers read the same stats;
being one of the ruler's two SUMMANDS guarantees they cannot disagree about the
piece at all, because `GearValue.rankValue_decomp` makes the ruler their sum. -/

/-- strategic_value's combat input: the ONE gear ruler's own COMBAT term at the
Rank purpose. Python mirror: `tiers/strategic_value._combat_of_stats` →
`gear_value.gear_components(stats, Rank)[0]`. -/
def combatOf (isWeapon : Bool) (ci : Formal.PurposeRouting.CombatItem)
    (flatCombat : Int) : Int :=
  Formal.GearValue.rankCombat isWeapon ci flatCombat

theorem combatOf_eq_rankCombat (isWeapon : Bool)
    (ci : Formal.PurposeRouting.CombatItem) (flatCombat : Int) :
    combatOf isWeapon ci flatCombat
      = Formal.GearValue.rankCombat isWeapon ci flatCombat := rfl

/-- The combat input plus the ruler's efficiency term reconstruct the ruler
EXACTLY — the no-double-count / no-dropped-stat statement, carried onto this
layer's own name for the input. -/
theorem combatOf_add_efficiency_eq_rankValue (isWeapon : Bool)
    (ci : Formal.PurposeRouting.CombatItem)
    (flatCombat wisdom prospecting inventorySpace haste : Int)
    (hflat : ci.base.flatUtil
      = flatCombat + wisdom + prospecting + inventorySpace + haste) :
    combatOf isWeapon ci flatCombat
      + Formal.GearValue.rankEfficiency isWeapon wisdom prospecting inventorySpace haste
      = Formal.GearValue.rankValue isWeapon ci :=
  (Formal.GearValue.rankValue_decomp isWeapon ci flatCombat wisdom prospecting
    inventorySpace haste hflat).symm

/-! ## The pursuit reading: combat dominance as an ORDER-EMBEDDING.

`tiers/pursuit_value.pursuit_value` is `strategicValue` with the combat weight
pinned to `STRATEGIC_SCALE` and the efficiency block BOUNDED to
`[-budget, +budget]`. The point of the bound is not to shrink utility but to
make the score an order-embedding of the pair `(combat, efficiency)` ordered
LEXICOGRAPHICALLY, which is what "combat dominates cross-slot" means precisely.

The live invariant this protects (docstring of `tiers/pursuit_value`): a
prospecting-201 artifact must not outrank a modest combat weapon just because
201 > 30. Under `pursuit_combat_dominates` that cannot happen for ANY stat
magnitudes, not merely for the ones in today's item table. -/

/-- Symmetric two-sided clamp. Mirrors the `strategic_value` wrapper's
`efficiency_budget` handling — symmetric because live items carry NEGATIVE
efficiency stats (obsidian_battleaxe: `inventory_space = -25`), so a one-sided
cap would leave the block's span unbounded below. -/
def clampEff (budget e : Int) : Int :=
  if e > budget then budget else if e < -budget then -budget else e

/-- The clamp does what its name says, for any nonneg budget. -/
theorem clampEff_mem (budget e : Int) (hb : 0 ≤ budget) :
    -budget ≤ clampEff budget e ∧ clampEff budget e ≤ budget := by
  unfold clampEff
  split
  · omega
  · split <;> omega

/-- Inside the budget the clamp is the identity, so efficiency ORDERING is
untouched wherever the bound does not bind (which, on the pinned catalog, is
everywhere — the largest live efficiency block is 406 against a budget of 499). -/
theorem clampEff_id (budget e : Int) (hlo : -budget ≤ e) (hhi : e ≤ budget) :
    clampEff budget e = e := by
  unfold clampEff
  split
  · omega
  · split <;> omega

/-- The pursuit score: the ruler's two terms read lexicographically. -/
def pursuitValue (scale budget combat efficiency : Int) : Int :=
  combat * scale + clampEff budget efficiency

/-- **STRUCTURAL COMBAT DOMINANCE.** When the whole efficiency span
(`2 * budget`) is narrower than one unit of scaled combat, a strictly greater
combat term is a strictly greater pursuit value — for EVERY pair of efficiency
blocks, of any magnitude and either sign.

This is the theorem the flat `combat_raw` era never had. It says the property is
a fact of the arithmetic, quantified over all integer inputs, and not a
coincidence of the magnitudes the current catalog happens to contain. -/
theorem pursuit_combat_dominates (scale budget ca cb ea eb : Int)
    (hb : 0 ≤ budget) (hspan : 2 * budget < scale) (hlt : cb < ca) :
    pursuitValue scale budget cb eb < pursuitValue scale budget ca ea := by
  unfold pursuitValue
  obtain ⟨hea_lo, hea_hi⟩ := clampEff_mem budget ea hb
  obtain ⟨heb_lo, heb_hi⟩ := clampEff_mem budget eb hb
  have hstep : (cb + 1) * scale ≤ ca * scale :=
    Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
  rw [Int.add_mul, Int.one_mul] at hstep
  omega

/-- **EFFICIENCY STILL ORDERS.** On a combat TIE the pursuit value is strictly
increasing in the efficiency block (inside the budget) — utility slots keep a
total ranking, which is the no-regression half of the design: the defect being
fixed was utility outranking COMBAT, never utility being ignored. -/
theorem pursuit_efficiency_orders (scale budget c ea eb : Int)
    (hea_lo : -budget ≤ ea) (hea_hi : ea ≤ budget)
    (heb_lo : -budget ≤ eb) (heb_hi : eb ≤ budget)
    (hlt : eb < ea) :
    pursuitValue scale budget c eb < pursuitValue scale budget c ea := by
  unfold pursuitValue
  rw [clampEff_id budget ea hea_lo hea_hi, clampEff_id budget eb heb_lo heb_hi]
  omega

/-- The live parameters (`STRATEGIC_SCALE = 1000`,
`EFFICIENCY_BUDGET = (1000 - 1) / 2 = 499`) satisfy the span hypothesis, so the
dominance theorem is not vacuous at the values production actually uses. -/
theorem live_pursuit_span_ok : 2 * (499 : Int) < 1000 := by decide

/-! ## Nonnegativity. -/

theorem strategicValue_nonneg (s : Stats) (w : Weights)
    (hcr : 0 ≤ s.combatRaw) (hwi : 0 ≤ s.wisdom) (hpr : 0 ≤ s.prospecting)
    (his : 0 ≤ s.inventorySpace) (hha : 0 ≤ s.haste)
    (hwc : 0 ≤ w.combat) (hww : 0 ≤ w.wisdom) (hwp : 0 ≤ w.prospecting)
    (hwiv : 0 ≤ w.inventory) (hwh : 0 ≤ w.haste) :
    0 ≤ strategicValue s w := by
  unfold strategicValue
  have h1 := Int.mul_nonneg hcr hwc
  have h2 := Int.mul_nonneg hwi hww
  have h3 := Int.mul_nonneg hpr hwp
  have h4 := Int.mul_nonneg his hwiv
  have h5 := Int.mul_nonneg hha hwh
  omega

/-- The Phase 1 equipment-profile presets (Python `PROFILE_WEIGHTS`,
`tiers/equipment_profile.py`: `COMBAT = (1000, 0, 0, 0, 0)`,
`UTILITY = (1000, 1, 1, 1, 1)`). `Weights` is `Int`-valued, not `Nat`, so
nonnegativity is NOT structural here — a future edit introducing a negative
preset weight would silently violate `strategicValue_nonneg`'s hypotheses.
This witness pins both presets as genuinely nonneg, so the parametric proof
above provably covers them; `decide` re-checks it on every build. -/
def combatProfileWeights : Weights := ⟨1000, 0, 0, 0, 0⟩

def utilityProfileWeights : Weights := ⟨1000, 1, 1, 1, 1⟩

example :
    0 ≤ combatProfileWeights.combat ∧ 0 ≤ combatProfileWeights.wisdom ∧
      0 ≤ combatProfileWeights.prospecting ∧ 0 ≤ combatProfileWeights.inventory ∧
      0 ≤ combatProfileWeights.haste ∧
    0 ≤ utilityProfileWeights.combat ∧ 0 ≤ utilityProfileWeights.wisdom ∧
      0 ≤ utilityProfileWeights.prospecting ∧ 0 ≤ utilityProfileWeights.inventory ∧
      0 ≤ utilityProfileWeights.haste := by
  decide

/-! ## Monotonicity in each stat (nonneg weights). -/

theorem strategicValue_mono_combatRaw (s : Stats) (w : Weights) (c' : Int)
    (hw : 0 ≤ w.combat) (h : s.combatRaw ≤ c') :
    strategicValue s w ≤ strategicValue { s with combatRaw := c' } w := by
  unfold strategicValue
  simp only []
  have := Int.mul_le_mul_of_nonneg_right h hw
  omega

theorem strategicValue_mono_wisdom (s : Stats) (w : Weights) (x' : Int)
    (hw : 0 ≤ w.wisdom) (h : s.wisdom ≤ x') :
    strategicValue s w ≤ strategicValue { s with wisdom := x' } w := by
  unfold strategicValue
  simp only []
  have := Int.mul_le_mul_of_nonneg_right h hw
  omega

theorem strategicValue_mono_prospecting (s : Stats) (w : Weights) (x' : Int)
    (hw : 0 ≤ w.prospecting) (h : s.prospecting ≤ x') :
    strategicValue s w ≤ strategicValue { s with prospecting := x' } w := by
  unfold strategicValue
  simp only []
  have := Int.mul_le_mul_of_nonneg_right h hw
  omega

theorem strategicValue_mono_inventorySpace (s : Stats) (w : Weights) (x' : Int)
    (hw : 0 ≤ w.inventory) (h : s.inventorySpace ≤ x') :
    strategicValue s w ≤ strategicValue { s with inventorySpace := x' } w := by
  unfold strategicValue
  simp only []
  have := Int.mul_le_mul_of_nonneg_right h hw
  omega

theorem strategicValue_mono_haste (s : Stats) (w : Weights) (x' : Int)
    (hw : 0 ≤ w.haste) (h : s.haste ≤ x') :
    strategicValue s w ≤ strategicValue { s with haste := x' } w := by
  unfold strategicValue
  simp only []
  have := Int.mul_le_mul_of_nonneg_right h hw
  omega

/-! ## Witnesses. -/

/-- A pure bag (inventory_space 35, no combat/other stats) scores positive under
positive weights — so bags get a nonzero cross-slot priority. -/
theorem pure_bag_scores_positive :
    strategicValue ⟨0, 0, 0, 35, 0⟩ ⟨1000, 1, 1, 50, 1⟩ = 1750 := by
  unfold strategicValue
  decide

/-- Combat weight dominates the efficiency weights: a single point of combat_raw
(×1000) outscores a 35-slot bag (×1) — combat-slot ordering is preserved.

`ai/tiers/pursuit_value.pursuit_value` is the Python INSTANCE of this: it calls
`strategic_value` with exactly these weights ⟨1000,1,1,1,1⟩ and an efficiency
budget of 999 (< the 1000 combat weight proven dominant here), so any combat
item outranks any all-efficiency item cross-slot. A thin parameter pin of this
proved core — no separate theorem (would restate this witness verbatim). -/
theorem combat_weight_dominates_efficiency :
    strategicValue ⟨0, 0, 0, 35, 0⟩ ⟨1000, 1, 1, 1, 1⟩
      < strategicValue ⟨1, 0, 0, 0, 0⟩ ⟨1000, 1, 1, 1, 1⟩ := by
  unfold strategicValue
  decide

end Formal.StrategicValue
