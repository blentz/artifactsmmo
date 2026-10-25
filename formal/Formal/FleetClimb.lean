-- @concept: fleet-climb @property: monotonicity, boundedness, dominance
/-
Formal model of the fleet climb's pure core,
`src/artifactsmmo_cli/ai/fleet_climb_core.py`
(spec docs/superpowers/specs/2026-10-18-global-gear-objective-design.md §2.5).
The Python core is bound to these semantics by `formal/diff/test_fleet_climb_diff.py`
(differential) and by the FLEET_CLIMB_CORE_MUTATIONS group (unit-killed,
formal/diff/mutate.py).

Two pieces:

  * `amortized` — a remaining climb divided across the `units` fleet units it
    unlocks (`amortized_climb_seconds`). Proven: with a non-negative climb and
    at least one unit, a unit's share never exceeds the whole climb
    (`amortized_le_remaining`), and more units never raise it
    (`amortized_antitone_in_units`).
  * `pick` — the climber (`climber`): candidates in fleet order, each
    `(id, remaining, committed)`; the first candidate whose key
    `(remaining, committed)` is lexicographically least, exactly Python's
    `min` over the fleet-ordered list. Proven: no candidate has a strictly
    smaller key than the pick (`climber_minimal`); the pick is a candidate
    (`pick_mem`); and a candidate strictly before the pick in fleet order has a
    strictly larger key (`pick_first`), so a full tie goes to the fleet order.

Non-vacuity: `amortized_le_remaining` and `amortized_antitone_in_units` are
instantiated by concrete `example`s below (a 100-cycle climb over 4 units
pays no more than the climb, and no more than over 2); `climber_minimal` and `pick_first` by a three-character
witness with a remaining tie broken by committed work.

Lean core only — no mathlib (mathlib is quarantined to Formal/Liveness/).
-/

namespace Formal.FleetClimb

/-! ### The amortized share -/

/-- `remaining / units`, the share one unlocked unit pays. -/
def amortized (remaining : Rat) (units : Nat) : Rat := remaining / (units : Rat)

theorem units_pos {units : Nat} (hu : 1 ≤ units) : (0 : Rat) < (units : Rat) :=
  Rat.natCast_pos.mpr hu

theorem amortized_le_remaining (remaining : Rat) (units : Nat)
    (hr : 0 ≤ remaining) (hu : 1 ≤ units) :
    amortized remaining units ≤ remaining := by
  unfold amortized
  apply Rat.not_lt.mp
  rw [Rat.lt_div_iff (units_pos hu)]
  intro hlt
  have h1 : ((1 : Nat) : Rat) ≤ (units : Rat) := Rat.natCast_le_natCast.mpr hu
  have hle : remaining * ((1 : Nat) : Rat) ≤ remaining * (units : Rat) :=
    Rat.mul_le_mul_of_nonneg_left h1 hr
  have hone : ((1 : Nat) : Rat) = 1 := rfl
  rw [hone, Rat.mul_one] at hle
  exact Rat.lt_irrefl (Std.lt_of_lt_of_le hlt hle)

theorem amortized_antitone_in_units (remaining : Rat) (u v : Nat)
    (hr : 0 ≤ remaining) (hu : 1 ≤ u) (huv : u ≤ v) :
    amortized remaining v ≤ amortized remaining u := by
  unfold amortized
  have hupos := units_pos hu
  have hvpos : (0 : Rat) < (v : Rat) := units_pos (Nat.le_trans hu huv)
  apply Rat.not_lt.mp
  rw [Rat.lt_div_iff hvpos]
  intro hlt
  have hnn : 0 ≤ remaining / (u : Rat) := by
    rw [Rat.div_def]
    exact Rat.mul_nonneg hr (Rat.le_of_lt (Rat.inv_pos.mpr hupos))
  have hback : remaining / (u : Rat) * (u : Rat) = remaining := by
    rw [Rat.div_def, Rat.mul_assoc, Rat.inv_mul_cancel _ (Ne.symm (Rat.lt_irrefl ∘ fun h => h ▸ hupos)), Rat.mul_one]
  have hle : remaining / (u : Rat) * (u : Rat) ≤ remaining / (u : Rat) * (v : Rat) := by
    rw [Rat.mul_comm _ (u : Rat), Rat.mul_comm _ (v : Rat)]
    exact Rat.mul_le_mul_of_nonneg_right (Rat.natCast_le_natCast.mpr huv) hnn
  rw [hback] at hle
  exact Rat.lt_irrefl (Std.lt_of_lt_of_le hlt hle)

