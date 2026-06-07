-- @concept: items, characters @property: dominance
/-
Formal model of the pure upgrade-selection cores from
`src/artifactsmmo_cli/ai/goals/upgrade_selection.py` (extracted from
`UpgradeEquipmentGoal` in `progression.py`).

The goal ranks equipment-upgrade candidates and selects one. The pure cores are:

* `best_by_value inv craft`: the higher-VALUE of an inventory pick vs a craftable
  pick; on a TIE the inventory pick wins (Python `inv.value >= craft.value`),
  since equipping an owned item is cheaper than crafting.
* `craftable_key c = (relevant, fills_empty, value, -craft_level, item_code)` and
  `inventory_key c = (relevant, value, level, item_code)`: lexicographic argmax
  sort keys. The comparator is a total PREORDER: `*_eq_imp_code` proves an `eq`
  forces equal `item_code`, so candidates with DISTINCT codes never tie (the
  winning ITEM is unique and order-independent). Candidates with the SAME code
  CAN tie: one item maps to MULTIPLE equipment slots (`ITEM_TYPE_TO_SLOTS`) and
  the finders emit one candidate per (item_code, slot) while `item_code` (not the
  slot) is the final key field — so same-code/multi-slot candidates compare equal.
  These ties are resolved FIRST-WINS by list order (the fixed slot order).
* `best_by_key`: deterministic argmax (first candidate to strictly exceed the
  running best, in list order — first-wins on ties). `bestByKey_sound` is the
  unconditional determinism guarantee: the argmax dominates every member and is a
  member, holding regardless of ties.

VALUE MODELLED AS `Int` (disclosure): `equip_value` (tiers/equip_value.py) is
`attack_sum + resistance_sum + hp_restore`, where `attack`/`resistance` are
`dict[str, int]` and `hp_restore : int`. The sum is therefore an EXACT integer;
the Python wraps it in `float(...)` but the value is always a whole number with no
fractional part and no NaN. Modelling `value : Int` is faithful: the comparisons
`>=` / `>` over these whole-number floats agree with `Int` comparison exactly. The
differential test exercises the `Int` model directly with integer values.

The comparators are modelled as `Ordering`-valued lexicographic comparisons built
from `compareLex`/`compareOn`, so the core `Std.TransCmp`/`Std.OrientedCmp`
instances synthesize automatically — giving transitivity and antisymmetry for free
and letting us prove trichotomy and argmax soundness with the Lean core `Std`
order machinery (no mathlib, no Batteries). -/

namespace Formal.UpgradeSelection

open Std

/-- An upgrade candidate, pre-resolved from game_data. `value` is the integer
`equip_value`; `relevant`/`fillsEmpty` are the two boolean rank bits. -/
structure Candidate where
  itemCode : String
  value : Int
  level : Int
  craftLevel : Int
  relevant : Bool
  fillsEmpty : Bool
deriving DecidableEq, Repr

/-- `int(bool)`: the `0/1` surrogate used in the Python key tuples. -/
def b2i (b : Bool) : Int := if b then 1 else 0

/-! ### `best_by_value`: higher value, tie → inventory. -/

/-- `best_by_value`: the higher-VALUE pick; on a tie the inventory pick wins. -/
def bestByValue (inv craft : Option Candidate) : Option Candidate :=
  match inv, craft with
  | none, c => c
  | i, none => i
  | some i, some c => if i.value ≥ c.value then some i else some c

/-! ### Lexicographic `Ordering` comparators over the key tuples.

The key is materialised as a nested tuple and compared with `compareLex`/
`compareOn`, exactly the lexicographic order Python's tuple comparison uses. The
final `String` (item_code) field means distinct-code candidates are strictly
ordered while same-code candidates compare equal (the slot is not in the key).
The `Std.TransCmp` / `Std.OrientedCmp` instances for these compositions
synthesize automatically. -/

