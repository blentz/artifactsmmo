namespace Formal.PotionBaseline

/-- Level→potion-baseline curve: flat `lowQty` through `lowLevel`, full `highQty`
at/above `highLevel`, floor-linear ramp between. Float-free; mirrors the Python
`potion_baseline_pure`. Nat `/` is floor division, matching Python `//` on the
non-negative ramp operands (`highLevel > lowLevel` on that branch). -/
def potionBaseline (level lowLevel lowQty highLevel highQty : Nat) : Nat :=
  if level ≤ lowLevel then lowQty
  else if highLevel ≤ level then highQty
  else lowQty + (highQty - lowQty) * (level - lowLevel) / (highLevel - lowLevel)

theorem baseline_flat_low (l ll lq hl hq : Nat) (h : l ≤ ll) :
    potionBaseline l ll lq hl hq = lq := by unfold potionBaseline; simp [h]

theorem baseline_full_high (l ll lq hl hq : Nat) (h : hl ≤ l) (h2 : ¬ l ≤ ll) :
    potionBaseline l ll lq hl hq = hq := by unfold potionBaseline; simp [h, h2]

/-- A floored ramp term never exceeds its full span: when the dividend factor
`x` does not exceed the (positive) denominator `d`, `a * x / d ≤ a`. -/
theorem ramp_le_span (a x d : Nat) (hxd : x ≤ d) : a * x / d ≤ a := by
  rcases Nat.eq_zero_or_pos d with hd | hd
  · subst hd; simp
  · calc a * x / d ≤ a * d / d := Nat.div_le_div_right (Nat.mul_le_mul_left a hxd)
      _ = a := by rw [Nat.mul_div_cancel _ hd]

/-- Monotonicity: stepping level up by one never lowers the baseline. The flat
and full branches are constant; on the ramp the numerator
`(highQty - lowQty) * (level - lowLevel)` is non-decreasing in `level` over a
fixed denominator, and Nat division is monotone in its dividend. -/
theorem baseline_monotone_step (l ll lq hl hq : Nat) (hlt : lq ≤ hq) :
    potionBaseline l ll lq hl hq ≤ potionBaseline (l + 1) ll lq hl hq := by
  unfold potionBaseline
  by_cases hb1 : l ≤ ll
  · by_cases hc1 : l + 1 ≤ ll
    · simp [hb1, hc1]
    · -- l ≤ ll but ¬(l+1 ≤ ll): LHS is lq, RHS enters ramp-or-full from lq base
      simp only [hb1, hc1, if_true, if_false]
      by_cases hd1 : hl ≤ l + 1
      · simp only [hd1, if_true]; exact hlt
      · simp only [hd1, if_false]
        exact Nat.le_add_right lq _
  · by_cases hb2 : hl ≤ l
    · -- LHS is full (hq); RHS is also full
      have hb1' : ¬ l + 1 ≤ ll := fun h => hb1 (Nat.le_trans (Nat.le_succ l) h)
      have hb2' : hl ≤ l + 1 := Nat.le_trans hb2 (Nat.le_succ l)
      simp [hb1, hb2, hb1', hb2']
    · -- LHS is ramp
      have hb1' : ¬ l + 1 ≤ ll := fun h => hb1 (Nat.le_trans (Nat.le_succ l) h)
      have hllt : ll < l := Nat.lt_of_not_le hb1
      have hlhl : l < hl := Nat.lt_of_not_le hb2
      have hxd : l - ll ≤ hl - ll := Nat.sub_le_sub_right (Nat.le_of_lt hlhl) ll
      simp only [hb1, hb2, if_false]
      by_cases hb3 : hl ≤ l + 1
      · -- RHS is full (hq); ramp value ≤ hq
        simp only [hb1', hb3, if_false, if_true]
        have hramp : (hq - lq) * (l - ll) / (hl - ll) ≤ hq - lq :=
          ramp_le_span _ _ _ hxd
        calc lq + (hq - lq) * (l - ll) / (hl - ll)
            ≤ lq + (hq - lq) := Nat.add_le_add_left hramp lq
          _ = hq := by omega
      · -- both ramp; division monotone in dividend
        simp only [hb1', hb3, if_false]
        apply Nat.add_le_add_left
        apply Nat.div_le_div_right
        apply Nat.mul_le_mul_left
        exact Nat.sub_le_sub_right (Nat.le_succ l) ll

end Formal.PotionBaseline
