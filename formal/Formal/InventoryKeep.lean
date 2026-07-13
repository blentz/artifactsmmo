-- @concept: inventory, characters @property: safety, liveness

/-!
# Formal.InventoryKeep

**Pure-Lean mirror of the single keep authority
(`src/artifactsmmo_cli/ai/inventory_keep.py`).**

Protection USED to be expressed as `frozenset[str]` code-sets. A code-set can
only say "keep ALL copies" — that type-level defect produced seven separate
hoard bugs (18 `copper_axe` shielded from every disposal path because the axe
was the best woodcutting tool; the whole healing stock pinned in the bag; the
BiS `target_gear | target_tools` blanket; ...). The replacement gives every
protection reason a QUANTITY, and the two caps are the MAX over their reasons:

* `keep_in_bag`  — copies that must stay in the BAG (banking is REVERSIBLE),
  max over `IN_BAG_REASONS` (7 reasons);
* `keep_owned`   — copies that must remain OWNED, bag+bank (destroying is NOT),
  max over `OWNED_REASONS` (7 reasons);
* `bankable   = bag        - keep_in_bag`
* `destroyable = (bag+bank) - keep_owned`.

`WORKING_KIT` and `COMBAT_WEAPON` feed BOTH registries (quantity 1 in each):
"keep ONE in the bag" (the copy the gather re-arm equips) and "never melt your
LAST one" are different obligations, and the second is an OWNERSHIP invariant —
`last_tool_never_melted` below is the row that hole showed up in.

## What is modelled, and what is deliberately OPAQUE

The individual reason functions (`_working_kit`, `_healing_consumable`,
`_committed_recipe`, ...) are game-data searches — a best-tool selector, a
greedy aggregate fill over held heal codes, a fuel-bounded recipe-chain walk.
They have no scalar arithmetic to mirror here, exactly like `hasGrindRung` in
`Formal.ActionApplicability`: they enter this model as an OPAQUE
`List Nat` of contributions and are pinned to the real Python end-to-end by
`formal/diff/test_inventory_keep_diff.py`, which calls the REAL
`inventory_keep.reason_quantity` for every registry member and feeds the
resulting vector to the oracle.

That is deliberate, because **the bug class lives in the COMBINATOR, not in the
reasons**. Every one of the seven hoard bugs was a reason that returned "all of
them" and a combinator that could not tell "all of them" from a quantity. So
the theorems below are about the combinator:

* `keep_dominates_each_reason` — the cap honours every reason (max dominates);
* `keep_is_a_reason` — the cap is 0 or IS one of the reasons: reasons never
  ADD (a `sum` combinator over-protects and is refuted by `keepFrom_not_sum`);
* `surplus_is_disposable` — held above the cap IS disposable. **THE property
  every hoard bug broke**: a blanket made `keep = held`, so the disposable
  quantity was 0 forever;
* `blanket_requires_keep_ge_held` — a blanket is legal only if it genuinely IS
  everything (the `KEEP_ALL` currency escape hatch, and nothing else);
* `bankable_never_eats_keep` / `destroyable_never_eats_keep` — SAFETY: what
  must stay never leaves;
* `destroyable_counts_bank_copies` — `keep_owned` is about OWNERSHIP, so a copy
  in the BANK satisfies it (a bag-only accounting under-reports the disposable
  surplus and re-hoards).

Task 3 of the inventory keep-unification epic.
-/

namespace Formal.InventoryKeep

/-! ## The registry contributions and the two caps. -/

/-- `inventory_keep.KEEP_ALL` — the sentinel "keep every copy" quantity. The ONLY
reason that returns it is `CURRENCY` (`tasks_coin`); every other reason must
express its protection as a finite, item-specific quantity. It is a plain Nat
here, so a blanket is just a very large cap — `blanket_requires_keep_ge_held`
below is what makes "very large" mean "legally total". -/
def keepAll : Nat := 1000000

