import Formal.EquipmentScoring
import Mathlib.Tactic

/-!
# Formal.GearPolicy

Composition-correctness lemmas for **gear selection policy**: the cross-cutting
invariants that bind `EquipmentScoring` (per-slot argmax math) to the
meta-objective ranking layer. None of these can be proved inside
`EquipmentScoring` alone because they say something about what the slot is
WORTH when EMPTY — the baseline against which any equipped item must beat
to enter the slot.

The user-facing claim being formalized:
"going from no armor → any armor with nonnegative resistance is at least as
good; if any element has a positive resistance against the attacker, it is
STRICTLY better."

Closes Phase G1 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.GearPolicy
open Formal.EquipmentScoring

/-! ## Empty-slot baseline.

An equipment slot containing no item contributes EXACTLY 0 to the projected
defense field. Concretely: the Python `_armor_score` returns `0.0` when given
`None`, and the integer surrogate `AScore` is defined only over real items —
the slot-empty case is modeled as a baseline `Int` constant. -/

def baselineScore : Int := 0

@[simp] theorem baselineScore_def : baselineScore = 0 := rfl

/-! ## Per-element armor term nonnegativity. -/

/-- Each armor term is nonnegative WHEN the monster attack AND the armor
resistance are both nonnegative. The game's resistance field is always ≥ 0
(no "negative armor" mechanic exists) and monster attacks are always ≥ 0. -/
theorem aTerm_nonneg (monAtk armorRes : Int)
    (hAtk : 0 ≤ monAtk) (hRes : 0 ≤ armorRes) :
    0 ≤ aTerm monAtk armorRes := by
  unfold aTerm
  exact Int.mul_nonneg hAtk hRes

/-- `armor_score_nonneg`: `AScore ≥ 0` whenever monster attacks AND armor
resistances are both nonnegative (the game-data invariant). Mirrors
`weapon_score_nonneg` from `EquipmentScoring`, but for AScore (which has no
`max 0` clamp because its two factors are both already nonneg by data
contract). -/
theorem armor_score_nonneg (item : Item) (monsterAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e) :
    0 ≤ AScore item monsterAtk := by
  unfold AScore
  apply sum_nonneg_of_terms
  intro x hx
  rw [List.mem_map] at hx
  obtain ⟨e, he, hxe⟩ := hx
  rw [← hxe]
  exact aTerm_nonneg _ _ (hAtk e he) (hRes e he)

/-! ## The empty-slot dominance theorems. -/

/-- **WEAK DOMINANCE**: any armor item is at least as good as leaving the
slot empty (under the data-contract nonnegativity hypotheses). This is the
formal foundation for the meta-objective claim "armor must enter an empty
slot before any tie-breaker is considered". -/
theorem armor_weakly_dominates_empty_slot
    (item : Item) (monsterAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e) :
    baselineScore ≤ AScore item monsterAtk := by
  rw [baselineScore_def]
  exact armor_score_nonneg item monsterAtk hAtk hRes

/-- **STRICT DOMINANCE**: when at least one element has both a nonzero
monster attack AND a nonzero armor resistance, the armor STRICTLY improves
over the empty-slot baseline. This is the user's stated invariant:
"there's simply no other correct answer than to go from no armor bonuses to
having armor bonuses."

The proof expands the concrete 4-element list (fire / earth / water / air)
and case-splits on which element is the strict one. -/
theorem armor_strictly_dominates_empty_slot
    (item : Item) (monsterAtk : ElemStats) (e : Int)
    (he : e ∈ elements)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e)
    (hStrictAtk : 0 < elemGet monsterAtk e)
    (hStrictRes : 0 < elemGet item.resistance e) :
    baselineScore < AScore item monsterAtk := by
  rw [baselineScore_def]
  unfold AScore
  -- The 4 element-terms are all ≥ 0; the one at element `e` is strictly > 0.
  set L := elements.map
    (fun e' => aTerm (elemGet monsterAtk e') (elemGet item.resistance e'))
  have hAll : ∀ x ∈ L, 0 ≤ x := by
    intro x hx
    simp only [L, List.mem_map] at hx
    obtain ⟨e', he', hxe'⟩ := hx
    rw [← hxe']
    exact aTerm_nonneg _ _ (hAtk e' he') (hRes e' he')
  have hMem : aTerm (elemGet monsterAtk e) (elemGet item.resistance e) ∈ L := by
    simp only [L, List.mem_map]
    exact ⟨e, he, rfl⟩
  have hTermPos : 0 < aTerm (elemGet monsterAtk e) (elemGet item.resistance e) := by
    unfold aTerm
    exact Int.mul_pos hStrictAtk hStrictRes
  -- one strictly-positive term plus a sum of nonneg ⇒ total > 0
  obtain ⟨pre, post, hSplit⟩ := List.append_of_mem hMem
  rw [hSplit]
  rw [List.sum_append, List.sum_cons]
  have hPre : 0 ≤ pre.sum := by
    apply sum_nonneg_of_terms
    intro x hx
    apply hAll
    rw [hSplit]
    exact List.mem_append.mpr (Or.inl hx)
  have hPost : 0 ≤ post.sum := by
    apply sum_nonneg_of_terms
    intro x hx
    apply hAll
    rw [hSplit]
    exact List.mem_append.mpr (Or.inr (List.mem_cons_of_mem _ hx))
  linarith

/-! ## Monotonicity in resistance.

`AScore` is componentwise monotone non-decreasing in armor resistance. This
formalizes "more resistance against attacking elements never makes the armor
worse" — the basis for the meta-objective ranker preferring strictly higher
resistance over weakly equal. -/

/-- Pointwise monotonicity of `aTerm`: increasing `armorRes` (while
monster attack is fixed nonneg) increases the term. -/
theorem aTerm_mono_in_res (monAtk a b : Int) (hAtk : 0 ≤ monAtk) (hab : a ≤ b) :
    aTerm monAtk a ≤ aTerm monAtk b := by
  unfold aTerm
  exact Int.mul_le_mul_of_nonneg_left hab hAtk

/-- Componentwise monotonicity proxy: when the per-element resistance of item
`a` is bounded above by item `b`'s on every element, `AScore a ≤ AScore b`. -/
theorem armor_score_mono_in_resistance
    (a b : Item) (monsterAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hLe : ∀ e ∈ elements,
              elemGet a.resistance e ≤ elemGet b.resistance e) :
    AScore a monsterAtk ≤ AScore b monsterAtk := by
  unfold AScore
  apply List.sum_le_sum
  intro e he
  exact aTerm_mono_in_res _ _ _ (hAtk e he) (hLe e he)

/-! ## Composition lemma: empty slot + nontrivial armor candidate ⇒
`pickSlot` returns SOME armor. -/

/-- If the candidate list is nonempty and the current slot is empty
(`current = none`), `pickSlot` returns `some best` — it NEVER leaves the
slot empty in the presence of a feasible item. This is the per-slot
restatement of the empty-slot dominance principle, lifted through the
existing `pickSlot` implementation in `EquipmentScoring`. -/
theorem pickSlot_empty_returns_some
    (score : Item → Int) (playerLevel : Int) (items : List Item)
    (hNonempty : (candidates playerLevel items) ≠ []) :
    ∃ x, pickSlot score playerLevel none items = some x := by
  unfold pickSlot
  cases hcands : candidates playerLevel items with
  | nil => exact absurd hcands hNonempty
  | cons c cs =>
    exact ⟨argmaxBy score c cs, by simp⟩

end Formal.GearPolicy
