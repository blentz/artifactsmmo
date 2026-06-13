import Formal.SkillTargetCurve
import Formal.Extracted.SkillTargetCurve

/-!
# Extracted bridges, part 8: the recipe-aware skill curve.

`tiers/skill_target_curve.py` → `Extracted.SkillTargetCurve.skill_curve_target_pure`
is String-keyed on the craft skill; the hand model
`Formal.SkillTargetCurve.skillCurveTarget` keys it by `Int`. The bridge is
UNIVERSAL over an arbitrary INJECTIVE skill embedding `enc : Int → String`
(the CombatPicker / EquipmentScoring code-embedding precedent): the extracted
target over the `enc`-encoded items equals the hand target over the original
`Item`s, for EVERY input. Only the `craftSkill` field is re-keyed; all other
fields pass through unchanged.

Transferred hand contracts (restated on the extracted def): `curve_le_max`
(THE clamp ceiling) and `curve_monotone_in_char_level` (raising char level
never lowers the target). Both carry the `0 ≤ maxSkill` hypothesis the hand
theorems require (false otherwise — a negative clamp ceiling inverts order).

No sorry/admit, no new axioms; core-only (safety-module convention).
-/

namespace Extracted.Bridges8

/-- Encode a hand `Item` (Int skill key) into the extracted String-keyed
`SkillItem`, re-keying only `craftSkill` through `enc`. -/
def encItem (enc : Int → String) (it : Formal.SkillTargetCurve.Item) :
    Extracted.SkillTargetCurve.SkillItem :=
  { craft_skill := enc it.craftSkill, craft_level := it.craftLevel,
    item_level := it.itemLevel, gear_relevant := it.gearRelevant }

/-- BRIDGE (universal over injective skill embeddings): the extracted
`skill_curve_target_pure` over the encoded items equals the hand
`skillCurveTarget`, for EVERY input. Both are `clamp (foldl step 0)`; the
foldls agree pointwise (the only difference, `decide (enc · = enc skill)` vs
`decide (· = skill)`, is settled by injectivity) and the clamp is identical. -/
theorem skill_curve_target_bridge (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill charLevel lookahead maxSkill : Int)
    (items : List Formal.SkillTargetCurve.Item) :
    Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) charLevel (items.map (encItem enc)) lookahead maxSkill
      = Formal.SkillTargetCurve.skillCurveTarget skill charLevel lookahead maxSkill items := by
  -- The extracted step (over encoded items) and the hand step compute the same
  -- running best, because the only differing test, `enc · = enc skill` vs
  -- `· = skill`, is settled by injectivity.
  have hstep : ∀ (best : Int) (it : Formal.SkillTargetCurve.Item),
      (if (encItem enc it).gear_relevant && decide ((encItem enc it).craft_skill = enc skill)
          && decide ((encItem enc it).item_level ≤ charLevel + lookahead)
          && decide ((encItem enc it).craft_level > best)
        then (encItem enc it).craft_level else best)
      = (if it.gearRelevant && decide (it.craftSkill = skill)
          && decide (it.itemLevel ≤ charLevel + lookahead)
          && decide (it.craftLevel > best)
        then it.craftLevel else best) := by
    intro best it
    simp only [encItem]
    by_cases hc : it.craftSkill = skill
    · simp [hc]
    · have hne : enc it.craftSkill ≠ enc skill := fun hcontra => hc (hinj _ _ hcontra)
      simp [hc, hne]
  -- Lift the step equality to the whole foldl by induction on the item list.
  -- Stated over the *encoded* list directly, matching the extracted def before
  -- any `foldl_map` rewriting.
  have hfold : ∀ (init : Int),
      List.foldl (fun best (it : Extracted.SkillTargetCurve.SkillItem) =>
        let best :=
          (if (it.gear_relevant && decide (it.craft_skill = enc skill)
              && decide (it.item_level ≤ charLevel + lookahead)
              && decide (it.craft_level > best)) then it.craft_level else best)
        best) init (items.map (encItem enc))
      = List.foldl (fun best it =>
        if it.gearRelevant && decide (it.craftSkill = skill)
            && decide (it.itemLevel ≤ charLevel + lookahead)
            && decide (it.craftLevel > best)
          then it.craftLevel else best) init items := by
    induction items with
    | nil => intro init; rfl
    | cons it rest ih =>
      intro init
      simp only [List.map_cons, List.foldl_cons]
      rw [hstep init it, ih]
  -- The clamp is the same total function on both sides, written `if (decide P)`
  -- (Bool form, extracted def) vs `if P` (Prop form, hand def); they agree on
  -- every value by a single case split.
  have hclamp : ∀ v : Int,
      (if (decide (v ≤ 0)) then 0
       else if (decide (v > maxSkill)) then maxSkill else v)
      = (if v ≤ 0 then 0 else if v > maxSkill then maxSkill else v) := by
    intro v
    by_cases h1 : v ≤ 0
    · simp [h1]
    · by_cases h2 : v > maxSkill <;> simp [h1, h2]
  simp only [Extracted.SkillTargetCurve.skill_curve_target_pure]
  rw [hfold 0]
  -- LHS is now the extracted clamp over the hand foldl; `hclamp` rewrites it to
  -- the hand clamp, which is `skillCurveTarget` definitionally.
  exact hclamp _

/-- TRANSFERRED (THE clamp ceiling, `curve_le_max`): the extracted target is
bounded by `maxSkill` (a game level, hence `0 ≤ maxSkill`). -/
theorem skill_curve_target_le_max_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill charLevel lookahead maxSkill : Int)
    (items : List Formal.SkillTargetCurve.Item) (hmax : 0 ≤ maxSkill) :
    Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) charLevel (items.map (encItem enc)) lookahead maxSkill ≤ maxSkill := by
  rw [skill_curve_target_bridge enc hinj]
  exact Formal.SkillTargetCurve.curve_le_max skill charLevel lookahead maxSkill items hmax

/-- TRANSFERRED (`curve_monotone_in_char_level`): raising char level never
lowers the extracted target (with `0 ≤ maxSkill`, else a negative clamp
ceiling inverts the order). -/
theorem skill_curve_target_mono_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill l1 l2 lookahead maxSkill : Int)
    (items : List Formal.SkillTargetCurve.Item) (h : l1 ≤ l2) (hmax : 0 ≤ maxSkill) :
    Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) l1 (items.map (encItem enc)) lookahead maxSkill
      ≤ Extracted.SkillTargetCurve.skill_curve_target_pure
        (enc skill) l2 (items.map (encItem enc)) lookahead maxSkill := by
  rw [skill_curve_target_bridge enc hinj, skill_curve_target_bridge enc hinj]
  exact Formal.SkillTargetCurve.curve_monotone_in_char_level skill l1 l2 lookahead maxSkill items h hmax

end Extracted.Bridges8
