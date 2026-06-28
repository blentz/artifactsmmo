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

`combatRaw` is the ONE shared genuine-combat primitive: `combatRawOf` below
delegates to `Formal.GearValue.combatRaw` (the same atom the `equip_value`
ranker uses, mirrored by `ai/gear_value.combat_raw_of` in Python), so
strategic_value's combat input cannot drift into a third combat ruler.
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

/-! ## The shared combat-raw primitive.

`combatRawOf` is strategic_value's combat input, defined as `Formal.GearValue.combatRaw`
— the SAME genuine-combat atom the unified Rank ruler (`equip_value`) uses.
Python mirror: `tiers/strategic_value._combat_raw_of_stats` → `gear_value.combat_raw_of`
→ `gear_value_core.combat_raw`. There is exactly ONE combat_raw definition, so
strategic_value's combat ordering cannot diverge from equip_value's. -/

/-- strategic_value's combat input = the unified `GearValue.combatRaw` primitive. -/
def combatRawOf (s : Formal.EquipValueAugmented.RawStats) : Int :=
  Formal.GearValue.combatRaw s

/-- `combatRawOf` is definitionally the one shared `GearValue.combatRaw`. -/
theorem combatRawOf_eq (s : Formal.EquipValueAugmented.RawStats) :
    combatRawOf s = Formal.GearValue.combatRaw s := rfl

/-- The shared combat-raw is nonneg when its combat fields are, so feeding it as
strategic_value's `combatRaw` input keeps the nonneg contract satisfiable. -/
theorem combatRawOf_nonneg (s : Formal.EquipValueAugmented.RawStats)
    (ha : 0 ≤ s.attack) (hr : 0 ≤ s.resistance) (hhr : 0 ≤ s.hpRestore)
    (hhb : 0 ≤ s.hpBonus) (hd : 0 ≤ s.dmg) (hc : 0 ≤ s.crit)
    (hl : 0 ≤ s.lifesteal) (hcb : 0 ≤ s.combatBuff) :
    0 ≤ combatRawOf s := by
  unfold combatRawOf Formal.GearValue.combatRaw
  omega

/-- strategic_value fed the shared `combatRawOf` is well-defined and expands to the
genuine-combat sum × combat weight plus the efficiency block — i.e. the combat
input is literally the one shared `combat_raw` definition, not a re-derived sum. -/
theorem strategicValue_combatRawOf
    (rs : Formal.EquipValueAugmented.RawStats) (w : Weights)
    (wi pr inv ha : Int) :
    strategicValue ⟨combatRawOf rs, wi, pr, inv, ha⟩ w
      = (rs.attack + rs.resistance + rs.hpRestore + rs.hpBonus + rs.dmg + rs.crit
          + rs.lifesteal + rs.combatBuff) * w.combat
        + wi * w.wisdom + pr * w.prospecting + inv * w.inventory + ha * w.haste := by
  unfold strategicValue combatRawOf Formal.GearValue.combatRaw
  rfl

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
(×1000) outscores a 35-slot bag (×1) — combat-slot ordering is preserved. -/
theorem combat_weight_dominates_efficiency :
    strategicValue ⟨0, 0, 0, 35, 0⟩ ⟨1000, 1, 1, 1, 1⟩
      < strategicValue ⟨1, 0, 0, 0, 0⟩ ⟨1000, 1, 1, 1, 1⟩ := by
  unfold strategicValue
  decide

end Formal.StrategicValue
