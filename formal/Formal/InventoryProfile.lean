-- @concept: bank, items, crafting @property: safety
/-
Formal model of the per-goal inventory-profile overstock core
(`overstock_excess` in `src/artifactsmmo_cli/ai/inventory_caps.py`) — the
SPACE-DRIVEN, profile-preserving overstock decision introduced by spec
2026-06-07 to kill the GatherMaterials(fishing_net) withdraw↔deposit livelock.

The Python `overstock_excess(held, profile_target, useful_floor, used, cap,
watermark_num, watermark_den)` decides how many of an item are overstock:

    if cap <= 0 or used * watermark_den < cap * watermark_num:
        return 0                                  # no space pressure
    floor = max(profile_target, useful_floor)
    return held - floor if held > floor else 0

We model it as `overstockExcess` over `Int` (the production values are all
non-negative integers; we prove over all `Int` and the differential feeds the
non-negative reachable domain). The contracts pin the THREE design guarantees:

1. PROFILE-PROTECTION: an item at or below its profile target is NEVER
   overstock, regardless of space pressure
   (`profile_protection` / `overstock_zero_of_le_profile`). This MIRRORS the
   proven bank keep-set protection (`BankSelection.task_material_not_deposited`)
   for the discard side.
2. SPACE-DRIVEN: below the high watermark (real free slots) NOTHING is
   overstock (`no_overstock_below_watermark`), so the per-item useful floor is
   no longer a space-blind dump trigger.
3. MONOTONE ACCUMULATION: with a profile item never shed below its target, the
   held count of a profile item is NON-DECREASING under a deposit/discard step
   that only removes `overstockExcess` — no withdraw↔deposit oscillation
   (`monotone_accumulation` / `held_after_shed_ge_target`).

Lean core only — no mathlib. Integer arithmetic via `omega`.
-/

namespace Formal.InventoryProfile

/-- Pressure predicate: the bag is under genuine space pressure when
`used / cap >= watermarkNum / watermarkDen`, compared by exact integer
cross-multiplication (`used * watermarkDen >= cap * watermarkNum`) — and
`cap > 0`. Mirrors the Python `cap > 0 and used * watermark_den >=
cap * watermark_num`. -/
def underPressure (used cap watermarkNum watermarkDen : Int) : Bool :=
  decide (cap > 0 ∧ used * watermarkDen ≥ cap * watermarkNum)

/-- The protected floor: the larger of the active goal's soft profile target
and the per-item useful floor. Defined by an explicit `if` (== `max`, but
kept core-Lean / omega-friendly so this SAFETY module needs no Mathlib).
Mirrors the Python `profile_target if profile_target > useful_floor else
useful_floor`. -/
def protectedFloor (profileTarget usefulFloor : Int) : Int :=
  if profileTarget > usefulFloor then profileTarget else usefulFloor

/-- `protectedFloor` is at least the profile target (the protected lower
bound the active goal accumulates toward). -/
theorem protectedFloor_ge_profile (profileTarget usefulFloor : Int) :
    protectedFloor profileTarget usefulFloor ≥ profileTarget := by
  unfold protectedFloor; split <;> omega

/-- `protectedFloor` is at least the useful floor. -/
theorem protectedFloor_ge_useful (profileTarget usefulFloor : Int) :
    protectedFloor profileTarget usefulFloor ≥ usefulFloor := by
  unfold protectedFloor; split <;> omega

/-- `overstock_excess`: the space-driven overstock amount. 0 unless the bag is
under pressure AND `held` exceeds the protected floor; then `held - floor`. -/
def overstockExcess (held profileTarget usefulFloor used cap
    watermarkNum watermarkDen : Int) : Int :=
  if underPressure used cap watermarkNum watermarkDen then
    (if held > protectedFloor profileTarget usefulFloor
     then held - protectedFloor profileTarget usefulFloor else 0)
  else 0

/-! ### Exact-shape theorem (pins the formula). -/

/-- `overstock_exact`: spells out the full branch structure so a differential /
mutation cannot weaken the formula without tripping the type. -/
theorem overstock_exact (held profileTarget usefulFloor used cap
    watermarkNum watermarkDen : Int) :
    overstockExcess held profileTarget usefulFloor used cap watermarkNum watermarkDen
      = (if underPressure used cap watermarkNum watermarkDen then
           (if held > protectedFloor profileTarget usefulFloor
            then held - protectedFloor profileTarget usefulFloor else 0)
         else 0) := by
  unfold overstockExcess
  rfl

/-! ### (1) SPACE-DRIVEN: nothing is overstock below the watermark. -/

/-- When NOT under pressure (free slots / low fraction / zero cap), the
overstock is exactly 0 — the per-item useful floor is not a dump trigger. -/
theorem no_overstock_below_watermark
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int)
    (h : underPressure used cap watermarkNum watermarkDen = false) :
    overstockExcess held profileTarget usefulFloor used cap watermarkNum watermarkDen = 0 := by
  unfold overstockExcess
  simp [h]

/-- Concrete witness of the space-driven property: with `used/cap = 16/20`
(80% < 85% watermark = 17/20) and held 100 over floor 0, the excess is still 0.
Pins that free slots really do suppress overstock (non-vacuous). -/
theorem space_driven_witness :
    overstockExcess 100 0 0 16 20 17 20 = 0 := by decide

