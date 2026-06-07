-- @concept: monsters @property: dominance, monotonicity, totality, reachability
/-
Formal model of the pure expected-kills monster-drop selector extracted from
`src/artifactsmmo_cli/ai/monster_drop_selection.py`
(`MonsterDropCandidate`, `_expected_kills`, `_key`, `select_monster_for_drop`).

When a needed item is DROPPED by more than one monster, the bot picks the source
minimizing the EXPECTED number of kills to acquire one unit:

    expected_kills = rate / avg_quantity   where avg_quantity = (min_q + max_q)/2

tie-broken by nearest monster tile (`distance`), then by `monster_code` — a strict
total order, so a unique deterministic winner. The Python core uses exact
`fractions.Fraction` (never float) so the proof is about the REAL ordering, not a
float surrogate; we mirror it over Lean-core `Rat` (= the `ℚ` of the comments, NO
mathlib — same core-only convention as `GatherSelection.lean` / `Scalarizer.lean`,
which write `Rat` in code and `ℚ` in prose).

This is the kills-for-drops sibling of `GatherSelection` (kills replace gathers,
monsters replace resource nodes); the lex scaffolding is reused verbatim so the
two share an identical, audited correctness story.

The diff oracle feeds candidates as `[code, rate, minQ, maxQ, dist]` integer
tuples (the surrogate `Nat` `code` is kept 1:1 with the Python `monster_code` so
the lex tie-break on code matches between sides), and compares the selected
`code` against the Python `select_monster_for_drop(...)` exactly.

INPUT-DOMAIN REALITY (from `monster_drop_selection.py` field comments + openapi
DropRateSchema):
  * `rate` is the 1-in-N drop rate, `≥ 1`.
  * `minQ ≥ 1`, `maxQ ≥ minQ` (a drop is at least 1 per success).
  * `dist ≥ 0` (Manhattan distance to the nearest monster tile).
  The MODEL ranges over all `Nat`; the monotonicity theorem only needs
  `0 < minQ + maxQ` (so the divisor is positive), which the `minQ ≥ 1` invariant
  supplies a fortiori. The other theorems hold for ALL `Nat` candidate lists.

Lean core only — no mathlib. `Rat` order/division via the core `Rat.*` lemmas
and the generic `Std.lt_trans` / `Std.ne_of_lt` / `Std.lt_irrefl`; the lex order is
a hand-rolled strict order with a `Decidable` instance; argmin is a `List.foldl`.
-/

namespace Formal.MonsterDropSelection

/-- One monster-drop candidate. `code` is a `Nat` surrogate for the Python
`monster_code` string (the diff test maps code ↔ index 1:1). -/
structure Candidate where
  code : Nat        -- monster code (Nat surrogate; the diff test maps code<->index)
  rate : Nat        -- 1-in-N drop rate, ≥ 1
  minQ : Nat        -- ≥ 1
  maxQ : Nat        -- ≥ minQ
  dist : Nat        -- Manhattan distance to nearest monster tile, ≥ 0
deriving Repr, DecidableEq

/-- Expected kills to acquire one unit: `rate / avg-yield`, exact `Rat`.
`avgYield = (minQ + maxQ) / 2`. Mirrors `_expected_kills` over the rationals
(Python `Fraction(rate) / Fraction(min+max, 2)`). -/
def expectedKills (c : Candidate) : Rat := (c.rate : Rat) / (((c.minQ + c.maxQ : Nat) : Rat) / 2)

/-- Strict lexicographic order on the key `(expectedKills, dist, code)` — the
exact `_key` tuple Python `min`s over. `a` strictly precedes `b` iff it has
strictly fewer expected kills, or ties there and is strictly nearer, or ties on
both and has a strictly smaller code. -/
def keyLt (a b : Candidate) : Prop :=
  expectedKills a < expectedKills b
  ∨ (expectedKills a = expectedKills b ∧ a.dist < b.dist)
  ∨ (expectedKills a = expectedKills b ∧ a.dist = b.dist ∧ a.code < b.code)

