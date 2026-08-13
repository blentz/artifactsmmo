-- @concept: planner, action, cost @property: monotonicity, safety
/-
Cost model for the BATCHED gather edge (`GatherAction.cost`,
`src/artifactsmmo_cli/ai/actions/gathering.py`).

A* optimality requires every edge cost to be non-negative
(`Formal.ActionCostNonneg`). Task 5 gave `GatherAction` a `quantity` and made
its cost scale with it — multiplying by a planner-chosen quantity is exactly
where that could break, so it is proved here rather than assumed.

## What the shipped code actually computes

```
static = (6.0 + dist) * quantity
static += min(banked, quantity) * _BANKED_REGATHER_PENALTY
static += GATHER_LOADOUT_PENALTY        # once, not scaled — CONDITIONAL
```

`gatherCost` below models the first two lines exactly, generalizing the
literal `6.0` to a `base` parameter (matching the `distanceCost`/`qtyCost`
convention in `Formal.ActionCostNonneg`). The `(6.0 + dist) * quantity` shape
— travel distance charged once PER UNIT rather than once per trip — is
deliberate, not a bug: it reproduces the pre-batching cost of the equivalent
singleton gather chain exactly, so batching is cost-neutral and changes only
reachability. It is modeled as-is, not "fixed".

## Deliberately NOT modeled here

* **`GATHER_LOADOUT_PENALTY`** — added at most once per action regardless of
  `quantity` (a single loadout swap serves the whole batch), and only when the
  equipped loadout differs from the resource's optimal one. It is a
  quantity-independent, non-negative additive constant, so it cannot affect
  either non-negativity (adding a non-negative constant preserves `≥ 0`) or
  monotonicity in `quantity` (it does not vary with `quantity`). Omitting it
  changes neither theorem's truth, only its statement's directness.
* **`learned_cost_pure` / `LearningStore` blending** — when a `LearningStore`
  is passed, `cost` folds in a per-unit learned figure scaled by `quantity`
  and a success-rate-derived divisor (`Formal.ActionCostNonneg.learnedCost`
  already proves that blend non-negative in general, via
  `learnedCost_nonneg`, for any non-negative `static` and `learned` and any
  `rateFloor > 0`). This module's `gatherCost` is exactly the `static`
  argument to that blend for the batched gather edge — the boundary this file
  covers is the STATIC term the planner search compares when no history has
  accumulated yet, and the term `learnedCost` is proved non-negative around.
  It does not re-derive `learnedCost_nonneg`; it supplies one more sound input
  to it.

Lean core only — no mathlib. Rat order via `Rat.add_nonneg`, `Rat.mul_nonneg`,
`Rat.mul_le_mul_of_nonneg_{left,right}`, `Rat.add_le_add_{left,right}`, and Nat
`min`/cast facts, matching `Formal.ActionCostNonneg`'s house style.
-/
import Formal.Extracted.CostCore

namespace Formal.GatherCost

/-- The static term of `GatherAction.cost`: `(base + dist) * qty` (distance
charged once per unit, per the controller ruling above) plus
`min(banked, qty) * penalty` (only the units this batch shares with the bank
are penalized). `base`/`dist`/`penalty` are `Rat` to match the production
formula's float arithmetic exactly; `qty`/`banked` are `Nat`, matching
`effective_quantity` and `bank_items` counts, which are never negative. -/
def gatherCost (base dist penalty : Rat) (qty banked : Nat) : Rat :=
  (base + dist) * (qty : Rat) + ((min banked qty : Nat) : Rat) * penalty

/-- Non-negativity: the obligation `Formal.ActionCostNonneg` discharges for
every action kind, now for any planner-chosen quantity. -/
theorem gather_cost_nonneg (base dist penalty : Rat) (qty banked : Nat)
    (hb : 0 ≤ base) (hd : 0 ≤ dist) (hp : 0 ≤ penalty) :
    0 ≤ gatherCost base dist penalty qty banked := by
  unfold gatherCost
  have hbd : 0 ≤ base + dist := Rat.add_nonneg hb hd
  have hq : (0 : Rat) ≤ (qty : Rat) := Rat.natCast_nonneg
  have hmb : (0 : Rat) ≤ ((min banked qty : Nat) : Rat) := Rat.natCast_nonneg
  have h1 : 0 ≤ (base + dist) * (qty : Rat) := Rat.mul_nonneg hbd hq
  have h2 : 0 ≤ ((min banked qty : Nat) : Rat) * penalty := Rat.mul_nonneg hmb hp
  exact Rat.add_nonneg h1 h2