/-- `craftable_key` comparator: lexicographic order over
`(relevant, fills_empty, value, -craft_level, item_code)`, built from
`compareLex`/`compareOn` so the Std order instances synthesize. (item_code, not
slot, is the final field — same-code candidates tie.) -/
def craftableCmp : Candidate → Candidate → Ordering :=
  compareLex (compareOn (fun c => b2i c.relevant))
    (compareLex (compareOn (fun c => b2i c.fillsEmpty))
      (compareLex (compareOn (fun c => c.value))
        (compareLex (compareOn (fun c => -c.craftLevel))
          (compareOn (fun c => c.itemCode)))))

/-- `inventory_key` comparator: lexicographic order over
`(relevant, value, level, item_code)`. -/
def inventoryCmp : Candidate → Candidate → Ordering :=
  compareLex (compareOn (fun c => b2i c.relevant))
    (compareLex (compareOn (fun c => c.value))
      (compareLex (compareOn (fun c => c.level))
        (compareOn (fun c => c.itemCode))))

instance : OrientedCmp craftableCmp :=
  inferInstanceAs (OrientedCmp (fun a b =>
    compareLex (compareOn (fun c : Candidate => b2i c.relevant))
      (compareLex (compareOn (fun c => b2i c.fillsEmpty))
        (compareLex (compareOn (fun c => c.value))
          (compareLex (compareOn (fun c => -c.craftLevel))
            (compareOn (fun c => c.itemCode))))) a b))
instance : TransCmp craftableCmp :=
  inferInstanceAs (TransCmp (fun a b =>
    compareLex (compareOn (fun c : Candidate => b2i c.relevant))
      (compareLex (compareOn (fun c => b2i c.fillsEmpty))
        (compareLex (compareOn (fun c => c.value))
          (compareLex (compareOn (fun c => -c.craftLevel))
            (compareOn (fun c => c.itemCode))))) a b))
instance : OrientedCmp inventoryCmp :=
  inferInstanceAs (OrientedCmp (fun a b =>
    compareLex (compareOn (fun c : Candidate => b2i c.relevant))
      (compareLex (compareOn (fun c => c.value))
        (compareLex (compareOn (fun c => c.level))
          (compareOn (fun c => c.itemCode)))) a b))
instance : TransCmp inventoryCmp :=
  inferInstanceAs (TransCmp (fun a b =>
    compareLex (compareOn (fun c : Candidate => b2i c.relevant))
      (compareLex (compareOn (fun c => c.value))
        (compareLex (compareOn (fun c => c.level))
          (compareOn (fun c => c.itemCode)))) a b))

/-! ### `best_by_key` (deterministic argmax). -/

/-- Fold an argmax over a list using a comparator `cmp`, keeping the running best
unless a later element compares STRICTLY greater (`cmp x best = .gt`). Mirrors the
Python `if key > best_key` loop: the first maximal element (in list order) wins. -/
def argMax (cmp : Candidate → Candidate → Ordering) : Candidate → List Candidate → Candidate
  | best, [] => best
  | best, x :: xs => argMax cmp (if cmp x best = .gt then x else best) xs

/-- `best_by_key`: argmax over a (possibly empty) list. -/
def bestByKey (cmp : Candidate → Candidate → Ordering) : List Candidate → Option Candidate
  | [] => none
  | x :: xs => some (argMax cmp x xs)

/-! ### Intent theorems.

#### (1) `best_by_value` never downgrades; tie → inventory. -/

/-- `bestByValue (some inv) (some craft)` has value ≥ both — never the strictly
worse pick. -/
theorem best_by_value_not_worse (inv craft : Candidate) :
    ∃ r, bestByValue (some inv) (some craft) = some r ∧
      inv.value ≤ r.value ∧ craft.value ≤ r.value := by
  unfold bestByValue
  by_cases h : inv.value ≥ craft.value
  · exact ⟨inv, by simp [h], le_refl _, by omega⟩
  · exact ⟨craft, by simp [h], by omega, le_refl _⟩

/-- On a TIE (`inv.value = craft.value`) the INVENTORY pick wins. -/
theorem best_by_value_tie_inv (inv craft : Candidate) (h : inv.value = craft.value) :
    bestByValue (some inv) (some craft) = some inv := by
  unfold bestByValue
  simp [h]

