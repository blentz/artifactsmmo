-- @concept: items @property: dominance, monotonicity, totality, safety
/-
Formal model of the pure overheal-aware consumable selector extracted from
`src/artifactsmmo_cli/ai/consumable_selection.py`
(`_key`, `select_consumable`).

The legacy `_best_consumable` picked the MAX-`hp_restore` consumable
unconditionally, overhealed on a small deficit, drove the UseConsumable cost to
its 100.0 sentinel, and the planner inserted a spurious Rest. The fixed core picks
the consumable that best FITS the deficit: among usable items (inventory
`qty > 0` and `hp_restore > 0`) it is the lex-argmin on the key

    (overheal_flag, waste, minus_coverage, code)

with
  * `overheal_flag = 1 if restore > deficit else 0`  (a fitter always beats an overhealer),
  * `waste = (restore - deficit) if overheal else 0`  (least overshoot among overhealers),
  * `minus_coverage = -restore`                       (largest restore among fitters),
  * `code`                                            (deterministic final tiebreak).

The Python core compares `(int, int, int, str)` tuples with Python `min`
semantics (first-wins on ties); we mirror it over `Int` for the numeric fields and
a `Nat` surrogate `code` (the diff test maps code ↔ index 1:1, and the diff feeds
distinct codes so the final tiebreak is well-defined). `restore`, `qty` and
`deficit` are `Int`; the model ranges over ALL `Int`, while the production
invariant supplies `restore ≥ 1`, `qty ≥ 1` on usable items.

Lean core only — no mathlib. Decidable `<`/`≤` on `Int` and `Nat`; the lex order is
a hand-rolled strict order with a `Decidable` instance; argmin is a `List.foldl`
mirroring the Python `min` accumulator (first-wins on ties).
-/

namespace Formal.ConsumableSelection

/-- One consumable candidate. `code` is a `Nat` surrogate for the Python item-code
string (the diff test maps code ↔ index 1:1). `restore` is `hp_restore`, `qty` the
inventory count. -/
structure Candidate where
  code : Nat       -- item code (Nat surrogate)
  restore : Int    -- hp_restore (≥ 1 on a real consumable)
  qty : Int        -- inventory quantity (≥ 1 when present)
deriving Repr, DecidableEq

/-- A candidate is USABLE iff it has positive quantity AND positive restore
(mirrors Python `qty > 0` and `stats.hp_restore > 0`). -/
def usable (c : Candidate) : Prop := 0 < c.qty ∧ 0 < c.restore

instance (c : Candidate) : Decidable (usable c) := by unfold usable; infer_instance

