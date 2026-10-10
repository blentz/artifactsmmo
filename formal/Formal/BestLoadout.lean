-- @concept: consumables, combat @property: dominance, totality, validity
/-
The best consumable loadout's pick (`docs/PLAN_consumable_utility.md`
increment 4, `src/artifactsmmo_cli/ai/best_loadout_core.py`).

## The model

The candidates are the loadouts in the reader's enumeration order (none, each
single potion, each pair, in catalogue order), each scored `(rate, units)`: its
XP per second as a `(num, den)` pair (`Formal.LoopRate.xpRate`, positive
denominator: `xpRate_den_pos`) and the consumable units one fight uses.

* `beats a b` — `a` has a strictly higher rate, or the same rate on strictly
  fewer units (fewer consumables bought or drawn for the same XP per second);
* `pick` — a left fold that replaces its choice only when the next candidate
  BEATS it, so on a full tie the earlier candidate (catalogue order of the API
  list) stays — never a spelling order.
-/

import Formal.ConsumablePrice

namespace Formal.BestLoadout

open Formal.ConsumablePrice (Q qle qle_trans)

/-- A candidate: `(rate, units used)`, the rate a `(num, den)` pair. -/
abbrev Cand := Q × Nat

/-- `a` strictly beats `b`: a higher rate, or the same rate on fewer units. -/
def beats (a b : Cand) : Bool :=
  decide (b.1.1 * a.1.2 < a.1.1 * b.1.2)
    || (decide (a.1.1 * b.1.2 = b.1.1 * a.1.2) && decide (a.2 < b.2))

def pickAux : List Cand → Nat → Option (Nat × Cand) → Option (Nat × Cand)
  | [], _, best => best
  | c :: cs, i, best =>
    let best' := match best with
      | none => some (i, c)
      | some (j, b) => if beats c b then some (i, c) else some (j, b)
    pickAux cs (i + 1) best'

/-- The index of the best candidate, none for no candidates. -/
def pick (cs : List Cand) : Option Nat := (pickAux cs 0 none).map Prod.fst

/-! ## Lemmas -/

theorem not_beats_iff (a b : Cand) :
    beats a b = false ↔ qle a.1 b.1 ∧ (qle b.1 a.1 → b.2 ≤ a.2) := by
  unfold beats qle
  simp only [Bool.or_eq_false_iff, Bool.and_eq_false_iff, decide_eq_false_iff_not]
  constructor
  · rintro ⟨h1, h2⟩
    refine ⟨by omega, fun h3 => ?_⟩
    rcases h2 with h2 | h2 <;> omega
  · rintro ⟨h1, h2⟩
    refine ⟨by omega, ?_⟩
    by_cases h3 : b.1.1 * a.1.2 ≤ a.1.1 * b.1.2
    · exact Or.inr (by have := h2 h3; omega)
    · exact Or.inl (by omega)

theorem qle_total (a b : Q) (h : ¬ qle a b) : qle b a := by
  unfold qle at *; omega

theorem not_beats_trans (a b c : Cand) (ha : 0 < a.1.2) (hb : 0 < b.1.2) (hc : 0 < c.1.2)
    (hab : beats a b = false) (hbc : beats b c = false) : beats a c = false := by
  rw [not_beats_iff] at *
  obtain ⟨hab1, hab2⟩ := hab
  obtain ⟨hbc1, hbc2⟩ := hbc
  refine ⟨qle_trans _ _ _ hb hab1 hbc1, fun hca => ?_⟩
  have hba : qle b.1 a.1 := qle_trans _ _ _ hc hbc1 hca
  have hcb : qle c.1 b.1 := qle_trans _ _ _ ha hca hab1
  exact Nat.le_trans (hbc2 hcb) (hab2 hba)

theorem beats_not_beats (c d b : Cand) (hb : 0 < b.1.2) (hc : 0 < c.1.2) (hd : 0 < d.1.2)
    (hcd : beats c d = true) (hcb : beats c b = false) : beats d b = false := by
  rw [not_beats_iff] at hcb ⊢
  obtain ⟨hcb1, hcb2⟩ := hcb
  by_cases hq : qle c.1 d.1
  · -- same rate, fewer units
    have hcd' : qle d.1 c.1 ∧ c.2 < d.2 := by
      unfold beats at hcd; unfold qle at hq ⊢
      simp only [Bool.or_eq_true, Bool.and_eq_true, decide_eq_true_eq] at hcd
      rcases hcd with h | ⟨h1, h2⟩
      · omega
      · exact ⟨by omega, h2⟩
    refine ⟨qle_trans _ _ _ hc hcd'.1 hcb1, fun hbd => ?_⟩
    have hbc : qle b.1 c.1 := qle_trans _ _ _ hd hbd hcd'.1
    have := hcb2 hbc
    omega
  · have hdc := qle_total _ _ hq
    refine ⟨qle_trans _ _ _ hc hdc hcb1, fun hbd => ?_⟩
    exact absurd (qle_trans _ _ _ hb hcb1 hbd) hq

/-! ## Theorems -/

/-- There is a pick exactly when there is a candidate. -/
theorem pickAux_some (cs : List Cand) :
    ∀ (i : Nat) (best : Option (Nat × Cand)), best ≠ none → pickAux cs i best ≠ none := by
  induction cs with
  | nil => intro i best h; exact h
  | cons c cs ih =>
    intro i best _
    simp only [pickAux]
    apply ih
    cases best with
    | none => simp
    | some p => obtain ⟨j, b⟩ := p; by_cases hb : beats c b <;> simp [hb]

theorem pick_none_iff (cs : List Cand) : pick cs = none ↔ cs = [] := by
  cases cs with
  | nil => simp [pick, pickAux]
  | cons c cs =>
    simp only [pick, pickAux, reduceCtorEq, iff_false, Option.map_eq_none_iff]
    exact pickAux_some cs 1 (some (0, c)) (by simp)