/-! #### (2) Each comparator is a STRICT TOTAL ORDER (trichotomy + antisymmetry +
transitivity). -/

/-- TRICHOTOMY of `craftableCmp`: always exactly one of lt/eq/gt. -/
theorem craftableCmp_trichotomy (a b : Candidate) :
    craftableCmp a b = .lt ∨ craftableCmp a b = .eq ∨ craftableCmp a b = .gt := by
  rcases h : craftableCmp a b with _ | _ | _
  · exact Or.inl rfl
  · exact Or.inr (Or.inl rfl)
  · exact Or.inr (Or.inr rfl)

/-- TRICHOTOMY of `inventoryCmp`. -/
theorem inventoryCmp_trichotomy (a b : Candidate) :
    inventoryCmp a b = .lt ∨ inventoryCmp a b = .eq ∨ inventoryCmp a b = .gt := by
  rcases h : inventoryCmp a b with _ | _ | _
  · exact Or.inl rfl
  · exact Or.inr (Or.inl rfl)
  · exact Or.inr (Or.inr rfl)

/-- ANTISYMMETRY of `craftableCmp`: `cmp b a = (cmp a b).swap`. -/
theorem craftableCmp_swap (a b : Candidate) :
    craftableCmp b a = (craftableCmp a b).swap :=
  OrientedCmp.eq_swap (cmp := craftableCmp) (a := b) (b := a)

/-- ANTISYMMETRY of `inventoryCmp`. -/
theorem inventoryCmp_swap (a b : Candidate) :
    inventoryCmp b a = (inventoryCmp a b).swap :=
  OrientedCmp.eq_swap (cmp := inventoryCmp) (a := b) (b := a)

/-- TRANSITIVITY of `craftableCmp` on the `.lt` relation. -/
theorem craftableCmp_lt_trans {a b c : Candidate}
    (hab : craftableCmp a b = .lt) (hbc : craftableCmp b c = .lt) :
    craftableCmp a c = .lt :=
  TransCmp.lt_trans hab hbc

/-- TRANSITIVITY of `inventoryCmp` on the `.lt` relation. -/
theorem inventoryCmp_lt_trans {a b c : Candidate}
    (hab : inventoryCmp a b = .lt) (hbc : inventoryCmp b c = .lt) :
    inventoryCmp a c = .lt :=
  TransCmp.lt_trans hab hbc

/-- `Ordering.then x y = .eq` forces the SECOND component `y = .eq` (and `x = .eq`).
`then` returns `x` whenever `x ≠ .eq`, so an `eq` result means `x = .eq` and the
result is `y`. -/
private theorem then_eq_imp_snd {x y : Ordering} (h : x.then y = .eq) : y = .eq := by
  cases x <;> simp_all [Ordering.then]

/-- DETERMINISM: an `eq` under `craftableCmp` FORCES equal item codes. Therefore
distinct-code candidates are strictly ordered (the winning ITEM is unique), and
any tie is between same-code candidates (one item, multiple equipment slots — the
slot is not in the key), resolved first-wins by list order. -/
theorem craftableCmp_eq_imp_code (a b : Candidate)
    (h : craftableCmp a b = .eq) : a.itemCode = b.itemCode := by
  -- An `eq` of the lex composition forces the LAST projection (item_code) to be eq.
  unfold craftableCmp compareLex at h
  replace h := then_eq_imp_snd (then_eq_imp_snd (then_eq_imp_snd (then_eq_imp_snd h)))
  exact LawfulEqCmp.eq_of_compare (cmp := compare) h

/-- DETERMINISM for `inventoryCmp`: `eq` forces equal item codes — distinct-code
candidates are strictly ordered, and any tie is between same-code candidates,
resolved first-wins by list order. -/
theorem inventoryCmp_eq_imp_code (a b : Candidate)
    (h : inventoryCmp a b = .eq) : a.itemCode = b.itemCode := by
  unfold inventoryCmp compareLex at h
  replace h := then_eq_imp_snd (then_eq_imp_snd (then_eq_imp_snd h))
  exact LawfulEqCmp.eq_of_compare (cmp := compare) h

