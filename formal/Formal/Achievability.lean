-- @concept: gear, planner @property: boundedness, monotonicity
/-
Mirrors `achievability_pure` in `src/artifactsmmo_cli/ai/tiers/achievability_core.py`.

The fourth modulating factor in the tree's selection weight. `aMin` is 1/2 — a
2:1 range, strictly inside `Synergy.sMin`'s 3:1, which is inside `falloff`'s
9:1, so aging dominates alignment dominates effort.

Lean core only — no mathlib (mathlib is quarantined to `Formal/Liveness/`).
Same idiom as `Formal/Synergy.lean`: `unfold`, `simp`, `decide`, `grind`,
`calc`, `exact_mod_cast`, and the `Rat.*` lemmas from core. This file imports
nothing, so the small `Rat` order helpers (`ratDivMono`, `ratDivNonneg`, and
the antitone counterpart `ratDivAntitone` this factor additionally needs,
since `achievabilityRatio`'s DENOMINATOR — not its numerator — tracks effort)
are re-stated locally rather than imported from `Formal.Synergy`.
-/

namespace Formal.Achievability

/-! ### Small `Rat` order helpers (core Lean, no mathlib). -/

/-- Division by a positive constant is monotone. -/
theorem ratDivMono {a b c : Rat} (h : a ≤ b) (hc : 0 < c) : a / c ≤ b / c := by
  rw [Rat.div_def, Rat.div_def]
  exact Rat.mul_le_mul_of_nonneg_right h (Rat.le_of_lt (Rat.inv_pos.mpr hc))

/-- A nonneg numerator over a positive denominator is nonneg. -/
theorem ratDivNonneg {a c : Rat} (ha : 0 ≤ a) (hc : 0 < c) : 0 ≤ a / c := by
  rw [Rat.div_def]
  exact Rat.mul_nonneg ha (Rat.le_of_lt (Rat.inv_pos.mpr hc))

/-- Division by a LARGER positive denominator (same nonneg numerator) yields a
smaller-or-equal quotient — the antitone counterpart of `ratDivMono`. Proved by
moving both sides to the common denominator `c1 * c2` (via `mul_inv_cancel`)
rather than by inverse-antitonicity, since core Lean has no `inv_le_inv`
lemma for `Rat`. -/
theorem ratDivAntitone {a c1 c2 : Rat} (ha : 0 ≤ a) (hc1 : 0 < c1) (hc2 : 0 < c2)
    (h : c1 ≤ c2) : a / c2 ≤ a / c1 := by
  have hne1 : c1 ≠ 0 := by intro hz; rw [hz] at hc1; exact absurd hc1 (by decide)
  have hne2 : c2 ≠ 0 := by intro hz; rw [hz] at hc2; exact absurd hc2 (by decide)
  have hcpos : (0 : Rat) < c1 * c2 := Rat.mul_pos hc1 hc2
  have lhs_eq : (c1 * c2) * c2⁻¹ = c1 := by
    rw [Rat.mul_assoc, Rat.mul_inv_cancel c2 hne2, Rat.mul_one]
  have rhs_eq : (c1 * c2) * c1⁻¹ = c2 := by
    rw [Rat.mul_comm c1 c2, Rat.mul_assoc, Rat.mul_inv_cancel c1 hne1, Rat.mul_one]
  have step : (c1 * c2) * c2⁻¹ ≤ (c1 * c2) * c1⁻¹ := by
    rw [lhs_eq, rhs_eq]; exact h
  have hinv : c2⁻¹ ≤ c1⁻¹ := Rat.le_of_mul_le_mul_left step hcpos
  rw [Rat.div_def, Rat.div_def]
  exact Rat.mul_le_mul_of_nonneg_left hinv ha

/-- Achievability floor: even an enormously distant target keeps a
strictly-positive weight, so d'Hondt still awards it a seat eventually
(`minWeight_pos`). `aMin = 1/2`; the range `1/aMin = 2` stays strictly inside
synergy's `3` (`sMin = 1/3`), which is itself inside falloff's `9`. -/
def aMin : Rat := mkRat 1 2

/-- How much unmet work counts as a MEANINGFUL difference, in demand units.
Added to BOTH sides of the effort ratio. Mirrors `EFFORT_SCALE` in
`achievability_core.py`, whose docstring records the live failure that fixed the
value: at a scale of 1 a zero-effort candidate drags the reference to 0 and
collapses every other candidate onto the floor together, so the factor stops
reordering anything. Positivity (`effortScale_pos`) is what every denominator
lemma below actually needs — the specific value is a calibration knob, so no
theorem here depends on it being 100. -/
def effortScale : Rat := 100

theorem effortScale_pos : (0 : Rat) < effortScale := by decide

/-- Relative-effort ratio `(minEffort + effortScale)/(effort + effortScale)` as
an exact `Rat`. Adding the scale to both sides also keeps a zero-effort
candidate from dividing by zero. -/
def achievabilityRatio (effort minEffort : Nat) : Rat :=
  ((minEffort : Rat) + effortScale) / ((effort : Rat) + effortScale)

/-- Effort multiplier: the affine map `aMin + (1 - aMin) * ratio`. Mirrors
Python `achievability_pure` (whose `effort <= 0` branch and `effort >=
min_effort >= 0` assert are precondition/degenerate-case handling, not
additional Lean cases: `effort = 0` over `Nat` forces `minEffort = 0` too by
the assembly-layer invariant `minEffort ≤ effort`, so the ratio is already `1`
and this single formula recovers the Python branch's return value exactly). -/
def achievabilityPure (effort minEffort : Nat) : Rat :=
  aMin + (1 - aMin) * achievabilityRatio effort minEffort

/-- `(effort : Rat) + effortScale` is always strictly positive — true for every
`Nat`, including `effort = 0`, since the scale itself is positive. -/
theorem denom_pos (effort : Nat) : (0 : Rat) < (effort : Rat) + effortScale := by
  have h0 : (0 : Rat) ≤ (effort : Rat) := Rat.natCast_nonneg (a := effort)
  have h1 := effortScale_pos
  grind

theorem ratio_nonneg (effort minEffort : Nat) :
    0 ≤ achievabilityRatio effort minEffort := by
  unfold achievabilityRatio
  have hd := denom_pos effort
  have hn : (0 : Rat) ≤ (minEffort : Rat) + effortScale := by
    have h0 : (0 : Rat) ≤ (minEffort : Rat) := Rat.natCast_nonneg (a := minEffort)
    have h1 := effortScale_pos
    grind
  exact ratDivNonneg hn hd

theorem ratio_le_one {effort minEffort : Nat} (h : minEffort ≤ effort) :
    achievabilityRatio effort minEffort ≤ 1 := by
  unfold achievabilityRatio
  have hd := denom_pos effort
  have hne : ((effort : Rat) + effortScale) ≠ 0 := by
    intro hz; rw [hz] at hd; exact absurd hd (by decide)
  have hn : (minEffort : Rat) + effortScale ≤ (effort : Rat) + effortScale := by
    have hcast : (minEffort : Rat) ≤ (effort : Rat) := by exact_mod_cast h
    exact (Rat.add_le_add_right (a := (minEffort : Rat)) (b := (effort : Rat))
      (c := effortScale)).mpr hcast
  have hself : ((effort : Rat) + effortScale) / ((effort : Rat) + effortScale) = 1 := by
    rw [Rat.div_def, Rat.mul_inv_cancel _ hne]
  calc ((minEffort : Rat) + effortScale) / ((effort : Rat) + effortScale)
      ≤ ((effort : Rat) + effortScale) / ((effort : Rat) + effortScale) := ratDivMono hn hd
    _ = 1 := hself

/-- `1 - aMin = 1/2 ≥ 0` (the ratio coefficient is nonneg). -/
theorem oneSubAMin_nonneg : (0 : Rat) ≤ 1 - aMin := by
  have h : aMin ≤ 1 := by decide
  grind

theorem achievability_ge_floor (effort minEffort : Nat) :
    aMin ≤ achievabilityPure effort minEffort := by
  unfold achievabilityPure
  have hr := ratio_nonneg effort minEffort
  have hnn : 0 ≤ (1 - aMin) * achievabilityRatio effort minEffort :=
    Rat.mul_nonneg oneSubAMin_nonneg hr
  grind

theorem achievability_le_one {effort minEffort : Nat} (h : minEffort ≤ effort) :
    achievabilityPure effort minEffort ≤ 1 := by
  unfold achievabilityPure
  have hr := ratio_le_one h
  have hmul : (1 - aMin) * achievabilityRatio effort minEffort ≤ (1 - aMin) * 1 :=
    Rat.mul_le_mul_of_nonneg_left hr oneSubAMin_nonneg
  rw [Rat.mul_one] at hmul
  grind

theorem achievability_floor_pos : (0 : Rat) < aMin := by decide

/-- ANTITONE: more effort scores no higher — the defining property. -/
theorem achievability_antitone {e1 e2 minEffort : Nat} (h : e1 ≤ e2) :
    achievabilityPure e2 minEffort ≤ achievabilityPure e1 minEffort := by
  unfold achievabilityPure achievabilityRatio
  have hd1 := denom_pos e1
  have hd2 := denom_pos e2
  have hdcast : (e1 : Rat) + effortScale ≤ (e2 : Rat) + effortScale := by
    have hcast : (e1 : Rat) ≤ (e2 : Rat) := by exact_mod_cast h
    exact (Rat.add_le_add_right (a := (e1 : Rat)) (b := (e2 : Rat))
      (c := effortScale)).mpr hcast
  have hnum_nonneg : (0 : Rat) ≤ (minEffort : Rat) + effortScale := by
    have h0 : (0 : Rat) ≤ (minEffort : Rat) := Rat.natCast_nonneg (a := minEffort)
    have h1 := effortScale_pos
    grind
  have hmono : ((minEffort : Rat) + effortScale) / ((e2 : Rat) + effortScale)
             ≤ ((minEffort : Rat) + effortScale) / ((e1 : Rat) + effortScale) :=
    ratDivAntitone hnum_nonneg hd1 hd2 hdcast
  have hmul : (1 - aMin) * (((minEffort : Rat) + effortScale) / ((e2 : Rat) + effortScale))
            ≤ (1 - aMin) * (((minEffort : Rat) + effortScale) / ((e1 : Rat) + effortScale)) :=
    Rat.mul_le_mul_of_nonneg_left hmono oneSubAMin_nonneg
  grind

end Formal.Achievability