-- Non-vacuity: both theorems' hypotheses hold for a 100-cycle climb shared by
-- 2 or 4 units.
example : amortized 100 4 ≤ 100 := amortized_le_remaining 100 4 (by decide) (by decide)
example : amortized 100 4 ≤ amortized 100 2 :=
  amortized_antitone_in_units 100 2 4 (by decide) (by decide) (by decide)

/-! ### The climber -/

/-- A candidate: `(id, remaining, committed)`. -/
abbrev Cand := Nat × Rat × Nat

/-- The candidate's key `(remaining, committed)`. -/
def key (c : Cand) : Rat × Nat := (c.2.1, c.2.2)

/-- `a < b` on keys, lexicographically, as a Python tuple compares. -/
def keyLt (a b : Rat × Nat) : Prop := a.1 < b.1 ∨ (a.1 = b.1 ∧ a.2 < b.2)

instance (a b : Rat × Nat) : Decidable (keyLt a b) := by
  unfold keyLt; exact inferInstance

/-- `a ≤ b` on keys. -/
def keyLe (a b : Rat × Nat) : Prop := a.1 < b.1 ∨ (a.1 = b.1 ∧ a.2 ≤ b.2)

instance (a b : Rat × Nat) : Decidable (keyLe a b) := by
  unfold keyLe; exact inferInstance