/-- The usable sublist: keep exactly the usable candidates, in order (mirrors the
Python loop's `continue` skips). -/
def usableList (cs : List Candidate) : List Candidate := cs.filter (fun c => decide (usable c))

/-- `overheal_flag`: 1 when `restore > deficit`, else 0. -/
def overhealFlag (deficit : Int) (c : Candidate) : Int := if c.restore > deficit then 1 else 0

/-- `waste`: the overshoot `restore - deficit` when overhealing, else 0. -/
def waste (deficit : Int) (c : Candidate) : Int := if c.restore > deficit then c.restore - deficit else 0

/-- The sort key `(overheal_flag, waste, minus_coverage, code)`. Mirrors `_key`. -/
def key (deficit : Int) (c : Candidate) : Int × Int × Int × Nat :=
  (overhealFlag deficit c, waste deficit c, -c.restore, c.code)

/-- Strict lexicographic order on the key. `a` strictly precedes `b` iff it has a
strictly smaller overheal flag, or ties there and a strictly smaller waste, or ties
on both and strictly larger coverage (`-restore` smaller), or ties on all three and
a strictly smaller code. -/
def keyLt (deficit : Int) (a b : Candidate) : Prop :=
  overhealFlag deficit a < overhealFlag deficit b
  ∨ (overhealFlag deficit a = overhealFlag deficit b ∧ waste deficit a < waste deficit b)
  ∨ (overhealFlag deficit a = overhealFlag deficit b ∧ waste deficit a = waste deficit b
      ∧ -a.restore < -b.restore)
  ∨ (overhealFlag deficit a = overhealFlag deficit b ∧ waste deficit a = waste deficit b
      ∧ -a.restore = -b.restore ∧ a.code < b.code)

instance (deficit : Int) (a b : Candidate) : Decidable (keyLt deficit a b) := by
  unfold keyLt; infer_instance

/-- Full key tie: all four components agree. -/
def keyEq (deficit : Int) (a b : Candidate) : Prop :=
  overhealFlag deficit a = overhealFlag deficit b ∧ waste deficit a = waste deficit b
  ∧ -a.restore = -b.restore ∧ a.code = b.code

/-- The argmin step: keep `x` over `best` iff `x` strictly precedes `best`
(first-wins on ties, mirroring Python `min`). -/
def minStep (deficit : Int) (best x : Candidate) : Candidate := if keyLt deficit x best then x else best

/-- Lex-argmin over the usable sublist: `none` when nothing is usable, else fold
the tail from the head. Mirrors `select_consumable` (the Python loop only ever
considers usable items, taking the first usable as the initial `best`). -/
def selectConsumable (deficit : Int) (cs : List Candidate) : Option Candidate :=
  match usableList cs with
  | [] => none
  | c :: cs' => some (cs'.foldl (minStep deficit) c)

/-! ### `Int` trichotomy helper (core-only). -/

/-- Trichotomy of `<` on `Int`. -/
theorem int_lt_trichotomy (a b : Int) : a < b ∨ a = b ∨ b < a := by
  rcases Int.lt_trichotomy a b with h | h | h
  · exact Or.inl h
  · exact Or.inr (Or.inl h)
  · exact Or.inr (Or.inr h)

/-! ### Key lex-order facts. -/

/-- `keyLt` is irreflexive. -/
theorem keyLt_irrefl (deficit : Int) (a : Candidate) : ¬ keyLt deficit a a := by
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩ | ⟨_, _, _, h⟩)
  · exact Std.lt_irrefl h
  · exact Std.lt_irrefl h
  · exact Std.lt_irrefl h
  · exact Nat.lt_irrefl _ h

/-- `keyLt` is transitive. -/
theorem keyLt_trans (deficit : Int) {a b c : Candidate}
    (hab : keyLt deficit a b) (hbc : keyLt deficit b c) : keyLt deficit a c := by
  unfold keyLt at *
  rcases hab with h1 | ⟨e1, h1⟩ | ⟨e1, w1, h1⟩ | ⟨e1, w1, r1, h1⟩
  · rcases hbc with h2 | ⟨e2, _⟩ | ⟨e2, _, _⟩ | ⟨e2, _, _, _⟩
    · exact Or.inl (Std.lt_trans h1 h2)
    · exact Or.inl (e2 ▸ h1)
    · exact Or.inl (e2 ▸ h1)
    · exact Or.inl (e2 ▸ h1)
  · rcases hbc with h2 | ⟨e2, h2⟩ | ⟨e2, w2, _⟩ | ⟨e2, w2, _, _⟩
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, Std.lt_trans h1 h2⟩)
    · exact Or.inr (Or.inl ⟨e1.trans e2, w2 ▸ h1⟩)
    · exact Or.inr (Or.inl ⟨e1.trans e2, w2 ▸ h1⟩)
  · rcases hbc with h2 | ⟨e2, h2⟩ | ⟨e2, w2, h2⟩ | ⟨e2, w2, r2, _⟩
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, w1 ▸ h2⟩)
    · exact Or.inr (Or.inr (Or.inl ⟨e1.trans e2, w1.trans w2, Std.lt_trans h1 h2⟩))
    · exact Or.inr (Or.inr (Or.inl ⟨e1.trans e2, w1.trans w2, r2 ▸ h1⟩))
  · rcases hbc with h2 | ⟨e2, h2⟩ | ⟨e2, w2, h2⟩ | ⟨e2, w2, r2, h2⟩
    · exact Or.inl (e1 ▸ h2)
    · exact Or.inr (Or.inl ⟨e1.trans e2, w1 ▸ h2⟩)
    · exact Or.inr (Or.inr (Or.inl ⟨e1.trans e2, w1.trans w2, r1 ▸ h2⟩))
    · exact Or.inr (Or.inr (Or.inr ⟨e1.trans e2, w1.trans w2, r1.trans r2, Nat.lt_trans h1 h2⟩))