/-- The combinator: a cap is the MAX over its reasons' quantities, and 0 when no
reason applies (Python `max(reason_quantity(r, ...) for r in REASONS)` over a
non-empty registry; `keepFrom []` = 0 is the vacuous-registry limit). -/
def keepFrom (contribs : List Nat) : Nat := contribs.foldl max 0

/-- `keep_in_bag` — the max over the IN_BAG registry's contributions. -/
def keepInBag (inBag : List Nat) : Nat := keepFrom inBag

/-- `keep_owned` — the max over the OWNED registry's contributions. -/
def keepOwned (owned : List Nat) : Nat := keepFrom owned

/-- `bankable` — bag copies beyond `keep_in_bag`. Nat truncation is the Python
`max(0, ...)`. -/
def bankable (bag : Nat) (inBag : List Nat) : Nat := bag - keepInBag inBag

/-- `destroyable` — bag+bank copies beyond `keep_owned`. The BANK copies are
counted, because `keep_owned` is about OWNERSHIP: a copy safe in the bank
already satisfies the demand, so it must not also pin a bag copy. -/
def destroyable (bag bank : Nat) (owned : List Nat) : Nat :=
  (bag + bank) - keepOwned owned

/-! ## Foldl-max scaffolding. -/

/-- The accumulator is a lower bound of the fold. -/
theorem le_foldl_max (a : Nat) : ∀ (l : List Nat), a ≤ l.foldl max a := by
  intro l
  induction l generalizing a with
  | nil => simp
  | cons c cs ih =>
    have h1 : a ≤ max a c := Nat.le_max_left a c
    exact Nat.le_trans h1 (ih (max a c))

/-- Every member of the list is a lower bound of the fold. -/
theorem mem_le_foldl_max (a q : Nat) : ∀ (l : List Nat), q ∈ l → q ≤ l.foldl max a := by
  intro l
  induction l generalizing a with
  | nil => intro h; cases h
  | cons c cs ih =>
    intro h
    rcases List.mem_cons.mp h with hq | hq
    · subst hq
      exact Nat.le_trans (Nat.le_max_right a q) (le_foldl_max (max a q) cs)
    · exact ih (max a c) hq

/-- The fold returns the accumulator or a member of the list — it never invents a
value (in particular it never SUMS). -/
theorem foldl_max_eq_or_mem (a : Nat) :
    ∀ (l : List Nat), l.foldl max a = a ∨ l.foldl max a ∈ l := by
  intro l
  induction l generalizing a with
  | nil => exact Or.inl rfl
  | cons c cs ih =>
    simp only [List.foldl_cons]
    rcases ih (max a c) with h | h
    · rcases Nat.le_total a c with hle | hle
      · exact Or.inr (by rw [h, Nat.max_eq_right hle]; simp)
      · exact Or.inl (by rw [h, Nat.max_eq_left hle])
    · exact Or.inr (List.mem_cons_of_mem c h)

/-! ## The load-bearing combinator properties. -/

/-- **A reason's quantity is always honoured** — the cap dominates every
individual contribution. (`max` dominates each argument: this is what makes the
registry a set of DEMANDS rather than a set of votes.) -/
theorem keep_dominates_each_reason (contribs : List Nat) (q : Nat)
    (h : q ∈ contribs) : keepFrom contribs ≥ q :=
  mem_le_foldl_max 0 q contribs h

/-- **Reasons never ADD**: the cap is 0 or it IS one of the reasons' quantities.
A `sum` combinator would over-protect — the cap would exceed every single
demand and re-create the hoard from the other side. -/
theorem keep_is_a_reason (contribs : List Nat) :
    keepFrom contribs = 0 ∨ keepFrom contribs ∈ contribs :=
  foldl_max_eq_or_mem 0 contribs

/-- An empty registry protects nothing. -/
theorem keepFrom_nil : keepFrom [] = 0 := rfl