/-- Monotone in the batch size: a bigger batch is never cheaper, so the
planner cannot manufacture a cheaper plan by inflating a quantity. Both
summands are individually monotone in `qty` under non-negative coefficients —
`(base + dist) ≥ 0` for the first, and `min banked ·` is monotone with
`penalty ≥ 0` for the second — so the sum is too. -/
theorem gather_cost_monotone (base dist penalty : Rat) (q₁ q₂ banked : Nat)
    (h : q₁ ≤ q₂) (hb : 0 ≤ base) (hd : 0 ≤ dist) (hp : 0 ≤ penalty) :
    gatherCost base dist penalty q₁ banked
      ≤ gatherCost base dist penalty q₂ banked := by
  unfold gatherCost
  have hbd : 0 ≤ base + dist := Rat.add_nonneg hb hd
  have hqcast : (q₁ : Rat) ≤ (q₂ : Rat) := by exact_mod_cast h
  have hterm1 : (base + dist) * (q₁ : Rat) ≤ (base + dist) * (q₂ : Rat) :=
    Rat.mul_le_mul_of_nonneg_left hqcast hbd
  have hminnat : min banked q₁ ≤ min banked q₂ := by omega
  have hmincast : ((min banked q₁ : Nat) : Rat) ≤ ((min banked q₂ : Nat) : Rat) := by
    exact_mod_cast hminnat
  have hterm2 : ((min banked q₁ : Nat) : Rat) * penalty
      ≤ ((min banked q₂ : Nat) : Rat) * penalty :=
    Rat.mul_le_mul_of_nonneg_right hmincast hp
  calc (base + dist) * (q₁ : Rat) + ((min banked q₁ : Nat) : Rat) * penalty
      ≤ (base + dist) * (q₂ : Rat) + ((min banked q₁ : Nat) : Rat) * penalty :=
        Rat.add_le_add_right.mpr hterm1
    _ ≤ (base + dist) * (q₂ : Rat) + ((min banked q₂ : Nat) : Rat) * penalty :=
        Rat.add_le_add_left.mpr hterm2

/-- `qty = 1` is the pre-batching edge cost exactly: with at least one banked
unit, `min banked 1 = 1`, so the whole penalty term applies once — the same
shape a singleton (unbatched) gather always had. -/
theorem gather_cost_one_is_base (base dist penalty : Rat) (banked : Nat)
    (h : 1 ≤ banked) :
    gatherCost base dist penalty 1 banked = (base + dist) + penalty := by
  unfold gatherCost
  have hmin : min banked 1 = 1 := by omega
  rw [hmin]
  simp

/-- Non-vacuity check, CONSTRUCTIVE rather than prose: these only typecheck if
`gather_cost_nonneg`/`gather_cost_monotone`'s hypotheses (`0 ≤ base/dist/
penalty`, `q₁ ≤ q₂`) are jointly satisfiable, applied at an unmistakably
satisfying point (all-zero base/dist/penalty, a real batch-size jump 3 → 9).
Contrast `Formal.MinGatherStepsBound`'s `PosRecipes`, which really can fail —
these side conditions cannot, so the witness is a one-line application rather
than a hunt for a counterexample-free corner. (A concrete NUMERIC pin of the
formula's VALUE — e.g. `(6+3)*5 + min(7,5)*100 = 545` — is carried instead by
the differential harness's `test_banked_exceeds_qty` against the live oracle:
this codebase's `Rat.add`/`Rat.mul` route through well-founded-recursive
`Nat.gcd` normalization, which does not reduce under kernel `decide` for
compound arithmetic the way single-literal comparisons like
`ActionCostNonneg.rateFloorProd_pos` do, and `ActionCostNonneg` never decides a
multi-step `Rat` arithmetic chain either, for the same reason.) -/
example : gatherCost 0 0 0 3 4 ≤ gatherCost 0 0 0 9 4 :=
  gather_cost_monotone 0 0 0 3 9 4 (by omega) Rat.le_refl Rat.le_refl Rat.le_refl

example : 0 ≤ gatherCost 0 0 0 3 4 :=
  gather_cost_nonneg 0 0 0 3 4 Rat.le_refl Rat.le_refl Rat.le_refl

end Formal.GatherCost