/-- `keyLt` is asymmetric. -/
theorem keyLt_asymm (deficit : Int) {a b : Candidate} (h : keyLt deficit a b) :
    ¬ keyLt deficit b a := fun h2 => keyLt_irrefl deficit a (keyLt_trans deficit h h2)

/-- TOTALITY of the key order (trichotomy): for distinct codes, exactly one of
`keyLt a b`, full key tie, `keyLt b a` holds. -/
theorem keyLt_total (deficit : Int) (a b : Candidate) :
    keyLt deficit a b ∨ keyEq deficit a b ∨ keyLt deficit b a := by
  unfold keyLt keyEq
  rcases int_lt_trichotomy (overhealFlag deficit a) (overhealFlag deficit b) with hf | hf | hf
  · exact Or.inl (Or.inl hf)
  · rcases int_lt_trichotomy (waste deficit a) (waste deficit b) with hw | hw | hw
    · exact Or.inl (Or.inr (Or.inl ⟨hf, hw⟩))
    · rcases int_lt_trichotomy (-a.restore) (-b.restore) with hr | hr | hr
      · exact Or.inl (Or.inr (Or.inr (Or.inl ⟨hf, hw, hr⟩)))
      · rcases Nat.lt_trichotomy a.code b.code with hc | hc | hc
        · exact Or.inl (Or.inr (Or.inr (Or.inr ⟨hf, hw, hr, hc⟩)))
        · exact Or.inr (Or.inl ⟨hf, hw, hr, hc⟩)
        · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inr ⟨hf.symm, hw.symm, hr.symm, hc⟩))))
      · exact Or.inr (Or.inr (Or.inr (Or.inr (Or.inl ⟨hf.symm, hw.symm, hr⟩))))
    · exact Or.inr (Or.inr (Or.inr (Or.inl ⟨hf.symm, hw⟩)))
  · exact Or.inr (Or.inr (Or.inl hf))

/-- A full key tie composes on the left of `keyLt`. -/
theorem keyEq_keyLt (deficit : Int) {a b c : Candidate}
    (he : keyEq deficit a b) (h : keyLt deficit b c) : keyLt deficit a c := by
  obtain ⟨ef, ew, er, ec⟩ := he
  unfold keyLt at h ⊢
  rcases h with h | ⟨e, h⟩ | ⟨e, w, h⟩ | ⟨e, w, r, h⟩
  · exact Or.inl (ef ▸ h)
  · exact Or.inr (Or.inl ⟨ef ▸ e, ew ▸ h⟩)
  · exact Or.inr (Or.inr (Or.inl ⟨ef ▸ e, ew ▸ w, er ▸ h⟩))
  · exact Or.inr (Or.inr (Or.inr ⟨ef ▸ e, ew ▸ w, er ▸ r, ec ▸ h⟩))

/-- A full key tie composes on the right of `keyLt`. -/
theorem keyLt_keyEq (deficit : Int) {a b c : Candidate}
    (h : keyLt deficit a b) (he : keyEq deficit b c) : keyLt deficit a c := by
  obtain ⟨ef, ew, er, ec⟩ := he
  unfold keyLt at h ⊢
  rcases h with h | ⟨e, h⟩ | ⟨e, w, h⟩ | ⟨e, w, r, h⟩
  · exact Or.inl (ef ▸ h)
  · exact Or.inr (Or.inl ⟨ef ▸ e, ew ▸ h⟩)
  · exact Or.inr (Or.inr (Or.inl ⟨ef ▸ e, ew ▸ w, er ▸ h⟩))
  · exact Or.inr (Or.inr (Or.inr ⟨ef ▸ e, ew ▸ w, er ▸ r, ec ▸ h⟩))