/-! #### (3) `best_by_key` argmax soundness. -/

/-- `cmp a b ≠ .gt` is `a < b ∨ a = b`. -/
private theorem not_gt_cases {α} (cmp : α → α → Ordering) {a b : α} (h : cmp a b ≠ .gt) :
    cmp a b = .lt ∨ cmp a b = .eq := by
  rcases hh : cmp a b with _ | _ | _
  · exact Or.inl rfl
  · exact Or.inr rfl
  · exact absurd hh h

/-- `≤` is transitive over an oriented transitive comparator: `a ≤ b` and `b ≤ c`
⇒ `a ≤ c` (writing `a ≤ b` as `cmp a b ≠ .gt`). -/
private theorem dom_trans {α} (cmp : α → α → Ordering) [OrientedCmp cmp] [TransCmp cmp]
    {a b c : α} (hab : cmp a b ≠ .gt) (hbc : cmp b c ≠ .gt) : cmp a c ≠ .gt := by
  intro hac
  have hca : cmp c a = .lt := (OrientedCmp.gt_iff_lt (cmp := cmp)).mp hac
  rcases not_gt_cases cmp hab with hab' | hab' <;>
    rcases not_gt_cases cmp hbc with hbc' | hbc'
  · -- a < b < c ⇒ a < c
    have hac' : cmp a c = .lt := TransCmp.lt_trans hab' hbc'
    rw [(OrientedCmp.gt_iff_lt (cmp := cmp)).mpr hac'] at hca; cases hca
  · -- a < b, b = c ⇒ a < c
    have hac' : cmp a c = .lt := TransCmp.lt_of_lt_of_eq hab' hbc'
    rw [(OrientedCmp.gt_iff_lt (cmp := cmp)).mpr hac'] at hca; cases hca
  · -- a = b, b < c ⇒ a < c
    have hac' : cmp a c = .lt := TransCmp.lt_of_eq_of_lt hab' hbc'
    rw [(OrientedCmp.gt_iff_lt (cmp := cmp)).mpr hac'] at hca; cases hca
  · -- a = b = c ⇒ a = c, so c = a is also eq, contradicting c < a
    have hac' : cmp a c = .eq := TransCmp.eq_trans hab' hbc'
    have hca' : cmp c a = .eq := by
      have := OrientedCmp.eq_swap (cmp := cmp) (a := a) (b := c)
      rw [hac'] at this; simpa using this.symm
    rw [hca'] at hca; cases hca

/-- The argmax result dominates the seed and every list element: nothing compares
strictly greater than it. Needs only an oriented + transitive comparator. -/
theorem argMax_dominates (cmp : Candidate → Candidate → Ordering)
    [OrientedCmp cmp] [TransCmp cmp] (best : Candidate) (xs : List Candidate) :
    ∀ y ∈ (best :: xs), cmp y (argMax cmp best xs) ≠ .gt := by
  induction xs generalizing best with
  | nil =>
    intro y hy
    simp only [List.mem_singleton] at hy
    subst hy
    simp [argMax, ReflCmp.compare_self]
  | cons x xs ih =>
    intro y hy
    simp only [argMax]
    have hrefl : ∀ z : Candidate, cmp z z ≠ .gt := by
      intro z; rw [ReflCmp.compare_self (cmp := cmp)]; decide
    simp only [List.mem_cons] at hy
    -- the new running best `nb` is `x` (if x > best) or `best`.
    by_cases hx : cmp x best = .gt
    · -- nb = x. Both best and x are ≤ x.
      simp only [hx, if_true]
      have hbest_le : cmp best x ≠ .gt := by
        intro hc; rw [(OrientedCmp.gt_iff_lt (cmp := cmp)).mp hc] at hx; cases hx
      have hdom := ih x
      rcases hy with hyb | hyx | hy
      · rw [hyb]; exact dom_trans cmp hbest_le (hdom x (by simp))
      · rw [hyx]; exact dom_trans cmp (hrefl x) (hdom x (by simp))
      · exact hdom y (by simp [hy])
    · -- nb = best. Both best and x are ≤ best.
      simp only [hx, if_false]
      have hx_le : cmp x best ≠ .gt := hx
      have hdom := ih best
      rcases hy with hyb | hyx | hy
      · rw [hyb]; exact dom_trans cmp (hrefl best) (hdom best (by simp))
      · rw [hyx]; exact dom_trans cmp hx_le (hdom best (by simp))
      · exact hdom y (by simp [hy])

/-- argMax result is always a member of the seed-prefixed list. -/
theorem argMax_mem (cmp : Candidate → Candidate → Ordering)
    (best : Candidate) (xs : List Candidate) :
    argMax cmp best xs ∈ (best :: xs) := by
  induction xs generalizing best with
  | nil => simp [argMax]
  | cons x xs ih =>
    simp only [argMax]
    by_cases hx : cmp x best = .gt
    · simp only [hx, if_true]
      have := ih x
      simp only [List.mem_cons] at this ⊢
      rcases this with h | h
      · exact Or.inr (Or.inl h)
      · exact Or.inr (Or.inr h)
    · simp only [hx, if_false]
      have := ih best
      simp only [List.mem_cons] at this ⊢
      rcases this with h | h
      · exact Or.inl h
      · exact Or.inr (Or.inr h)

/-- `best_by_key` soundness: the result dominates every list member and is itself
a member of the list (when nonempty). -/
theorem bestByKey_sound (cmp : Candidate → Candidate → Ordering)
    [OrientedCmp cmp] [TransCmp cmp] (x : Candidate) (xs : List Candidate) :
    ∃ r, bestByKey cmp (x :: xs) = some r ∧
      r ∈ (x :: xs) ∧ ∀ y ∈ (x :: xs), cmp y r ≠ .gt :=
  ⟨argMax cmp x xs, rfl, argMax_mem cmp x xs, argMax_dominates cmp x xs⟩

/-! ### Non-vacuity witnesses. -/

private def cWood : Candidate :=
  { itemCode := "wooden_shield", value := 10, level := 1, craftLevel := 1,
    relevant := false, fillsEmpty := true }
private def cFish : Candidate :=
  { itemCode := "fishing_net", value := 5, level := 1, craftLevel := 1,
    relevant := false, fillsEmpty := true }

/-- best_by_value picks the higher-value shield over the weaker net. -/
example : bestByValue (some cWood) (some cFish) = some cWood := by decide

/-- A tie returns the inventory (first) pick exactly. -/
example :
    let a : Candidate := { itemCode := "a", value := 7, level := 2, craftLevel := 0,
                           relevant := true, fillsEmpty := false }
    let bb : Candidate := { itemCode := "b", value := 7, level := 3, craftLevel := 0,
                            relevant := true, fillsEmpty := false }
    bestByValue (some a) (some bb) = some a := by decide

/-- argmax over a 2-element list picks the genuinely highest craftable key. -/
example : bestByKey craftableCmp [cFish, cWood] = some cWood := by decide

/-- The comparator genuinely orders these two distinct candidates (not eq). -/
example : craftableCmp cFish cWood = .lt := by decide

/-- Two SAME-code candidates (one item, two slots) TIE under the comparator, and
the argmax keeps the FIRST in list order (first-wins). -/
example :
    let s1 : Candidate := { itemCode := "ring_of_x", value := 4, level := 1,
                            craftLevel := 1, relevant := false, fillsEmpty := true }
    let s2 : Candidate := { itemCode := "ring_of_x", value := 4, level := 1,
                            craftLevel := 1, relevant := false, fillsEmpty := true }
    craftableCmp s1 s2 = .eq ∧ bestByKey craftableCmp [s1, s2] = some s1 := by decide

end Formal.UpgradeSelection