/-! ### (2) PROFILE-PROTECTION: at/below the profile target ⇒ never overstock. -/

/-- `held ≤ profileTarget ⇒ overstock = 0`, for ANY pressure. The active
goal's materials accumulating toward their target are never shed. Mirrors
`BankSelection.task_material_not_deposited` on the discard side. -/
theorem profile_protection
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int)
    (h : held ≤ profileTarget) :
    overstockExcess held profileTarget usefulFloor used cap watermarkNum watermarkDen = 0 := by
  unfold overstockExcess
  by_cases hp : underPressure used cap watermarkNum watermarkDen
  · simp only [hp, if_true]
    have hfloor := protectedFloor_ge_profile profileTarget usefulFloor
    simp only [if_neg (by omega : ¬ held > protectedFloor profileTarget usefulFloor)]
  · simp [hp]

/-- Phrased as a non-strict inequality on the protected floor: held at or below
the floor (which is ≥ profileTarget) is never overstock. -/
theorem overstock_zero_of_le_floor
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int)
    (h : held ≤ protectedFloor profileTarget usefulFloor) :
    overstockExcess held profileTarget usefulFloor used cap watermarkNum watermarkDen = 0 := by
  unfold overstockExcess
  by_cases hp : underPressure used cap watermarkNum watermarkDen
  · simp only [hp, if_true]
    simp only [if_neg (by omega : ¬ held > protectedFloor profileTarget usefulFloor)]
  · simp [hp]

/-- Profile-protection witness: even at full pressure (used = cap = 20, ≥
17/20) and a tiny useful floor 0, held 10 ≤ profileTarget 10 ⇒ 0 overstock.
Non-vacuous: the SAME inputs with profileTarget 0 would be overstock 10. -/
theorem profile_protection_witness :
    overstockExcess 10 10 0 20 20 17 20 = 0
      ∧ overstockExcess 10 0 0 20 20 17 20 = 10 := by
  refine ⟨by decide, by decide⟩

/-! ### (3) MONOTONE ACCUMULATION (the real win): no oscillation. -/

/-- The held count AFTER a deposit/discard step that removes exactly the
overstock. -/
def heldAfterShed (held profileTarget usefulFloor used cap
    watermarkNum watermarkDen : Int) : Int :=
  held - overstockExcess held profileTarget usefulFloor used cap watermarkNum watermarkDen

/-- MONOTONE: a profile item never drops below its target under a shed step.
If `held ≥ profileTarget` before the step, then `heldAfterShed ≥ profileTarget`
after — the accumulation toward the target is monotone, so a withdrawn profile
material is never banked/deleted back below target (no withdraw↔deposit
oscillation). -/
theorem monotone_accumulation
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int)
    (h : held ≥ profileTarget) :
    heldAfterShed held profileTarget usefulFloor used cap watermarkNum watermarkDen
      ≥ profileTarget := by
  unfold heldAfterShed overstockExcess
  have hge := protectedFloor_ge_profile profileTarget usefulFloor
  split
  · split <;> omega
  · omega

/-- Sheds at most down to the protected floor (the floor is preserved): the
step never removes a unit below `max(profileTarget, usefulFloor)`. -/
theorem held_after_shed_ge_floor
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int)
    (h : held ≥ protectedFloor profileTarget usefulFloor) :
    heldAfterShed held profileTarget usefulFloor used cap watermarkNum watermarkDen
      ≥ protectedFloor profileTarget usefulFloor := by
  unfold heldAfterShed overstockExcess
  split
  · split <;> omega
  · omega

/-- A shed step is IDEMPOTENT on the held floor: after shedding once, a second
shed under the same pressure removes nothing more (held is already at the
floor). Pins that the discard cycle converges — it can't ping-pong. -/
theorem shed_idempotent
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int) :
    overstockExcess
      (heldAfterShed held profileTarget usefulFloor used cap watermarkNum watermarkDen)
      profileTarget usefulFloor used cap watermarkNum watermarkDen = 0 := by
  unfold heldAfterShed overstockExcess
  split
  · split
    · split <;> omega
    · split <;> omega
  · rfl

/-! ### Positivity (the excess, when reported, is a real positive amount). -/

/-- Overstock is strictly positive exactly when under pressure AND over floor. -/
theorem overstock_pos_iff
    (held profileTarget usefulFloor used cap watermarkNum watermarkDen : Int) :
    overstockExcess held profileTarget usefulFloor used cap watermarkNum watermarkDen > 0
      ↔ (underPressure used cap watermarkNum watermarkDen = true
          ∧ held > protectedFloor profileTarget usefulFloor) := by
  unfold overstockExcess
  by_cases hp : underPressure used cap watermarkNum watermarkDen = true
  · rw [hp]
    simp only [if_true, true_and]
    by_cases hover : held > protectedFloor profileTarget usefulFloor
    · simp only [if_pos hover]; omega
    · simp only [if_neg hover]; omega
  · simp only [Bool.not_eq_true] at hp
    rw [hp]
    simp only [Bool.false_eq_true, if_false, false_and, iff_false]
    omega

end Formal.InventoryProfile
