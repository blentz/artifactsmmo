-- @concept: combat, cost @property: monotonicity, safety, totality
/-
A fight's learned loss risk, priced (`docs/PLAN_loss_risk.md`,
`src/artifactsmmo_cli/ai/loss_risk_core.py`).

USER 2026-10-08, "Price the loss risk": a drop or grind fight's cost includes
its learned loss rate. Expected fights per win is `1/p`; each loss is charged
its death plus recovery.

## The model

With `p = wins / samples` the expected LOSSES per win are `1/p - 1 =
(samples - wins) / wins`. The surcharge per win is that times one loss's cost
`costNum / costDen`. It is returned as an unreduced `(num, den)` pair:

    num = (samples - wins) * costNum
    den = max wins 1 * costDen

Below `minSamples` fights there is no evidence: `(0, costDen)`. `wins = 0` past
the warmup is the learned-loss veto's territory; it is charged every loss
against one win so the function stays total. Ratios are compared by
cross-multiplication, so the model never divides.
-/

namespace Formal.LossRisk

/-- The surcharge per win, as `(numerator, denominator)`. -/
def lossSurcharge (samples wins minSamples costNum costDen : Nat) : Nat × Nat :=
  if samples < minSamples then (0, costDen)
  else ((samples - wins) * costNum, max wins 1 * costDen)

/-! ## Theorems -/

/-- Below the warmup there is no evidence and no surcharge. -/
theorem cold_zero (samples wins minSamples costNum costDen : Nat)
    (h : samples < minSamples) :
    (lossSurcharge samples wins minSamples costNum costDen).1 = 0 := by
  simp [lossSurcharge, h]

/-- A fight never lost costs nothing extra. -/
theorem lossless_zero (samples wins minSamples costNum costDen : Nat)
    (h : samples ≤ wins) :
    (lossSurcharge samples wins minSamples costNum costDen).1 = 0 := by
  unfold lossSurcharge
  split <;> simp [Nat.sub_eq_zero_of_le h]

/-- The denominator is positive whenever the loss cost's is. -/
theorem den_pos (samples wins minSamples costNum costDen : Nat) (h : 0 < costDen) :
    0 < (lossSurcharge samples wins minSamples costNum costDen).2 := by
  unfold lossSurcharge
  split
  · exact h
  · exact Nat.mul_pos (by omega) h

/-- THE EXPECTATION: past the warmup with at least one win, the surcharge is
`(1/p - 1) × cost`, stated without division: `num * wins * costDen =
(samples - wins) * costNum * den`. -/
theorem expected_losses (samples wins minSamples costNum costDen : Nat)
    (hw : 0 < wins) (hs : minSamples ≤ samples) :
    lossSurcharge samples wins minSamples costNum costDen
      = ((samples - wins) * costNum, wins * costDen) := by
  have : ¬ samples < minSamples := by omega
  simp [lossSurcharge, this, Nat.max_eq_left hw]

/-- MORE WINS, NO DEARER: at the same sample count, a better record never
raises the surcharge (`num' / den' ≤ num / den`, cross-multiplied). -/
theorem antitone_wins (samples w w' minSamples costNum costDen : Nat)
    (hw : w ≤ w') :
    (lossSurcharge samples w' minSamples costNum costDen).1
        * (lossSurcharge samples w minSamples costNum costDen).2
      ≤ (lossSurcharge samples w minSamples costNum costDen).1
        * (lossSurcharge samples w' minSamples costNum costDen).2 := by
  unfold lossSurcharge
  split
  · simp
  · have hl : samples - w' ≤ samples - w := by omega
    have hm : max w 1 ≤ max w' 1 := by omega
    calc (samples - w') * costNum * (max w 1 * costDen)
        ≤ (samples - w) * costNum * (max w 1 * costDen) :=
          Nat.mul_le_mul_right _ (Nat.mul_le_mul_right _ hl)
      _ ≤ (samples - w) * costNum * (max w' 1 * costDen) :=
          Nat.mul_le_mul_left _ (Nat.mul_le_mul_right _ hm)

/-- A DEARER LOSS, A DEARER SURCHARGE: the numerator is monotone in the loss
cost at a fixed denominator. -/
theorem mono_cost (samples wins minSamples c c' costDen : Nat) (hc : c ≤ c') :
    (lossSurcharge samples wins minSamples c costDen).1
      ≤ (lossSurcharge samples wins minSamples c' costDen).1 := by
  unfold lossSurcharge
  split
  · simp
  · exact Nat.mul_le_mul_left _ hc

/-! ## Witnesses -/

-- R2D2 vs king_slime at L30 (2026-10-08): 22 fights, 14 wins; a loss costs the
-- Fight plus a full-bar Rest, (30 + 100) / 30.
example : lossSurcharge 22 14 5 130 30 = (1040, 420) := by decide
example : lossSurcharge 4 0 5 130 30 = (0, 30) := by decide
example : lossSurcharge 10 10 5 130 30 = (0, 300) := by decide

end Formal.LossRisk
