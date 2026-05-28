/-
Formal model of the slot-bookkeeping core of
`src/artifactsmmo_cli/ai/actions/gathering.py`
(specifically `GatherAction.is_applicable` and `GatherAction.apply`).

The Python `apply` mints `+1` of `drop_item` into the inventory dict; the
planner-projected `inventory_used` therefore increases by exactly one per
chained `apply`. The planner re-checks `is_applicable` on every popped node
(`src/artifactsmmo_cli/ai/planner.py:122`), so the per-step precondition
`inventory_free >= MIN_FREE_SLOTS` is enforced on every step of a multi-step
gather chain.

`MIN_FREE_SLOTS = 3` in the Python (it is a buffer for the executed action,
which may produce ore + random bonus drops); the planner's projection only
mints `+1`, so the precondition is comfortably tight: with `MIN_FREE_SLOTS >=
1`, `apply` cannot mint past `inventory_max`. We bake the contract as `>= k`
for any `k >= 1` and instantiate `k = 3` for the production constant.

The pure cores live in
`src/artifactsmmo_cli/ai/actions/gather_apply_core.py`; the differential test
exercises `gather_apply_pure` / `gather_is_applicable_pure` against this Lean
model.

Lean core only — no mathlib. Nat arithmetic via `omega`.
-/

namespace Formal.GatherApply

/-- Minimal inventory projection: `used` is the current slot count and `cap`
is `inventory_max`. The actual item dictionary is irrelevant to the slot-
bookkeeping safety theorem; the diff test pins the per-key bookkeeping
separately. -/
structure Inv where
  used : Nat
  cap : Nat
  deriving Repr, DecidableEq

/-- `inventory_free`. Defined symmetrically to the Python property
`WorldState.inventory_free = inventory_max - inventory_used` (with `Nat`
truncating subtraction; the invariant `used ≤ cap` is the safety claim and
is maintained by `apply` when `is_applicable` held). -/
def free (i : Inv) : Nat := i.cap - i.used

/-- `MIN_FREE_SLOTS` — the production constant from `gathering.py`. -/
def MIN_FREE_SLOTS : Nat := 3

/-- The slot half of `GatherAction.is_applicable`: True iff at least `k` free
slots remain. -/
def isApplicable (i : Inv) (k : Nat) : Bool :=
  decide (k ≤ i.cap - i.used)

/-- Planner-projection of `GatherAction.apply` over inventory slots: mint
exactly one item, leaving `cap` unchanged. The pure core's item-dict bookkeeping
is exercised by the differential test; only the slot count matters here. -/
def apply (i : Inv) : Inv := { i with used := i.used + 1 }

/-! ### Contracts. -/

/-- `is_applicable` lower-bound: a successful check guarantees the claimed
slot floor. -/
theorem is_applicable_imp_free_ge (i : Inv) (k : Nat) :
    isApplicable i k = true → k ≤ i.cap - i.used := by
  intro h
  simp [isApplicable] at h
  exact h

/-- **Per-step safety**: under the production precondition (`k ≥ 1`) and a
passing `is_applicable` check, `apply` never overflows the inventory cap. -/
theorem apply_inventory_safe (i : Inv) (k : Nat) (hk : 1 ≤ k)
    (h : isApplicable i k = true) :
    (apply i).used ≤ i.cap := by
  have hfree := is_applicable_imp_free_ge i k h
  -- k ≤ cap - used, k ≥ 1, Nat subtraction: cap - used ≥ 1 ⇒ used + 1 ≤ cap
  simp [apply]
  omega

/-- Same theorem instantiated at the production constant `MIN_FREE_SLOTS = 3`. -/
theorem apply_inventory_safe_prod (i : Inv) (h : isApplicable i MIN_FREE_SLOTS = true) :
    (apply i).used ≤ i.cap :=
  apply_inventory_safe i MIN_FREE_SLOTS (by decide) h

/-- Iterated `apply`. -/
def applyN : Inv → Nat → Inv
  | i, 0 => i
  | i, n + 1 => apply (applyN i n)

/-- `applyN` increases `used` by exactly `n`. -/
theorem applyN_used (i : Inv) (n : Nat) : (applyN i n).used = i.used + n := by
  induction n with
  | zero => simp [applyN]
  | succ m ih => simp [applyN, apply, ih]; omega

/-- `applyN` preserves `cap`. -/
theorem applyN_cap (i : Inv) (n : Nat) : (applyN i n).cap = i.cap := by
  induction n with
  | zero => simp [applyN]
  | succ m ih => simp [applyN, apply, ih]

/-- **Chain safety**: if the starting state has at least `n` free slots, then
after `n` chained `apply`s the inventory still has `used ≤ cap`. This is the
per-chain invariant the planner depends on (the planner's per-pop
`is_applicable` re-check at `planner.py:122` enforces the per-step `k ≥
MIN_FREE_SLOTS` precondition, but even under the weaker per-step `k ≥ 1`
precondition the chain stays in-band). -/
theorem chain_safe (i : Inv) (n : Nat) (hwf : i.used ≤ i.cap)
    (h : n ≤ i.cap - i.used) :
    (applyN i n).used ≤ i.cap := by
  rw [applyN_used]
  omega

/-- Witness: non-vacuous chain safety — a state with 3 free slots admits 3
chained applies without overflow. Pins production constant `MIN_FREE_SLOTS = 3`
as a real, reachable witness (not an unreachable-hypothesis dodge). -/
theorem chain_safe_min_free_witness :
    let i : Inv := { used := 5, cap := 8 }
    (applyN i 3).used ≤ i.cap := by
  decide

/-- Witness: `is_applicable` holds at the boundary `used = cap - k`. -/
theorem is_applicable_boundary_witness :
    isApplicable { used := 5, cap := 8 } 3 = true := by decide

/-- Witness: `is_applicable` fails one slot below the boundary. -/
theorem is_applicable_off_boundary_witness :
    isApplicable { used := 6, cap := 8 } 3 = false := by decide

end Formal.GatherApply