/-- The pick is a candidate: the candidate at the picked index. -/
theorem pickAux_mem (cs : List Cand) :
    ∀ (i : Nat) (best : Option (Nat × Cand)) (j : Nat) (b : Cand),
      pickAux cs i best = some (j, b) → best = some (j, b) ∨ (i ≤ j ∧ cs[j - i]? = some b) := by
  induction cs with
  | nil => intro i best j b h; exact Or.inl h
  | cons c cs ih =>
    intro i best j b h
    simp only [pickAux] at h
    rcases ih (i + 1) _ j b h with h' | ⟨hij, hget⟩
    · cases best with
      | none =>
        simp at h'; obtain ⟨rfl, rfl⟩ := h'
        exact Or.inr ⟨Nat.le_refl _, by simp⟩
      | some p =>
        obtain ⟨k, d⟩ := p
        by_cases hb : beats c d
        · simp [hb] at h'; obtain ⟨rfl, rfl⟩ := h'
          exact Or.inr ⟨Nat.le_refl _, by simp⟩
        · simp [hb] at h'; obtain ⟨rfl, rfl⟩ := h'; exact Or.inl rfl
    · refine Or.inr ⟨by omega, ?_⟩
      have : j - i = (j - (i + 1)) + 1 := by omega
      rw [this]; simpa using hget

theorem pick_mem (cs : List Cand) (j : Nat) (b : Cand) (h : pickAux cs 0 none = some (j, b)) :
    cs[j]? = some b := by
  rcases pickAux_mem cs 0 none j b h with h' | ⟨_, h'⟩
  · simp at h'
  · simpa using h'

theorem pickAux_optimal (cs : List Cand) :
    ∀ (i : Nat) (best : Option (Nat × Cand)) (j : Nat) (b : Cand),
      (∀ c ∈ cs, 0 < c.1.2) → (∀ k d, best = some (k, d) → 0 < d.1.2) →
      pickAux cs i best = some (j, b) →
      0 < b.1.2 ∧ (∀ c ∈ cs, beats c b = false) ∧ (∀ k d, best = some (k, d) → beats d b = false) := by
  induction cs with
  | nil =>
    intro i best j b _ hbest h
    simp only [pickAux] at h; subst h
    refine ⟨hbest j b rfl, by simp, ?_⟩
    intro k d hkd; simp at hkd; obtain ⟨-, rfl⟩ := hkd
    simp [beats]
  | cons c cs ih =>
    intro i best j b hpos hbest h
    have hc : 0 < c.1.2 := hpos c (List.mem_cons_self ..)
    have htail : ∀ x ∈ cs, 0 < x.1.2 := fun x hx => hpos x (List.mem_cons_of_mem _ hx)
    simp only [pickAux] at h
    cases best with
    | none =>
      obtain ⟨hbpos, hcs, hb'⟩ := ih (i + 1) _ j b htail (by simp; omega) h
      refine ⟨hbpos, ?_, by simp⟩
      intro x hx
      rcases List.mem_cons.mp hx with rfl | hx
      · exact hb' i x rfl
      · exact hcs x hx
    | some p =>
      obtain ⟨k0, d0⟩ := p
      have hd0 : 0 < d0.1.2 := hbest k0 d0 rfl
      by_cases hbt : beats c d0 = true
      · simp only [hbt, if_true] at h
        obtain ⟨hbpos, hcs, hb'⟩ := ih (i + 1) _ j b htail
          (by intro k d hkd; simp at hkd; obtain ⟨-, rfl⟩ := hkd; exact hc) h
        have hcb := hb' i c rfl
        refine ⟨hbpos, ?_, ?_⟩
        · intro x hx
          rcases List.mem_cons.mp hx with rfl | hx
          · exact hcb
          · exact hcs x hx
        · intro k d hkd; cases hkd
          exact beats_not_beats c _ b hbpos hc hd0 hbt hcb
      · simp only [Bool.not_eq_true] at hbt; simp only [hbt] at h
        obtain ⟨hbpos, hcs, hb'⟩ := ih (i + 1) _ j b htail
          (by intro k d hkd; simp at hkd; obtain ⟨-, rfl⟩ := hkd; exact hd0) h
        have hdb := hb' k0 d0 rfl
        refine ⟨hbpos, ?_, ?_⟩
        · intro x hx
          rcases List.mem_cons.mp hx with rfl | hx
          · exact not_beats_trans x d0 b hc hd0 hbpos hbt hdb
          · exact hcs x hx
        · intro k d hkd; simp at hkd; obtain ⟨rfl, rfl⟩ := hkd; exact hdb

/-- OPTIMALITY: no candidate beats the pick — none has a higher XP rate, and
none with the same rate uses fewer units (every rate has a positive
denominator, `Formal.LoopRate.xpRate_den_pos`). -/
theorem pick_optimal (cs : List Cand) (hpos : ∀ c ∈ cs, 0 < c.1.2) (j : Nat) (b : Cand)
    (h : pickAux cs 0 none = some (j, b)) : ∀ c ∈ cs, beats c b = false :=
  (pickAux_optimal cs 0 none j b hpos (by simp) h).2.1

/-! ## Witnesses -/

-- A higher rate wins; on the same rate (1/3 = 2/6) fewer units win; on a full
-- tie the earlier candidate stays.
example : pick [((1, 4), 0), ((1, 3), 5), ((2, 6), 2)] = some 2 := by decide
example : pick [((1, 3), 2), ((2, 6), 2)] = some 0 := by decide
example : pick [((0, 30), 0), ((0, 31), 0)] = some 0 := by decide
example : pick [] = none := by decide

end Formal.BestLoadout
