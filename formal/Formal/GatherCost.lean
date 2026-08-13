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
static += GATHER_LOADOUT_PENALTY * quantity   # CONDITIONAL on tool mismatch
```

`gatherCost` below models all three lines exactly, generalizing the literal
`6.0` to a `base` parameter (matching the `distanceCost`/`qtyCost` convention
in `Formal.ActionCostNonneg`). The `(6.0 + dist) * quantity` shape — travel
distance charged once PER UNIT rather than once per trip — is deliberate, not
a bug: it reproduces the pre-batching cost of the equivalent singleton gather
chain exactly. It is modeled as-is, not "fixed".

## Exactly how far cost-neutrality goes

An earlier draft of this header said flatly that "batching is cost-neutral and
changes only reachability". That is true of two of the three terms and FALSE of
the third, so it is restated here per-term rather than left as a slogan the
theorems below do not cover:

* **travel** `(base + dist) * qty` and **loadout**
  `(mismatch ? loadPenalty * qty : 0)` — neutral UNCONDITIONALLY. A batch of
  `qty` costs exactly `qty` singleton charges for every `banked`, `qty` and
  `mismatch`. Proved by `gather_cost_loadout_parity` (with `loadTerm_scales`),
  which takes NO side condition.
* **bank** `min(banked, qty) * bankPenalty` — neutral only on `qty ≤ banked`.
  Below that the batch is deliberately CHEAPER than the singleton chain, by
  `(qty − min(banked, qty)) * bankPenalty`: a chain would charge the penalty on
  every gather (gathering never lowers the bank), but the deficit units the
  bank cannot cover must not be discouraged. `gather_cost_batch_parity` states
  the full-cost neutrality and carries `qty ≤ banked` as a REAL hypothesis for
  exactly this reason.

The distinction is load-bearing, not pedantry: `banked = 0` is the live
configuration of the 2026-07-05 re-arm defect, and it sits outside
`gather_cost_batch_parity`'s region. Anything the re-arm depends on must come
from the unconditional theorem.

## The loadout penalty is now MODELED, and per-unit

Until 2026-08-13 this file recorded `GATHER_LOADOUT_PENALTY` as "added at most
once per action regardless of `quantity` (a single loadout swap serves the
whole batch)", and omitted it on the grounds that a quantity-INDEPENDENT
non-negative constant can affect neither theorem. That description of the
shipped code was accurate but the code was wrong, and the error was invisible
while nothing ever set `quantity` above 1.

The penalty prices gathering with the WRONG TOOL — which a batch of N pays N
times, once per server gather — not the swap, which is separately priced as its
own `OptimizeLoadout` edge at `SWAP_COST_PER_SLOT * 2 * n`. Charged once per
action it broke this module's own cost-neutrality invariant: the singleton
chain of N gathers paid `N * penalty`, the batch paid `penalty`. Because the
term was then CONSTANT, an `OptimizeLoadout` re-arm could recover at most 6.0
against a 10.0 swap at ANY batch size, so the proven gather re-arm (live trace
2026-07-05: the bot mined with a dagger for a whole session while the ferried
pickaxe sat in the bag) died the moment the goals began sizing their gathers.
The shipped code now charges `GATHER_LOADOUT_PENALTY * quantity` and this model
carries the term, so the omission cannot silently drift again.

## Deliberately NOT modeled here

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
charged once per unit, per the controller ruling above), plus
`min(banked, qty) * bankPenalty` (only the units this batch shares with the
bank are penalized), plus `loadPenalty * qty` when the equipped loadout is
suboptimal for the resource's skill (`mismatch`) — per unit, because a batch of
`qty` is `qty` server gathers each paying for the wrong tool.
`base`/`dist`/`bankPenalty`/`loadPenalty` are `Rat` to match the production
formula's float arithmetic exactly; `qty`/`banked` are `Nat`, matching
`effective_quantity` and `bank_items` counts, which are never negative;
`mismatch` is the `Bool` the `pick_loadout_cached` comparison decides. -/
def gatherCost (base dist bankPenalty loadPenalty : Rat) (qty banked : Nat)
    (mismatch : Bool) : Rat :=
  (base + dist) * (qty : Rat) + ((min banked qty : Nat) : Rat) * bankPenalty
    + (if mismatch then loadPenalty * (qty : Rat) else 0)

/-- The conditional loadout term is non-negative on both branches. -/
theorem loadTerm_nonneg (loadPenalty : Rat) (qty : Nat) (mismatch : Bool)
    (hlp : 0 ≤ loadPenalty) :
    0 ≤ (if mismatch then loadPenalty * (qty : Rat) else 0) := by
  cases mismatch with
  | false => simp
  | true => simpa using Rat.mul_nonneg hlp (Rat.natCast_nonneg (a := qty))

/-- The conditional loadout term is monotone in `qty` on both branches — the
property a once-per-action charge destroyed, and with it the re-arm. -/
theorem loadTerm_monotone (loadPenalty : Rat) (q₁ q₂ : Nat) (mismatch : Bool)
    (h : q₁ ≤ q₂) (hlp : 0 ≤ loadPenalty) :
    (if mismatch then loadPenalty * (q₁ : Rat) else 0)
      ≤ (if mismatch then loadPenalty * (q₂ : Rat) else 0) := by
  have hqcast : (q₁ : Rat) ≤ (q₂ : Rat) := by exact_mod_cast h
  cases mismatch with
  | false => simp
  | true => simpa using Rat.mul_le_mul_of_nonneg_left hqcast hlp

/-- Non-negativity: the obligation `Formal.ActionCostNonneg` discharges for
every action kind, now for any planner-chosen quantity. -/
theorem gather_cost_nonneg (base dist bankPenalty loadPenalty : Rat)
    (qty banked : Nat) (mismatch : Bool)
    (hb : 0 ≤ base) (hd : 0 ≤ dist) (hp : 0 ≤ bankPenalty) (hlp : 0 ≤ loadPenalty) :
    0 ≤ gatherCost base dist bankPenalty loadPenalty qty banked mismatch := by
  unfold gatherCost
  have hbd : 0 ≤ base + dist := Rat.add_nonneg hb hd
  have hq : (0 : Rat) ≤ (qty : Rat) := Rat.natCast_nonneg
  have hmb : (0 : Rat) ≤ ((min banked qty : Nat) : Rat) := Rat.natCast_nonneg
  have h1 : 0 ≤ (base + dist) * (qty : Rat) := Rat.mul_nonneg hbd hq
  have h2 : 0 ≤ ((min banked qty : Nat) : Rat) * bankPenalty := Rat.mul_nonneg hmb hp
  have h3 := loadTerm_nonneg loadPenalty qty mismatch hlp
  exact Rat.add_nonneg (Rat.add_nonneg h1 h2) h3

/-- Monotone in the batch size: a bigger batch is never cheaper, so the
planner cannot manufacture a cheaper plan by inflating a quantity. All three
summands are individually monotone in `qty` under non-negative coefficients —
`(base + dist) ≥ 0` for the first, `min banked ·` is monotone with
`bankPenalty ≥ 0` for the second, and `loadTerm_monotone` for the third — so
the sum is too. -/
theorem gather_cost_monotone (base dist bankPenalty loadPenalty : Rat)
    (q₁ q₂ banked : Nat) (mismatch : Bool)
    (h : q₁ ≤ q₂) (hb : 0 ≤ base) (hd : 0 ≤ dist) (hp : 0 ≤ bankPenalty)
    (hlp : 0 ≤ loadPenalty) :
    gatherCost base dist bankPenalty loadPenalty q₁ banked mismatch
      ≤ gatherCost base dist bankPenalty loadPenalty q₂ banked mismatch := by
  unfold gatherCost
  have hbd : 0 ≤ base + dist := Rat.add_nonneg hb hd
  have hqcast : (q₁ : Rat) ≤ (q₂ : Rat) := by exact_mod_cast h
  have hterm1 : (base + dist) * (q₁ : Rat) ≤ (base + dist) * (q₂ : Rat) :=
    Rat.mul_le_mul_of_nonneg_left hqcast hbd
  have hminnat : min banked q₁ ≤ min banked q₂ := by omega
  have hmincast : ((min banked q₁ : Nat) : Rat) ≤ ((min banked q₂ : Nat) : Rat) := by
    exact_mod_cast hminnat
  have hterm2 : ((min banked q₁ : Nat) : Rat) * bankPenalty
      ≤ ((min banked q₂ : Nat) : Rat) * bankPenalty :=
    Rat.mul_le_mul_of_nonneg_right hmincast hp
  have hterm3 := loadTerm_monotone loadPenalty q₁ q₂ mismatch h hlp
  calc (base + dist) * (q₁ : Rat) + ((min banked q₁ : Nat) : Rat) * bankPenalty
        + (if mismatch then loadPenalty * (q₁ : Rat) else 0)
      ≤ (base + dist) * (q₂ : Rat) + ((min banked q₁ : Nat) : Rat) * bankPenalty
        + (if mismatch then loadPenalty * (q₁ : Rat) else 0) :=
        Rat.add_le_add_right.mpr (Rat.add_le_add_right.mpr hterm1)
    _ ≤ (base + dist) * (q₂ : Rat) + ((min banked q₂ : Nat) : Rat) * bankPenalty
        + (if mismatch then loadPenalty * (q₁ : Rat) else 0) :=
        Rat.add_le_add_right.mpr (Rat.add_le_add_left.mpr hterm2)
    _ ≤ (base + dist) * (q₂ : Rat) + ((min banked q₂ : Nat) : Rat) * bankPenalty
        + (if mismatch then loadPenalty * (q₂ : Rat) else 0) :=
        Rat.add_le_add_left.mpr hterm3

/-- `qty = 1` is the pre-batching edge cost exactly: with at least one banked
unit, `min banked 1 = 1`, so the bank term applies once, and the loadout term
`loadPenalty * 1` is likewise the single charge a singleton (unbatched) gather
always had. This is why the once-per-action bug was INVISIBLE for as long as
nothing set `quantity` above 1: at `qty = 1` scaled and unscaled coincide. -/
theorem gather_cost_one_is_base (base dist bankPenalty loadPenalty : Rat)
    (banked : Nat) (mismatch : Bool) (h : 1 ≤ banked) :
    gatherCost base dist bankPenalty loadPenalty 1 banked mismatch
      = (base + dist) + bankPenalty + (if mismatch then loadPenalty else 0) := by
  unfold gatherCost
  have hmin : min banked 1 = 1 := by omega
  rw [hmin]
  cases mismatch <;> simp

/-- The conditional loadout term is exactly `qty` copies of the SINGLETON
loadout charge. Unconditional in `banked` and `qty`: no side condition at all. -/
theorem loadTerm_scales (loadPenalty : Rat) (qty : Nat) (mismatch : Bool) :
    (if mismatch then loadPenalty * (qty : Rat) else 0)
      = (qty : Rat) * (if mismatch then loadPenalty else 0) := by
  cases mismatch <;> simp [Rat.mul_comm]

/-- TERM-BY-TERM DECOMPOSITION, and with it the parity property the gather
re-arm actually depends on — **for every `banked`, including `banked = 0`,
which is the exact configuration of the live 2026-07-05 defect**.

The whole static cost splits into `qty` copies of the singleton travel charge,
the bank term, and `qty` copies of the singleton loadout charge. Rearranged
(`Rat` subtraction is avoided so the proof stays inside Lean core):

    gatherCost − qty*(base + dist) − min(banked, qty)*bankPenalty
      = qty * (mismatch ? loadPenalty : 0)

THIS is the theorem the once-per-action loadout penalty violated. With a
constant third term the residual was `loadPenalty` instead of
`qty * loadPenalty`, so a batch was cheaper than the singleton chain it
replaced by `(qty - 1) * loadPenalty` — and since that discount did not shrink
with the batch, an `OptimizeLoadout` re-arm could never recover more than one
unit's worth of penalty at ANY size. The planner spent the discount by never
re-arming. `gather_cost_batch_parity` below cannot pin this alone: its
`qty ≤ banked` hypothesis excludes `banked = 0`, and a bot gathering a material
it has none of is precisely the case that broke. -/
theorem gather_cost_loadout_parity (base dist bankPenalty loadPenalty : Rat)
    (qty banked : Nat) (mismatch : Bool) :
    gatherCost base dist bankPenalty loadPenalty qty banked mismatch
      = (qty : Rat) * (base + dist)
        + ((min banked qty : Nat) : Rat) * bankPenalty
        + (qty : Rat) * (if mismatch then loadPenalty else 0) := by
  unfold gatherCost
  rw [loadTerm_scales]
  cases mismatch <;> simp [Rat.mul_comm]

/-- FULL-COST neutrality of batching, on the region where it actually holds:
when the bank covers the whole batch (`qty ≤ banked`, so the `min` is `qty` and
every term is linear in `qty`), one batched edge of size `qty` costs EXACTLY
`qty` times the singleton edge.

SCOPE, stated plainly because the hypothesis is real: for `banked < qty` full
neutrality is FALSE, and deliberately so. A chain of `qty` singleton gathers
would pay `bankPenalty` on every one of them (gathering never lowers the bank,
so every singleton sees `banked ≥ 1`), whereas the batch pays it only
`min(banked, qty)` times. The batch is therefore cheaper by
`(qty − min(banked, qty)) * bankPenalty` — which is the INTENT: the deficit
units the bank cannot cover must not be discouraged from being gathered
(`_BANKED_REGATHER_PENALTY`'s own docstring: "once the bank is exhausted … the
remaining deficit gathers carry no penalty, preserving optimal handling of the
unavoidable shortfall").

So the travel and loadout terms are neutral UNCONDITIONALLY
(`gather_cost_loadout_parity`), and only the bank term is region-limited. Use
this theorem for the full-cost claim and that one for anything that must hold
at `banked = 0`. -/
theorem gather_cost_batch_parity (base dist bankPenalty loadPenalty : Rat)
    (qty banked : Nat) (mismatch : Bool) (h : qty ≤ banked) :
    gatherCost base dist bankPenalty loadPenalty qty banked mismatch
      = (qty : Rat) * ((base + dist) + bankPenalty
                        + (if mismatch then loadPenalty else 0)) := by
  unfold gatherCost
  have hmin : min banked qty = qty := by omega
  rw [hmin]
  cases mismatch <;>
    simp [Rat.mul_add, Rat.add_mul, Rat.mul_comm, Rat.add_assoc]

/-- Non-vacuity check, CONSTRUCTIVE rather than prose: these only typecheck if
`gather_cost_nonneg`/`gather_cost_monotone`'s hypotheses (`0 ≤ base/dist/
bankPenalty/loadPenalty`, `q₁ ≤ q₂`) are jointly satisfiable — witnessed at the
REAL production constants (`base = 6`, `bankPenalty = 100 =
_BANKED_REGATHER_PENALTY`, `loadPenalty = 6 = GATHER_LOADOUT_PENALTY`,
`dist = 3`), not a degenerate all-zero corner where every term of the formula
vanishes. `q₁ = 3 → q₂ = 9` is a real batch-size jump, and `banked = 7` sits
strictly between `q₁` and `q₂` so the `min` term is live on both sides too.
`mismatch = true` throughout, so the loadout term is LIVE in every witness —
at `mismatch = false` the third summand is identically `0` and these examples
would say nothing about the term this file was amended to carry.
Contrast `Formal.MinGatherStepsBound`'s `PosRecipes`, which really can fail —
these side conditions cannot, so the witness is a one-line application rather
than a hunt for a counterexample-free corner.

Each single-literal hypothesis (`0 ≤ 6`, `0 ≤ 100`, `3 ≤ 9`, …) closes with
`decide` — confirmed against this build. What does NOT reduce under kernel
`decide` is a compound VALUE equality over the formula's output — e.g.
`gatherCost 6 3 100 6 5 7 true = 575` — because computing that result routes
`Rat.add`/`Rat.mul` through well-founded-recursive `Nat.gcd` normalization,
which the kernel's `decide` evaluator gets stuck unfolding for a multi-step
arithmetic chain (single-literal comparisons like
`ActionCostNonneg.rateFloorProd_pos` never hit this because there is no
arithmetic to perform, only two already-normalized literals to compare). Those
numeric VALUE pins — including the per-unit loadout term, whose whole point is
that it grows with `qty` — are carried instead by the differential harness
(`test_banked_exceeds_qty`, `test_loadout_penalty_scales_with_quantity`)
against the live oracle. -/
example : 0 ≤ gatherCost 6 3 100 6 5 7 true :=
  gather_cost_nonneg 6 3 100 6 5 7 true (by decide) (by decide) (by decide) (by decide)

example : gatherCost 6 3 100 6 3 7 true ≤ gatherCost 6 3 100 6 9 7 true :=
  gather_cost_monotone 6 3 100 6 3 9 7 true (by omega) (by decide) (by decide)
    (by decide) (by decide)

/-- Batch parity at the production constants with the loadout term LIVE: 5 units
covered by a bank of 7 cost exactly 5 singleton edges. `qty ≤ banked` is a real
side condition (5 ≤ 7), not a vacuous one. -/
example : gatherCost 6 3 100 6 5 7 true = (5 : Rat) * ((6 + 3) + 100 + 6) :=
  gather_cost_batch_parity 6 3 100 6 5 7 true (by omega)

/-- The unconditional decomposition AT `banked = 0` — the corner
`gather_cost_batch_parity` cannot reach, and the exact live configuration of the
2026-07-05 re-arm defect (a bot gathering a material it holds none of). The
loadout residual is `5 * 6`, not `6`: five units of batch pay five units of
penalty, which is the whole property the re-arm rests on.

These two check ELABORATION against the instantiated RHS, not a VALUE. The
stronger `gatherCost 6 3 100 6 5 0 true = 75` does not close here, and the
reason is the one this module's non-vacuity note gives above: `decide` gets
stuck on `instDecidableEqRat` (confirmed against this build — reduction halts
at `(((6 + 3) * ↑5 + ↑(min 0 5) * 100).add …).num`), `rfl` likewise, `simp`
leaves the goal, and `norm_num` needs mathlib, which this file does not import.
`native_decide` would close it and is not used: it would add
`Lean.ofReduceBool` to the axiom set and `gate/check_axioms.sh` would (rightly)
flag it. The value pin therefore lives in the differential harness, where
`test_loadout_term_parity_at_an_empty_bank` asserts this same point `== 75.0`
against the live oracle. -/
example : gatherCost 6 3 100 6 5 0 true
    = (5 : Rat) * (6 + 3) + ((min 0 5 : Nat) : Rat) * 100 + (5 : Rat) * 6 :=
  gather_cost_loadout_parity 6 3 100 6 5 0 true

/-- …and the same decomposition with NO mismatch, so the loadout residual is
`5 * 0`. Both branches of the conditional are witnessed, so neither `example`
is passing merely because the `if` collapsed. -/
example : gatherCost 6 3 100 6 5 0 false
    = (5 : Rat) * (6 + 3) + ((min 0 5 : Nat) : Rat) * 100 + (5 : Rat) * 0 :=
  gather_cost_loadout_parity 6 3 100 6 5 0 false

end Formal.GatherCost
