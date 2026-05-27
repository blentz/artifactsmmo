/-
Formal model of `clamp_into_band` from
`src/artifactsmmo_cli/ai/priority_band.py`.

The Python helper clamps a learned priority `bonus` into a discretionary goal's
`[floor, ceiling]` band:

    clamp_into_band(floor, ceiling, bonus) = min(ceiling, max(floor, floor + bonus))

The live caller is `GrindCharacterXPGoal.value`, which passes the band
`[PRIORITY_FLOOR, PRIORITY_CEILING] = [30, 45]`. Every discretionary band's
ceiling sits strictly below the survival floor (70); the key safety theorem
below shows the clamped result can therefore NEVER reach the survival floor,
regardless of the bonus's sign or magnitude — a learned bonus can never reorder
a discretionary goal above a survival goal.

We model over `Int`, while the live Python uses `float` (floor/ceiling are 30.0/
45.0 and the bonus `char_xp * 5.0` is fractional and may be negative). This is an
order-faithful abstraction: `clamp_into_band` is built solely from `min`/`max`/`+`,
which preserve the band invariant `floor ≤ result ≤ ceiling` identically over the
ordered field of finite floats and over `Int`, so the proved bounds carry to the
float implementation. The differential test exercises the `Int` model directly.
Lean core only — no mathlib. Integer arithmetic via `omega`.
-/

namespace Formal.PriorityBand

/-- `clamp_into_band`: `floor + bonus` clamped into `[floor, ceiling]`. -/
def clampIntoBand (floor ceiling bonus : Int) : Int :=
  min ceiling (max floor (floor + bonus))

/-! ### Theorems (the band-safety contracts). -/

/-- The clamped result never drops below `floor` (when `floor ≤ ceiling`). -/
theorem clamp_lower_bound (floor ceiling bonus : Int) (h : floor ≤ ceiling) :
    floor ≤ clampIntoBand floor ceiling bonus := by
  unfold clampIntoBand
  have hle : floor ≤ max floor (floor + bonus) := Int.le_max_left _ _
  exact Int.le_min.mpr ⟨h, hle⟩

/-- The clamped result never rises above `ceiling`. -/
theorem clamp_upper_bound (floor ceiling bonus : Int) (_h : floor ≤ ceiling) :
    clampIntoBand floor ceiling bonus ≤ ceiling := by
  unfold clampIntoBand
  exact Int.min_le_left _ _

/-- THE safety theorem: when the band ceiling sits strictly below the survival
floor, the clamped discretionary priority is strictly below the survival floor —
for ANY bonus (negative, zero, or arbitrarily large). A learned bonus can never
reorder a discretionary goal above a survival goal. -/
theorem clamp_below_survival (floor ceiling bonus survival : Int)
    (h : floor ≤ ceiling) (hc : ceiling < survival) :
    clampIntoBand floor ceiling bonus < survival := by
  have hupper := clamp_upper_bound floor ceiling bonus h
  omega

end Formal.PriorityBand