/-- The first least candidate of a fleet-ordered list (Python's `min`). -/
def pick : List Cand → Option Cand
  | [] => none
  | c :: cs =>
    match pick cs with
    | none => some c
    | some d => if keyLe (key c) (key d) then some c else some d

theorem keyLt_irrefl (a : Rat × Nat) : ¬ keyLt a a := by
  unfold keyLt
  rintro (h | ⟨_, h⟩)
  · exact Rat.lt_irrefl h
  · omega

theorem keyLt_of_not_keyLe {a b : Rat × Nat} (h : ¬ keyLe a b) : keyLt b a := by
  unfold keyLe at h
  unfold keyLt
  have hnlt : ¬ a.1 < b.1 := fun hab => h (Or.inl hab)
  have hba : b.1 ≤ a.1 := Rat.not_lt.mp hnlt
  rcases Rat.le_total (a := a.1) (b := b.1) with hab | hab
  · have heq : b.1 = a.1 := Rat.le_antisymm hba hab
    refine Or.inr ⟨heq, ?_⟩
    have : ¬ a.2 ≤ b.2 := fun hle => h (Or.inr ⟨heq.symm, hle⟩)
    omega
  · by_cases heq : b.1 = a.1
    · refine Or.inr ⟨heq, ?_⟩
      have : ¬ a.2 ≤ b.2 := fun hle => h (Or.inr ⟨heq.symm, hle⟩)
      omega
    · exact Or.inl (Rat.lt_of_le_of_ne hba heq)

theorem not_keyLt_of_keyLe {a b : Rat × Nat} (h : keyLe a b) : ¬ keyLt b a := by
  unfold keyLe at h
  unfold keyLt
  rintro (hba | ⟨heq, hba⟩)
  · rcases h with hab | ⟨heq, _⟩
    · exact Rat.lt_irrefl (Std.lt_trans hab hba)
    · rw [heq] at hba; exact Rat.lt_irrefl hba
  · rcases h with hab | ⟨_, hle⟩
    · rw [heq] at hab; exact Rat.lt_irrefl hab
    · omega

theorem keyLe_of_keyLt {a b : Rat × Nat} (h : keyLt a b) : keyLe a b := by
  unfold keyLt at h
  unfold keyLe
  rcases h with h | ⟨e, l⟩
  · exact Or.inl h
  · exact Or.inr ⟨e, Nat.le_of_lt l⟩

theorem keyLe_of_not_keyLt {a b : Rat × Nat} (h : ¬ keyLt b a) : keyLe a b := by
  by_cases hle : keyLe a b
  · exact hle
  · exact absurd (keyLt_of_not_keyLe hle) h

theorem not_keyLt_trans {a b c : Rat × Nat} (hab : ¬ keyLt a b) (hbc : ¬ keyLt b c) :
    ¬ keyLt a c := by
  have h1 := keyLe_of_not_keyLt hab
  have h2 := keyLe_of_not_keyLt hbc
  apply not_keyLt_of_keyLe
  unfold keyLe at h1 h2 ⊢
  rcases h2 with h2 | ⟨e2, l2⟩ <;> rcases h1 with h1 | ⟨e1, l1⟩
  · exact Or.inl (Std.lt_trans h2 h1)
  · rw [← e1]; exact Or.inl h2
  · rw [e2]; exact Or.inl h1
  · exact Or.inr ⟨e2.trans e1, by omega⟩

theorem pick_cons_some (c : Cand) (cs : List Cand) : ∃ d, pick (c :: cs) = some d := by
  simp only [pick]
  cases pick cs with
  | none => exact ⟨c, rfl⟩
  | some d => by_cases hk : keyLe (key c) (key d) <;> simp [hk]

/-- The pick is a candidate. -/
theorem pick_mem : ∀ {cs : List Cand} {d : Cand}, pick cs = some d → d ∈ cs
  | [], d, h => by simp [pick] at h
  | c :: cs, d, h => by
    simp only [pick] at h
    cases hp : pick cs with
    | none => rw [hp] at h; simp at h; simp [h]
    | some e =>
      rw [hp] at h
      by_cases hk : keyLe (key c) (key e)
      · simp [hk] at h; simp [h]
      · simp [hk] at h; subst h; exact List.mem_cons_of_mem _ (pick_mem hp)

theorem pick_none : ∀ {cs : List Cand}, pick cs = none → cs = []
  | [], _ => rfl
  | c :: cs, h => by obtain ⟨d, hd⟩ := pick_cons_some c cs; rw [hd] at h; simp at h

/-- MINIMAL: no candidate has a strictly smaller `(remaining, committed)` than
the pick. -/
theorem climber_minimal : ∀ {cs : List Cand} {d : Cand}, pick cs = some d →
    ∀ x ∈ cs, ¬ keyLt (key x) (key d)
  | [], d, h, _, _ => by simp [pick] at h
  | c :: cs, d, h, x, hx => by
    simp only [pick] at h
    cases hp : pick cs with
    | none =>
      rw [hp] at h
      simp at h
      subst h
      have hnil := pick_none hp
      subst hnil
      simp at hx
      subst hx
      exact keyLt_irrefl _
    | some e =>
      rw [hp] at h
      have ihe := climber_minimal hp
      by_cases hk : keyLe (key c) (key e)
      · simp [hk] at h
        subst h
        rcases List.mem_cons.mp hx with hxc | hxs
        · subst hxc; exact keyLt_irrefl _
        · exact not_keyLt_trans (ihe x hxs) (not_keyLt_of_keyLe hk)
      · simp [hk] at h
        subst h
        rcases List.mem_cons.mp hx with hxc | hxs
        · subst hxc
          exact not_keyLt_of_keyLe (keyLe_of_keyLt (keyLt_of_not_keyLe hk))
        · exact ihe x hxs

/-- FLEET ORDER: the pick is the FIRST least candidate — every candidate ahead
of it in fleet order has a strictly larger key, so a full tie goes to the
earliest. -/
theorem pick_first : ∀ {cs : List Cand} {d : Cand}, pick cs = some d →
    ∃ pre post, cs = pre ++ d :: post ∧ ∀ x ∈ pre, keyLt (key d) (key x)
  | [], d, h => by simp [pick] at h
  | c :: cs, d, h => by
    simp only [pick] at h
    cases hp : pick cs with
    | none =>
      rw [hp] at h; simp at h; subst h
      exact ⟨[], cs, rfl, by simp⟩
    | some e =>
      rw [hp] at h
      by_cases hk : keyLe (key c) (key e)
      · simp [hk] at h; subst h
        exact ⟨[], cs, rfl, by simp⟩
      · simp [hk] at h; subst h
        obtain ⟨pre, post, hcs, hpre⟩ := pick_first hp
        refine ⟨c :: pre, post, by simp [hcs], ?_⟩
        intro x hx
        rcases List.mem_cons.mp hx with hxc | hxs
        · subst hxc; exact keyLt_of_not_keyLe hk
        · exact hpre x hxs

-- Three characters; 0 and 1 tie on remaining 7, 1 has less committed work:
-- 1 climbs, and 0, ahead of it, has a strictly larger key.
example : pick [(0, 7, 2), (1, 7, 0), (2, 9, 0)] = some (1, 7, 0) := by decide
-- A full tie goes to the first in fleet order.
example : pick [(5, 7, 0), (3, 7, 0)] = some (5, 7, 0) := by decide

end Formal.FleetClimb
