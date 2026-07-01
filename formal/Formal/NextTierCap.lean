-- @concept: crafting, planner @property: safety
/- Hand model of next_tier_cap_pure (skill-grind dampener). Skill keys are Int
(String bridged later, EquipmentScoring precedent). Mirrors the extracted
List.foldl. Core only. Mirrors SkillTargetCurve clamp/fold-invariant proofs.
No Mathlib import: safety modules stay core-only (gate cross-namespace leak
check forbids `import Mathlib`); proof uses only core/Std tactics, as in
SkillTargetCurve.lean. -/
namespace Formal.NextTierCap

structure Item where
  craftSkill : Int
  craftLevel : Int
  itemLevel : Int
  gearRelevant : Bool
  deriving Repr

def nextTierFloor (charLevel : Int) : Int := ((charLevel / 10) + 1) * 10

def rawCap (skill charLevel : Int) (items : List Item) : Int :=
  let floor := nextTierFloor charLevel
  items.foldl (fun best it =>
    if it.gearRelevant && it.craftSkill == skill
        && floor ≤ it.itemLevel && it.itemLevel ≤ floor + 9
        && it.craftLevel > best
      then it.craftLevel else best) 0

def nextTierCap (skill charLevel maxSkill : Int) (items : List Item) : Int :=
  let best := rawCap skill charLevel items
  if best ≤ 0 then 0 else if best > maxSkill then maxSkill else best

def nextTierDampened (currentSkill cap : Int) : Bool :=
  decide (cap > 0 ∧ currentSkill ≥ cap)

/-- rawCap ≥ 0: the fold is seeded at 0 and each step either keeps `best` or
replaces it with a strictly-greater craftLevel, so a nonneg seed stays nonneg.
Mirrors SkillTargetCurve's `rawBest` fold-invariant approach. -/
theorem rawCap_nonneg (skill charLevel : Int) (items : List Item) :
    0 ≤ rawCap skill charLevel items := by
  simp only [rawCap]
  generalize nextTierFloor charLevel = floor
  suffices H : ∀ (a : Int), 0 ≤ a →
      0 ≤ items.foldl (fun best it =>
        if it.gearRelevant && it.craftSkill == skill
            && floor ≤ it.itemLevel && it.itemLevel ≤ floor + 9
            && it.craftLevel > best
          then it.craftLevel else best) a by
    exact H 0 (Int.le_refl 0)
  intro a ha
  induction items generalizing a with
  | nil => simpa using ha
  | cons it rest ih =>
    simp only [List.foldl_cons]
    apply ih
    by_cases hc : (it.gearRelevant && it.craftSkill == skill
        && floor ≤ it.itemLevel && it.itemLevel ≤ floor + 9
        && it.craftLevel > a) = true
    · rw [if_pos hc]
      revert hc
      simp only [Bool.and_eq_true, decide_eq_true_eq]
      rintro ⟨_, hlt⟩
      omega
    · rw [if_neg hc]
      exact ha

/-- target ≤ maxSkill -/
theorem cap_le_max (skill charLevel maxSkill : Int) (items : List Item)
    (hmax : 0 ≤ maxSkill) : nextTierCap skill charLevel maxSkill items ≤ maxSkill := by
  simp only [nextTierCap]; split
  · exact hmax
  · split <;> omega

/-- target ≥ 0 (mirror SkillTargetCurve.curve_nonneg; discharged via rawCap_nonneg). -/
theorem cap_nonneg (skill charLevel maxSkill : Int) (items : List Item)
    (hmax : 0 ≤ maxSkill) : 0 ≤ nextTierCap skill charLevel maxSkill items := by
  have hraw := rawCap_nonneg skill charLevel items
  simp only [nextTierCap]; split
  · exact Int.le_refl 0
  · split <;> omega

/-- Empty band ⇒ never dampened (scopes feature to gear-crafting skills). -/
theorem empty_band_not_dampened (currentSkill : Int) :
    nextTierDampened currentSkill 0 = false := by
  simp [nextTierDampened]

/-- Safety decode: suppress only when the skill genuinely covers the whole next tier. -/
theorem dampened_safety (currentSkill cap : Int)
    (h : nextTierDampened currentSkill cap = true) : cap > 0 ∧ currentSkill ≥ cap := by
  simpa [nextTierDampened] using h

end Formal.NextTierCap
