-- @concept: items, characters @property: dominance, safety
import Formal.EquipmentScoring

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

/-! ## Core-only list-sum helpers (replace Mathlib `List.sum_pos` / `List.sum_le_sum`). -/

/-- If every element of `l` is nonnegative and some element is strictly
positive, the sum is strictly positive. -/
private theorem sum_pos_of_mem_pos (l : List Int) (x : Int)
    (hAll : ∀ y ∈ l, 0 ≤ y) (hMem : x ∈ l) (hx : 0 < x) :
    0 < l.sum := by
  obtain ⟨pre, post, hSplit⟩ := List.append_of_mem hMem
  rw [hSplit, List.sum_append, List.sum_cons]
  have hPre : 0 ≤ pre.sum := by
    apply sum_nonneg_of_terms
    intro y hy
    exact hAll y (by rw [hSplit]; exact List.mem_append.mpr (Or.inl hy))
  have hPost : 0 ≤ post.sum := by
    apply sum_nonneg_of_terms
    intro y hy
    exact hAll y (by rw [hSplit]; exact List.mem_append.mpr (Or.inr (List.mem_cons_of_mem _ hy)))
  omega

/-- Pointwise-`≤` mapped lists have `≤` sums (core induction). -/
private theorem map_sum_le_map_sum (l : List Int) (f g : Int → Int)
    (h : ∀ e ∈ l, f e ≤ g e) :
    (l.map f).sum ≤ (l.map g).sum := by
  induction l with
  | nil => simp
  | cons a t ih =>
    simp only [List.map_cons, List.sum_cons]
    have hHead : f a ≤ g a := h a List.mem_cons_self
    have hTail : (t.map f).sum ≤ (t.map g).sum :=
      ih (fun e he => h e (List.mem_cons_of_mem _ he))
    omega

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

/-- Each armor OFFENSE term is nonnegative when the WEARER's attack is
nonnegative and the piece's damage/crit percentages are. `wTerm`'s `max 0` clamp
already makes the resistance factor nonneg for ANY monster resistance (even one
above 100), so only the wearer's attack and the piece's boost need the data
contract — exactly the split `weapon_score_nonneg` uses. -/
theorem oTerm_nonneg (playerAtk monRes dmgPct crit : Int)
    (hAtk : 0 ≤ playerAtk) (hDmg : 0 ≤ dmgPct) (hCrit : 0 ≤ crit) :
    0 ≤ oTerm playerAtk monRes dmgPct crit := by
  unfold oTerm
  exact Int.mul_nonneg (wTerm_nonneg _ _ hAtk) (by omega)

/-- `armor_score_nonneg`: `AScore ≥ 0` whenever monster attacks, armor
resistances, the WEARER's attack and the piece's damage/crit percentages are all
nonnegative (the game-data invariant — no item in `/v3/items` carries a negative
`dmg`, `dmg_<elem>` or `critical_strike`). Mirrors `weapon_score_nonneg` from
`EquipmentScoring`. The defense sum has no `max 0` clamp because its two factors
are both already nonneg by data contract; the offense sum inherits the weapon
clamp through `oTerm`.

The `hPAtk`/`hDmg`/`hDmgElem`/`hCrit` hypotheses are the data contract of the
NEW offense sum, added exactly as `hUtil` was added when `flatUtil` joined
`AScore`: a new summand brings its own nonnegativity hypothesis rather than
silently narrowing what the theorem covers. -/
theorem armor_score_nonneg (item : Item) (monsterAtk monsterRes playerAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e)
    (hUtil : 0 ≤ item.flatUtil)
    (hPAtk : ∀ e ∈ elements, 0 ≤ elemGet playerAtk e)
    (hDmg : 0 ≤ item.dmg)
    (hDmgElem : ∀ e ∈ elements, 0 ≤ elemGet item.dmgElem e)
    (hCrit : 0 ≤ item.crit) :
    0 ≤ AScore item monsterAtk monsterRes playerAtk := by
  unfold AScore
  have hsum : 0 ≤ (elements.map
      (fun e => aTerm (elemGet monsterAtk e) (elemGet item.resistance e))).sum := by
    apply sum_nonneg_of_terms
    intro x hx
    rw [List.mem_map] at hx
    obtain ⟨e, he, hxe⟩ := hx
    rw [← hxe]
    exact aTerm_nonneg _ _ (hAtk e he) (hRes e he)
  have hoff : 0 ≤ (elements.map
      (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
          (item.dmg + elemGet item.dmgElem e) item.crit)).sum := by
    apply sum_nonneg_of_terms
    intro x hx
    rw [List.mem_map] at hx
    obtain ⟨e, he, hxe⟩ := hx
    rw [← hxe]
    exact oTerm_nonneg _ _ _ _ (hPAtk e he) (by have := hDmgElem e he; omega) hCrit
  omega

/-! ## The empty-slot dominance theorems. -/

