-- @concept: npcs, items @property: safety
/-
Formal model of the slot-bookkeeping core of
`src/artifactsmmo_cli/ai/actions/npc.py`
(specifically `NpcBuyAction.is_applicable` and `NpcBuyAction.apply`).

REAL BUG #6: The pre-fix `NpcBuyAction.is_applicable` checked
`npc_location` / sell-price / gold / event tradeability but NOT
`inventory_free >= quantity`. The `apply` then blindly mints `+quantity` of
`item_code`, overflowing `inventory_max`. The verified counterexample (Python
probe): used=9, max=10, quantity=5 -> post.used=14 > 10 = cap.

The Python fix mirrors the `GatherAction` shape:
  * `is_applicable` gains a slot-floor precondition `inv_free >= quantity`.
  * `apply` asserts the same precondition before mutating (Phase-3
    OptimizeLoadout-shape defense in depth).

The pure cores live in `src/artifactsmmo_cli/ai/actions/npc_buy_core.py`;
the differential test exercises `npc_buy_is_applicable_pure` /
`npc_buy_apply_pure` against this Lean model.

Lean core only — no mathlib. Nat arithmetic via `omega`.
-/

namespace Formal.NpcBuyInventory

/-- Minimal inventory projection: `used` is the current slot count and `cap`
is `inventory_max`. Mirrors the slot-only projection used in `GatherApply`. -/
structure Inv where
  used : Nat
  cap : Nat
  deriving Repr, DecidableEq

/-- `inventory_free`. Defined symmetrically to the Python property
`WorldState.inventory_free = inventory_max - inventory_used` (Nat-truncating). -/
def free (i : Inv) : Nat := i.cap - i.used

/-- The slot+gold conjunction half of `NpcBuyAction.is_applicable`. The
non-slot/gold gates (`npc_location`, sell-price, event tradeability) are
orthogonal and live in the production method itself. -/
def isApplicable (i : Inv) (quantity gold price : Nat) : Bool :=
  decide (quantity ≤ i.cap - i.used) && decide (price * quantity ≤ gold)

/-- Planner-projection of `NpcBuyAction.apply` over inventory slots: mint
exactly `quantity` items into the `item_code` count, leaving `cap` unchanged.
The pure core's per-key bookkeeping is exercised by the differential test;
only the slot count matters here. -/
def apply (i : Inv) (quantity : Nat) : Inv :=
  { i with used := i.used + quantity }

/-! ### Contracts. -/

/-- `is_applicable` lower bound: a successful check guarantees the claimed
slot floor (the chain-safe contract). -/
theorem npc_buy_is_applicable_imp_free_ge
    (i : Inv) (quantity gold price : Nat) :
    isApplicable i quantity gold price = true → quantity ≤ i.cap - i.used := by
  intro h
  simp [isApplicable] at h
  exact h.1

/-- Companion lower bound on the gold component. -/
theorem npc_buy_is_applicable_imp_gold_ge
    (i : Inv) (quantity gold price : Nat) :
    isApplicable i quantity gold price = true → price * quantity ≤ gold := by
  intro h
  simp [isApplicable] at h
  exact h.2

/-- **Per-step safety**: under the slot-floor precondition (and any
`quantity ≥ 0`), `apply` never overflows the inventory cap. This is the
post-fix contract — pre-fix `is_applicable` lacked the slot check, so the
hypothesis was vacuously False on overflow cases and `apply` overran. -/
theorem npc_buy_apply_inventory_safe
    (i : Inv) (quantity gold price : Nat)
    (hwf : i.used ≤ i.cap)
    (h : isApplicable i quantity gold price = true) :
    (apply i quantity).used ≤ i.cap := by
  have hfree := npc_buy_is_applicable_imp_free_ge i quantity gold price h
  simp [apply]
  omega

/-- Iterated `apply`: chain N buys with a per-step `quantity` schedule. -/
def applyN : Inv → List Nat → Inv
  | i, [] => i
  | i, q :: rest => applyN (apply i q) rest

/-- `applyN` increases `used` by exactly the sum of the per-step quantities. -/
theorem applyN_used (i : Inv) (qs : List Nat) :
    (applyN i qs).used = i.used + qs.sum := by
  induction qs generalizing i with
  | nil => simp [applyN]
  | cons q rest ih =>
    simp [applyN, apply, ih]
    omega

/-- `applyN` preserves `cap`. -/
theorem applyN_cap (i : Inv) (qs : List Nat) :
    (applyN i qs).cap = i.cap := by
  induction qs generalizing i with
  | nil => simp [applyN]
  | cons q rest ih =>
    simp [applyN, apply, ih]

/-- **Chain safety**: if the starting state has at least `qs.sum` free slots,
then after chaining `apply` for every quantity in `qs` the inventory still
has `used ≤ cap`. This is the per-chain invariant the planner depends on
(the planner re-checks `is_applicable` on every popped node, so per-step
safety + bookkeeping gives chain safety as a corollary). -/
theorem npc_buy_chain_safe (i : Inv) (qs : List Nat)
    (hwf : i.used ≤ i.cap)
    (h : qs.sum ≤ i.cap - i.used) :
    (applyN i qs).used ≤ i.cap := by
  rw [applyN_used]
  omega

/-! ### Item-currency purchase (task #13b).