/-- A full key tie is incompatible with `keyLt`. -/
theorem keyEq_not_keyLt (deficit : Int) {a b : Candidate} (he : keyEq deficit a b) :
    ¬ keyLt deficit a b := by
  obtain ⟨ef, ew, er, ec⟩ := he
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩ | ⟨_, _, _, h⟩)
  · exact (Std.ne_of_lt h) ef
  · exact (Std.ne_of_lt h) ew
  · exact (Std.ne_of_lt h) er
  · exact (Nat.ne_of_lt h) ec

/-- ORDER-CONNECTION: if `y` does not beat `m` and `m` does not beat `v`, then `y`
does not beat `v` (the key order is total, so `v ≤ m ≤ y ⇒ v ≤ y`). -/
theorem keyLt_not_of_chain (deficit : Int) {m v y : Candidate}
    (hy_not_m : ¬ keyLt deficit y m) (hm_not_v : ¬ keyLt deficit m v) :
    ¬ keyLt deficit y v := by
  have hv_le_m : keyLt deficit v m ∨ keyEq deficit v m := by
    rcases keyLt_total deficit v m with h | h | h
    · exact Or.inl h
    · exact Or.inr h
    · exact absurd h hm_not_v
  have hm_le_y : keyLt deficit m y ∨ keyEq deficit m y := by
    rcases keyLt_total deficit m y with h | h | h
    · exact Or.inl h
    · exact Or.inr h
    · exact absurd h hy_not_m
  intro hyv
  have hv_le_y : keyLt deficit v y ∨ keyEq deficit v y := by
    rcases hv_le_m with hvm | hvm
    · rcases hm_le_y with hmy | hmy
      · exact Or.inl (keyLt_trans deficit hvm hmy)
      · exact Or.inl (keyLt_keyEq deficit hvm hmy)
    · rcases hm_le_y with hmy | hmy
      · exact Or.inl (keyEq_keyLt deficit hvm hmy)
      · exact Or.inr ⟨hvm.1.trans hmy.1, hvm.2.1.trans hmy.2.1,
          hvm.2.2.1.trans hmy.2.2.1, hvm.2.2.2.trans hmy.2.2.2⟩
  rcases hv_le_y with hvy | hvy
  · exact keyLt_asymm deficit hvy hyv
  · exact keyEq_not_keyLt deficit
      (⟨hvy.1.symm, hvy.2.1.symm, hvy.2.2.1.symm, hvy.2.2.2.symm⟩ : keyEq deficit y v) hyv

/-! ### `minStep` characterization + `foldl` argmin invariant. -/

/-- The step result is one of its two arguments. -/
theorem minStep_eq (deficit : Int) (best x : Candidate) :
    minStep deficit best x = best ∨ minStep deficit best x = x := by
  unfold minStep; by_cases hf : keyLt deficit x best
  · exact Or.inr (if_pos hf)
  · exact Or.inl (if_neg hf)

/-- The step result is never strictly beaten by the running best. -/
theorem minStep_not_lt_best (deficit : Int) (best x : Candidate) :
    ¬ keyLt deficit best (minStep deficit best x) := by
  unfold minStep; by_cases hf : keyLt deficit x best
  · rw [if_pos hf]; exact keyLt_asymm deficit hf
  · rw [if_neg hf]; exact keyLt_irrefl deficit best

