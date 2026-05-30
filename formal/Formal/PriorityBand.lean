/-
Formal model of `clamp_into_band` from
`src/artifactsmmo_cli/ai/priority_band.py`.

The Python helper clamps a learned priority `bonus` into a discretionary goal's
`[floor, ceiling]` band:

    clamp_into_band(floor, ceiling, bonus) = min(ceiling, max(floor, floor + bonus))

The live caller is `GrindCharacterXPGoal.value`, which passes the band
`[PRIORITY_FLOOR, PRIORITY_CEILING] = [30, 45]` and a fractional bonus
`char_xp * SCALAR_TO_PRIORITY_GAIN`. `char_xp` is the average of integer
per-cycle XP deltas (a rational), so the bonus is FRACTIONAL in general.

EXACT-RATIONAL MODEL (over `Rat`, Lean core — no mathlib). The Python core has
been switched to operate over `fractions.Fraction` (the call site lifts the
inputs to `Fraction` before invoking `clamp_into_band`). `min`/`max`/`+` on
`Fraction` is exact, so the Python value is BIT-EQUAL to this `Rat` model for
every input. The previous Int abstraction / "order-faithful" caveat is closed.

The safety theorem below shows the clamped result can NEVER reach the survival
floor (70), regardless of the bonus's sign or magnitude — a learned bonus can
never reorder a discretionary goal above a survival goal.

Lean core only — no mathlib. Rational arithmetic via `Rat.le_min`,
`Rat.le_max_left`, `Rat.min_le_left`, `Rat.le_trans`.
-/

namespace Formal.PriorityBand

/-- `clamp_into_band`: `floor + bonus` clamped into `[floor, ceiling]`. -/
def clampIntoBand (floor ceiling bonus : Rat) : Rat :=
  min ceiling (max floor (floor + bonus))

/-! ### Theorems (the band-safety contracts). -/

/-- The clamped result never drops below `floor` (when `floor ≤ ceiling`). -/
theorem clamp_lower_bound (floor ceiling bonus : Rat) (h : floor ≤ ceiling) :
    floor ≤ clampIntoBand floor ceiling bonus := by
  unfold clampIntoBand
  grind

/-- The clamped result never rises above `ceiling`. -/
theorem clamp_upper_bound (floor ceiling bonus : Rat) (_h : floor ≤ ceiling) :
    clampIntoBand floor ceiling bonus ≤ ceiling := by
  unfold clampIntoBand
  grind

/-- THE safety theorem: when the band ceiling sits strictly below the survival
floor, the clamped discretionary priority is strictly below the survival floor —
for ANY bonus (negative, zero, or arbitrarily large). A learned bonus can never
reorder a discretionary goal above a survival goal. -/
theorem clamp_below_survival (floor ceiling bonus survival : Rat)
    (h : floor ≤ ceiling) (hc : ceiling < survival) :
    clampIntoBand floor ceiling bonus < survival := by
  have hupper := clamp_upper_bound floor ceiling bonus h
  grind

end Formal.PriorityBand