When the vendor's pay currency is NOT gold, the player pays in an inventory ITEM:
the buy needs a free slot for the bought item AND `spent` (= price*quantity) units
of the currency on hand; `apply` mints `quantity` of the item and draws the
currency stack down by `spent`. The net slot count is `used + quantity - spent`
(Nat-truncating) — the consumption can only FREE space, so cap-safety holds a
fortiori. The Python cores are `npc_buy_currency_is_applicable_pure` /
`npc_buy_currency_apply_pure`. -/

/-- Currency-purchase applicability: a free slot for the mint AND enough of the
pay currency on hand. (The gold gate is replaced by a currency-on-hand gate.) -/
def isApplicableCurrency (i : Inv) (quantity currencyOnHand spent : Nat) : Bool :=
  decide (quantity ≤ i.cap - i.used) && decide (spent ≤ currencyOnHand)

/-- Currency-purchase slot projection: net `used' = used + quantity - spent`
(mint the bought item, consume `spent` units of the currency item). -/
def applyCurrency (i : Inv) (quantity spent : Nat) : Inv :=
  { i with used := i.used + quantity - spent }

/-- Lower bound: a passing currency check guarantees the slot floor. -/
theorem npc_buy_currency_is_applicable_imp_free_ge
    (i : Inv) (quantity currencyOnHand spent : Nat) :
    isApplicableCurrency i quantity currencyOnHand spent = true →
      quantity ≤ i.cap - i.used := by
  intro h; simp [isApplicableCurrency] at h; exact h.1

/-- Companion lower bound on the currency-on-hand component. -/
theorem npc_buy_currency_is_applicable_imp_currency_ge
    (i : Inv) (quantity currencyOnHand spent : Nat) :
    isApplicableCurrency i quantity currencyOnHand spent = true →
      spent ≤ currencyOnHand := by
  intro h; simp [isApplicableCurrency] at h; exact h.2

/-- **Per-step safety** for a currency purchase: under the slot floor, the net
count never overflows the cap. The currency consumption only lowers `used`, so
this holds a fortiori versus the gold case (mint-only). -/
theorem npc_buy_currency_apply_inventory_safe
    (i : Inv) (quantity currencyOnHand spent : Nat)
    (hwf : i.used ≤ i.cap)
    (h : isApplicableCurrency i quantity currencyOnHand spent = true) :
    (applyCurrency i quantity spent).used ≤ i.cap := by
  have hfree := npc_buy_currency_is_applicable_imp_free_ge i quantity currencyOnHand spent h
  simp [applyCurrency]
  omega

/-! ### Non-vacuity witnesses (boundary cases). -/

/-- Witness: a currency buy at the slot boundary (`quantity = free`) with exactly
enough currency succeeds and stays in cap. -/
theorem currency_boundary_accepted_witness :
    let i : Inv := { used := 5, cap := 10 }
    isApplicableCurrency i 5 100 100 = true ∧ (applyCurrency i 5 100).used ≤ i.cap := by
  refine ⟨by decide, ?_⟩; decide

/-- Witness: insufficient currency-on-hand is REFUSED even with free slots and
plenty of gold (gold is irrelevant on the currency path). -/
theorem currency_short_refused_witness :
    isApplicableCurrency { used := 0, cap := 100 } 1 50 100 = false := by decide

/-- Witness: paying a currency frees net space — buying 1 item for 5 currency
units leaves `used` DOWN by 4 (10 → 6). Pins that consumption is modeled, not
dropped. -/
theorem currency_consumption_frees_space_witness :
    (applyCurrency { used := 10, cap := 20 } 1 5).used = 6 := by decide

/-- Witness: a buy of exactly `quantity = free` succeeds and stays in cap.
The boundary anchor — `quantity == free` is the contested case where the
pre-fix bug allowed overflow only when `quantity > free`, and the
strengthened post-fix check holds at equality. -/
theorem boundary_quantity_eq_free_witness :
    let i : Inv := { used := 5, cap := 10 }
    isApplicable i 5 100 1 = true ∧ (apply i 5).used ≤ i.cap := by
  refine ⟨by decide, ?_⟩
  decide

/-- Witness: `is_applicable` REFUSES one slot past the boundary (the verified
Python regression-pin scenario, generalized: used=9 cap=10 quantity=5 ⇒ free
is 1, way below quantity ⇒ refuse). Pins that the post-fix check catches the
original counterexample. -/
theorem regression_used9_cap10_qty5_refused :
    isApplicable { used := 9, cap := 10 } 5 1000 1 = false := by decide

/-- Witness: with the boundary right, a chain of two buys totaling exactly
`free` stays within cap. Non-vacuous chain safety witness. -/
theorem chain_safe_boundary_witness :
    let i : Inv := { used := 4, cap := 10 }
    (applyN i [3, 3]).used ≤ i.cap := by decide

/-- Witness: gold gate failure refuses even when slots are fine. -/
theorem gold_short_refused_witness :
    isApplicable { used := 0, cap := 100 } 5 4 1 = false := by decide

/-- Witness: both gates pass at the precise minimum gold for quantity. -/
theorem gold_exact_min_accepted_witness :
    isApplicable { used := 0, cap := 100 } 5 5 1 = true := by decide

end Formal.NpcBuyInventory
