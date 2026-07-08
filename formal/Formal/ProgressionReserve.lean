-- formal/Formal/ProgressionReserve.lean
-- @concept: core, economy @property: deduction-accounting, monotonicity
/-
Formal model of the progression-reserve arithmetic extracted from
`src/artifactsmmo_cli/ai/progression_reserve_core.py`. `reserved` is an assoc
list (code -> buy-cost); the impure layer dedups so `costOf` (first match) is
the item's reservation. Costs are `Nat` (gold prices are non-negative); the
affordability predicate is `gold ≥ price + effectiveFloor` (no signed sub),
matching the Python form exactly.
-/
namespace Formal.ProgressionReserve

abbrev Reserved := List (String × Nat)

/-- Total reserved gold = sum of costs. -/
def reserveTotal (reserved : Reserved) : Nat := (reserved.map (·.2)).sum

/-- The reservation credited to `buying` (first match), 0 if not reserved. -/
def costOf (reserved : Reserved) (buying : String) : Nat :=
  match reserved.find? (fun p => p.1 == buying) with
  | some p => p.2
  | none => 0

/-- Floor while buying `buying`: total minus its own reservation. -/
def effectiveFloor (reserved : Reserved) (buying : String) : Nat :=
  reserveTotal reserved - costOf reserved buying

/-- Affordability: gold covers price plus the effective floor. -/
def affordable (gold price : Nat) (reserved : Reserved) (buying : String) : Bool :=
  decide (gold ≥ price + effectiveFloor reserved buying)

/-! ### Role theorems. -/

/-- Membership-implied summand bound: an element's `.2` never exceeds the sum of
all `.2`. Proved mathlib-free by induction on the list. -/
theorem snd_le_sum_of_mem {p : String × Nat} :
    ∀ (l : Reserved), p ∈ l → p.2 ≤ (l.map (·.2)).sum := by
  intro l
  induction l with
  | nil => intro h; cases h
  | cons hd tl ih =>
    intro h
    rw [List.map_cons, List.sum_cons]
    cases List.mem_cons.mp h with
    | inl heq => subst heq; exact Nat.le_add_right _ _
    | inr hmem => exact Nat.le_trans (ih hmem) (Nat.le_add_left _ _)

/-- The credited reservation is a summand, so never exceeds the total. -/
theorem costOf_le_total (reserved : Reserved) (buying : String) :
    costOf reserved buying ≤ reserveTotal reserved := by
  unfold costOf reserveTotal
  cases h : reserved.find? (fun p => p.1 == buying) with
  | none => simp
  | some p =>
    have hmem : p ∈ reserved := List.mem_of_find?_eq_some h
    exact snd_le_sum_of_mem reserved hmem

/-- DEDUCTION IDENTITY: the floor plus the bought item's reservation is the full
total — a reserved item's own cost is exactly credited toward buying it. -/
theorem floor_plus_cost (reserved : Reserved) (buying : String) :
    effectiveFloor reserved buying + costOf reserved buying = reserveTotal reserved := by
  unfold effectiveFloor
  exact Nat.sub_add_cancel (costOf_le_total reserved buying)

/-- The floor never exceeds the total (the deduction only lowers it). -/
theorem effectiveFloor_le_total (reserved : Reserved) (buying : String) :
    effectiveFloor reserved buying ≤ reserveTotal reserved := by
  unfold effectiveFloor; exact Nat.sub_le _ _

/-- A non-reserved (cost 0) buy protects the FULL reserve. -/
theorem nonreserved_full (reserved : Reserved) (buying : String)
    (h : costOf reserved buying = 0) :
    effectiveFloor reserved buying = reserveTotal reserved := by
  unfold effectiveFloor; rw [h]; exact Nat.sub_zero _

/-- MONOTONE: appending more unmet targets never lowers the total (so never
loosens a discretionary gate). -/
theorem total_le_append (reserved extra : Reserved) :
    reserveTotal reserved ≤ reserveTotal (reserved ++ extra) := by
  unfold reserveTotal; simp [List.map_append, List.sum_append]