instance (a b : Candidate) : Decidable (keyLt a b) := by
  unfold keyLt; infer_instance

/-- The two candidates tie on the FULL key `(expectedKills, dist, code)`. -/
def keyEq (a b : Candidate) : Prop :=
  expectedKills a = expectedKills b ∧ a.dist = b.dist ∧ a.code = b.code

/-- The argmin step: keep `x` over `best` iff `x` is strictly smaller. -/
def minStep (best x : Candidate) : Candidate := if keyLt x best then x else best

/-- Lex-argmin over the list: fold the tail starting from the head, keeping the
strictly-smaller key at each step (first-wins on ties, mirroring Python `min`'s
stability). `none` on the empty list (mirrors `if not candidates: return None`). -/
def selectMonsterForDrop : List Candidate → Option Candidate
  | [] => none
  | c :: cs => some (cs.foldl minStep c)

/-! ### `Rat` and `Nat` trichotomy helpers (core-only). -/

/-- Trichotomy of `<` on `Rat`, built from `Rat.not_lt` + `Rat.le_antisymm`
(no mathlib `lt_trichotomy`). -/
theorem rat_lt_trichotomy (a b : Rat) : a < b ∨ a = b ∨ b < a := by
  by_cases h1 : a < b
  · exact Or.inl h1
  · by_cases h2 : b < a
    · exact Or.inr (Or.inr h2)
    · exact Or.inr (Or.inl (Rat.le_antisymm (Rat.not_lt.mp h2) (Rat.not_lt.mp h1)))

/-! ### Key lex-order facts. -/

/-- `keyLt` is irreflexive: nothing strictly precedes itself. -/
theorem keyLt_irrefl (a : Candidate) : ¬ keyLt a a := by
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩)
  · exact Std.lt_irrefl h
  · exact Std.lt_irrefl h
  · exact Std.lt_irrefl h

/-- `keyLt` transitivity. -/
theorem keyLt_trans {a b c : Candidate} (hab : keyLt a b) (hbc : keyLt b c) :
    keyLt a c := by
  unfold keyLt at *
  rcases hab with (h1 | ⟨e1, h1⟩ | ⟨e1, d1, h1⟩)
  · rcases hbc with (h2 | ⟨e2, h2⟩ | ⟨e2, h2⟩)
    · exact Or.inl (Std.lt_trans h1 h2)
    · exact Or.inl (e2 ▸ h1)
    · exact Or.inl (e2 ▸ h1)
  · rcases hbc with (h2 | ⟨e2, h2⟩ | ⟨e2, d2, h2⟩)
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, Std.lt_trans h1 h2⟩)
    · exact Or.inr (Or.inl ⟨e1.trans e2, d2 ▸ h1⟩)
  · rcases hbc with (h2 | ⟨e2, h2⟩ | ⟨e2, d2, h2⟩)
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, d1 ▸ h2⟩)
    · exact Or.inr (Or.inr ⟨e1.trans e2, d1.trans d2, Std.lt_trans h1 h2⟩)

/-- `keyLt` is asymmetric: `a < b` excludes `b < a`. -/
theorem keyLt_asymm {a b : Candidate} (h : keyLt a b) : ¬ keyLt b a := fun h2 =>
  keyLt_irrefl a (keyLt_trans h h2)