/-- The step result is never strictly beaten by the incoming element. -/
theorem minStep_not_lt_elem (deficit : Int) (best x : Candidate) :
    ¬ keyLt deficit x (minStep deficit best x) := by
  unfold minStep; by_cases hf : keyLt deficit x best
  · rw [if_pos hf]; exact keyLt_irrefl deficit x
  · rw [if_neg hf]; exact hf

/-- The fold accumulator is always either the initial seed or one of the folded
elements. -/
theorem foldl_minStep_mem (deficit : Int) :
    ∀ (cs : List Candidate) (init : Candidate),
      cs.foldl (minStep deficit) init = init ∨ cs.foldl (minStep deficit) init ∈ cs := by
  intro cs
  induction cs with
  | nil => intro init; exact Or.inl rfl
  | cons d ds ih =>
    intro init
    rw [List.foldl_cons]
    rcases ih (minStep deficit init d) with h | h
    · rcases minStep_eq deficit init d with hs | hs
      · exact Or.inl (h.trans hs)
      · refine Or.inr ?_
        rw [h.trans hs]
        exact List.mem_cons_self
    · exact Or.inr (List.mem_cons_of_mem d h)

/-- HEADLINE INVARIANT: the fold result's key is `≤` both the seed and every folded
element (no candidate strictly beats it). -/
theorem foldl_minStep_dominates (deficit : Int) :
    ∀ (cs : List Candidate) (init : Candidate),
      (¬ keyLt deficit init (cs.foldl (minStep deficit) init)) ∧
      (∀ y ∈ cs, ¬ keyLt deficit y (cs.foldl (minStep deficit) init)) := by
  intro cs
  induction cs with
  | nil => intro init; exact ⟨keyLt_irrefl deficit init, by intro y hy; cases hy⟩
  | cons d ds ih =>
    intro init
    rw [List.foldl_cons]
    obtain ⟨ihinit, ihmem⟩ := ih (minStep deficit init d)
    have seed_not_beats : ¬ keyLt deficit init (ds.foldl (minStep deficit) (minStep deficit init d)) :=
      keyLt_not_of_chain deficit (minStep_not_lt_best deficit init d) ihinit
    refine ⟨seed_not_beats, ?_⟩
    intro y hy
    rcases List.mem_cons.mp hy with rfl | hmem
    · exact keyLt_not_of_chain deficit (minStep_not_lt_elem deficit init y) ihinit
    · exact ihmem y hmem

/-! ### Role theorems. -/

/-- TOTALITY / no-deadlock: the selector returns `none` IFF the usable sublist is
empty. A non-empty usable set always yields a winner. -/
theorem select_none_iff_no_usable (deficit : Int) (cs : List Candidate) :
    selectConsumable deficit cs = none ↔ usableList cs = [] := by
  unfold selectConsumable
  cases usableList cs with
  | nil => simp
  | cons c cs' => simp

/-- The winner is a USABLE candidate (it is a member of the usable sublist). -/
theorem select_mem (deficit : Int) {cs : List Candidate} {c : Candidate}
    (h : selectConsumable deficit cs = some c) : c ∈ usableList cs := by
  unfold selectConsumable at h
  cases hu : usableList cs with
  | nil => rw [hu] at h; simp at h
  | cons d ds =>
    rw [hu] at h
    simp only [Option.some.injEq] at h
    subst h
    rcases foldl_minStep_mem deficit ds d with hm | hm
    · rw [hm]; exact List.mem_cons_self
    · exact List.mem_cons_of_mem d hm

/-- The winner is genuinely usable: positive qty and positive restore. -/
theorem select_usable (deficit : Int) {cs : List Candidate} {c : Candidate}
    (h : selectConsumable deficit cs = some c) : usable c := by
  have hmem := select_mem deficit h
  unfold usableList at hmem
  exact of_decide_eq_true (List.mem_filter.mp hmem).2

