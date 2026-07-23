-- @concept: synergy @property: safety, boundedness
/-
Formal model of the pure synergy core
`src/artifactsmmo_cli/ai/tiers/synergy_core.py`
(spec docs/superpowers/specs/2026-07-19-synergy-weighting-design.md §3).
The Python core is bound to these semantics by the SYNERGY_CORE_MUTATIONS
group (unit-killed, formal/diff/mutate.py).

`synergyPure shared total` is the third modulating factor in the tree's
selection weight `gain * falloff(focus) * synergy`: an affine map of the
demand-weighted overlap ratio `shared/total` into `[sMin, 1]`. Same curve
shape as `falloff` (FLOOR + (1 - FLOOR) * x), so the obligations below are
structural twins of `falloff_le_one` / `falloff_ge_floor` / `falloff_floor_pos`
in `Formal/ProgressionTree.lean`. This file imports nothing (core Lean only),
so the two small `Rat` order helpers are re-stated locally.
-/

namespace Formal.Synergy

/-! ### Small `Rat` order helpers (core Lean, no mathlib). -/

/-- Division by a positive constant is monotone. -/
theorem ratDivMono {a b c : Rat} (h : a ≤ b) (hc : 0 < c) : a / c ≤ b / c := by
  rw [Rat.div_def, Rat.div_def]
  exact Rat.mul_le_mul_of_nonneg_right h (Rat.le_of_lt (Rat.inv_pos.mpr hc))

/-- A nonneg numerator over a positive denominator is nonneg. -/
theorem ratDivNonneg {a c : Rat} (ha : 0 ≤ a) (hc : 0 < c) : 0 ≤ a / c := by
  rw [Rat.div_def]
  exact Rat.mul_nonneg ha (Rat.le_of_lt (Rat.inv_pos.mpr hc))

/-- Synergy floor: even a zero-overlap target keeps a strictly-positive weight,
so d'Hondt still seats it eventually (`minWeight_pos`). `sMin = 1/3`; the range
`sMax/sMin = 3` stays strictly inside falloff's `1/focusFloor = 9`. -/
def sMin : Rat := mkRat 1 3

/-- Overlap ratio `shared/total` as an exact `Rat` (Python
`Fraction(shared, total)`). Evaluated only where `total ≠ 0`. -/
def synergyRatio (shared total : Nat) : Rat :=
  (shared : Rat) / (total : Rat)

/-- Purity multiplier: `total = 0` (needs nothing) is maximally aligned and
returns `1`; otherwise the affine map `sMin + (1 - sMin) * (shared/total)`.
Mirrors Python `synergy_pure` (whose `total <= 0` guard is `total = 0` over
`Nat`, and whose `shared <= total` assert is a precondition, not a branch). -/
def synergyPure (shared total : Nat) : Rat :=
  if total = 0 then 1
  else sMin + (1 - sMin) * synergyRatio shared total

/-- `total ≠ 0` lifts to `0 < (total : Rat)`. -/
theorem total_pos_of_ne {total : Nat} (h : total ≠ 0) : (0 : Rat) < (total : Rat) := by
  have : (0 : Nat) < total := Nat.pos_of_ne_zero h
  exact_mod_cast this

/-- `(total : Rat) ≠ 0` from `total ≠ 0`. -/
theorem total_rat_ne_zero {total : Nat} (h : total ≠ 0) : (total : Rat) ≠ 0 := by
  have hpos := total_pos_of_ne h
  intro hz; rw [hz] at hpos; exact absurd hpos (by decide)

/-- `1 - sMin = 2/3 ≥ 0` (the alignment coefficient is nonneg). -/
theorem oneSubMin_nonneg : (0 : Rat) ≤ 1 - sMin := by
  have : sMin ≤ 1 := by decide
  grind

/-- The ratio is nonneg. -/
theorem synergyRatio_nonneg {shared total : Nat} (h : total ≠ 0) :
    0 ≤ synergyRatio shared total := by
  unfold synergyRatio
  exact ratDivNonneg (by exact_mod_cast Nat.zero_le _) (total_pos_of_ne h)

/-- With `shared ≤ total` the ratio is `≤ 1`. -/
theorem synergyRatio_le_one {shared total : Nat} (h : total ≠ 0) (hst : shared ≤ total) :
    synergyRatio shared total ≤ 1 := by
  unfold synergyRatio
  have hpos := total_pos_of_ne h
  have hcast : (shared : Rat) ≤ (total : Rat) := by exact_mod_cast hst
  have hself : (total : Rat) / (total : Rat) = 1 := by
    rw [Rat.div_def, Rat.mul_inv_cancel _ (total_rat_ne_zero h)]
  calc (shared : Rat) / (total : Rat)
      ≤ (total : Rat) / (total : Rat) := ratDivMono hcast hpos
    _ = 1 := hself

/-- §3.4 degenerate: a candidate that needs nothing is maximally aligned.
Proven, not commented. -/
theorem synergy_total_zero (shared : Nat) : synergyPure shared 0 = 1 := by
  simp [synergyPure]

/-- The multiplier never drops below `sMin` (the anti-starvation floor). -/
theorem synergy_ge_floor (shared total : Nat) : sMin ≤ synergyPure shared total := by
  unfold synergyPure
  split
  · decide
  · rename_i h
    have hnn : 0 ≤ (1 - sMin) * synergyRatio shared total :=
      Rat.mul_nonneg oneSubMin_nonneg (synergyRatio_nonneg h)
    grind

/-- The multiplier never exceeds `1` when `shared ≤ total` (guaranteed by the
assembly layer: an intersection cannot exceed its own set). -/
theorem synergy_le_one {shared total : Nat} (h : shared ≤ total) :
    synergyPure shared total ≤ 1 := by
  unfold synergyPure
  split
  · exact Rat.le_refl
  · rename_i ht
    have hr : synergyRatio shared total ≤ 1 := synergyRatio_le_one ht h
    have hmul : (1 - sMin) * synergyRatio shared total ≤ (1 - sMin) * 1 :=
      Rat.mul_le_mul_of_nonneg_left hr oneSubMin_nonneg
    rw [Rat.mul_one] at hmul
    grind

/-- The floor is strictly positive — the `minWeight_pos` feeder that preserves
`interleaveDue_reaches` (no-starvation). -/
theorem synergy_floor_pos (shared total : Nat) :
    (0 : Rat) < synergyPure shared total := by
  unfold synergyPure
  split
  · decide
  · rename_i h
    have h1 : (0 : Rat) < sMin := by decide
    have hnn : 0 ≤ (1 - sMin) * synergyRatio shared total :=
      Rat.mul_nonneg oneSubMin_nonneg (synergyRatio_nonneg h)
    grind

/-- MONOTONE: higher overlap yields no-lower synergy (more aligned work scores
at least as high). -/
theorem synergy_monotone {s1 s2 total : Nat} (h : s1 ≤ s2) :
    synergyPure s1 total ≤ synergyPure s2 total := by
  unfold synergyPure
  split
  · exact Rat.le_refl
  · rename_i ht
    have hpos := total_pos_of_ne ht
    have hratio : synergyRatio s1 total ≤ synergyRatio s2 total := by
      unfold synergyRatio
      exact ratDivMono (by exact_mod_cast h) hpos
    have hmul : (1 - sMin) * synergyRatio s1 total ≤ (1 - sMin) * synergyRatio s2 total :=
      Rat.mul_le_mul_of_nonneg_left hratio oneSubMin_nonneg
    grind

end Formal.Synergy
