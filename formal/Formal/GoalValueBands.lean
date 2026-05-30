/-
Phase-17 headline theorems: PursueTaskGoal.value and GatherMaterialsGoal.value
are both routed through `Formal.PriorityBand.clampIntoBand` with band ceilings
strictly below the survival floor (70), so each goal's value is < 70 for ANY
learned scalar bonus (positive, zero, negative, or arbitrarily large).

This is the formal statement of the Phase-17 design contract:

    Production constants  →     band ceiling  <  survival floor
    PursueTask     [35, 50]     50            <  70
    GatherMaterials [1, 50]      50            <  70

So both goals' clamped value is strictly below 70 (the survival floor) by
`Formal.PriorityBand.clamp_below_survival`. A discretionary goal's learned-yield
priority can NEVER reach the survival floor.

We also pin a `_mono_in_bonus` corollary: holding floor/ceiling fixed, the
clamped result is monotone-nondecreasing in `bonus` — so a higher observed
scalar_yield never demotes the goal.

Lean core only — no mathlib. Rational arithmetic via the proved
`Formal.PriorityBand.clamp_below_survival` and `clamp_upper_bound`.
-/

import Formal.PriorityBand

namespace Formal.GoalValueBands

open Formal.PriorityBand

/-! ### Production band constants (mirror Python). -/

/-- PursueTaskGoal floor: 35 (matches retired FarmItems(35) cold-start). -/
def pursueTaskFloor : Rat := 35

/-- PursueTaskGoal ceiling: 50 (strictly below survival floor 70). -/
def pursueTaskCeiling : Rat := 50

/-- GatherMaterialsGoal floor: 1 (matches `max(1.0, ...)` base lower bound). -/
def gatherMaterialsFloor : Rat := 1

/-- GatherMaterialsGoal ceiling: 50 (strictly below survival floor 70). -/
def gatherMaterialsCeiling : Rat := 50

/-- The Phase-1 survival floor (70). Pinned here for the survival-safety
contracts; matches the live constant in the strategy arbiter. -/
def survivalFloor : Rat := 70

/-! ### Production goal value functions (modeled). -/

/-- Modeled `PursueTaskGoal.value` warm-path: clamp the bonus into the
discretionary band `[35, 50]`. Cold path (history None or zero samples) is
modeled by `bonus = 0`, which returns `min 50 (max 35 (35 + 0)) = 35` —
exactly the production `PRIORITY_FLOOR`. -/
def pursueTaskValue (bonus : Rat) : Rat :=
  clampIntoBand pursueTaskFloor pursueTaskCeiling bonus

/-- Modeled `GatherMaterialsGoal.value` warm-path: clamp the (existing-ramp +
scalar-derived) bonus into `[1, 50]`. -/
def gatherMaterialsValue (bonus : Rat) : Rat :=
  clampIntoBand gatherMaterialsFloor gatherMaterialsCeiling bonus

/-! ### Band sanity (constants well-formed). -/

theorem pursueTask_floor_le_ceiling : pursueTaskFloor ≤ pursueTaskCeiling := by
  unfold pursueTaskFloor pursueTaskCeiling; decide

theorem gatherMaterials_floor_le_ceiling :
    gatherMaterialsFloor ≤ gatherMaterialsCeiling := by
  unfold gatherMaterialsFloor gatherMaterialsCeiling; decide

theorem pursueTask_ceiling_lt_survival : pursueTaskCeiling < survivalFloor := by
  unfold pursueTaskCeiling survivalFloor; decide

theorem gatherMaterials_ceiling_lt_survival :
    gatherMaterialsCeiling < survivalFloor := by
  unfold gatherMaterialsCeiling survivalFloor; decide

/-! ### Headline survival-floor safety. -/