/-- ANTITONE IN FLOOR: a higher floor never turns an unaffordable buy
affordable. Stated on the underlying arithmetic the predicate decides. -/
theorem affordable_antitone_floor (gold price f1 f2 : Nat)
    (hle : f1 ≤ f2) (h : gold ≥ price + f2) : gold ≥ price + f1 := by
  omega

/-! ### Multi-leaf (joint affordability) core.

Mirrors `effective_floor_multi` in `progression_reserve_core.py`: the reserve
floor while buying EVERY leaf in `buying` TOGETHER dedups each admitted leaf's
OWN reservation from the total, not just one. `buying` is a duplicate-free key
list (callers pass a `frozenset`); the `List.Nodup` hypothesis is the model of
that no-duplicate contract — a duplicate would double-deduct that leaf's
reservation and break the floor-plus-cost identity. Consumed by
`reserve_floor_multi` / `_admit_gold_leaves`. -/

/-- The summed reservation credited to a whole leaf set (each via first-match).
Mirrors `sum(reserved.get(b, 0) for b in buying)`. -/
def sumCosts (reserved : Reserved) (buying : List String) : Nat :=
  (buying.map (costOf reserved)).sum

/-- Floor while jointly buying every leaf in `buying`: total minus the summed
own-reservations. Mirrors `reserve_total(reserved) - sum(reserved.get(b,0) ...)`. -/
def effectiveFloorMulti (reserved : Reserved) (buying : List String) : Nat :=
  reserveTotal reserved - sumCosts reserved buying

/-- SINGLETON REDUCTION: the multi floor over one leaf is exactly the
single-leaf floor. Holds unconditionally (one key can never duplicate). This is
the model-level witness of the Python generalization claim
`effective_floor_multi(r, [x]) == effective_floor(r, x)`. -/
theorem effectiveFloorMulti_singleton (reserved : Reserved) (x : String) :
    effectiveFloorMulti reserved [x] = effectiveFloor reserved x := by
  unfold effectiveFloorMulti effectiveFloor sumCosts
  simp

/-- The multi floor never exceeds the total (the deduction only lowers it).
Holds unconditionally — even a duplicate leaf set only over-deducts, and `Nat`
subtraction truncates at 0. -/
theorem effectiveFloorMulti_le_total (reserved : Reserved) (buying : List String) :
    effectiveFloorMulti reserved buying ≤ reserveTotal reserved := by
  unfold effectiveFloorMulti; exact Nat.sub_le _ _

/-! #### Deduction accounting for a distinct-key leaf set.

The floor-plus-cost identity needs `sumCosts ≤ reserveTotal` for a `Nodup`
key list. The proof threads each distinct leaf onto a DISTINCT reserved entry by
removing its matched entry and recursing on the shrunk reserve. -/

/-- Total as head-cost plus tail total. -/
theorem reserveTotal_cons (p : String × Nat) (rest : Reserved) :
    reserveTotal (p :: rest) = p.2 + reserveTotal rest := by
  unfold reserveTotal; rw [List.map_cons, List.sum_cons]

/-- `costOf` unfolded one entry: head cost when it matches, else recurse. -/
theorem costOf_cons (p : String × Nat) (rest : Reserved) (k : String) :
    costOf (p :: rest) k = if p.1 == k then p.2 else costOf rest k := by
  unfold costOf
  rw [List.find?_cons]
  cases p.1 == k <;> simp

/-- Remove the FIRST reserved entry whose key matches `k` (the entry `costOf`
credits). Non-matching reserves are returned unchanged. -/
def removeKey (reserved : Reserved) (k : String) : Reserved :=
  match reserved with
  | [] => []
  | p :: rest => if p.1 == k then rest else p :: removeKey rest k