/-- **WEAK DOMINANCE**: any armor item is at least as good as leaving the
slot empty (under the data-contract nonnegativity hypotheses). This is the
formal foundation for the meta-objective claim "armor must enter an empty
slot before any tie-breaker is considered". -/
theorem armor_weakly_dominates_empty_slot
    (item : Item) (monsterAtk monsterRes playerAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e)
    (hUtil : 0 ≤ item.flatUtil)
    (hPAtk : ∀ e ∈ elements, 0 ≤ elemGet playerAtk e)
    (hDmg : 0 ≤ item.dmg)
    (hDmgElem : ∀ e ∈ elements, 0 ≤ elemGet item.dmgElem e)
    (hCrit : 0 ≤ item.crit) :
    baselineScore ≤ AScore item monsterAtk monsterRes playerAtk := by
  rw [baselineScore_def]
  exact armor_score_nonneg item monsterAtk monsterRes playerAtk hAtk hRes hUtil
    hPAtk hDmg hDmgElem hCrit

/-- **STRICT DOMINANCE**: when at least one element has both a nonzero
monster attack AND a nonzero armor resistance, the armor STRICTLY improves
over the empty-slot baseline. This is the user's stated invariant:
"there's simply no other correct answer than to go from no armor bonuses to
having armor bonuses."

