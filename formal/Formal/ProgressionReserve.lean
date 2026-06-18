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

end Formal.ProgressionReserve
