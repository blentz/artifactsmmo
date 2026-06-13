/- Hand model of skill_curve_target_pure. Skill keys are Int (String bridged
later, EquipmentScoring precedent). Mirrors the extracted List.foldl. Core only. -/
namespace Formal.SkillTargetCurve

structure Item where
  craftSkill : Int
  craftLevel : Int
  itemLevel : Int
  gearRelevant : Bool
deriving Repr, DecidableEq

def qualifies (skill charLevel lookahead : Int) (it : Item) : Bool :=
  it.gearRelevant && decide (it.craftSkill = skill)
    && decide (it.itemLevel ≤ charLevel + lookahead)

def rawBest (skill charLevel lookahead : Int) (items : List Item) : Int :=
  items.foldl (fun best it =>
    if qualifies skill charLevel lookahead it && decide (it.craftLevel > best)
    then it.craftLevel else best) 0

def skillCurveTarget (skill charLevel lookahead maxSkill : Int) (items : List Item) : Int :=
  let best := rawBest skill charLevel lookahead items
  if best ≤ 0 then 0 else if best > maxSkill then maxSkill else best

/-- target ≤ maxSkill -/
theorem curve_le_max (skill charLevel lookahead maxSkill : Int) (items : List Item)
    (hmax : 0 ≤ maxSkill) :
    skillCurveTarget skill charLevel lookahead maxSkill items ≤ maxSkill := by
  simp only [skillCurveTarget]; split
  · exact hmax
  · split <;> omega

/-- target ≥ 0 -/
theorem curve_nonneg (skill charLevel lookahead maxSkill : Int) (items : List Item)
    (hmax : 0 ≤ maxSkill) :
    0 ≤ skillCurveTarget skill charLevel lookahead maxSkill items := by
  simp only [skillCurveTarget]; split
  · exact Int.le_refl 0
  · split <;> omega

/-- rawBest is monotone as the lookahead window widens (more char level admits a
SUPERSET of qualifying items, so the running max cannot fall). Key lemma. -/
theorem rawBest_mono_char (skill cl1 cl2 lookahead : Int) (items : List Item)
    (h : cl1 ≤ cl2) :
    rawBest skill cl1 lookahead items ≤ rawBest skill cl2 lookahead items := by
  unfold rawBest
  suffices H : ∀ (a b : Int), a ≤ b →
      items.foldl (fun best it => if qualifies skill cl1 lookahead it && decide (it.craftLevel > best) then it.craftLevel else best) a
      ≤ items.foldl (fun best it => if qualifies skill cl2 lookahead it && decide (it.craftLevel > best) then it.craftLevel else best) b by
    exact H 0 0 (Int.le_refl 0)
  intro a b hab
  induction items generalizing a b with
  | nil => simpa using hab
  | cons it rest ih =>
    simp only [List.foldl_cons]
    apply ih
    by_cases q1 : qualifies skill cl1 lookahead it = true
    · have q2 : qualifies skill cl2 lookahead it = true := by
        unfold qualifies at q1 ⊢; revert q1
        simp only [Bool.and_eq_true, decide_eq_true_eq]
        rintro ⟨⟨hg, hs⟩, hle⟩; exact ⟨⟨hg, hs⟩, by omega⟩
      by_cases c1 : decide (it.craftLevel > a) = true <;>
        by_cases c2 : decide (it.craftLevel > b) = true <;> simp_all <;> omega
    · simp only [Bool.not_eq_true] at q1
      simp only [q1, Bool.false_and]
      by_cases q2 : qualifies skill cl2 lookahead it = true
      · by_cases c2 : decide (it.craftLevel > b) = true <;> simp_all <;> omega
      · simp_all

/-- raising char level never lowers the target (max_skill_level is a game level,
hence `0 ≤ maxSkill`; without it a negative clamp ceiling would invert the order). -/
theorem curve_monotone_in_char_level (skill l1 l2 lookahead maxSkill : Int)
    (items : List Item) (h : l1 ≤ l2) (hmax : 0 ≤ maxSkill) :
    skillCurveTarget skill l1 lookahead maxSkill items
      ≤ skillCurveTarget skill l2 lookahead maxSkill items := by
  have key := rawBest_mono_char skill l1 l2 lookahead items h
  simp only [skillCurveTarget]
  split <;> rename_i h1 <;> split <;> rename_i h2 <;> (try split) <;> (try split) <;> omega

end Formal.SkillTargetCurve