The proof expands the concrete 4-element list (fire / earth / water / air)
and case-splits on which element is the strict one. -/
theorem armor_strictly_dominates_empty_slot
    (item : Item) (monsterAtk monsterRes playerAtk : ElemStats) (e : Int)
    (he : e ∈ elements)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hRes : ∀ e ∈ elements, 0 ≤ elemGet item.resistance e)
    (hStrictAtk : 0 < elemGet monsterAtk e)
    (hStrictRes : 0 < elemGet item.resistance e)
    (hUtil : 0 ≤ item.flatUtil)
    (hPAtk : ∀ e ∈ elements, 0 ≤ elemGet playerAtk e)
    (hDmg : 0 ≤ item.dmg)
    (hDmgElem : ∀ e ∈ elements, 0 ≤ elemGet item.dmgElem e)
    (hCrit : 0 ≤ item.crit) :
    baselineScore < AScore item monsterAtk monsterRes playerAtk := by
  rw [baselineScore_def]
  unfold AScore
  -- The offense sum is ≥ 0 (it only ever ADDS to the strict defense gain).
  have hoff : 0 ≤ (elements.map
      (fun e' => oTerm (elemGet playerAtk e') (elemGet monsterRes e')
          (item.dmg + elemGet item.dmgElem e') item.crit)).sum := by
    apply sum_nonneg_of_terms
    intro x hx
    rw [List.mem_map] at hx
    obtain ⟨e', he', hxe'⟩ := hx
    rw [← hxe']
    exact oTerm_nonneg _ _ _ _ (hPAtk e' he') (by have := hDmgElem e' he'; omega) hCrit
  -- The 4 element-terms are all ≥ 0; the one at element `e` is strictly > 0.
  have hAll : ∀ x ∈ elements.map
      (fun e' => aTerm (elemGet monsterAtk e') (elemGet item.resistance e')), 0 ≤ x := by
    intro x hx
    rw [List.mem_map] at hx
    obtain ⟨e', he', hxe'⟩ := hx
    rw [← hxe']
    exact aTerm_nonneg _ _ (hAtk e' he') (hRes e' he')
  have hMem : aTerm (elemGet monsterAtk e) (elemGet item.resistance e) ∈
      elements.map
        (fun e' => aTerm (elemGet monsterAtk e') (elemGet item.resistance e')) := by
    rw [List.mem_map]
    exact ⟨e, he, rfl⟩
  have hTermPos : 0 < aTerm (elemGet monsterAtk e) (elemGet item.resistance e) := by
    unfold aTerm
    exact Int.mul_pos hStrictAtk hStrictRes
  have hSumPos : 0 < (elements.map
      (fun e' => aTerm (elemGet monsterAtk e') (elemGet item.resistance e'))).sum :=
    sum_pos_of_mem_pos _ _ hAll hMem hTermPos
  omega

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

/-- Pointwise monotonicity of `oTerm` in the piece's damage/crit boost: with the
wearer's attack fixed nonneg, a bigger `2 * dmgPct + crit` never scores lower.
`wTerm`'s clamp makes the left factor nonneg for ANY monster resistance. -/
theorem oTerm_mono_in_boost (playerAtk monRes dA cA dB cB : Int)
    (hAtk : 0 ≤ playerAtk) (hBoost : 2 * dA + cA ≤ 2 * dB + cB) :
    oTerm playerAtk monRes dA cA ≤ oTerm playerAtk monRes dB cB := by
  unfold oTerm
  exact Int.mul_le_mul_of_nonneg_left hBoost (wTerm_nonneg _ _ hAtk)

/-- Componentwise monotonicity proxy: when the per-element resistance of item
`a` is bounded above by item `b`'s on every element, `AScore a ≤ AScore b`.

`hBoost` is the offense sum's share of the hypothesis, added exactly as `hUtil`
was when `flatUtil` joined `AScore`: this theorem says "more resistance never
makes armor worse, ALL ELSE EQUAL OR BETTER", and the offense boost is now part
of "all else". Without it the claim would be false, and weakening it to a
resistance-only statement would be claiming something `AScore` no longer
computes. -/
theorem armor_score_mono_in_resistance
    (a b : Item) (monsterAtk monsterRes playerAtk : ElemStats)
    (hAtk : ∀ e ∈ elements, 0 ≤ elemGet monsterAtk e)
    (hLe : ∀ e ∈ elements,
              elemGet a.resistance e ≤ elemGet b.resistance e)
    (hUtil : a.flatUtil ≤ b.flatUtil)
    (hPAtk : ∀ e ∈ elements, 0 ≤ elemGet playerAtk e)
    (hBoost : ∀ e ∈ elements,
              2 * (a.dmg + elemGet a.dmgElem e) + a.crit
                ≤ 2 * (b.dmg + elemGet b.dmgElem e) + b.crit) :
    AScore a monsterAtk monsterRes playerAtk
      ≤ AScore b monsterAtk monsterRes playerAtk := by
  unfold AScore
  have hSumLe : (elements.map
      (fun e => aTerm (elemGet monsterAtk e) (elemGet a.resistance e))).sum ≤
      (elements.map
      (fun e => aTerm (elemGet monsterAtk e) (elemGet b.resistance e))).sum := by
    apply map_sum_le_map_sum
    intro e he
    exact aTerm_mono_in_res _ _ _ (hAtk e he) (hLe e he)
  have hOffLe : (elements.map
      (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
          (a.dmg + elemGet a.dmgElem e) a.crit)).sum ≤
      (elements.map
      (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
          (b.dmg + elemGet b.dmgElem e) b.crit)).sum := by
    apply map_sum_le_map_sum
    intro e he
    exact oTerm_mono_in_boost _ _ _ _ _ _ (hPAtk e he) (hBoost e he)
  omega

/-! ## Monotonicity of the WEAPON score.

The armor half above is what licenses the live occupancy rule in
`ai/equipment/slot_occupancy.may_displace`: a candidate that dominates the
incumbent stat-wise scores at least as high for EVERY monster and EVERY wearer,
so `pickSlot`'s strict-improvement rule can never swap it back and the equip is
a fixed point. `may_displace` is applied to weapon slots too, so the same
statement is owed for `WScore` — otherwise the rule would rest on a proof that
covers only half the slots. -/

/-- Pointwise monotonicity of `wTerm` in the wearer's attack: the clamp makes
the second factor nonneg for ANY monster resistance, so more attack on an
element never scores lower there. -/
theorem wTerm_mono_in_atk (a b monRes : Int) (hab : a ≤ b) :
    wTerm a monRes ≤ wTerm b monRes := by
  unfold wTerm
  exact Int.mul_le_mul_of_nonneg_right hab (Int.le_max_left _ _)

/-- **Weapon dominance**: if `a`'s per-element attack is bounded above by `b`'s
on every element and `a.crit ≤ b.crit`, then `WScore a ≤ WScore b` against ANY
monster resistance.

`hAtkA`/`hCritA` are the nonnegativity hypotheses the products need (real item
stats always satisfy them); they are hypotheses rather than assumptions baked
into `Item` for the same reason `armor_score_nonneg` states them — narrowing
`Item` would silently narrow every theorem over it. -/
theorem weapon_score_mono_of_dominates
    (a b : Item) (monsterRes : ElemStats)
    (hAtkA : ∀ e ∈ elements, 0 ≤ elemGet a.attack e)
    (hCritA : 0 ≤ a.crit)
    (hAtk : ∀ e ∈ elements, elemGet a.attack e ≤ elemGet b.attack e)
    (hCrit : a.crit ≤ b.crit) :
    WScore a monsterRes ≤ WScore b monsterRes := by
  unfold WScore
  have hSumA : 0 ≤ (elements.map
      (fun e => wTerm (elemGet a.attack e) (elemGet monsterRes e))).sum := by
    apply sum_nonneg_of_terms
    intro x hx
    rw [List.mem_map] at hx
    obtain ⟨e, he, hxe⟩ := hx
    rw [← hxe]
    exact wTerm_nonneg _ _ (hAtkA e he)
  have hSumLe : (elements.map
      (fun e => wTerm (elemGet a.attack e) (elemGet monsterRes e))).sum ≤
      (elements.map
      (fun e => wTerm (elemGet b.attack e) (elemGet monsterRes e))).sum := by
    apply map_sum_le_map_sum
    intro e he
    exact wTerm_mono_in_atk _ _ _ (hAtk e he)
  have hSumB : 0 ≤ (elements.map
      (fun e => wTerm (elemGet b.attack e) (elemGet monsterRes e))).sum := by
    omega
  calc (elements.map (fun e => wTerm (elemGet a.attack e) (elemGet monsterRes e))).sum
        * (200 + a.crit)
      ≤ (elements.map (fun e => wTerm (elemGet b.attack e) (elemGet monsterRes e))).sum
        * (200 + a.crit) :=
        Int.mul_le_mul_of_nonneg_right hSumLe (by omega)
    _ ≤ (elements.map (fun e => wTerm (elemGet b.attack e) (elemGet monsterRes e))).sum
        * (200 + b.crit) :=
        Int.mul_le_mul_of_nonneg_left (by omega) hSumB

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