/-- The credited cost of `k` plus the total of the reserve with `k`'s matched
entry removed is exactly the full total (removing an entry drops precisely its
own cost; when `k` is absent both the cost is 0 and nothing is removed). -/
theorem costOf_add_reserveTotal_removeKey (reserved : Reserved) (k : String) :
    costOf reserved k + reserveTotal (removeKey reserved k) = reserveTotal reserved := by
  induction reserved with
  | nil => simp [costOf, removeKey, reserveTotal]
  | cons p rest ih =>
    rw [costOf_cons, reserveTotal_cons]
    unfold removeKey
    cases hk : p.1 == k with
    | true => simp
    | false =>
      simp only [Bool.false_eq_true, if_false]
      rw [reserveTotal_cons]
      omega

/-- Removing `k`'s matched entry does not change the credited cost of any OTHER
key `k'` — the removed entry never matched `k'`, and dropping a non-matching
entry preserves the first match for `k'`. -/
theorem costOf_removeKey_of_ne (reserved : Reserved) (k k' : String) (h : k' ≠ k) :
    costOf (removeKey reserved k) k' = costOf reserved k' := by
  induction reserved with
  | nil => simp [removeKey]
  | cons p rest ih =>
    unfold removeKey
    cases hk : p.1 == k with
    | true =>
      simp only [if_true]
      rw [costOf_cons]
      have hpk : p.1 = k := eq_of_beq hk
      have hne : (p.1 == k') = false := by
        cases hb : p.1 == k' with
        | false => rfl
        | true => exact absurd (hpk ▸ eq_of_beq hb) (Ne.symm h)
      simp [hne]
    | false =>
      simp only [Bool.false_eq_true, if_false]
      rw [costOf_cons, costOf_cons, ih]

/-- KEY BOUND: for a duplicate-free leaf set the summed credited reservations
never exceed the total. Each distinct leaf is charged against a distinct
reserved entry (removed before recursing), so the sum stays a sub-total. -/
theorem sumCosts_le_total (reserved : Reserved) :
    ∀ (keys : List String), keys.Nodup → sumCosts reserved keys ≤ reserveTotal reserved := by
  intro keys
  induction keys generalizing reserved with
  | nil => intro _; simp [sumCosts]
  | cons k rest ih =>
    intro hnd
    rw [List.nodup_cons] at hnd
    obtain ⟨hnotin, hrest⟩ := hnd
    have hsum : sumCosts reserved (k :: rest)
        = costOf reserved k + sumCosts reserved rest := by
      unfold sumCosts; rw [List.map_cons, List.sum_cons]
    have hcong : sumCosts reserved rest = sumCosts (removeKey reserved k) rest := by
      unfold sumCosts
      apply congrArg List.sum
      apply List.map_congr_left
      intro x hx
      have hxne : x ≠ k := fun hh => hnotin (hh ▸ hx)
      exact (costOf_removeKey_of_ne reserved k x hxne).symm
    rw [hsum, hcong]
    have hle : sumCosts (removeKey reserved k) rest ≤ reserveTotal (removeKey reserved k) :=
      ih (removeKey reserved k) hrest
    have hA : costOf reserved k + reserveTotal (removeKey reserved k) = reserveTotal reserved :=
      costOf_add_reserveTotal_removeKey reserved k
    omega

/-- MULTI DEDUCTION IDENTITY: for a distinct-key leaf set, the joint floor plus
every leaf's own reservation is the full total — each admitted leaf's cost is
exactly credited toward buying it, with no double counting. -/
theorem floor_plus_cost_multi (reserved : Reserved) (keys : List String)
    (hnd : keys.Nodup) :
    effectiveFloorMulti reserved keys + sumCosts reserved keys = reserveTotal reserved := by
  unfold effectiveFloorMulti
  exact Nat.sub_add_cancel (sumCosts_le_total reserved keys hnd)

/-! #### Never-overspend admission (OPTIONAL, DISCHARGED).

Models `_admit_gold_leaves`'s deterministic cheapest-first prefix walk: over a
sorted candidate list `(cost, leaf)` it admits a leaf iff
`gold ≥ spent + cost + floor(trial)` where `trial` is the FULL admitted-so-far
set plus the leaf, else breaks. `floorFn` abstracts `reserve_floor_multi` over
the trial leaf list (kept abstract because the impure `max _MIN_SAFETY_FLOOR`
only RAISES the floor, so the safety bound transfers). The invariant proven:
whenever anything is admitted, `spent + floorFn(admitted) ≤ gold` — the admitted
set never overspends its own joint reserve floor. -/

/-- Sum of the costs of an admitted candidate list. -/
def spentOf (admitted : List (Nat × String)) : Nat :=
  (admitted.map (·.1)).sum

/-- The cheapest-first prefix admission walk. `acc` is the reversed admitted
prefix; a candidate joins iff gold covers spent-so-far + its cost + the floor of
the resulting leaf set, else the walk stops (prefix semantics: `break`). -/
def admitPrefix (gold : Nat) (floorFn : List String → Nat) :
    List (Nat × String) → List (Nat × String) → List (Nat × String)
  | acc, [] => acc
  | acc, (cost, leaf) :: rest =>
    let trial := acc ++ [(cost, leaf)]
    if gold ≥ spentOf trial + floorFn (trial.map (·.2)) then
      admitPrefix gold floorFn trial rest
    else
      acc

/-- The budget-safety predicate on an admitted prefix: either nothing has been
admitted, or spent gold plus the joint reserve floor of the admitted leaves fits
within `gold`. This is EXACTLY the Python guarantee (`_admit_gold_leaves` starts
from `admitted = ∅` and never overspends its own joint floor). -/
def budgetSafe (gold : Nat) (floorFn : List String → Nat)
    (admitted : List (Nat × String)) : Prop :=
  admitted = [] ∨ spentOf admitted + floorFn (admitted.map (·.2)) ≤ gold

/-- NEVER-OVERSPEND (DISCHARGED): the admission walk PRESERVES budget-safety.
Started from `acc = []` (where `budgetSafe` holds trivially — the real entry
point), the returned admitted set satisfies `budgetSafe`: it is either empty or
its spend plus its joint reserve floor is within `gold`. Proven by induction on
the remaining candidates — each admitted step passes the check against the FULL
trial leaf set, moving the prefix into the `≤ gold` branch; a failed check stops
the walk with the (already safe) prefix unchanged. Requires NO entry
precondition beyond the trivially-true `budgetSafe gold floorFn []`. -/
theorem admit_preserves_budgetSafe (gold : Nat) (floorFn : List String → Nat) :
    ∀ (rest acc : List (Nat × String)),
      budgetSafe gold floorFn acc →
      budgetSafe gold floorFn (admitPrefix gold floorFn acc rest) := by
  intro rest
  induction rest with
  | nil => intro acc hsafe; simpa [admitPrefix] using hsafe
  | cons c rest ih =>
    intro acc hsafe
    obtain ⟨cost, leaf⟩ := c
    unfold admitPrefix
    by_cases hcheck : gold ≥ spentOf (acc ++ [(cost, leaf)])
        + floorFn ((acc ++ [(cost, leaf)]).map (·.2))
    · simp only [hcheck, if_true]
      exact ih (acc ++ [(cost, leaf)]) (Or.inr hcheck)
    · simp only [hcheck, if_false]
      exact hsafe

/-- The starting state (nothing admitted) is trivially budget-safe, so the walk
from `[]` always returns a budget-safe admitted set — the corner-free
never-overspend conclusion. -/
theorem admit_from_empty_budgetSafe (gold : Nat) (floorFn : List String → Nat)
    (cands : List (Nat × String)) :
    budgetSafe gold floorFn (admitPrefix gold floorFn [] cands) :=
  admit_preserves_budgetSafe gold floorFn cands [] (Or.inl rfl)

end Formal.ProgressionReserve