/-- DOMINANCE: no usable candidate strictly beats the winner on the lex key.
The chosen consumable is the lex-minimum, so nothing usable is strictly better. -/
theorem select_is_min (deficit : Int) {cs : List Candidate} {c : Candidate}
    (h : selectConsumable deficit cs = some c) :
    ∀ x ∈ usableList cs, ¬ keyLt deficit x c := by
  unfold selectConsumable at h
  cases hu : usableList cs with
  | nil => rw [hu] at h; simp at h
  | cons d ds =>
    rw [hu] at h
    simp only [Option.some.injEq] at h
    subst h
    obtain ⟨hseed, hmem⟩ := foldl_minStep_dominates deficit ds d
    intro x hx
    rcases List.mem_cons.mp hx with rfl | hxmem
    · exact hseed
    · exact hmem x hxmem

/-- SAFETY (no overheal when a fitter exists): if SOME usable candidate fits the
deficit (`restore ≤ deficit`), then the WINNER also fits. Equivalently: the bug
where a big potion is chosen over a small fitting one cannot recur — whenever a
fitting consumable is usable, the chosen one is fitting, so the 100.0 overheal
cost-sentinel (and its spurious Rest) never fires. -/
theorem select_no_overheal_when_fit_exists (deficit : Int) {cs : List Candidate} {c f : Candidate}
    (h : selectConsumable deficit cs = some c)
    (hf : f ∈ usableList cs) (hfit : f.restore ≤ deficit) : c.restore ≤ deficit := by
  -- Case split on whether the winner fits; the overhealing case is contradictory.
  rcases Int.lt_or_le deficit c.restore with hover' | hle
  · -- deficit < c.restore: c overheals. But f fits and is usable, so f's overheal
    -- flag (0) is strictly below c's (1), making `keyLt f c` — contradicting that
    -- c is the lex-min over the usable list.
    exfalso
    have hnotlt : ¬ keyLt deficit f c := select_is_min deficit h f hf
    apply hnotlt
    have hf0 : overhealFlag deficit f = 0 := by unfold overhealFlag; rw [if_neg (by omega)]
    have hc1 : overhealFlag deficit c = 1 := by unfold overhealFlag; rw [if_pos hover']
    exact Or.inl (by rw [hf0, hc1]; decide)
  · exact hle

/-- MONOTONICITY (dominance among fitters): among candidates that FIT the deficit
and share a code, a STRICTLY-larger-coverage fitter is never ranked worse. If `a`
and `b` both fit, have equal code, and `a.restore ≥ b.restore` (a covers at least
as much), then the SMALLER fitter `b` does NOT strictly beat `a` — i.e. raising a
fitter's restore can only improve (or hold) its rank. This is the "prefer the
largest fitting heal" guarantee that makes the winner the best-coverage fitter. -/
theorem select_dominance_monotone (deficit : Int) (a b : Candidate)
    (ha : a.restore ≤ deficit) (hb : b.restore ≤ deficit)
    (hcode : a.code = b.code) (hge : b.restore ≤ a.restore) :
    ¬ keyLt deficit b a := by
  -- Both fit ⇒ overhealFlag = 0 and waste = 0 for both; coverage -b.restore ≥ -a.restore.
  have ha0 : overhealFlag deficit a = 0 := by unfold overhealFlag; rw [if_neg (by omega)]
  have hb0 : overhealFlag deficit b = 0 := by unfold overhealFlag; rw [if_neg (by omega)]
  have haw : waste deficit a = 0 := by unfold waste; rw [if_neg (by omega)]
  have hbw : waste deficit b = 0 := by unfold waste; rw [if_neg (by omega)]
  have hcov : ¬ (-b.restore < -a.restore) := by omega
  unfold keyLt
  rintro (h | ⟨_, h⟩ | ⟨_, _, h⟩ | ⟨_, _, hr, h⟩)
  · rw [ha0, hb0] at h; exact Std.lt_irrefl h
  · rw [haw, hbw] at h; exact Std.lt_irrefl h
  · exact hcov h
  · rw [hcode] at h; exact Nat.lt_irrefl _ h

end Formal.ConsumableSelection