/-- Concrete refutation of the `sum` combinator: two reasons wanting 3 and 4
copies keep 4, not 7. -/
theorem keepFrom_not_sum : keepFrom [3, 4] = 4 ∧ keepFrom [3, 4] ≠ 3 + 4 := by
  constructor
  · decide
  · decide

/-- **SAFETY (bag)**: what must stay never leaves. Banking the `bankable`
quantity leaves at least `min bag keep` copies in the bag — i.e. the whole keep
demand, or everything held if the bag is short of it. -/
theorem bankable_never_eats_keep (bag : Nat) (inBag : List Nat) :
    bag - bankable bag inBag ≥ min bag (keepInBag inBag) := by
  unfold bankable
  omega

/-- **SAFETY (owned)**: destroying the `destroyable` quantity leaves at least
`min owned keep_owned` copies owned. -/
theorem destroyable_never_eats_keep (bag bank : Nat) (owned : List Nat) :
    (bag + bank) - destroyable bag bank owned ≥ min (bag + bank) (keepOwned owned) := by
  unfold destroyable
  omega

/-- **THE property every hoard bug broke (bag)**: bag copies above the cap ARE
bankable. A blanket set `keep = bag`, so `bankable` was 0 forever and 18 axes
sat in the bag through every DepositAll. -/
theorem surplus_is_disposable (bag : Nat) (inBag : List Nat)
    (h : bag > keepInBag inBag) : bankable bag inBag > 0 := by
  unfold bankable
  omega

/-- **THE property every hoard bug broke (owned)**: owned copies above the
`keep_owned` cap ARE destroyable (recycle / sell / discard). -/
theorem owned_surplus_is_destroyable (bag bank : Nat) (owned : List Nat)
    (h : bag + bank > keepOwned owned) : destroyable bag bank owned > 0 := by
  unfold destroyable
  omega

/-- **No silent blankets (bag)**: nothing bankable ⇒ the cap genuinely IS
everything held. The contrapositive of `surplus_is_disposable`, stated as the
audit the old code-sets could not pass. -/
theorem blanket_requires_keep_ge_held (bag : Nat) (inBag : List Nat)
    (h : bankable bag inBag = 0) : keepInBag inBag ≥ bag := by
  unfold bankable at h
  omega

/-- **No silent blankets (owned)**: nothing destroyable ⇒ `keep_owned` IS the
whole owned pile. Only `KEEP_ALL` (currency) may legitimately reach this. -/
theorem owned_blanket_requires_keep_ge_owned (bag bank : Nat) (owned : List Nat)
    (h : destroyable bag bank owned = 0) : keepOwned owned ≥ bag + bank := by
  unfold destroyable at h
  omega

/-- Exact quantity on the surplus branch: banking sheds precisely down to the
cap, never below it. -/
theorem bankable_sheds_to_cap (bag : Nat) (inBag : List Nat)
    (h : bag ≥ keepInBag inBag) : bag - bankable bag inBag = keepInBag inBag := by
  unfold bankable
  omega

/-- **Bank copies count toward ownership**: a copy already in the bank satisfies
`keep_owned`, so it frees a bag copy for disposal. A bag-only accounting
(`destroyable = bag - keep_owned`) under-reports the surplus — the third mutant
in `INVENTORY_KEEP_MUTATIONS`. -/
theorem destroyable_counts_bank_copies (bag bank : Nat) (owned : List Nat) :
    destroyable bag bank owned ≥ destroyable bag 0 owned := by
  unfold destroyable
  omega