/-- TOTALITY of the key order (trichotomy): for any two candidates, exactly one of
`keyLt a b`, full key tie, or `keyLt b a` holds. -/
theorem keyLt_total (a b : Candidate) : keyLt a b ∨ keyEq a b ∨ keyLt b a := by
  unfold keyLt keyEq
  rcases rat_lt_trichotomy (expectedKills a) (expectedKills b) with he | he | he
  · exact Or.inl (Or.inl he)
  · rcases Nat.lt_trichotomy a.dist b.dist with hd | hd | hd
    · exact Or.inl (Or.inr (Or.inl ⟨he, hd⟩))
    · rcases Nat.lt_trichotomy a.code b.code with hc | hc | hc
      · exact Or.inl (Or.inr (Or.inr ⟨he, hd, hc⟩))
      · exact Or.inr (Or.inl ⟨he, hd, hc⟩)
      · exact Or.inr (Or.inr (Or.inr (Or.inr ⟨he.symm, hd.symm, hc⟩)))
    · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨he.symm, hd⟩)))
  · exact Or.inr (Or.inr (Or.inl he))

/-- A full key tie composes on the left of `keyLt`: `keyEq a b → keyLt b c → keyLt a c`. -/
theorem keyEq_keyLt {a b c : Candidate} (he : keyEq a b) (h : keyLt b c) : keyLt a c := by
  obtain ⟨e, d, co⟩ := he
  unfold keyLt at h ⊢
  rcases h with (h | ⟨e', h⟩ | ⟨e', d', h⟩)
  · exact Or.inl (e ▸ h)
  · exact Or.inr (Or.inl ⟨e ▸ e', d ▸ h⟩)
  · exact Or.inr (Or.inr ⟨e ▸ e', d ▸ d', co ▸ h⟩)

/-- A full key tie composes on the right of `keyLt`: `keyLt a b → keyEq b c → keyLt a c`. -/
theorem keyLt_keyEq {a b c : Candidate} (h : keyLt a b) (he : keyEq b c) : keyLt a c := by
  obtain ⟨e, d, co⟩ := he
  unfold keyLt at h ⊢
  rcases h with (h | ⟨e', h⟩ | ⟨e', d', h⟩)
  · exact Or.inl (e ▸ h)
  · exact Or.inr (Or.inl ⟨e' ▸ e, d ▸ h⟩)
  · exact Or.inr (Or.inr ⟨e' ▸ e, d' ▸ d, co ▸ h⟩)

/-- A full key tie is incompatible with `keyLt` (it has no strict component). -/
theorem keyEq_not_keyLt {a b : Candidate} (he : keyEq a b) : ¬ keyLt a b := by
  obtain ⟨e, d, co⟩ := he
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩)
  · exact (Std.ne_of_lt h) e
  · exact (Std.ne_of_lt h) d
  · exact (Std.ne_of_lt h) co

/-- ORDER-CONNECTION: if `y` does not beat `m` and `m` does not beat `v`, then `y`
does not beat `v` (the key order is total, so `v ≤ m ≤ y ⇒ v ≤ y`). -/
theorem keyLt_not_of_chain {m v y : Candidate}
    (hy_not_m : ¬ keyLt y m) (hm_not_v : ¬ keyLt m v) : ¬ keyLt y v := by
  have hv_le_m : keyLt v m ∨ keyEq v m := by
    rcases keyLt_total v m with h | h | h
    · exact Or.inl h
    · exact Or.inr h
    · exact absurd h hm_not_v
  have hm_le_y : keyLt m y ∨ keyEq m y := by
    rcases keyLt_total m y with h | h | h
    · exact Or.inl h
    · exact Or.inr h
    · exact absurd h hy_not_m
  intro hyv
  have hv_le_y : keyLt v y ∨ keyEq v y := by
    rcases hv_le_m with hvm | hvm
    · rcases hm_le_y with hmy | hmy
      · exact Or.inl (keyLt_trans hvm hmy)
      · exact Or.inl (keyLt_keyEq hvm hmy)
    · rcases hm_le_y with hmy | hmy
      · exact Or.inl (keyEq_keyLt hvm hmy)
      · exact Or.inr ⟨hvm.1.trans hmy.1, hvm.2.1.trans hmy.2.1, hvm.2.2.trans hmy.2.2⟩
  rcases hv_le_y with hvy | hvy
  · exact keyLt_asymm hvy hyv
  · exact keyEq_not_keyLt (⟨hvy.1.symm, hvy.2.1.symm, hvy.2.2.symm⟩ : keyEq y v) hyv

/-! ### `minStep` characterization + `foldl` argmin invariant. -/

/-- The step result is one of its two arguments. -/
theorem minStep_eq (best x : Candidate) : minStep best x = best ∨ minStep best x = x := by
  unfold minStep; by_cases hf : keyLt x best
  · exact Or.inr (if_pos hf)
  · exact Or.inl (if_neg hf)

/-- The step result is never strictly beaten by the running best. -/
theorem minStep_not_lt_best (best x : Candidate) : ¬ keyLt best (minStep best x) := by
  unfold minStep; by_cases hf : keyLt x best
  · rw [if_pos hf]; exact keyLt_asymm hf
  · rw [if_neg hf]; exact keyLt_irrefl best

/-- The step result is never strictly beaten by the incoming element. -/
theorem minStep_not_lt_elem (best x : Candidate) : ¬ keyLt x (minStep best x) := by
  unfold minStep; by_cases hf : keyLt x best
  · rw [if_pos hf]; exact keyLt_irrefl x
  · rw [if_neg hf]; exact hf

/-- The fold accumulator is always either the initial seed or one of the folded
elements. -/
theorem foldl_minStep_mem :
    ∀ (cs : List Candidate) (init : Candidate),
      cs.foldl minStep init = init ∨ cs.foldl minStep init ∈ cs := by
  intro cs
  induction cs with
  | nil => intro init; exact Or.inl rfl
  | cons d ds ih =>
    intro init
    rw [List.foldl_cons]
    rcases ih (minStep init d) with h | h
    · rcases minStep_eq init d with hs | hs
      · exact Or.inl (h.trans hs)
      · refine Or.inr ?_
        rw [h.trans hs]
        exact List.mem_cons_self
    · exact Or.inr (List.mem_cons_of_mem d h)

/-- HEADLINE INVARIANT: the fold result's key is `≤` both the seed and every
folded element (no candidate strictly beats it). -/
theorem foldl_minStep_dominates :
    ∀ (cs : List Candidate) (init : Candidate),
      (¬ keyLt init (cs.foldl minStep init)) ∧
      (∀ y ∈ cs, ¬ keyLt y (cs.foldl minStep init)) := by
  intro cs
  induction cs with
  | nil => intro init; exact ⟨keyLt_irrefl init, by intro y hy; cases hy⟩
  | cons d ds ih =>
    intro init
    rw [List.foldl_cons]
    obtain ⟨ihinit, ihmem⟩ := ih (minStep init d)
    have seed_not_beats : ¬ keyLt init (ds.foldl minStep (minStep init d)) :=
      keyLt_not_of_chain (minStep_not_lt_best init d) ihinit
    refine ⟨seed_not_beats, ?_⟩
    intro y hy
    rcases List.mem_cons.mp hy with rfl | hmem
    · exact keyLt_not_of_chain (minStep_not_lt_elem init y) ihinit
    · exact ihmem y hmem

/-! ### Role theorems. -/

/-- TOTALITY / no-deadlock: the selector returns `none` IFF the list is empty.
A non-empty candidate set always yields a winner (the bot never deadlocks on a
real multi-source drop choice). -/
theorem select_some_iff_nonempty (cs : List Candidate) :
    selectMonsterForDrop cs = none ↔ cs = [] := by
  cases cs with
  | nil => simp [selectMonsterForDrop]
  | cons c cs => simp [selectMonsterForDrop]

/-- The winner is a REAL candidate: `selectMonsterForDrop cs = some c → c ∈ cs`. -/
theorem select_mem {cs : List Candidate} {c : Candidate}
    (h : selectMonsterForDrop cs = some c) : c ∈ cs := by
  cases cs with
  | nil => simp [selectMonsterForDrop] at h
  | cons d ds =>
    simp only [selectMonsterForDrop, Option.some.injEq] at h
    subst h
    rcases foldl_minStep_mem ds d with hm | hm
    · rw [hm]; exact List.mem_cons_self
    · exact List.mem_cons_of_mem d hm

/-- DOMINANCE: no candidate strictly beats the winner on the lex key.
`selectMonsterForDrop cs = some c → ∀ x ∈ cs, ¬ keyLt x c`. The chosen monster is
the lex-minimum, so nothing is strictly better. -/
theorem select_is_lex_min {cs : List Candidate} {c : Candidate}
    (h : selectMonsterForDrop cs = some c) : ∀ x ∈ cs, ¬ keyLt x c := by
  cases cs with
  | nil => simp [selectMonsterForDrop] at h
  | cons d ds =>
    simp only [selectMonsterForDrop, Option.some.injEq] at h
    subst h
    obtain ⟨hseed, hmem⟩ := foldl_minStep_dominates ds d
    intro x hx
    rcases List.mem_cons.mp hx with rfl | hxmem
    · exact hseed
    · exact hmem x hxmem

/-- DOMINANCE corollary (no fewer kills at ≤ distance): if some candidate has
STRICTLY fewer expected kills than the winner, it must be strictly FARTHER. So
nothing offers strictly fewer expected kills at a `≤` distance — the winner is on
the efficiency frontier. Derived from `select_is_lex_min`. -/
theorem select_no_fewer_kills_at_le_distance {cs : List Candidate} {c : Candidate}
    (h : selectMonsterForDrop cs = some c) :
    ∀ x ∈ cs, expectedKills x < expectedKills c → c.dist < x.dist := by
  intro x hx hlt
  exact absurd (Or.inl hlt) (select_is_lex_min h x hx)

/-- MONOTONICITY: with `minQ`, `maxQ` fixed and the average yield positive, raising
the drop `rate` never decreases the expected kills (a worse — higher-`rate` —
source costs at least as many kills). The `0 < minQ + maxQ` precondition is
supplied by the `minQ ≥ 1` game invariant. -/
theorem expected_kills_mono_in_rate (a b : Candidate)
    (hmin : a.minQ = b.minQ) (hmax : a.maxQ = b.maxQ)
    (hpos : 0 < a.minQ + a.maxQ) (hrate : a.rate ≤ b.rate) :
    expectedKills a ≤ expectedKills b := by
  unfold expectedKills
  rw [hmin, hmax]
  have hden_pos : (0 : Rat) < ((b.minQ + b.maxQ : Nat) : Rat) / 2 := by
    have hsum_nat : 0 < b.minQ + b.maxQ := by rw [← hmin, ← hmax]; exact hpos
    have hsum : (0 : Rat) < ((b.minQ + b.maxQ : Nat) : Rat) := by exact_mod_cast hsum_nat
    rw [Rat.div_def]
    exact Rat.mul_pos hsum (Rat.inv_pos.mpr (by decide))
  have hinv : (0 : Rat) ≤ (((b.minQ + b.maxQ : Nat) : Rat) / 2)⁻¹ :=
    Rat.le_of_lt (Rat.inv_pos.mpr hden_pos)
  have hnum : (a.rate : Rat) ≤ (b.rate : Rat) := by exact_mod_cast hrate
  rw [Rat.div_def, Rat.div_def]
  exact Rat.mul_le_mul_of_nonneg_right hnum hinv

/-- REACHABILITY (needed quantity): killing `+1` repeatedly reaches the needed
amount. Over `Nat`, `owned + (needed - owned) ≥ needed` for ALL inputs (truncated
subtraction makes this hold both when already-owned ≥ needed and when short) — the
minimal honest reachability fact: the kill loop's drop target is attainable. -/
theorem kills_reach_needed (needed owned : Nat) :
    needed ≤ owned + (needed - owned) := by
  omega

end Formal.MonsterDropSelection