/-- **THE headline contract.** `PursueTaskGoal.value` is strictly below the
survival floor for ANY learned bonus. -/
theorem pursueTask_value_below_survival_floor (bonus : Rat) :
    pursueTaskValue bonus < survivalFloor := by
  unfold pursueTaskValue
  exact clamp_below_survival
    pursueTaskFloor pursueTaskCeiling bonus survivalFloor
    pursueTask_floor_le_ceiling
    pursueTask_ceiling_lt_survival

/-- **THE headline contract.** `GatherMaterialsGoal.value` is strictly below
the survival floor for ANY learned bonus. -/
theorem gatherMaterials_value_below_survival_floor (bonus : Rat) :
    gatherMaterialsValue bonus < survivalFloor := by
  unfold gatherMaterialsValue
  exact clamp_below_survival
    gatherMaterialsFloor gatherMaterialsCeiling bonus survivalFloor
    gatherMaterials_floor_le_ceiling
    gatherMaterials_ceiling_lt_survival

/-! ### Band-inclusion corollaries (both bounds). -/

theorem pursueTask_value_in_band (bonus : Rat) :
    pursueTaskFloor ≤ pursueTaskValue bonus ∧
    pursueTaskValue bonus ≤ pursueTaskCeiling := by
  refine ⟨?lower, ?upper⟩
  · exact clamp_lower_bound _ _ _ pursueTask_floor_le_ceiling
  · exact clamp_upper_bound _ _ _ pursueTask_floor_le_ceiling

theorem gatherMaterials_value_in_band (bonus : Rat) :
    gatherMaterialsFloor ≤ gatherMaterialsValue bonus ∧
    gatherMaterialsValue bonus ≤ gatherMaterialsCeiling := by
  refine ⟨?lower, ?upper⟩
  · exact clamp_lower_bound _ _ _ gatherMaterials_floor_le_ceiling
  · exact clamp_upper_bound _ _ _ gatherMaterials_floor_le_ceiling

/-! ### Monotonicity in bonus.

Higher observed scalar_yield ⇒ value no less. Locks the "yield as priority
signal" contract: ranking is monotone in the learned signal. -/

theorem clampIntoBand_mono_bonus (floor ceiling b₁ b₂ : Rat) (h : b₁ ≤ b₂) :
    clampIntoBand floor ceiling b₁ ≤ clampIntoBand floor ceiling b₂ := by
  unfold clampIntoBand
  -- min ceiling (max floor (floor + b₁)) ≤ min ceiling (max floor (floor + b₂))
  -- follows from monotonicity of (· + floor), max, and min in their right arg.
  grind

theorem pursueTask_value_monotone_in_bonus (b₁ b₂ : Rat) (h : b₁ ≤ b₂) :
    pursueTaskValue b₁ ≤ pursueTaskValue b₂ := by
  unfold pursueTaskValue
  exact clampIntoBand_mono_bonus _ _ _ _ h

theorem gatherMaterials_value_monotone_in_bonus (b₁ b₂ : Rat) (h : b₁ ≤ b₂) :
    gatherMaterialsValue b₁ ≤ gatherMaterialsValue b₂ := by
  unfold gatherMaterialsValue
  exact clampIntoBand_mono_bonus _ _ _ _ h

/-! ### Cold-path identities (no-history ⇒ exactly the floor constant).

These pin that a cold goal (history=None or sample_count=0) reproduces the
pre-Phase-17 priority bit-exactly. The Python warm path passes `bonus = 0`
in the cold case (`yield_bonus_for_goal` returns `Fraction(0)`), so the
clamped value equals `floor`. -/

theorem pursueTask_cold_eq_floor :
    pursueTaskValue 0 = pursueTaskFloor := by
  unfold pursueTaskValue clampIntoBand pursueTaskFloor pursueTaskCeiling
  grind

theorem gatherMaterials_cold_eq_floor :
    gatherMaterialsValue 0 = gatherMaterialsFloor := by
  unfold gatherMaterialsValue clampIntoBand gatherMaterialsFloor gatherMaterialsCeiling
  grind

end Formal.GoalValueBands