/-- Monotone in the bank: more banked copies never SHRINK the destroyable
surplus. -/
theorem destroyable_mono_in_bank (bag bank bank' : Nat) (owned : List Nat)
    (h : bank ≤ bank') :
    destroyable bag bank owned ≤ destroyable bag bank' owned := by
  unfold destroyable
  omega

/-! ## Non-vacuity witnesses.

Each hypothesis above is satisfiable, and the headline bug is refuted by a
concrete evaluation of the model on the exact numbers of the live incident. -/

/-- **The axe bug, refuted.** `WORKING_KIT` contributes 1 (keep ONE working
tool), every other in-bag reason contributes 0, 18 are held: 17 bank. Under the
old code-set the contribution was "all 18" and `bankable` was 0. -/
theorem copper_axe_hoard_refuted :
    keepInBag [0, 0, 0, 0, 1, 0, 0] = 1 ∧ bankable 18 [0, 0, 0, 0, 1, 0, 0] = 17 := by
  constructor
  · decide
  · decide

/-- The `surplus_is_disposable` hypothesis is SATISFIABLE (it is exactly the
axe row above), so the theorem is not vacuous. -/
theorem surplus_is_disposable_nonvacuous :
    18 > keepInBag [0, 0, 0, 0, 1, 0, 0] ∧ bankable 18 [0, 0, 0, 0, 1, 0, 0] > 0 := by
  constructor
  · decide
  · exact surplus_is_disposable 18 [0, 0, 0, 0, 1, 0, 0] (by decide)

/-- The `blanket_requires_keep_ge_held` hypothesis is SATISFIABLE, and the ONLY
legal witness is a genuine total: `CURRENCY` returns `KEEP_ALL`, so nothing of
the 40 `tasks_coin` held is destroyable — and the theorem confirms the cap
really does cover every held copy. (OWNED vector, in registry order: currency,
active_task, combat_weapon, working_kit, equipped, gear_demand, recipe_demand.) -/
theorem currency_blanket_is_the_only_legal_blanket :
    destroyable 40 0 [keepAll, 0, 0, 0, 0, 0, 0] = 0
      ∧ keepOwned [keepAll, 0, 0, 0, 0, 0, 0] ≥ 40 + 0 := by
  refine ⟨by decide, ?_⟩
  exact owned_blanket_requires_keep_ge_owned 40 0 [keepAll, 0, 0, 0, 0, 0, 0] (by decide)

/-- The `destroyable_counts_bank_copies` inequality is STRICT in the live case:
1 axe in the bag, 5 in the bank, a gear demand of 2 (and the kit/recipe reasons
asking 1 each) ⇒ 4 destroyable. A bag-only accounting would report 0 and hoard
the 5 banked copies forever. -/
theorem destroyable_bank_copies_nonvacuous :
    destroyable 1 5 [0, 0, 0, 1, 0, 2, 1] = 4 ∧ destroyable 1 0 [0, 0, 0, 1, 0, 2, 1] = 0 := by
  constructor
  · decide
  · decide

/-- **The last-tool melt, refuted.** The DESTRUCTION dual of the axe hoard: once
the one bag copy of the best woodcutting tool is spent or equipped, all 18 copies
sit in the BANK. With `WORKING_KIT` filed under the BAG cap ONLY, every owned
reason contributes 0 (an un-profiled tool has `EQUIPPABLE_KEEP` suppressed), so
`keepOwned = 0` and the bank drain is licensed to destroy ALL 18 — zero tools
left. `WORKING_KIT`/`COMBAT_WEAPON` also feed the OWNED registry (contribution 1,
4th slot), so 17 are destroyable and the last one is not. -/
theorem last_tool_never_melted :
    keepOwned [0, 0, 0, 1, 0, 0, 0] = 1
      ∧ destroyable 0 18 [0, 0, 0, 1, 0, 0, 0] = 17
      ∧ destroyable 0 18 [0, 0, 0, 0, 0, 0, 0] = 18 := by
  refine ⟨by decide, by decide, by decide⟩

/-- The healing-stock row: an aggregate target of 5 greedily filled across the
held heals (chicken 3 + apple 2) keeps 3 of the 3 chickens and 2 of the 10
apples — 8 apples bank. Under the old code-set BOTH stacks were pinned. -/
theorem healing_stock_surplus_banks :
    bankable 3 [0, 0, 3, 0, 0, 0, 0] = 0 ∧ bankable 10 [0, 0, 2, 0, 0, 0, 0] = 8 := by
  constructor
  · decide
  · decide

end Formal.InventoryKeep
