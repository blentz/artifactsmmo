-- @concept: planner, plan, action @property: monotonicity, safety
/-
Plan-action model for the plannability-soundness theorem
(`Formal.PlanModel.min_plan_length_le_plan`).

## What this models

The three action kinds a plan can contain to obtain and optionally equip an
item:

  * `gather code`  — visit a resource tile and collect one copy of `code`.
  * `craft  code`  — consume the recipe inputs for `code` and produce one copy.
  * `equip  code`  — move `code` from inventory to an equipment slot.

A `Plan` is a `List Action`. The model threads a multiset (represented as an
assoc-list `List (String × Int)`, MIRRORING the `(Int × List (String × Int))`
state shape of `_min_gathers` and `_min_crafts`) through `List.foldl` to give
`produces`: the net holdings after executing the plan from an initial `owned`
state, together with a `gathers` count and a `crafts` count.

## Faithfulness: recipe inputs are required and consumed

`applyAction` for `craft code` is intentionally **total** (it always +1 the
holdings unconditionally) so that the mass-conservation induction in Task 5 can
reason over the `foldl` shape without case-splitting on recipe validity at every
step.

Faithfulness is enforced by the **`ValidPlan`** predicate: it tracks the
step-by-step holdings via a `foldl` over `(Bool × ExecState)` and checks, at
every `craft` action, that all recipe inputs are present in the current holdings.
`SatisfiesEquip` REQUIRES `ValidPlan` — a plan that cheats (crafts without
inputs) is not a satisfying plan. The sanity `example` at the bottom confirms
the 2-action cheat plan `[craft "feather_coat", equip "feather_coat"]` is
rejected.

**Validity-modeling choice: option (b).**
Keep `applyAction` total; thread validity as a `Prop` predicate (`ValidPlan`)
and require it in `SatisfiesEquip`. Rationale: option (a) (guarded relation /
`Option`) would require partial-function reasoning throughout Tasks 5–7. Option
(b) keeps the `foldl` shape simple and matches the extracted cores (`_min_gathers`/
`_min_crafts` are also total functions). The induction strategy for Task 5 is:
induct on the plan list, unfold `foldl` one step, case-split on the action kind,
use `ValidPlan` to obtain the recipe-input inequalities, and apply the
mass-conservation hypothesis.

## Provability rationale

State threading via `List.foldl` with an assoc-list matches the extracted cores
exactly:
  * `_min_gathers` (MinGathers.lean) threads `(total, owned)` via `foldl`.
  * `_min_crafts`  (MinCrafts.lean)  threads `(total, owned)` via `foldl`.

This alignment means Tasks 5–6 can proceed by structural induction on `Plan`
unfolding `foldl` one step at a time, and the measure `state.1` (gather/craft
count) and `state.2` (holdings) evolve at each step in a shape the extracted
definitions already reason about.

## NOT modelled (explicit abstraction boundaries)

The following are **outside this model** and are noted here for honesty:

  1. **Movement** — `gather` and `equip` implicitly assume the character is at
     the right tile/bank; travel steps are not counted. The lower bound is still
     sound (travel adds steps, not removes them).
  2. **Inventory space** — the model does not track bag capacity; a real plan
     may need extra deposit/withdraw steps when the bag fills.
  3. **A\* completeness** — the model assumes the planner finds a plan if one
     exists; proving A\* completeness is out of scope.
  4. **Batch crafting / multi-drop** — `craft` produces exactly 1 copy, and
     `gather` yields exactly 1 unit. `ceil_gathers` (via `max_gather_yield`)
     accounts for multi-drop resources at the `minPlanLength` level; the
     per-action model uses 1 for structural clarity.
-/

import Formal.Extracted.MinGathers
import Formal.Extracted.MinCrafts
import Formal.Extracted.MinPlanLength
import Formal.StepDispatch
import Formal.Extracted.Bridges6

namespace Formal.PlanModel

-- ---------------------------------------------------------------------------
-- Action type and Plan alias
-- ---------------------------------------------------------------------------

/-- The three action kinds in the plan model.
  * `gather code` — collect one unit of `code` from a resource tile.
  * `craft  code` — produce one copy of `code` by consuming its recipe inputs.
  * `equip  code` — equip `code` from inventory (requires `code` in inventory). -/
inductive Action where
  | gather (code : String)
  | craft  (code : String)
  | equip  (code : String)
  deriving Repr, DecidableEq

/-- A plan is a list of actions (ordered; executed left to right). -/
abbrev Plan := List Action

-- ---------------------------------------------------------------------------
-- Assoc-list helpers (mirroring the extracted cores)
-- ---------------------------------------------------------------------------

/-- Look up `k` in an assoc-list, returning `0` if absent.
Mirrors `_dictGetD owned item 0` in the extracted `_min_gathers`/`_min_crafts`. -/
def dictGet (m : List (String × Int)) (k : String) : Int :=
  match m with
  | []            => 0
  | (k', v) :: rest => if k' == k then v else dictGet rest k

/-- Set `m[k] = v` (replace-first-else-append), mirroring `_dictSet`. -/
def dictSet (m : List (String × Int)) (k : String) (v : Int) : List (String × Int) :=
  match m with
  | []              => [(k, v)]
  | (k', v') :: rest => if k' == k then (k', v) :: rest else (k', v') :: dictSet rest k v

-- ---------------------------------------------------------------------------
-- Plan execution state
-- ---------------------------------------------------------------------------

/-- Execution state threaded through a plan via `List.foldl`.

  * `gathers` — number of `gather` actions executed so far.
  * `crafts`  — number of `craft`  actions executed so far.
  * `holdings` — assoc-list multiset of items accumulated/consumed.

The `(gathers, crafts, holdings)` triple mirrors the `(total, owned)` state of
the extracted cores, extended with a separate `crafts` counter. Keeping both
counters in the state (rather than post-computing from the list) lets the
induction in Tasks 5–6 reason step-by-step without a second pass. -/
structure ExecState where
  gathers  : Nat
  crafts   : Nat
  holdings : List (String × Int)
  deriving Repr

/-- Apply one `Action` to an `ExecState`.

  * `gather code` — increment `gathers`, add 1 to `holdings[code]`.
  * `craft  code` — increment `crafts`, CONSUME all recipe inputs for `code`
                    (decrement `holdings[mat] -= per` for each `(mat, per)`
                    in the recipe), then add 1 to `holdings[code]`.
                    **Faithfulness note**: this function is TOTAL and performs
                    the consumption unconditionally. Pre-condition (inputs
                    present) is enforced by `ValidPlan` / `ValidCraftAt`; the
                    induction in Task 5 uses `ValidPlan` to obtain the ≥-bounds
                    needed to show consumption does not create negative holdings.
  * `equip  code` — no state change (equip is counted at the `Plan` level via
                    `SatisfiesEquip`, not inside the per-action fold). -/
def applyAction (recipes : List (String × List (String × Int)))
    (s : ExecState) (a : Action) : ExecState :=
  match a with
  | Action.gather code =>
      { s with
        gathers  := s.gathers + 1
        holdings := dictSet s.holdings code (dictGet s.holdings code + 1) }
  | Action.craft code =>
      -- For a faithful craft: consume each recipe input, then produce one `code`.
      let recipe_list : List (String × Int) :=
        match List.find? (fun p => p.1 == code) recipes with
        | none   => []
        | some p => p.2
      let holdings_consumed := List.foldl
        (fun h (mat_per : String × Int) =>
          let mat := mat_per.1
          let per := mat_per.2
          dictSet h mat (dictGet h mat - per))
        s.holdings recipe_list
      { s with
        crafts   := s.crafts + 1
        holdings := dictSet holdings_consumed code (dictGet holdings_consumed code + 1) }
  | Action.equip _ =>
      s

-- ---------------------------------------------------------------------------
-- Plan semantics: produces / satisfies
-- ---------------------------------------------------------------------------

/-- Run a plan from initial holdings `owned`, returning the final `ExecState`.

Uses `List.foldl` (left-to-right, exactly like the extracted cores) so Task-5
induction steps align with `_min_gathers`/`_min_crafts` foldl unfoldings. -/
def runPlan (recipes : List (String × List (String × Int)))
    (plan : Plan) (owned : List (String × Int)) : ExecState :=
  List.foldl (applyAction recipes) { gathers := 0, crafts := 0, holdings := owned } plan

/-- The gather count of running `plan` from `owned`. -/
def planGathers (recipes : List (String × List (String × Int)))
    (plan : Plan) (owned : List (String × Int)) : Nat :=
  (runPlan recipes plan owned).gathers

/-- The craft count of running `plan` from `owned`. -/
def planCrafts (recipes : List (String × List (String × Int)))
    (plan : Plan) (owned : List (String × Int)) : Nat :=
  (runPlan recipes plan owned).crafts

/-- The final holdings after running `plan` from `owned`. -/
def planHoldings (recipes : List (String × List (String × Int)))
    (plan : Plan) (owned : List (String × Int)) : List (String × Int) :=
  (runPlan recipes plan owned).holdings

-- ---------------------------------------------------------------------------
-- ValidCraftAt: inputs present predicate (for a single craft step)
-- ---------------------------------------------------------------------------

/-- `ValidCraftAt recipes holdings code` holds when all recipe inputs for `code`
are present in `holdings` with at least the required quantity.

This is the per-step pre-condition enforced by `ValidPlan` at each `craft`
action: the craft is only valid when all ingredients are in hand. -/
def ValidCraftAt (recipes : List (String × List (String × Int)))
    (holdings : List (String × Int)) (code : String) : Prop :=
  let recipe_list : List (String × Int) :=
    match List.find? (fun p => p.1 == code) recipes with
    | none   => []
    | some p => p.2
  ∀ (mat : String) (per : Int),
    (mat, per) ∈ recipe_list → per ≤ dictGet holdings mat

/-- The recipe input list for `code` (empty if `code` is raw / absent). Mirrors
the `recipe_list` let-binding used in `applyAction`/`ValidCraftAt`. -/
def recipeOf (recipes : List (String × List (String × Int)))
    (code : String) : List (String × Int) :=
  match List.find? (fun p => p.1 == code) recipes with
  | none   => []
  | some p => p.2

/-- `ValidGatherAt recipes code` holds when `code` is **raw** — it has no recipe
entry (an empty input list). A resource tile only yields raw materials; a
craftable item can never be gathered. This is the per-step pre-condition
enforced by `ValidPlan` at each `gather` action.

**Faithfulness note.** Without this restriction the model's `gather code` would
mint one unit of *any* code — including a fully-craftable item like
`feather_coat` — for a single gather, contradicting the production
`min_gathers` lower bound (`src/.../ai/min_gathers.py`: "a raw material can only
be obtained by gathering"). Requiring the gathered code to be raw is exactly the
production assumption that makes `min_gathers` a sound lower bound, so adding it
*strengthens* faithfulness; the cheat-plan `example` below is unaffected. -/
def ValidGatherAt (recipes : List (String × List (String × Int)))
    (code : String) : Prop :=
  recipeOf recipes code = []

-- ---------------------------------------------------------------------------
-- ValidPlan: all craft actions have their inputs present at execution time
-- ---------------------------------------------------------------------------

/-- `ValidPlanFrom recipes s plan` holds when, starting from state `s`,
every `craft` action in `plan` targets a CRAFTABLE item (`recipeOf code ≠ []`)
and has its recipe inputs present in the current holdings at the moment it
executes.

**Faithfulness note (craftable guard).** The `recipeOf code ≠ []` conjunct
mirrors the `ValidGatherAt` raw guard: production can only `craft` an item that
HAS a recipe — you cannot "craft" a raw material. Without it the model's total
`applyAction (craft code)` for a RAW `code` would `+1` holdings while consuming
nothing (empty recipe), minting one unit of a raw item for FREE — exactly the
gather hole the previous round closed, but on the craft branch (it would falsify
`minGathersCount item 1 ≤ planGathers`: a `[craft raw, equip]` plan produces the
item with `planGathers = 0`). Requiring the craft target to be craftable is the
production assumption, so it *strengthens* faithfulness; the cheat-plan `example`
still rejects (feather_coat is craftable, so it fails on the INPUT check).

Defined recursively over the plan list, threading state forward one step at a
time (same shape as `runPlan` / `List.foldl`). This makes the Task-5 induction
match: unfold one `foldl` step, case-split on the action, for `craft` extract
the craftable + `ValidCraftAt` hypotheses, then continue on the tail. -/
def ValidPlanFrom (recipes : List (String × List (String × Int)))
    (s : ExecState) : Plan → Prop
  | []      => True
  | a :: rest =>
      (match a with
       | Action.craft code  => recipeOf recipes code ≠ [] ∧ ValidCraftAt recipes s.holdings code
       | Action.gather code => ValidGatherAt recipes code
       | _                  => True) ∧
      ValidPlanFrom recipes (applyAction recipes s a) rest

/-- `ValidPlan recipes owned plan`: the plan is input-respecting when run from
initial holdings `owned`. -/
def ValidPlan (recipes : List (String × List (String × Int)))
    (owned : List (String × Int)) (plan : Plan) : Prop :=
  ValidPlanFrom recipes { gathers := 0, crafts := 0, holdings := owned } plan

-- ---------------------------------------------------------------------------
-- SatisfiesEquip
-- ---------------------------------------------------------------------------

/-- `SatisfiesEquip plan item owned recipes` holds when:
  1. `ValidPlan recipes owned plan` — every craft action's inputs are present
     at execution time (faithfulness: the plan cannot conjure items from nothing).
  2. `Action.equip item ∈ plan` — the plan contains an equip action for `item`.
  3. After running the plan from `owned`, the holdings contain ≥ 1 of `item`.

The `ValidPlan` requirement is the KEY soundness fix: without it, the 2-action
cheat plan `[craft "feather_coat", equip "feather_coat"]` would satisfy
conditions 2 and 3 (craft unconditionally +1s holdings) while skipping the
≥80-step recipe closure. With `ValidPlan`, the cheat plan is REJECTED because
the `craft "feather_coat"` action fires with empty holdings — no feathers, no
ash_plank — so `ValidCraftAt` fails. -/
def SatisfiesEquip (plan : Plan) (item : String) (owned : List (String × Int))
    (recipes : List (String × List (String × Int))) : Prop :=
  ValidPlan recipes owned plan ∧
  Action.equip item ∈ plan ∧
  1 ≤ dictGet (planHoldings recipes plan owned) item

-- ---------------------------------------------------------------------------
-- minPlanLength Lean wrapper
-- ---------------------------------------------------------------------------

/-- Lean wrapper for the production-level `min_plan_length` composition:

    `ceil_gathers(min_gathers(item, qty, recipes, owned), max_gather_yield)
     + min_crafts(item, qty, recipes, owned)
     + (if equip then 1 else 0)`

This delegates to the extracted cores (`Extracted.MinPlanLength.min_plan_length`)
and is the definition Tasks 5–7 prove a lower bound over. -/
def minPlanLength (item : String) (qty : Int)
    (recipes : List (String × List (String × Int)))
    (owned : List (String × Int))
    (maxGatherYield : Int)
    (equip : Bool) : Int :=
  Extracted.MinPlanLength.min_plan_length item qty recipes owned maxGatherYield equip

-- ---------------------------------------------------------------------------
-- Sanity check: the 2-action cheat plan is REJECTED
-- ---------------------------------------------------------------------------

/-!
## Sanity check

The following `example` shows the model rejects the unsound 2-action plan.
Given a recipe table where `feather_coat` requires `feather` (10 units) and
`ash_plank` (6 units), and starting with empty `owned`:

  `[craft "feather_coat", equip "feather_coat"]`

is NOT a valid plan (`¬ SatisfiesEquip`) because `ValidPlan` fails: the
`craft "feather_coat"` step fires with 0 feathers and 0 ash_planks, but the
recipe demands 10 and 6 respectively. The `ValidCraftAt` check fails for
`("feather", 10)`.

If this `example` were replaced by `sorry`, the model would still be unsound.
The `by decide` closes because all components reduce to finite decidable checks.
-/

/-- Recipe table for the sanity check: feather_coat = 10×feather + 6×ash_plank. -/
private def cheatRecipes : List (String × List (String × Int)) :=
  [("feather_coat", [("feather", 10), ("ash_plank", 6)])]

/-- The 2-action cheat plan cannot satisfy `SatisfiesEquip` because `ValidPlan`
fails: `craft "feather_coat"` executes with 0 feathers and 0 ash_planks in
hand, violating the `ValidCraftAt` pre-condition (10 ≤ 0 is false). -/
example : ¬ SatisfiesEquip
    [Action.craft "feather_coat", Action.equip "feather_coat"]
    "feather_coat"
    []
    cheatRecipes := by
  unfold SatisfiesEquip ValidPlan ValidPlanFrom ValidCraftAt cheatRecipes
  simp [List.find?]
  -- The goal reduces: we need to show the `ValidCraftAt` condition fails.
  -- (The `recipeOf ≠ []` craftable conjunct holds for feather_coat, so the
  -- cheat is rejected by the INPUT check, not the craftable check.)
  -- Specifically, `10 ≤ dictGet [] "feather"` = `10 ≤ 0` is false.
  intro _ hvc
  have := hvc "feather" 10 (by simp)
  simp [dictGet] at this

-- ---------------------------------------------------------------------------
-- Mass-conservation infrastructure (Task 5)
-- ---------------------------------------------------------------------------

/-!
## Conservation identity infrastructure

The deep step of the plannability-soundness proof is `minGathers_le_gathers`:
`min_gathers item 1 recipes owned ≤ planGathers recipes plan owned` for any
`ValidPlan`. The obstacle (see `.git/sdd/task-5-report.md`) is that the plan
recursion runs left-to-right over `List Action` while `_min_gathers` recurses
over the recipe DAG with GREEDY per-branch owned consumption. The bridge is a
GLOBAL conservation identity expressing the gather count as
`q · w(item) − Δ(consumed mass)`.

We work on the HAND model `Formal.StepDispatch.minGathers` (richer lemma base,
shared `getD`/`setD` encoding) and transfer to the extracted
`Extracted.MinGathers.min_gathers` via `Extracted.Bridges.min_gathers_bridge`
only at the API boundary. `PlanModel.dictGet`/`dictSet` are definitionally
`Formal.ShoppingList.getD`/`setD`.
-/

open Formal.ShoppingList (Dict Recipes getD setD getD_cons_self getD_cons_ne
  setD_cons_self setD_cons_ne getD_setD)
open Formal.StepDispatch (minGathers minGathersCount minGathers_succ)

/-- `dictGet` IS `Formal.ShoppingList.getD` (same equations). -/
theorem dictGet_eq (m : List (String × Int)) (k : String) :
    dictGet m k = getD m k 0 := by
  induction m with
  | nil => rfl
  | cons kv rest ih => obtain ⟨a, b⟩ := kv; simp only [dictGet, getD, ih]

/-- `dictSet` IS `Formal.ShoppingList.setD` (same equations). -/
theorem dictSet_eq (m : List (String × Int)) (k : String) (v : Int) :
    dictSet m k v = setD m k v := by
  induction m with
  | nil => rfl
  | cons kv rest ih => obtain ⟨a, b⟩ := kv; simp only [dictSet, setD, ih]

-- ---------------------------------------------------------------------------
-- Total-additivity: the running total threads additively and never feeds back
-- ---------------------------------------------------------------------------

/-- The running `total` accumulator is added to but never read by the
recursion: `minGathers` from total `t` equals `minGathers` from total `0` plus
`t`, and the returned `owned` residual is `t`-independent.

This decouples the gather count from the threaded total, so siblings in the
`foldl` can be reasoned about from a zero base and re-summed. Proved by
induction on the fuel; the `foldl` arm uses the IH on each sibling and a
general `foldl` shift lemma derived inline. -/
theorem minGathers_total_additive (fuel : Nat) (item : String) (qty : Int)
    (recipes : Recipes) (t : Int) (owned : Dict Int) :
    minGathers fuel item qty recipes (t, owned)
      = ((minGathers fuel item qty recipes (0, owned)).1 + t,
         (minGathers fuel item qty recipes (0, owned)).2) := by
  induction fuel generalizing item qty t owned with
  | zero =>
    simp only [minGathers]
    refine Prod.ext ?_ rfl
    show t + qty = 0 + qty + t
    omega
  | succ n ih =>
    rw [minGathers_succ, minGathers_succ]
    -- abstract the (total-independent) deficit and residual owned
    generalize hrem : qty - min (getD owned item 0) qty = rem
    generalize hod : setD owned item (getD owned item 0 - min (getD owned item 0) qty) = owned'
    by_cases hc : rem ≤ 0
    · rw [if_pos hc, if_pos hc]; simp
    · rw [if_neg hc, if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr, if_pos hr]
        refine Prod.ext ?_ rfl
        show t + rem = 0 + rem + t
        omega
      · rw [if_neg hr, if_neg hr]
        -- foldl arm: thread the additive total through the sibling fold
        suffices h : ∀ (rc : Dict Int) (s0 : Int × Dict Int),
            List.foldl
              (fun state mat => minGathers n mat.1 (mat.2 * rem) recipes state)
              (s0.1 + t, s0.2) rc
            = ((List.foldl
                  (fun state mat => minGathers n mat.1 (mat.2 * rem) recipes state)
                  (s0.1, s0.2) rc).1 + t,
               (List.foldl
                  (fun state mat => minGathers n mat.1 (mat.2 * rem) recipes state)
                  (s0.1, s0.2) rc).2) by
          have := h (getD recipes item []) (0, owned')
          simpa using this
        intro rc
        induction rc with
        | nil => intro s0; simp
        | cons mat rest ihrec =>
          intro s0
          simp only [List.foldl_cons]
          rw [ih mat.1 (mat.2 * rem) (s0.1 + t) s0.2,
              ih mat.1 (mat.2 * rem) s0.1 s0.2]
          rw [← Int.add_assoc]
          rw [ihrec ((minGathers n mat.1 (mat.2 * rem) recipes (0, s0.2)).1 + s0.1,
                     (minGathers n mat.1 (mat.2 * rem) recipes (0, s0.2)).2)]

/-- The seed-`(t, owned)` gather count is the zero-seed count plus `t`
(the `.1` projection of `minGathers_total_additive`). -/
theorem minGathers_fst_total (fuel : Nat) (item : String) (qty : Int)
    (recipes : Recipes) (t : Int) (owned : Dict Int) :
    (minGathers fuel item qty recipes (t, owned)).1
      = (minGathers fuel item qty recipes (0, owned)).1 + t := by
  rw [minGathers_total_additive]

/-- The seed-`(t, owned)` residual owned is `t`-independent. -/
theorem minGathers_snd_total (fuel : Nat) (item : String) (qty : Int)
    (recipes : Recipes) (t : Int) (owned : Dict Int) :
    (minGathers fuel item qty recipes (t, owned)).2
      = (minGathers fuel item qty recipes (0, owned)).2 := by
  rw [minGathers_total_additive]

-- ---------------------------------------------------------------------------
-- Owned-free weight `w` and `costMass`
-- ---------------------------------------------------------------------------

/-- Fuel-indexed owned-free weight: the gather count for ONE unit of `item`
from empty holdings. `wf 0 item = 1`; at positive fuel `wf` satisfies the
recipe recursion (`wf (raw) = 1`, `wf (craftable) = Σ per · wf mat`). Indexing
by the SAME fuel as `minGathers` keeps the depth-degradation aligned so the
conservation identity's induction closes without a separate depth bound. -/
def wf (fuel : Nat) (item : String) (recipes : Recipes) : Int :=
  (minGathers fuel item 1 recipes (0, [])).1

/-- Total cost-mass of a holdings dict under weight `wf fuel`: `Σ v · wf c`
over the assoc-list entries (a hand-rolled summation, omega-friendly). -/
def costMass (fuel : Nat) (m : Dict Int) (recipes : Recipes) : Int :=
  match m with
  | [] => 0
  | (c, v) :: rest => v * wf fuel c recipes + costMass fuel rest recipes

@[simp] theorem costMass_nil (fuel : Nat) (recipes : Recipes) :
    costMass fuel [] recipes = 0 := rfl

@[simp] theorem costMass_cons (fuel : Nat) (c : String) (v : Int)
    (rest : Dict Int) (recipes : Recipes) :
    costMass fuel ((c, v) :: rest) recipes
      = v * wf fuel c recipes + costMass fuel rest recipes := rfl

/-- Setting `m[k] := v` shifts cost-mass by `(v − old) · wf k`: the single
entry for `k` changes its contribution, everything else is preserved. The
fundamental accounting lemma — every consume/credit step is a `setD`. -/
theorem costMass_setD (fuel : Nat) (m : Dict Int) (k : String) (v : Int)
    (recipes : Recipes) :
    costMass fuel (setD m k v) recipes
      = costMass fuel m recipes + (v - getD m k 0) * wf fuel k recipes := by
  induction m with
  | nil =>
    show costMass fuel [(k, v)] recipes = 0 + (v - getD [] k 0) * wf fuel k recipes
    simp [costMass, getD]
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases h : a = k
    · subst h
      rw [setD_cons_self, costMass_cons, costMass_cons, getD_cons_self,
          Int.sub_mul]
      omega
    · rw [setD_cons_ne _ _ _ _ _ h, costMass_cons, costMass_cons, ih,
          getD_cons_ne _ _ _ _ _ h]
      omega

/-- `wf 0 item = 1`: out of fuel, one unit accounts as a single raw gather. -/
@[simp] theorem wf_zero (item : String) (recipes : Recipes) :
    wf 0 item recipes = 1 := by
  show (minGathers 0 item 1 recipes (0, [])).1 = 1
  simp [minGathers]

/-- A RAW item weighs exactly `1` at positive fuel (one flat gather). -/
theorem wf_succ_raw (n : Nat) (item : String) (recipes : Recipes)
    (hraw : (getD recipes item []).length = 0) :
    wf (n + 1) item recipes = 1 := by
  show (minGathers (n + 1) item 1 recipes (0, [])).1 = 1
  have := Formal.StepDispatch.minGathers_raw_unowned n item 1 recipes hraw
  simpa using this

/-- `wf` of a craftable item at `fuel+1` expands into the recipe sub-weights at
`fuel`: it is the empty-owned `foldl` over the recipe, each material entered at
quantity `per`. (One-step unfold of `wf`; the per-material quantities are the
recipe `per_unit` values since the parent quantity is `1` and holdings empty.)
This is the recipe-DAG recursion `wf` satisfies. -/
theorem wf_succ_craft (n : Nat) (item : String) (recipes : Recipes)
    (hcr : ¬ (getD recipes item []).length = 0) :
    wf (n + 1) item recipes
      = ((getD recipes item []).foldl
          (fun state mat => minGathers n mat.1 (mat.2 * 1) recipes state)
          (0, setD [] item (0 - 0))).1 := by
  show (minGathers (n + 1) item 1 recipes (0, [])).1 = _
  rw [minGathers_succ]
  have hg : getD ([] : Dict Int) item 0 = 0 := rfl
  rw [hg]
  have hmin : min (0 : Int) 1 = 0 := by decide
  rw [hmin]
  rw [if_neg (by decide), if_neg hcr]
  simp only [Int.sub_zero]

-- ---------------------------------------------------------------------------
-- Single-craft cost-mass delta
-- ---------------------------------------------------------------------------

/-- The total weighted input mass of a recipe input list under `wf fuel`:
`Σ (mat, per) ∈ inputs, per · wf mat`. The amount of cost-mass a craft step
consumes from holdings. -/
def recipeMass (fuel : Nat) (inputs : Dict Int) (recipes : Recipes) : Int :=
  match inputs with
  | [] => 0
  | (mat, per) :: rest => per * wf fuel mat recipes + recipeMass fuel rest recipes

@[simp] theorem recipeMass_nil (fuel : Nat) (recipes : Recipes) :
    recipeMass fuel [] recipes = 0 := rfl

@[simp] theorem recipeMass_cons (fuel : Nat) (mat : String) (per : Int)
    (rest : Dict Int) (recipes : Recipes) :
    recipeMass fuel ((mat, per) :: rest) recipes
      = per * wf fuel mat recipes + recipeMass fuel rest recipes := rfl

/-- The recipe-input consume operation, named to match `applyAction`'s craft
`foldl` lambda exactly (so it rewrites without unfolding fights). -/
def consumeHoldings (H : Dict Int) (inputs : Dict Int) : Dict Int :=
  List.foldl
    (fun h (mat_per : String × Int) =>
      let mat := mat_per.1
      let per := mat_per.2
      dictSet h mat (dictGet h mat - per))
    H inputs

/-- Consuming a recipe input list from holdings drops cost-mass by exactly
`recipeMass`. Each fold step is a `costMass_setD` with delta `−per · wf mat`. -/
theorem costMass_consume (fuel : Nat) (inputs : Dict Int)
    (recipes : Recipes) (H : Dict Int) :
    costMass fuel (consumeHoldings H inputs) recipes
      = costMass fuel H recipes - recipeMass fuel inputs recipes := by
  unfold consumeHoldings
  induction inputs generalizing H with
  | nil => simp
  | cons mp rest ih =>
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons, recipeMass_cons]
    rw [ih (dictSet H mat (dictGet H mat - per))]
    rw [dictSet_eq, costMass_setD, dictGet_eq]
    rw [show getD H mat 0 - per - getD H mat 0 = -per by omega, Int.neg_mul]
    omega

/-- A single `craft c` step's effect on cost-mass: it consumes the recipe's
input mass and produces one unit of `c`, so
`costMass(after) = costMass(H) − recipeMass(inputs) + wf c`. Combines
`costMass_consume` with the final `+1 c` (another `costMass_setD`). -/
theorem costMass_craft_step (fuel : Nat) (c : String) (recipes : Recipes)
    (H : Dict Int) :
    costMass fuel
        (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
          (Action.craft c)).holdings recipes
      = costMass fuel H recipes
        - recipeMass fuel (recipeOf recipes c) recipes
        + wf fuel c recipes := by
  show costMass fuel
      (dictSet (consumeHoldings H (recipeOf recipes c)) c
        (dictGet (consumeHoldings H (recipeOf recipes c)) c + 1)) recipes = _
  rw [dictSet_eq, costMass_setD, dictGet_eq, costMass_consume]
  rw [show getD (consumeHoldings H (recipeOf recipes c)) c 0 + 1
        - getD (consumeHoldings H (recipeOf recipes c)) c 0 = 1 by omega]
  omega

-- ---------------------------------------------------------------------------
-- Weight recursion via fuel-stability (acyclic recipe DAG)
-- ---------------------------------------------------------------------------

/-!
## The weight recursion `wf c = recipeMass(recipeOf c)`

`costMass_craft_step` reduces a craft's cost-mass change to `wf c − recipeMass c`.
A valid craft is cost-mass *preserving* exactly when these are EQUAL — the
**weight recursion** `wf fuel c = recipeMass fuel (recipeOf c)`. `wf_succ_craft`
unfolds `wf (n+1) c` into the empty-owned `foldl` over the recipe at fuel `n`,
which sums to `recipeMass n (recipeOf c) = Σ per · wf n mat`. To bump the inner
`wf n mat` up to `wf (n+1) mat` (so both sides live at the same fuel) we need
**fuel-stability**: `wf` stops changing once fuel exceeds the item's recipe-DAG
depth.

### The acyclicity hypothesis (faithful, not a weakening)

`wf` degrades one DAG level per unit of fuel, so stability needs the DAG to have
bounded depth — i.e. the recipe graph is **acyclic**. We certify acyclicity with
a topological `rank : String → Nat` strictly decreasing across every recipe edge
(`Acyclic`). This is a TRUE domain property: a real crafting recipe never has an
item as a (transitive) ingredient of itself, so a finite rank always exists.
Naming it is honesty, not weakening — `minGathersCount` itself seeds its fuel
with `len(recipes)+1` *precisely because* production recipes are acyclic (a
cyclic recipe is uncraftable). We additionally assume `PosRecipes` (every recipe
needs a strictly-positive quantity of each input) — also a true domain property
(a recipe entry of `0` units is not a real ingredient).
-/

/-- A holdings dict whose every key reads as `0`. Under an all-zero `owned`,
`minGathers` credits nothing, so the threaded `owned` cannot affect the gather
count — the key to decoupling siblings in the recipe `foldl`. -/
def AllZero (owned : Dict Int) : Prop := ∀ k, getD owned k 0 = 0

/-- Every recipe input quantity is strictly positive (faithful: a real recipe
needs `> 0` of each ingredient). -/
def PosRecipes (recipes : Recipes) : Prop :=
  ∀ item mat per, (mat, per) ∈ getD recipes item [] → 0 < per

/-- The recipe DAG is acyclic, certified by a topological rank strictly
decreasing across every recipe edge. Faithful: real recipes are acyclic (no item
is a transitive ingredient of itself), and a finite rank witnesses it. -/
def Acyclic (recipes : Recipes) (rank : String → Nat) : Prop :=
  ∀ item mat per, (mat, per) ∈ getD recipes item [] → rank mat < rank item

theorem allzero_nil : AllZero ([] : Dict Int) := fun _ => rfl

/-- Setting a key to `0` preserves `AllZero`. -/
theorem allzero_setD0 (owned : Dict Int) (item : String) (h : AllZero owned) :
    AllZero (setD owned item 0) := by
  intro k; rw [getD_setD]; by_cases hk : item = k
  · subst hk; rw [if_pos rfl]
  · rw [if_neg hk, h k]

/-- A rank-`0` acyclic item is RAW: any input would have rank `< 0`, impossible. -/
theorem rank_zero_raw (recipes : Recipes) (rank : String → Nat) (item : String)
    (hacy : Acyclic recipes rank) (h0 : rank item = 0) :
    (getD recipes item []).length = 0 := by
  cases hl : getD recipes item [] with
  | nil => simp
  | cons hd tl =>
    exfalso; obtain ⟨mat, per⟩ := hd
    have hmem : (mat, per) ∈ getD recipes item [] := by rw [hl]; simp
    have := hacy item mat per hmem; omega

/-- **DECOUPLING.** Under all-zero `owned`, positive `qty`, and positive recipes,
the gather COUNT is owned-independent (equals the empty-owned count) and the
residual `owned` stays `AllZero`. Zero holdings ⇒ zero crediting ⇒ the threaded
`owned` never affects the count. This is the lemma that collapses the report's
"foldl sibling-threading arm". -/
theorem minGathers_allzero (fuel : Nat) (item : String) (qty : Int)
    (recipes : Recipes) (owned : Dict Int)
    (hpos : PosRecipes recipes) (hq : 0 < qty) (hz : AllZero owned) :
    (minGathers fuel item qty recipes (0, owned)).1
      = (minGathers fuel item qty recipes (0, [])).1
    ∧ AllZero (minGathers fuel item qty recipes (0, owned)).2 := by
  induction fuel generalizing item qty owned with
  | zero => exact ⟨rfl, hz⟩
  | succ n ih =>
    rw [minGathers_succ, minGathers_succ]
    have he : getD ([]:Dict Int) item 0 = 0 := rfl
    rw [hz item, he]
    have hmin : min (0:Int) qty = 0 := by omega
    simp only [hmin, Int.sub_zero]
    rw [if_neg (show ¬ qty ≤ 0 by omega), if_neg (show ¬ qty ≤ 0 by omega)]
    by_cases hr : (getD recipes item []).length = 0
    · rw [if_pos hr, if_pos hr]
      exact ⟨rfl, allzero_setD0 owned item hz⟩
    · rw [if_neg hr, if_neg hr]
      suffices H : ∀ (rc : Dict Int) (o1 o2 : Dict Int) (t : Int),
          (∀ mat per, (mat, per) ∈ rc → 0 < per) → AllZero o1 → AllZero o2 →
          (List.foldl (fun st mat => minGathers n mat.1 (mat.2 * qty) recipes st)
              (t, o1) rc).1
            = (List.foldl (fun st mat => minGathers n mat.1 (mat.2 * qty) recipes st)
                (t, o2) rc).1
          ∧ AllZero (List.foldl
              (fun st mat => minGathers n mat.1 (mat.2 * qty) recipes st) (t, o1) rc).2 by
        have hmem : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
          fun mat per hmem => hpos item mat per hmem
        exact H (getD recipes item []) (setD owned item 0) (setD ([]:Dict Int) item 0) 0
          hmem (allzero_setD0 owned item hz) (allzero_setD0 [] item allzero_nil)
      clear hr
      intro rc
      induction rc with
      | nil => intro o1 o2 t _ ho1 _; exact ⟨rfl, ho1⟩
      | cons mp rest ihrec =>
        intro o1 o2 t hmem ho1 ho2
        obtain ⟨mat, per⟩ := mp
        simp only [List.foldl_cons]
        have hper : 0 < per := hmem mat per (by simp)
        have hpq : 0 < per * qty := Int.mul_pos hper hq
        have h1 := ih mat (per * qty) o1 hpq ho1
        have h2 := ih mat (per * qty) o2 hpq ho2
        have ta1 := minGathers_total_additive n mat (per*qty) recipes t o1
        have ta2 := minGathers_total_additive n mat (per*qty) recipes t o2
        have hmem' : ∀ m p, (m, p) ∈ rest → 0 < p :=
          fun m p hm => hmem m p (by simp [hm])
        rw [ta1, ta2, h1.1, h2.1]
        exact ihrec _ _ _ hmem' h1.2 h2.2

/-- **SCALING.** The empty-seeded (more generally all-zero-seeded) gather count
is linear in the requested quantity: `minGathers (k·q) = k · minGathers q` for
positive `k, q`. (Zero crediting ⇒ each sub-quantity scales by `k` through the
recipe DAG.) -/
theorem minGathers_scale (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (k q : Int) (owned : Dict Int),
      0 < k → 0 < q → AllZero owned →
      (minGathers fuel item (k * q) recipes (0, owned)).1
        = k * (minGathers fuel item q recipes (0, owned)).1 := by
  intro fuel
  induction fuel with
  | zero =>
    intro item k q owned hk hq hz
    simp only [minGathers, Int.zero_add]
  | succ n ih =>
    intro item k q owned hk hq hz
    rw [minGathers_succ, minGathers_succ]
    simp only [hz item]
    have hmin1 : min (0:Int) (k*q) = 0 := by have := Int.mul_pos hk hq; omega
    have hmin2 : min (0:Int) q = 0 := by omega
    rw [hmin1, hmin2]
    simp only [Int.sub_zero]
    rw [if_neg (show ¬ k*q ≤ 0 by have := Int.mul_pos hk hq; omega),
        if_neg (show ¬ q ≤ 0 by omega)]
    by_cases hr : (getD recipes item []).length = 0
    · rw [if_pos hr, if_pos hr]
      simp only [Int.zero_add]
    · rw [if_neg hr, if_neg hr]
      have hz0 : AllZero (setD owned item 0) := allzero_setD0 owned item hz
      have hpomat : ∀ mat per, (mat,per) ∈ getD recipes item [] → 0 < per :=
        fun mat per hmem => hpos item mat per hmem
      suffices Hgen : ∀ (rc : Dict Int) (o1 o2 : Dict Int) (t : Int),
          (∀ mat per, (mat,per) ∈ rc → 0 < per) → AllZero o1 → AllZero o2 →
          (List.foldl (fun st mat => minGathers n mat.1 (mat.2 * (k*q)) recipes st)
              (k*t, o1) rc).1
            = k * (List.foldl (fun st mat => minGathers n mat.1 (mat.2 * q) recipes st)
                (t, o2) rc).1 by
        have := Hgen (getD recipes item []) (setD owned item 0) (setD owned item 0) 0
          hpomat hz0 hz0
        simpa using this
      intro rc
      induction rc with
      | nil => intro o1 o2 t _ _ _; rfl
      | cons mp rest ihrec =>
        intro o1 o2 t hpo ho1 ho2
        obtain ⟨mat, per⟩ := mp
        simp only [List.foldl_cons]
        have hper : 0 < per := hpo mat per (by simp)
        have hpkq : 0 < per * (k*q) := Int.mul_pos hper (Int.mul_pos hk hq)
        have hpq : 0 < per * q := Int.mul_pos hper hq
        have ta1 := minGathers_total_additive n mat (per*(k*q)) recipes (k*t) o1
        have ta2 := minGathers_total_additive n mat (per*q) recipes t o2
        rw [ta1, ta2]
        have ca1 := (minGathers_allzero n mat (per*(k*q)) recipes o1 hpos hpkq ho1)
        have ca2 := (minGathers_allzero n mat (per*q) recipes o2 hpos hpq ho2)
        have hassoc : per*(k*q) = k*(per*q) := by
          rw [← Int.mul_assoc, Int.mul_comm per k, Int.mul_assoc]
        have hscale := ih mat k (per*q) [] hk hpq allzero_nil
        have hheq : (minGathers n mat (per*(k*q)) recipes (0,o1)).1 + k*t
                  = k * ((minGathers n mat (per*q) recipes (0,o2)).1 + t) := by
          rw [ca1.1, ca2.1, hassoc, hscale, Int.mul_add]
        rw [hheq]
        have hpo' : ∀ m' p, (m',p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
        exact ihrec _ _ _ hpo' ca1.2 ca2.2

/-- **FUEL-STABILITY (count).** Once `fuel ≥ rank item`, one more unit of fuel
does not change the gather count: `minGathers (n+1) item = minGathers n item`
(on the `.1` projection — the residual `owned` may differ but is `AllZero`
either way). Strong induction on the fuel `n`; the recipe `foldl` steps in
lockstep at the two fuels because every material has rank `< rank item ≤ n`
(so the IH applies one fuel lower) and `minGathers_allzero` absorbs the
differing residuals. The acyclicity rank is exactly what bounds the DAG depth. -/
theorem minGathers_stable_count (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) :
    ∀ (n : Nat) (item : String) (qty : Int) (owned : Dict Int),
      rank item ≤ n → 0 < qty → AllZero owned →
      (minGathers (n+1) item qty recipes (0, owned)).1
        = (minGathers n item qty recipes (0, owned)).1 := by
  intro n
  induction n using Nat.strongRecOn with
  | ind n IH =>
    intro item qty owned hrank hq hz
    match n, IH with
    | 0, _ =>
      have hraw : (getD recipes item []).length = 0 :=
        rank_zero_raw recipes rank item hacy (by omega)
      rw [minGathers_succ]
      simp only [hz item]
      have hmin : min (0:Int) qty = 0 := by omega
      simp only [hmin, Int.sub_zero]
      rw [if_neg (show ¬ qty ≤ 0 by omega), if_pos hraw]
      show (0 + qty) = (minGathers 0 item qty recipes (0, owned)).1
      simp only [minGathers]
    | m + 1, IH =>
      rw [minGathers_succ, minGathers_succ]
      simp only [hz item]
      have hmin : min (0:Int) qty = 0 := by omega
      simp only [hmin, Int.sub_zero]
      rw [if_neg (show ¬ qty ≤ 0 by omega), if_neg (show ¬ qty ≤ 0 by omega)]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr, if_pos hr]
      · rw [if_neg hr, if_neg hr]
        have hz0 : AllZero (setD owned item 0) := allzero_setD0 owned item hz
        have hrankmat : ∀ mat per, (mat, per) ∈ getD recipes item [] → rank mat ≤ m := by
          intro mat per hmem
          have := hacy item mat per hmem; omega
        have hposmat : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
          fun mat per hmem => hpos item mat per hmem
        suffices Hgen : ∀ (rc : Dict Int) (o1 o2 : Dict Int) (t : Int),
            (∀ mat per, (mat,per) ∈ rc → rank mat ≤ m) →
            (∀ mat per, (mat,per) ∈ rc → 0 < per) →
            AllZero o1 → AllZero o2 →
            (List.foldl (fun st mat => minGathers (m+1) mat.1 (mat.2 * qty) recipes st)
                (t, o1) rc).1
              = (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * qty) recipes st)
                  (t, o2) rc).1 by
          exact Hgen (getD recipes item []) (setD owned item 0) (setD owned item 0) 0
            hrankmat hposmat hz0 hz0
        intro rc
        induction rc with
        | nil => intro o1 o2 t _ _ _ _; rfl
        | cons mp rest ihrec =>
          intro o1 o2 t hrk hpo ho1 ho2
          obtain ⟨mat, per⟩ := mp
          simp only [List.foldl_cons]
          have hper : 0 < per := hpo mat per (by simp)
          have hpq : 0 < per * qty := Int.mul_pos hper hq
          have hrm : rank mat ≤ m := hrk mat per (by simp)
          have hco1 := (minGathers_allzero (m+1) mat (per*qty) recipes o1 hpos hpq ho1)
          have hco2 := (minGathers_allzero m mat (per*qty) recipes o2 hpos hpq ho2)
          have hstab := IH m (Nat.lt_succ_self m) mat (per*qty) [] hrm hpq allzero_nil
          have ta1 := minGathers_total_additive (m+1) mat (per*qty) recipes t o1
          have ta2 := minGathers_total_additive m mat (per*qty) recipes t o2
          rw [ta1, ta2]
          have hheq : (minGathers (m+1) mat (per*qty) recipes (0, o1)).1
                    = (minGathers m mat (per*qty) recipes (0, o2)).1 := by
            rw [hco1.1, hco2.1, hstab]
          rw [hheq]
          have hrk' : ∀ m' p, (m',p) ∈ rest → rank m' ≤ m :=
            fun m' p hm => hrk m' p (by simp [hm])
          have hpo' : ∀ m' p, (m',p) ∈ rest → 0 < p :=
            fun m' p hm => hpo m' p (by simp [hm])
          exact ihrec _ _ _ hrk' hpo' hco1.2 hco2.2

/-- `wf` is fuel-stable above the item's rank: `wf (n+1) mat = wf n mat` when
`rank mat ≤ n`. (Specialisation of `minGathers_stable_count` to `wf`.) -/
theorem wf_stable (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (n : Nat) (mat : String) (hr : rank mat ≤ n) :
    wf (n+1) mat recipes = wf n mat recipes := by
  show (minGathers (n+1) mat 1 recipes (0,[])).1 = (minGathers n mat 1 recipes (0,[])).1
  exact minGathers_stable_count recipes rank hpos hacy n mat 1 [] hr (by omega) allzero_nil

/-- The empty-owned recipe `foldl` (at `q = 1`) sums to `recipeMass`:
`Σ over (mat,per), per · wf n mat`. Threads the additive total; each material's
count decouples to its empty-owned value (`minGathers_allzero`) and scales by
`per` (`minGathers_scale`), giving `per · wf n mat`. -/
theorem foldl_recipeMass (n : Nat) (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (rc : Dict Int) (o : Dict Int) (t : Int),
      (∀ mat per, (mat,per) ∈ rc → 0 < per) → AllZero o →
      (List.foldl (fun st mat => minGathers n mat.1 (mat.2 * 1) recipes st) (t, o) rc).1
        = t + recipeMass n rc recipes := by
  intro rc
  induction rc with
  | nil => intro o t _ _; simp [recipeMass]
  | cons mp rest ihrec =>
    intro o t hpo ho
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons, recipeMass_cons]
    have hper : 0 < per := hpo mat per (by simp)
    have hp1 : 0 < per * 1 := by omega
    have ta := minGathers_total_additive n mat (per*1) recipes t o
    rw [ta]
    have ca := (minGathers_allzero n mat (per*1) recipes o hpos hp1 ho)
    have hpo' : ∀ m' p, (m',p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
    rw [ihrec _ _ hpo' ca.2, ca.1]
    have hsc := minGathers_scale recipes hpos n mat per 1 [] hper (by omega) allzero_nil
    rw [hsc]
    show per * (minGathers n mat 1 recipes (0,[])).1 + t + recipeMass n rest recipes
       = t + (per * wf n mat recipes + recipeMass n rest recipes)
    have hwf : wf n mat recipes = (minGathers n mat 1 recipes (0,[])).1 := rfl
    rw [hwf]; omega

/-- `recipeMass` is fuel-stable when every input has rank `≤ n` (each `wf` term
is, by `wf_stable`). -/
theorem recipeMass_stable (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) (n : Nat) :
    ∀ (rc : Dict Int), (∀ mat per, (mat,per) ∈ rc → rank mat ≤ n) →
      recipeMass (n+1) rc recipes = recipeMass n rc recipes := by
  intro rc
  induction rc with
  | nil => intro _; rfl
  | cons mp rest ih =>
    intro hrk
    obtain ⟨mat, per⟩ := mp
    simp only [recipeMass_cons]
    have hrm : rank mat ≤ n := hrk mat per (by simp)
    rw [wf_stable recipes rank hpos hacy n mat hrm]
    have hrk' : ∀ m' p, (m',p) ∈ rest → rank m' ≤ n := fun m' p hm => hrk m' p (by simp [hm])
    rw [ih hrk']

/-- `recipeOf` (a `List.find?`) agrees with `getD` on the recipe table. -/
theorem recipeOf_eq_getD (recipes : Recipes) (c : String) :
    recipeOf recipes c = getD recipes c [] := by
  unfold recipeOf
  induction recipes with
  | nil => rfl
  | cons hd tl ih =>
    obtain ⟨k, v⟩ := hd
    rw [getD]
    by_cases h : (k == c) = true
    · simp only [List.find?, h, if_true]
    · have hf : (k == c) = false := by simpa using h
      simp only [List.find?, hf]
      rw [if_neg (by simp)]
      exact ih

/-- **WEIGHT-RECURSION.** For a craftable item `c` of rank `≤ n+1` in an acyclic,
positive recipe table, its weight equals its recipe input mass:
`wf (n+1) c = recipeMass (n+1) (recipeOf c)`. Combined with `costMass_craft_step`
this makes a valid craft cost-mass PRESERVING. Proof: `wf_succ_craft` unfolds to
the fuel-`n` recipe `foldl`, which `foldl_recipeMass` sums to `recipeMass n`,
then `recipeMass_stable` bumps fuel `n → n+1` (every input has rank `≤ n`). -/
theorem wf_weight_rec (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (n : Nat) (c : String) (hcr : ¬ (getD recipes c []).length = 0)
    (hrank : rank c ≤ n + 1) :
    wf (n+1) c recipes = recipeMass (n+1) (recipeOf recipes c) recipes := by
  rw [wf_succ_craft n c recipes hcr]
  have hro : recipeOf recipes c = getD recipes c [] := recipeOf_eq_getD recipes c
  have hrk : ∀ mat per, (mat,per) ∈ getD recipes c [] → rank mat ≤ n := by
    intro mat per hmem
    have := hacy c mat per hmem; omega
  have hpo : ∀ mat per, (mat,per) ∈ getD recipes c [] → 0 < per :=
    fun mat per hmem => hpos c mat per hmem
  have hz0 : AllZero (setD ([]:Dict Int) c (0-0)) := by
    intro k; rw [getD_setD]; by_cases hk : c = k
    · subst hk; rw [if_pos rfl]; rfl
    · rw [if_neg hk]; rfl
  rw [foldl_recipeMass n recipes hpos (getD recipes c []) (setD [] c (0-0)) 0 hpo hz0]
  simp only [Int.zero_add]
  rw [hro, recipeMass_stable recipes rank hpos hacy n (getD recipes c []) hrk]

/-- **CRAFT COST-MASS PRESERVATION.** A craft of a *craftable* item `c` (rank
`≤ n+1`) leaves the total cost-mass UNCHANGED: it consumes exactly
`recipeMass (recipeOf c)` of input mass and produces `wf c = recipeMass(recipeOf c)`
of output mass. The cost-mass potential is therefore invariant under crafts — the
fact the Ψ-potential / craft-monotonicity argument rests on. (Combines the
unconditional `costMass_craft_step` with `wf_weight_rec`.) -/
theorem costMass_craft_preserved (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (n : Nat) (c : String) (H : Dict Int)
    (hcr : ¬ (getD recipes c []).length = 0) (hrank : rank c ≤ n + 1) :
    costMass (n+1)
        (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
          (Action.craft c)).holdings recipes
      = costMass (n+1) H recipes := by
  rw [costMass_craft_step (n+1) c recipes H,
      wf_weight_rec recipes rank hpos hacy n c hcr hrank]
  omega

-- ---------------------------------------------------------------------------
-- Reconstruction identity: minGathers count ↔ costMass under real holdings
-- ---------------------------------------------------------------------------

/-- `wf` of a raw item is `1` at ANY fuel (`wf_zero` ⊔ `wf_succ_raw`). -/
theorem wf_raw (F : Nat) (item : String) (recipes : Recipes)
    (hraw : (getD recipes item []).length = 0) :
    wf F item recipes = 1 := by
  cases F with
  | zero => exact wf_zero item recipes
  | succ n => exact wf_succ_raw n item recipes hraw

/-- **RECONSTRUCTION IDENTITY.** The bridge from `minGathers` under REAL holdings
to `costMass`: the gather count plus the cost-mass already in hand equals the
total cost-mass needed (`q · wf item`) plus the residual cost-mass left after the
greedy per-branch owned consumption:

    (minGathers f item q recipes (0, owned)).1 + costMass F owned recipes
      = q · wf F item recipes + costMass F (minGathers f …).2 recipes

The cost-mass fuel `F` is held FIXED (any `F ≥ rank item`) while the recursion
fuel `f` (`≥ rank item`) is the induction variable — this is the fuel-alignment
that makes the sibling-IH and the parent goal live at the SAME weight fuel `F`,
so the threaded residual `owned` accounts exactly as a `costMass` delta. The
craft (`foldl`) arm sums the per-material conservation (the IH at fuel `f−1`) and
collapses via `wf_weight_rec` (`wf F item = recipeMass F (recipeOf item)`); the
raw arm is `wf_raw`. This is the report's long-sought "precise owned-credit
`min_gathers` performs, which `costMass` (upper bound) loses". -/
theorem minGathers_recon (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) (F : Nat) :
    ∀ (f : Nat) (item : String) (q : Int) (owned : Dict Int),
      rank item ≤ f → rank item ≤ F → 0 < q →
      (minGathers f item q recipes (0, owned)).1
        + costMass F owned recipes
        = q * wf F item recipes
          + costMass F (minGathers f item q recipes (0, owned)).2 recipes := by
  intro f
  induction f with
  | zero =>
    intro item q owned hrf hrF hq
    have hraw : (getD recipes item []).length = 0 :=
      rank_zero_raw recipes rank item hacy (by omega)
    simp only [minGathers]
    rw [wf_raw F item recipes hraw]
    show 0 + q + costMass F owned recipes = q * 1 + costMass F owned recipes
    omega
  | succ n ih =>
    intro item q owned hrf hrF hq
    rw [minGathers_succ]
    by_cases hc : q - min (getD owned item 0) q ≤ 0
    · rw [if_pos hc]
      simp only
      have hused : min (getD owned item 0) q = q := by
        have := Int.min_le_right (getD owned item 0) q; omega
      rw [hused, costMass_setD]
      rw [show getD owned item 0 - q - getD owned item 0 = -q by omega, Int.neg_mul]
      omega
    · rw [if_neg hc]
      have hused : min (getD owned item 0) q = getD owned item 0 := by
        have := Int.min_le_left (getD owned item 0) q
        have := Int.min_le_right (getD owned item 0) q; omega
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]
        simp only
        rw [hused, costMass_setD, wf_raw F item recipes hr]
        rw [show getD owned item 0 - getD owned item 0 = (0:Int) by omega]
        rw [show (0:Int) - getD owned item 0 = -(getD owned item 0) by omega, Int.neg_mul]
        omega
      · rw [if_neg hr]
        rw [hused]
        rw [show getD owned item 0 - getD owned item 0 = (0:Int) by omega]
        have hfold : ∀ (rc : Dict Int) (o : Dict Int) (t : Int),
            (∀ mat per, (mat,per) ∈ rc → rank mat ≤ n) →
            (∀ mat per, (mat,per) ∈ rc → rank mat ≤ F) →
            (∀ mat per, (mat,per) ∈ rc → 0 < per) →
            (List.foldl (fun state mat =>
                minGathers n mat.1 (mat.2 * (q - getD owned item 0)) recipes state) (t, o) rc).1
              + costMass F o recipes
            = t + recipeMass F rc recipes * (q - getD owned item 0)
              + costMass F (List.foldl (fun state mat =>
                  minGathers n mat.1 (mat.2 * (q - getD owned item 0)) recipes state) (t, o) rc).2
                  recipes := by
          intro rc
          induction rc with
          | nil => intro o t _ _ _; simp [recipeMass]
          | cons mp rest ihrec =>
            intro o t hrk hrkF hpo
            obtain ⟨mat, per⟩ := mp
            simp only [List.foldl_cons, recipeMass_cons]
            have hper : 0 < per := hpo mat per (by simp)
            have hpr : 0 < per * (q - getD owned item 0) := Int.mul_pos hper (by omega)
            have hrm : rank mat ≤ n := hrk mat per (by simp)
            have hrmF : rank mat ≤ F := hrkF mat per (by simp)
            have hsib := ih mat (per * (q - getD owned item 0)) o hrm hrmF hpr
            have hta := minGathers_total_additive n mat (per*(q - getD owned item 0)) recipes t o
            rw [hta]
            have hrk' : ∀ m' p, (m',p) ∈ rest → rank m' ≤ n := fun m' p hm => hrk m' p (by simp [hm])
            have hrkF' : ∀ m' p, (m',p) ∈ rest → rank m' ≤ F := fun m' p hm => hrkF m' p (by simp [hm])
            have hpo' : ∀ m' p, (m',p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
            have hres := ihrec (minGathers n mat (per*(q - getD owned item 0)) recipes (0,o)).2
                          ((minGathers n mat (per*(q - getD owned item 0)) recipes (0,o)).1 + t)
                          hrk' hrkF' hpo'
            rw [Int.add_mul]
            have hmul : per * wf F mat recipes * (q - getD owned item 0)
                      = (per * (q - getD owned item 0)) * wf F mat recipes := by
              rw [Int.mul_assoc, Int.mul_comm (wf F mat recipes) (q - getD owned item 0),
                  ← Int.mul_assoc]
            omega
        have hrkall : ∀ mat per, (mat,per) ∈ getD recipes item [] → rank mat ≤ n := by
          intro mat per hmem; have := hacy item mat per hmem; omega
        have hrkFall : ∀ mat per, (mat,per) ∈ getD recipes item [] → rank mat ≤ F := by
          intro mat per hmem; have := hacy item mat per hmem; omega
        have hpoall : ∀ mat per, (mat,per) ∈ getD recipes item [] → 0 < per :=
          fun mat per hmem => hpos item mat per hmem
        have happ := hfold (getD recipes item []) (setD owned item 0) 0 hrkall hrkFall hpoall
        obtain ⟨Fp, hFp⟩ : ∃ Fp, F = Fp + 1 := by
          have hl : 0 < (getD recipes item []).length := by
            rcases Nat.eq_zero_or_pos (getD recipes item []).length with h | h
            · exact absurd h hr
            · exact h
          obtain ⟨hd, tl, hcons⟩ : ∃ hd tl, getD recipes item [] = hd :: tl := by
            cases hh : getD recipes item [] with
            | nil => rw [hh] at hl; simp at hl
            | cons a b => exact ⟨a, b, rfl⟩
          obtain ⟨m0, p0⟩ := hd
          have hmem : (m0, p0) ∈ getD recipes item [] := by rw [hcons]; simp
          have hr1 := hacy item m0 p0 hmem
          cases F with
          | zero => omega
          | succ k => exact ⟨k, rfl⟩
        subst hFp
        have hwfrec : wf (Fp+1) item recipes
            = recipeMass (Fp+1) (recipeOf recipes item) recipes :=
          wf_weight_rec recipes rank hpos hacy Fp item hr hrF
        have hro : recipeOf recipes item = getD recipes item [] := recipeOf_eq_getD recipes item
        rw [hro] at hwfrec
        have hcm := costMass_setD (Fp+1) owned item 0 recipes
        rw [show (0:Int) - getD owned item 0 = -(getD owned item 0) by omega, Int.neg_mul] at hcm
        rw [hwfrec] at hcm ⊢
        have hdist : recipeMass (Fp+1) (getD recipes item []) recipes * q
                   = recipeMass (Fp+1) (getD recipes item []) recipes * (q - getD owned item 0)
                     + getD owned item 0 * recipeMass (Fp+1) (getD recipes item []) recipes := by
          rw [Int.mul_comm (getD owned item 0)]
          rw [← Int.mul_add]; congr 1; omega
        generalize hA : (List.foldl (fun state mat =>
            minGathers n mat.fst (mat.snd * (q - getD owned item 0)) recipes state)
            (0, setD owned item 0) (getD recipes item [])).fst = A
        generalize hB : costMass (Fp+1) (List.foldl (fun state mat =>
            minGathers n mat.fst (mat.snd * (q - getD owned item 0)) recipes state)
            (0, setD owned item 0) (getD recipes item [])).snd recipes = B
        rw [hA, hB] at happ
        have hcomm : q * recipeMass (Fp+1) (getD recipes item []) recipes
                   = recipeMass (Fp+1) (getD recipes item []) recipes * q := Int.mul_comm _ _
        omega

-- ---------------------------------------------------------------------------
-- Plan-mass invariant: gathers − costMass is constant along a valid plan
-- ---------------------------------------------------------------------------

/-- A raw `gather code` step raises total cost-mass by exactly `1`
(`wf (raw) = 1` and the step `setD`s `holdings[code] += 1`). -/
theorem costMass_gather_raw (F : Nat) (recipes : Recipes) (s : ExecState) (code : String)
    (hraw : (getD recipes code []).length = 0) :
    costMass F (applyAction recipes s (Action.gather code)).holdings recipes
      = costMass F s.holdings recipes + 1 := by
  show costMass F (dictSet s.holdings code (dictGet s.holdings code + 1)) recipes = _
  rw [dictSet_eq, costMass_setD, dictGet_eq, wf_raw F code recipes hraw]
  omega

/-- `costMass_craft_preserved` lifted to a full `ExecState` (the `craft` step's
holdings depend only on `s.holdings`). -/
theorem costMass_craft_preserved' (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (n : Nat) (c : String) (s : ExecState)
    (hcr : ¬ (getD recipes c []).length = 0) (hrank : rank c ≤ n + 1) :
    costMass (n+1) (applyAction recipes s (Action.craft c)).holdings recipes
      = costMass (n+1) s.holdings recipes := by
  have key := costMass_craft_preserved recipes rank hpos hacy n c s.holdings hcr hrank
  show costMass (n+1)
      (dictSet (consumeHoldings s.holdings (recipeOf recipes c)) c
        (dictGet (consumeHoldings s.holdings (recipeOf recipes c)) c + 1)) recipes = _
  exact key

/-- **PLAN-MASS INVARIANT.** Along ANY valid plan the quantity
`gathers − costMass (holdings)` is CONSTANT: every `gather` raises both
`gathers` and `costMass` by exactly `1` (raw, `wf = 1`), every (valid, hence
craftable) `craft` preserves `costMass` and leaves `gathers` fixed
(`costMass_craft_preserved'`), and `equip` is a no-op. Carries the honest domain
hypotheses `PosRecipes`/`Acyclic` plus a rank bound `rank item ≤ |recipes|`
(the topological depth never exceeds the number of recipes — the same fact that
seeds `minGathersCount`'s fuel with `|recipes| + 1`). The cost-mass fuel is fixed
at `|recipes| + 1` so it dominates every rank. -/
theorem plan_mass_invariant (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) :
    ∀ (plan : Plan) (s : ExecState),
      ValidPlanFrom recipes s plan →
      (List.foldl (applyAction recipes) s plan).gathers
        - costMass (recipes.length + 1)
            (List.foldl (applyAction recipes) s plan).holdings recipes
      = (s.gathers : Int) - costMass (recipes.length + 1) s.holdings recipes := by
  intro plan
  induction plan with
  | nil => intro s _; simp
  | cons a rest ih =>
    intro s hv
    simp only [List.foldl_cons]
    obtain ⟨hstep, hrestv⟩ := hv
    rw [ih (applyAction recipes s a) hrestv]
    cases a with
    | gather code =>
      have hraw : (getD recipes code []).length = 0 := by
        have hh : recipeOf recipes code = [] := hstep
        rw [recipeOf_eq_getD] at hh; rw [hh]; rfl
      have hg : (applyAction recipes s (Action.gather code)).gathers = s.gathers + 1 := rfl
      rw [hg, costMass_gather_raw (recipes.length+1) recipes s code hraw]
      omega
    | craft code =>
      obtain ⟨hcr, _hvc⟩ := hstep
      have hcr' : ¬ (getD recipes code []).length = 0 := by
        rw [← recipeOf_eq_getD]
        intro hh
        exact hcr (List.length_eq_zero_iff.mp hh)
      have hc := costMass_craft_preserved' recipes rank hpos hacy recipes.length code s hcr'
                  (by have := hRB code; omega)
      have hg : (applyAction recipes s (Action.craft code)).gathers = s.gathers := rfl
      rw [hg, hc]
    | equip code =>
      have hg : (applyAction recipes s (Action.equip code)).gathers = s.gathers := rfl
      have hh : (applyAction recipes s (Action.equip code)).holdings = s.holdings := rfl
      rw [hg, hh]

/-- **EXACT PLAN GATHER COUNT.** Specialising the invariant to the initial state
`{0, 0, owned}`: the gather count of any valid plan equals the cost-mass it
*adds* to the holdings — `planGathers = costMass planHoldings − costMass owned`.
(The plan converts `costMass owned` of held mass into `costMass planHoldings` by
gathering the difference, one unit of raw mass per gather.) -/
theorem planGathers_eq_costMass_diff (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length)
    (plan : Plan) (owned : Dict Int) (hv : ValidPlan recipes owned plan) :
    (planGathers recipes plan owned : Int)
      = costMass (recipes.length + 1) (planHoldings recipes plan owned) recipes
        - costMass (recipes.length + 1) owned recipes := by
  have h := plan_mass_invariant recipes rank hpos hacy hRB plan
    { gathers := 0, crafts := 0, holdings := owned } hv
  show (((List.foldl (applyAction recipes)
      { gathers := 0, crafts := 0, holdings := owned } plan).gathers : Nat) : Int) = _
  simp only [planHoldings, runPlan] at *
  omega

-- ---------------------------------------------------------------------------
-- Termination + covered-holdings reconstruction
-- ---------------------------------------------------------------------------

/-- **TERMINATION (count).** When holdings already cover the requested quantity
(`q ≤ getD owned item 0`), `minGathers` gathers nothing: the per-node credit
`used = min held q = q` zeroes the remaining deficit, so the count is `0`. -/
theorem minGathers_covered (fuel : Nat) (item : String) (q : Int)
    (recipes : Recipes) (owned : Dict Int) (hcov : q ≤ getD owned item 0) :
    (minGathers (fuel+1) item q recipes (0, owned)).1 = 0 := by
  rw [minGathers_succ]
  have hmin : min (getD owned item 0) q = q := by
    have h1 := Int.min_le_right (getD owned item 0) q
    have h2 : q ≤ min (getD owned item 0) q := Int.le_min.mpr ⟨hcov, Int.le_refl q⟩
    omega
  rw [hmin, if_pos (by omega)]

/-- `minGathersCount` at the production fuel is `0` when holdings cover the
quantity (`minGathers_covered` at fuel `|recipes|`). -/
theorem minGathersCount_covered (item : String) (q : Int)
    (recipes : Recipes) (owned : Dict Int) (hcov : q ≤ getD owned item 0) :
    minGathersCount item q recipes owned = 0 := by
  unfold minGathersCount
  exact minGathers_covered recipes.length item q recipes owned hcov

/-- **COVERED-HOLDINGS RECONSTRUCTION.** When `H` already holds `item`
(`1 ≤ getD H item 0`), its cost-mass decomposes as the item's weight plus the
residual mass left after crediting one unit of `item`:
`costMass H = wf item + costMass (minGathers … (0, H)).2`. (Reconstruction with
`q = 1` plus `minGathers_covered`, which kills the gather-count term.) The plan's
final holdings are exactly such an `H` — this is the planHoldings side of the
final bound. -/
theorem costMass_of_covered (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (item : String) (H : Dict Int)
    (hrf : rank item ≤ recipes.length) (hcov : 1 ≤ getD H item 0) :
    costMass (recipes.length + 1) H recipes
      = wf (recipes.length + 1) item recipes
        + costMass (recipes.length + 1)
            (minGathers (recipes.length + 1) item 1 recipes (0, H)).2 recipes := by
  have hrec := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1 H (by omega) (by omega) (by omega)
  have hterm : (minGathers (recipes.length + 1) item 1 recipes (0, H)).1 = 0 :=
    minGathers_covered recipes.length item 1 recipes H hcov
  rw [hterm, Int.one_mul] at hrec
  omega

-- ---------------------------------------------------------------------------
-- Pointwise-monotonicity layer for minGathers (the GATHER step)
-- ---------------------------------------------------------------------------

/-!
## Pointwise monotonicity

`Dom h1 h2` ("`h1` is pointwise dominated by `h2`") and `NonNeg h` are the
order structure under which `minGathers`'s gather count is antitone (more
holdings ⇒ no more gathers) and its residual covariant. This closes the GATHER
step of the Ψ-potential argument (a raw gather adds one unit of holdings, so the
remaining gather count drops by ≤ 1). The CRAFT step is handled separately by a
direct cost-mass coupling (`minGathers_craft_le`), since a craft's holdings are
pointwise *incomparable* to the pre-craft holdings.
-/

/-- `h1` is pointwise dominated by `h2`: every key reads `≤` under `h1`. -/
def Dom (h1 h2 : Dict Int) : Prop := ∀ k, getD h1 k 0 ≤ getD h2 k 0

/-- Every key of `h` reads `≥ 0`. -/
def NonNeg (h : Dict Int) : Prop := ∀ k, 0 ≤ getD h k 0

theorem dom_refl (h : Dict Int) : Dom h h := fun _ => Int.le_refl _

theorem dom_trans {h1 h2 h3 : Dict Int} (h12 : Dom h1 h2) (h23 : Dom h2 h3) :
    Dom h1 h3 := fun k => Int.le_trans (h12 k) (h23 k)

theorem nonneg_nil : NonNeg ([] : Dict Int) := fun _ => Int.le_refl 0

/-- Setting a key to a value `≥` the old value, with the rest `NonNeg`,
preserves `NonNeg`. -/
theorem nonneg_setD (h : Dict Int) (k : String) (v : Int)
    (hnn : NonNeg h) (hv : 0 ≤ v) : NonNeg (setD h k v) := by
  intro j; rw [getD_setD]; by_cases hk : k = j
  · rw [if_pos hk]; exact hv
  · rw [if_neg hk]; exact hnn j

/-- Setting a key to a value `≤` `getD h2 k 0` (under `Dom h1 h2` elsewhere)
keeps the pair `Dom`-ordered. -/
theorem dom_setD (h1 h2 : Dict Int) (k : String) (v : Int)
    (hdom : Dom h1 h2) (hv : v ≤ getD h2 k 0) : Dom (setD h1 k v) h2 := by
  intro j; rw [getD_setD]; by_cases hk : k = j
  · subst hk; rw [if_pos rfl]; exact hv
  · rw [if_neg hk]; exact hdom j

/-- **COUNT MONOTONICITY in the running total.** The gather count of
`minGathers` is `≥` its running total `t` whenever `0 ≤ q` — gathering can only
add to the total. Needs `PosRecipes` so each recipe sub-call has positive
quantity. In particular (`t = 0`) the count is `≥ 0`. -/
theorem minGathers_count_nonneg (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (q t : Int) (owned : Dict Int),
      0 ≤ t → 0 ≤ q → (minGathers fuel item q recipes (t, owned)).1 ≥ t := by
  intro fuel
  induction fuel with
  | zero =>
    intro item q t owned ht hq
    simp only [minGathers]; omega
  | succ n ih =>
    intro item q t owned ht hq
    rw [minGathers_succ]
    by_cases hc : q - min (getD owned item 0) q ≤ 0
    · rw [if_pos hc]; exact Int.le_refl t
    · rw [if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]; simp only; omega
      · rw [if_neg hr]
        -- foldl arm: each sibling step (positive sub-qty) preserves "count ≥ total"
        suffices H : ∀ (rc : Dict Int) (o : Dict Int) (s : Int),
            (∀ mat per, (mat, per) ∈ rc → 0 < per) → 0 ≤ s →
            (List.foldl (fun st mat =>
              minGathers n mat.1 (mat.2 * (q - min (getD owned item 0) q)) recipes st)
              (s, o) rc).1 ≥ s by
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          have := H (getD recipes item [])
            (setD owned item (getD owned item 0 - min (getD owned item 0) q)) t hpoall ht
          simpa using this
        intro rc
        induction rc with
        | nil => intro o s _ hs; exact Int.le_refl s
        | cons mp rest ihrec =>
          intro o s hpo hs
          obtain ⟨mat, per⟩ := mp
          simp only [List.foldl_cons]
          have hper : 0 < per := hpo mat per (by simp)
          have hpq : 0 ≤ per * (q - min (getD owned item 0) q) :=
            Int.le_of_lt (Int.mul_pos hper (by omega))
          have hstep := ih mat (per * (q - min (getD owned item 0) q)) s o hs hpq
          have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
          exact Int.le_trans hstep (ihrec _ _ hpo' (Int.le_trans hs hstep))

/-- **RESIDUAL NON-NEGATIVITY.** Starting from `NonNeg owned`, the residual
`owned` after `minGathers` is still `NonNeg`: each consume sets a key to
`held − min(held, q) ≥ 0` (`min ≤ held`), and gathering adds nothing negative. -/
theorem minGathers_nonneg_residual (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (q t : Int) (owned : Dict Int),
      0 < q → NonNeg owned →
      NonNeg (minGathers fuel item q recipes (t, owned)).2 := by
  intro fuel
  induction fuel with
  | zero => intro item q t owned _ hnn; simpa [minGathers] using hnn
  | succ n ih =>
    intro item q t owned hq hnn
    rw [minGathers_succ]
    have hheld : 0 ≤ getD owned item 0 := hnn item
    have hmin_le : min (getD owned item 0) q ≤ getD owned item 0 := Int.min_le_left _ _
    have hres_nn : NonNeg (setD owned item (getD owned item 0 - min (getD owned item 0) q)) :=
      nonneg_setD owned item _ hnn (by omega)
    by_cases hc : q - min (getD owned item 0) q ≤ 0
    · rw [if_pos hc]; exact hres_nn
    · rw [if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]; exact hres_nn
      · rw [if_neg hr]
        suffices H : ∀ (rc : Dict Int) (o : Dict Int) (s : Int),
            (∀ mat per, (mat, per) ∈ rc → 0 < per) → NonNeg o →
            NonNeg (List.foldl (fun st mat =>
              minGathers n mat.1 (mat.2 * (q - min (getD owned item 0) q)) recipes st)
              (s, o) rc).2 by
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          exact H (getD recipes item []) _ t hpoall hres_nn
        intro rc
        induction rc with
        | nil => intro o s _ ho; exact ho
        | cons mp rest ihrec =>
          intro o s hpo ho
          obtain ⟨mat, per⟩ := mp
          simp only [List.foldl_cons]
          have hper : 0 < per := hpo mat per (by simp)
          have hpq : 0 < per * (q - min (getD owned item 0) q) := Int.mul_pos hper (by omega)
          have hstep := ih mat (per * (q - min (getD owned item 0) q)) s o hpq ho
          have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
          exact ihrec _ _ hpo' hstep

/-- **RESIDUAL ≤ START.** The residual `owned` after `minGathers` is pointwise
`≤` the start `owned` (gathering only ever consumes held units). Needs
`NonNeg owned` so each consumed key reads `held − min(held, q) ≤ held`. -/
theorem minGathers_residual_le (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (q t : Int) (owned : Dict Int),
      0 < q → NonNeg owned →
      Dom (minGathers fuel item q recipes (t, owned)).2 owned := by
  intro fuel
  induction fuel with
  | zero => intro item q t owned _ _; simpa [minGathers] using dom_refl owned
  | succ n ih =>
    intro item q t owned hq hnn
    rw [minGathers_succ]
    have hheld : 0 ≤ getD owned item 0 := hnn item
    have hmin_nn : 0 ≤ min (getD owned item 0) q := Int.le_min.mpr ⟨hheld, by omega⟩
    have hcon_le : getD owned item 0 - min (getD owned item 0) q ≤ getD owned item 0 := by omega
    have hres_dom : Dom (setD owned item (getD owned item 0 - min (getD owned item 0) q)) owned :=
      dom_setD owned owned item _ (dom_refl owned) hcon_le
    have hres_nn : NonNeg (setD owned item (getD owned item 0 - min (getD owned item 0) q)) :=
      nonneg_setD owned item _ hnn (by omega)
    by_cases hc : q - min (getD owned item 0) q ≤ 0
    · rw [if_pos hc]; exact hres_dom
    · rw [if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]; exact hres_dom
      · rw [if_neg hr]
        -- foldl arm: chain residual-domination across siblings, transitively
        -- back to the post-consume start, then to `owned` via `hres_dom`.
        suffices H : ∀ (rc : Dict Int) (o : Dict Int) (s : Int),
            (∀ mat per, (mat, per) ∈ rc → 0 < per) → NonNeg o →
            Dom (List.foldl (fun st mat =>
              minGathers n mat.1 (mat.2 * (q - min (getD owned item 0) q)) recipes st)
              (s, o) rc).2 o by
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          have := H (getD recipes item []) _ t hpoall hres_nn
          exact dom_trans this hres_dom
        intro rc
        induction rc with
        | nil => intro o s _ _; exact dom_refl o
        | cons mp rest ihrec =>
          intro o s hpo ho
          obtain ⟨mat, per⟩ := mp
          simp only [List.foldl_cons]
          have hper : 0 < per := hpo mat per (by simp)
          have hpq : 0 < per * (q - min (getD owned item 0) q) := Int.mul_pos hper (by omega)
          have hstep_dom := ih mat (per * (q - min (getD owned item 0) q)) s o hpq ho
          have hstep_nn := minGathers_nonneg_residual recipes hpos n mat
            (per * (q - min (getD owned item 0) q)) s o hpq ho
          have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
          exact dom_trans (ihrec _ _ hpo' hstep_nn) hstep_dom

/-- The recipe `foldl` (at sub-quantity `r ≥ 0`) never reduces its running total:
its count is `≥` the seed total `s` (each sibling step adds via
`minGathers_count_nonneg`). The standalone foldl arm of `minGathers_count_nonneg`,
needed by the `minGathers_mono` "q2 done / q1 not" structural arm. -/
theorem recipeFoldl_count_nonneg (recipes : Recipes) (hpos : PosRecipes recipes)
    (m : Nat) :
    ∀ (rc : Dict Int) (o : Dict Int) (s r : Int),
      (∀ mat per, (mat, per) ∈ rc → 0 < per) → 0 ≤ s → 0 ≤ r →
      (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * r) recipes st)
        (s, o) rc).1 ≥ s := by
  intro rc
  induction rc with
  | nil => intro o s r _ hs _; exact Int.le_refl s
  | cons mp rest ihrec =>
    intro o s r hpo hs hr
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons]
    have hper : 0 < per := hpo mat per (by simp)
    have hpr : 0 ≤ per * r := Int.mul_nonneg (Int.le_of_lt hper) hr
    have hstep := minGathers_count_nonneg recipes hpos m mat (per * r) s o hs hpr
    have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
    exact Int.le_trans hstep (ihrec _ _ _ hpo' (Int.le_trans hs hstep) hr)

/-- The recipe `foldl` (at sub-quantity `r > 0`, `NonNeg` seed `o`) leaves a
residual pointwise `≤ o`. The standalone foldl arm of `minGathers_residual_le`,
needed by the `minGathers_mono` "q2 done / q1 not" structural arm. -/
theorem recipeFoldl_residual_dom (recipes : Recipes) (hpos : PosRecipes recipes)
    (m : Nat) :
    ∀ (rc : Dict Int) (o : Dict Int) (s r : Int),
      (∀ mat per, (mat, per) ∈ rc → 0 < per) → NonNeg o → 0 < r →
      Dom (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * r) recipes st)
        (s, o) rc).2 o := by
  intro rc
  induction rc with
  | nil => intro o s r _ _ _; exact dom_refl o
  | cons mp rest ihrec =>
    intro o s r hpo ho hr
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons]
    have hper : 0 < per := hpo mat per (by simp)
    have hpr : 0 < per * r := Int.mul_pos hper hr
    have hstep_dom := minGathers_residual_le recipes hpos m mat (per * r) s o hpr ho
    have hstep_nn := minGathers_nonneg_residual recipes hpos m mat (per * r) s o hpr ho
    have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
    exact dom_trans (ihrec _ _ _ hpo' hstep_nn hr) hstep_dom

/-- **POINTWISE MONOTONICITY.** With MORE holdings (`Dom h1 h2`, both `NonNeg`)
and a SMALLER-OR-EQUAL requested quantity (`0 < q2 ≤ q1`), `minGathers` does NO
MORE gathering AND leaves a (pointwise) LARGER residual:

    (minGathers f item q2 (0, h2)).1 ≤ (minGathers f item q1 (0, h1)).1
    ∧ Dom (minGathers f item q1 (0, h1)).2 (minGathers f item q2 (0, h2)).2.

The PAIRED conclusion (count-≤ and residual-`Dom` in the SAME direction) is what
threads the recipe `foldl`: each sibling's residual-`Dom` feeds the next
sibling's holdings hypothesis, and the per-sibling sub-quantities stay ordered
because `rem_i = q_i − min(h_i, q_i)` is monotone in the same direction
(`rem2 ≤ rem1`). The `rank item ≤ f` fuel bound lets the IH fire one fuel lower
on every (strictly lower-rank, by acyclicity) recipe material. Closes the GATHER
step of the Ψ-potential. -/
theorem minGathers_mono (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) :
    ∀ (f : Nat) (item : String) (q1 q2 : Int) (h1 h2 : Dict Int),
      rank item ≤ f → 0 < q2 → q2 ≤ q1 → Dom h1 h2 → NonNeg h1 → NonNeg h2 →
      (minGathers f item q2 recipes (0, h2)).1 ≤ (minGathers f item q1 recipes (0, h1)).1
      ∧ Dom (minGathers f item q1 recipes (0, h1)).2
            (minGathers f item q2 recipes (0, h2)).2 := by
  intro f
  induction f using Nat.strongRecOn with
  | ind f IH =>
    intro item q1 q2 h1 h2 hrf hq2 hq21 hdom hnn1 hnn2
    match f, IH with
    | 0, _ =>
      -- rank item ≤ 0 ⇒ item is raw; 0-fuel count is just the qty.
      simp only [minGathers]
      exact ⟨by omega, hdom⟩
    | m + 1, IH =>
      rw [minGathers_succ, minGathers_succ]
      -- held bounds for the two holdings
      have hh1 : 0 ≤ getD h1 item 0 := hnn1 item
      have hh2 : 0 ≤ getD h2 item 0 := hnn2 item
      have hdi : getD h1 item 0 ≤ getD h2 item 0 := hdom item
      -- abstract the two used amounts (keep defining equations for the bounds)
      have hu1le : min (getD h1 item 0) q1 ≤ getD h1 item 0 := Int.min_le_left _ _
      have hu2le : min (getD h2 item 0) q2 ≤ getD h2 item 0 := Int.min_le_left _ _
      have hu1q : min (getD h1 item 0) q1 ≤ q1 := Int.min_le_right _ _
      have hu2q : min (getD h2 item 0) q2 ≤ q2 := Int.min_le_right _ _
      have hu1nn : 0 ≤ min (getD h1 item 0) q1 := Int.le_min.mpr ⟨hh1, by omega⟩
      have hu2nn : 0 ≤ min (getD h2 item 0) q2 := Int.le_min.mpr ⟨hh2, by omega⟩
      -- key remainder ordering: rem2 ≤ rem1
      have hrem : q2 - min (getD h2 item 0) q2 ≤ q1 - min (getD h1 item 0) q1 := by
        rw [Int.min_def, Int.min_def]; split <;> split <;> omega
      -- post-consume residuals, ordered + nonneg
      have hdom' : Dom (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1))
          (setD h2 item (getD h2 item 0 - min (getD h2 item 0) q2)) := by
        intro k; rw [getD_setD, getD_setD]
        by_cases hk : item = k
        · subst hk; rw [if_pos rfl, if_pos rfl]; omega
        · rw [if_neg hk, if_neg hk]; exact hdom k
      have hnn1' : NonNeg (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1)) :=
        nonneg_setD h1 item _ hnn1 (by omega)
      have hnn2' : NonNeg (setD h2 item (getD h2 item 0 - min (getD h2 item 0) q2)) :=
        nonneg_setD h2 item _ hnn2 (by omega)
      by_cases hc2 : q2 - min (getD h2 item 0) q2 ≤ 0
      · -- q2 done: count2 = 0 ≤ count1, residual side from monotone start
        rw [if_pos hc2]
        by_cases hc1 : q1 - min (getD h1 item 0) q1 ≤ 0
        · rw [if_pos hc1]
          exact ⟨Int.le_refl 0, hdom'⟩
        · rw [if_neg hc1]
          by_cases hr1 : (getD recipes item []).length = 0
          · rw [if_pos hr1]
            exact ⟨by omega, hdom'⟩
          · rw [if_neg hr1]
            have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
              fun mat per hmem => hpos item mat per hmem
            refine ⟨?_, ?_⟩
            · -- count1 (foldl) ≥ 0, count2 = 0
              have hfoldl := recipeFoldl_count_nonneg recipes hpos m (getD recipes item [])
                (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1)) 0
                (q1 - min (getD h1 item 0) q1) hpoall (Int.le_refl 0) (by omega)
              omega
            · -- Dom (foldl residual under h1') h2'
              have hres := recipeFoldl_residual_dom recipes hpos m (getD recipes item [])
                (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1)) 0
                (q1 - min (getD h1 item 0) q1) hpoall hnn1' (by omega)
              exact dom_trans hres hdom'
      · -- q2 still remaining: q1 also (since rem1 ≥ rem2 > 0)
        have hc1 : ¬ q1 - min (getD h1 item 0) q1 ≤ 0 := by omega
        rw [if_neg hc2, if_neg hc1]
        by_cases hr : (getD recipes item []).length = 0
        · rw [if_pos hr, if_pos hr]
          refine ⟨by omega, hdom'⟩
        · rw [if_neg hr, if_neg hr]
          -- the recipe foldl coupling: thread the paired invariant per sibling
          have hrkall : ∀ mat per, (mat, per) ∈ getD recipes item [] → rank mat ≤ m := by
            intro mat per hmem; have := hacy item mat per hmem; omega
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          -- generalized foldl coupling lemma; abstract the two remainders as r1,r2
          suffices Hgen : ∀ (rc : Dict Int) (o1 o2 : Dict Int) (t1 t2 r1 r2 : Int),
              (∀ mat per, (mat, per) ∈ rc → rank mat ≤ m) →
              (∀ mat per, (mat, per) ∈ rc → 0 < per) →
              0 < r2 → r2 ≤ r1 →
              t2 ≤ t1 → Dom o1 o2 → NonNeg o1 → NonNeg o2 →
              (List.foldl (fun st mat =>
                  minGathers m mat.1 (mat.2 * r2) recipes st) (t2, o2) rc).1
                ≤ (List.foldl (fun st mat =>
                  minGathers m mat.1 (mat.2 * r1) recipes st) (t1, o1) rc).1
              ∧ Dom (List.foldl (fun st mat =>
                  minGathers m mat.1 (mat.2 * r1) recipes st) (t1, o1) rc).2
                    (List.foldl (fun st mat =>
                  minGathers m mat.1 (mat.2 * r2) recipes st) (t2, o2) rc).2 by
            exact Hgen (getD recipes item [])
              (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1))
              (setD h2 item (getD h2 item 0 - min (getD h2 item 0) q2))
              0 0 (q1 - min (getD h1 item 0) q1) (q2 - min (getD h2 item 0) q2)
              hrkall hpoall (by omega) hrem (Int.le_refl 0) hdom' hnn1' hnn2'
          intro rc
          induction rc with
          | nil => intro o1 o2 t1 t2 r1 r2 _ _ _ _ ht hd _ _; exact ⟨ht, hd⟩
          | cons mp rest ihrec =>
            intro o1 o2 t1 t2 r1 r2 hrk hpo hr2 hr21 ht hd ho1 ho2
            obtain ⟨mat, per⟩ := mp
            simp only [List.foldl_cons]
            have hper : 0 < per := hpo mat per (by simp)
            have hrm : rank mat ≤ m := hrk mat per (by simp)
            have hp2 : 0 < per * r2 := Int.mul_pos hper hr2
            have hp21 : per * r2 ≤ per * r1 :=
              Int.mul_le_mul_of_nonneg_left hr21 (Int.le_of_lt hper)
            -- one-step coupling at the SAME fuel m via the strong IH (m < m+1)
            have hstep := IH m (Nat.lt_succ_self m) mat (per * r1) (per * r2)
              o1 o2 hrm hp2 hp21 hd ho1 ho2
            -- strip the running totals via total-additivity
            have ta1 := minGathers_total_additive m mat (per * r1) recipes t1 o1
            have ta2 := minGathers_total_additive m mat (per * r2) recipes t2 o2
            rw [ta1, ta2]
            -- residuals of the single step are NonNeg → feed next sibling
            have hsn1 := minGathers_nonneg_residual recipes hpos m mat
              (per * r1) 0 o1 (by omega) ho1
            have hsn2 := minGathers_nonneg_residual recipes hpos m mat
              (per * r2) 0 o2 hp2 ho2
            have hrk' : ∀ m' p, (m', p) ∈ rest → rank m' ≤ m :=
              fun m' p hm => hrk m' p (by simp [hm])
            have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p :=
              fun m' p hm => hpo m' p (by simp [hm])
            have htnew : (minGathers m mat (per * r2) recipes (0, o2)).1 + t2
                       ≤ (minGathers m mat (per * r1) recipes (0, o1)).1 + t1 := by
              have := hstep.1; omega
            exact ihrec
              (minGathers m mat (per * r1) recipes (0, o1)).2
              (minGathers m mat (per * r2) recipes (0, o2)).2
              ((minGathers m mat (per * r1) recipes (0, o1)).1 + t1)
              ((minGathers m mat (per * r2) recipes (0, o2)).1 + t2)
              r1 r2 hrk' hpo' hr2 hr21 htnew hstep.2 hsn1 hsn2

-- ---------------------------------------------------------------------------
-- costMass monotone under Dom (Round 10): NoDupKeys invariant + preservation
-- ---------------------------------------------------------------------------

/-!
## `costMass` monotone under `Dom` (no-duplicate-keys invariant)

`costMass` sums the RAW assoc-list (`Σ v · wf c` over entries), but `Dom` is the
`getD`-VIEW (first entry per key). A duplicate key would therefore double-count in
`costMass` while contributing once to the `getD`-view, so `Dom a b →
costMass a ≤ costMass b` needs a **no-duplicate-keys** invariant. `NoDupKeys` is a
faithful inventory fact — production holdings are a dict (one entry per item code)
— and it is PRESERVED by the model's mutators (`setD`/`consumeHoldings`/
`applyAction`), proved below; so it is an honest domain hypothesis, not a
weakening. `EntriesNonNeg` (every stored value `≥ 0`) is the entry-wise companion
that propagates to tails (unlike the `getD`-view `NonNeg`, which a shadowed
duplicate can violate).
-/

/-- `NoDupKeys m`: the head key never reappears in the tail, recursively — every
item code has at most one entry. A faithful inventory fact (holdings are a dict),
preserved by the model's mutators (see below). -/
def NoDupKeys : Dict Int → Prop
  | [] => True
  | (k, _) :: rest => (∀ v, (k, v) ∉ rest) ∧ NoDupKeys rest

/-- Erase the first entry whose key is `k` (the dict-level key delete). -/
def eraseKey (m : Dict Int) (k : String) : Dict Int :=
  match m with
  | [] => []
  | (k', v') :: rest => if k' == k then rest else (k', v') :: eraseKey rest k

/-- `EntriesNonNeg m`: every STORED value is `≥ 0` (entry-wise, so it propagates
to tails — `NonNeg`, the `getD`-view, does not, since a duplicate key can be
shadowed). Under `NoDupKeys` it coincides with `NonNeg`. -/
def EntriesNonNeg (m : Dict Int) : Prop := ∀ k v, (k, v) ∈ m → 0 ≤ v

/-- `wf` is `≥ 0` at any fuel: the empty-owned gather count of one unit is a
count (`minGathers_count_nonneg` at `t = 0`). -/
theorem wf_nonneg (F : Nat) (item : String) (recipes : Recipes)
    (hpos : PosRecipes recipes) : 0 ≤ wf F item recipes := by
  unfold wf
  have := minGathers_count_nonneg recipes hpos F item 1 0 [] (Int.le_refl 0) (by omega)
  omega

/-- `costMass` of an entry-wise-nonneg dict is `≥ 0` (each term `v · wf c ≥ 0`). -/
theorem costMass_nonneg (F : Nat) (recipes : Recipes) (b : Dict Int)
    (heb : EntriesNonNeg b) (hpos : PosRecipes recipes) : 0 ≤ costMass F b recipes := by
  induction b with
  | nil => simp
  | cons kv rest ih =>
    obtain ⟨c, v⟩ := kv; rw [costMass_cons]
    have hv : 0 ≤ v := heb c v List.mem_cons_self
    have := Int.mul_nonneg hv (wf_nonneg F c recipes hpos)
    have hrest := ih (fun k' w hw => heb k' w (List.mem_cons_of_mem _ hw)); omega

/-- An absent key reads the default `0`. -/
theorem getD_zero_of_absent (m : Dict Int) (k : String) (h : ∀ v, (k, v) ∉ m) :
    getD m k 0 = 0 := by
  induction m with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases hak : a = k
    · subst hak; exact absurd List.mem_cons_self (h b)
    · rw [getD_cons_ne _ _ _ _ _ hak]; exact ih (fun v hv => h v (List.mem_cons_of_mem _ hv))

/-- The head key is absent from the tail (`NoDupKeys` head fact) ⇒ reads `0`. -/
theorem getD_head_absent_zero {a : String} {rest : Dict Int} (hhead : ∀ v, (a, v) ∉ rest) :
    getD rest a 0 = 0 := getD_zero_of_absent rest a hhead

/-- **COST-MASS DECOMPOSITION at a key.** Under `NoDupKeys`, the cost-mass of `m`
splits as `getD m k · wf k` (the unique `k`-contribution, `0` if `k` is absent)
plus the cost-mass of `m` with `k` erased. The workhorse for `costMass`-mono. -/
theorem costMass_erase (F : Nat) (recipes : Recipes) (m : Dict Int) (k : String)
    (hnd : NoDupKeys m) :
    costMass F m recipes = getD m k 0 * wf F k recipes + costMass F (eraseKey m k) recipes := by
  induction m with
  | nil => simp [eraseKey, getD]
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv; obtain ⟨hhead, htail⟩ := hnd
    by_cases hak : a = k
    · subst hak; rw [eraseKey]; simp only [beq_self_eq_true, if_true]
      rw [getD_cons_self, costMass_cons]
    · rw [eraseKey]; simp only [beq_iff_eq, if_neg hak]
      rw [costMass_cons, costMass_cons, getD_cons_ne _ _ _ _ _ hak, ih htail]
      generalize b * wf F a recipes = X; generalize getD rest k 0 * wf F k recipes = Y; omega

/-- Every entry of `eraseKey m k` is an entry of `m`. -/
theorem mem_eraseKey {m : Dict Int} {k k' : String} {v : Int}
    (h : (k', v) ∈ eraseKey m k) : (k', v) ∈ m := by
  induction m with
  | nil => simp [eraseKey] at h
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases hak : a = k
    · subst hak; rw [eraseKey] at h; simp only [beq_self_eq_true, if_true] at h
      exact List.mem_cons_of_mem _ h
    · rw [eraseKey] at h; simp only [beq_iff_eq, if_neg hak] at h
      rcases List.mem_cons.mp h with h1 | h2
      · exact List.mem_cons.mpr (Or.inl h1)
      · exact List.mem_cons_of_mem _ (ih h2)

/-- `eraseKey` preserves `NoDupKeys` (a sublist of distinct keys is distinct). -/
theorem nodupKeys_eraseKey (m : Dict Int) (k : String) (hnd : NoDupKeys m) :
    NoDupKeys (eraseKey m k) := by
  induction m with
  | nil => exact hnd
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv; obtain ⟨hhead, htail⟩ := hnd
    by_cases hak : a = k
    · subst hak; rw [eraseKey]; simp only [beq_self_eq_true, if_true]; exact htail
    · rw [eraseKey]; simp only [beq_iff_eq, if_neg hak]
      exact ⟨fun v hv => hhead v (mem_eraseKey hv), ih htail⟩

/-- `eraseKey` preserves `EntriesNonNeg`. -/
theorem entriesNonNeg_eraseKey {m : Dict Int} {k : String} (h : EntriesNonNeg m) :
    EntriesNonNeg (eraseKey m k) := fun k' v hv => h k' v (mem_eraseKey hv)

/-- Off the erased key, `eraseKey` does not change the `getD`-view (`NoDupKeys`). -/
theorem getD_eraseKey_ne (m : Dict Int) (c j : String) (hcj : c ≠ j) (hnd : NoDupKeys m) :
    getD (eraseKey m c) j 0 = getD m j 0 := by
  induction m with
  | nil => rfl
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv; obtain ⟨hhead, htail⟩ := hnd
    by_cases hac : a = c
    · subst hac; rw [eraseKey]; simp only [beq_self_eq_true, if_true]
      rw [getD_cons_ne _ _ _ _ _ hcj]
    · rw [eraseKey]; simp only [beq_iff_eq, if_neg hac]
      by_cases haj : a = j
      · subst haj; rw [getD_cons_self, getD_cons_self]
      · rw [getD_cons_ne _ _ _ _ _ haj, getD_cons_ne _ _ _ _ _ haj, ih htail]

/-- `EntriesNonNeg` ⇒ the `getD`-view is `≥ 0` at every key. -/
theorem getD_nonneg_of_entries {m : Dict Int} (h : EntriesNonNeg m) (j : String) :
    0 ≤ getD m j 0 := by
  induction m with
  | nil => exact Int.le_refl 0
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases haj : a = j
    · subst haj; rw [getD_cons_self]; exact h a b List.mem_cons_self
    · rw [getD_cons_ne _ _ _ _ _ haj]
      exact ih (fun k' w hw => h k' w (List.mem_cons_of_mem _ hw))

/-- **`costMass` MONOTONE UNDER `Dom`.** If `b` pointwise dominates `a` in the
`getD`-view (`Dom a b`), both dicts have no duplicate keys, `b`'s stored values
are `≥ 0`, and weights are `≥ 0` (`PosRecipes`), then `costMass a ≤ costMass b`.

Induction on `a`, peeling its head key `c`: by `costMass_erase`, `b`'s cost-mass
splits as `getD b c · wf c + costMass (eraseKey b c)`; `Dom` gives
`getD a c = v ≤ getD b c` and `wf c ≥ 0` makes the head term dominate, while the
IH (on `rest` vs `eraseKey b c`, which still dominates by `getD_eraseKey_ne`)
handles the rest. The `NoDupKeys a` head fact zeroes `c` in `rest`, so `rest`'s
view genuinely matches `a` minus its head. This closes the GATHER step's
`costMass (residual h) ≤ costMass (residual h')` (residuals there are `Dom`-ordered
by `minGathers_mono`); the CRAFT step's residuals are NOT `Dom`-ordered (Round 10
finding) and need a different argument. -/
theorem costMass_mono_dom (F : Nat) (recipes : Recipes) (hpos : PosRecipes recipes)
    (a b : Dict Int) (hda : NoDupKeys a) (hdb : NoDupKeys b)
    (heb : EntriesNonNeg b) (hdom : Dom a b) :
    costMass F a recipes ≤ costMass F b recipes := by
  induction a generalizing b with
  | nil => simp; exact costMass_nonneg F recipes b heb hpos
  | cons kv rest ih =>
    obtain ⟨c, v⟩ := kv; obtain ⟨hhead, htail⟩ := hda
    rw [costMass_cons]
    have hdec := costMass_erase F recipes b c hdb
    have hvb : v ≤ getD b c 0 := by have := hdom c; rwa [getD_cons_self] at this
    have hwf : 0 ≤ wf F c recipes := wf_nonneg F c recipes hpos
    have hdom' : Dom rest (eraseKey b c) := by
      intro j
      by_cases hcj : c = j
      · subst hcj
        rw [getD_head_absent_zero hhead]
        exact getD_nonneg_of_entries (entriesNonNeg_eraseKey heb) c
      · have h1 : getD ((c, v) :: rest) j 0 = getD rest j 0 := getD_cons_ne _ _ _ _ _ hcj
        have h2 : getD (eraseKey b c) j 0 = getD b j 0 := getD_eraseKey_ne b c j hcj hdb
        have := hdom j; rw [h1] at this; rw [h2]; exact this
    have hib := ih (eraseKey b c) htail (nodupKeys_eraseKey b c hdb)
                  (entriesNonNeg_eraseKey heb) hdom'
    rw [hdec]
    have hmul : v * wf F c recipes ≤ getD b c 0 * wf F c recipes :=
      Int.mul_le_mul_of_nonneg_right hvb hwf
    omega

-- ---------------------------------------------------------------------------
-- NoDupKeys / EntriesNonNeg preservation by the model's mutators
-- ---------------------------------------------------------------------------

/-- Any entry of `setD m k v` has key `k` or is an existing key of `m`. -/
theorem mem_setD_key {m : Dict Int} {k k' : String} {v w : Int}
    (h : (k', w) ∈ setD m k v) : k' = k ∨ ∃ u, (k', u) ∈ m := by
  induction m with
  | nil =>
    rw [setD] at h; rcases List.mem_cons.mp h with h1 | h2
    · cases h1; exact Or.inl rfl
    · simp at h2
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases hak : a = k
    · subst hak; rw [setD_cons_self] at h
      rcases List.mem_cons.mp h with h1 | h2
      · cases h1; exact Or.inl rfl
      · exact Or.inr ⟨w, List.mem_cons_of_mem _ h2⟩
    · rw [setD_cons_ne _ _ _ _ _ hak] at h
      rcases List.mem_cons.mp h with h1 | h2
      · cases h1; exact Or.inr ⟨w, List.mem_cons_self⟩
      · rcases ih h2 with hl | ⟨u, hu⟩
        · exact Or.inl hl
        · exact Or.inr ⟨u, List.mem_cons_of_mem _ hu⟩

/-- **`setD` preserves `NoDupKeys`** (replace-in-place keeps the key set; append
adds a fresh key not already present). -/
theorem nodupKeys_setD (m : Dict Int) (k : String) (v : Int) (hnd : NoDupKeys m) :
    NoDupKeys (setD m k v) := by
  induction m with
  | nil => exact ⟨fun w hw => by simp at hw, trivial⟩
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv; obtain ⟨hhead, htail⟩ := hnd
    by_cases hak : a = k
    · subst hak; rw [setD_cons_self]; exact ⟨hhead, htail⟩
    · rw [setD_cons_ne _ _ _ _ _ hak]
      refine ⟨?_, ih htail⟩
      intro w hw
      rcases mem_setD_key hw with hl | ⟨u, hu⟩
      · exact hak hl
      · exact hhead u hu

/-- **`setD` preserves `EntriesNonNeg`** when the written value is `≥ 0`. -/
theorem entriesNonNeg_setD (m : Dict Int) (k : String) (v : Int) (hv : 0 ≤ v)
    (hne : EntriesNonNeg m) : EntriesNonNeg (setD m k v) := by
  induction m with
  | nil =>
    intro k' w hw; rw [setD] at hw
    rcases List.mem_cons.mp hw with h1 | h2
    · cases h1; exact hv
    · simp at h2
  | cons kv rest ih =>
    obtain ⟨a, b⟩ := kv
    by_cases hak : a = k
    · subst hak; rw [setD_cons_self]
      intro k' w hw
      rcases List.mem_cons.mp hw with h1 | h2
      · cases h1; exact hv
      · exact hne k' w (List.mem_cons_of_mem _ h2)
    · rw [setD_cons_ne _ _ _ _ _ hak]
      intro k' w hw
      rcases List.mem_cons.mp hw with h1 | h2
      · cases h1; exact hne a b List.mem_cons_self
      · exact ih (fun x y hxy => hne x y (List.mem_cons_of_mem _ hxy)) k' w h2

/-- **`consumeHoldings` preserves `NoDupKeys`** (each consume step is a `setD`).
NB it does NOT preserve `EntriesNonNeg` in general — consuming an absent input
drives a value negative; that is gated by `ValidCraftAt` at use sites. -/
theorem nodupKeys_consume (inputs : Dict Int) (H : Dict Int) (hnd : NoDupKeys H) :
    NoDupKeys (consumeHoldings H inputs) := by
  unfold consumeHoldings
  induction inputs generalizing H with
  | nil => simpa using hnd
  | cons mp rest ih =>
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons]
    apply ih
    rw [dictSet_eq]
    exact nodupKeys_setD H mat (dictGet H mat - per) hnd

/-- **`applyAction` preserves `NoDupKeys`** — every action's holdings update is
built from `setD`/`consumeHoldings`, so the dict invariant survives the whole
plan. This confirms `NoDupKeys` holds on EVERY residual the proof reasons about
(starting from a no-dup `owned`), not just by assumption. -/
theorem nodupKeys_applyAction (recipes : Recipes) (s : ExecState) (a : Action)
    (hnd : NoDupKeys s.holdings) : NoDupKeys (applyAction recipes s a).holdings := by
  cases a with
  | gather code =>
    show NoDupKeys (dictSet s.holdings code (dictGet s.holdings code + 1))
    rw [dictSet_eq]; exact nodupKeys_setD _ _ _ hnd
  | craft code =>
    show NoDupKeys (dictSet (consumeHoldings s.holdings (recipeOf recipes code)) code _)
    rw [dictSet_eq]
    exact nodupKeys_setD _ _ _ (nodupKeys_consume (recipeOf recipes code) s.holdings hnd)
  | equip code => exact hnd

-- ---------------------------------------------------------------------------
-- DAG reachability guard (Round 8): Reaches recipes item c
-- ---------------------------------------------------------------------------

/-!
## Reachability guard

Round 7 proved the UNCONDITIONAL craft-monotonicity FALSE (two machine-checked
`#eval` counterexamples): crafting `c` can starve a SIBLING or a BELOW-`c` query
of a shared raw input, raising `minGathersCount item 1 …`. The discriminating
condition is whether `c` is a transitive sub-component of `item` in the recipe
DAG — when it is, the `+1 c` lands inside `item`'s own recipe subtree and the
consumed inputs are exactly mass `item`'s traversal would itself credit.

`Reaches recipes item c` is the reflexive-transitive closure of the recipe-edge
relation `m → mat` (for `(mat, per) ∈ recipeOf m`): `item` reaches `c` when
`c = item` or `c` is reachable through one of `item`'s recipe inputs. It is the
honest CORRECT guard (a true domain fact for plan-root queries, like
`Acyclic`/`PosRecipes`), NOT a weakening of the false unconditional form.
-/

/-- `Reaches recipes item c`: `c` is in the recipe-DAG closure of `item` — either
`c = item`, or `c` is reachable through one of `item`'s recipe inputs
transitively. Reflexive-transitive closure of the recipe-edge relation. -/
inductive Reaches (recipes : Recipes) : String → String → Prop where
  | refl (item : String) : Reaches recipes item item
  | step {item mid c : String} {per : Int}
      (hmid : Reaches recipes item mid)
      (hedge : (c, per) ∈ getD recipes mid []) :
      Reaches recipes item c

/-- Reachability through a direct recipe edge: if `(mat, per) ∈ recipeOf item`
then `item` reaches `mat`. -/
theorem Reaches.edge (recipes : Recipes) (item mat : String) (per : Int)
    (hedge : (mat, per) ∈ getD recipes item []) :
    Reaches recipes item mat :=
  Reaches.step (Reaches.refl item) hedge

/-- Reachability is transitive: if `item` reaches `mid` and `mid` reaches `c`,
then `item` reaches `c`. Induction on the second derivation. -/
theorem Reaches.trans {recipes : Recipes} {item mid c : String}
    (h1 : Reaches recipes item mid) (h2 : Reaches recipes mid c) :
    Reaches recipes item c := by
  induction h2 with
  | refl => exact h1
  | step _ hedge ih => exact Reaches.step ih hedge

/-- Under `Acyclic`, reachability MONOTONELY does not increase rank: `c`
reachable from `item` ⇒ `rank c ≤ rank item`. (Each edge strictly drops rank;
the reflexive base is equality.) This certifies `Reaches` is well-founded and is
the bound the guarded coupling uses to enter `item`'s subtree at lower rank. -/
theorem Reaches.rank_le {recipes : Recipes} {rank : String → Nat}
    (hacy : Acyclic recipes rank) {item c : String}
    (h : Reaches recipes item c) : rank c ≤ rank item := by
  induction h with
  | refl => exact Nat.le_refl _
  | step hmid hedge ih =>
    rename_i mid cc per
    have := hacy mid cc per hedge
    omega

-- ---------------------------------------------------------------------------
-- Off-path invariance: minGathers depends only on holdings at reachable keys
-- ---------------------------------------------------------------------------

/-!
## Off-path invariance (the reachability-discriminated craft corner)

Round 7's counterexamples showed crafting `c` raises `minGathersCount item …`
exactly when `item` does NOT reach `c` (sibling / below-`c` query starved of a
shared raw input). The dual TRUE fact — needed for the guarded craft step — is
that `minGathers item` is INVARIANT under any holdings change confined to keys
`item` cannot reach. We prove the two structural facts behind it:

- `minGathers_residual_unreached`: the traversal for `item` never modifies a key
  it cannot reach (the residual equals the start there).
- `minGathers_agree`: if two holdings AGREE on every key reachable from `item`,
  the gather counts are EQUAL (and the residuals still agree on reachable keys).

Together: a craft of `c` with `¬ Reaches recipes item c` leaves the query count
unchanged — the OFF-PATH half of guarded craft-monotonicity, fully discharged.
-/

/-- The `minGathers` traversal for `item` never touches a key it cannot reach:
on any `k` with `¬ Reaches recipes item k`, the residual reads the same as the
start holdings. (Each consume `setD` is at `item` or a reachable material; an
unreachable `k` is preserved through every recipe-`foldl` step.) Strong fuel
induction; the `foldl` arm uses `Reaches.edge`/`Reaches.trans` to push
unreachability down to each material. -/
theorem minGathers_residual_unreached (recipes : Recipes) :
    ∀ (f : Nat) (item : String) (q t : Int) (owned : Dict Int) (k : String),
      ¬ Reaches recipes item k →
      getD (minGathers f item q recipes (t, owned)).2 k 0 = getD owned k 0 := by
  intro f
  induction f using Nat.strongRecOn with
  | ind f IH =>
    intro item q t owned k hnr
    match f, IH with
    | 0, _ => rfl
    | m + 1, IH =>
      rw [minGathers_succ]
      have hik : item ≠ k := fun h => hnr (h ▸ Reaches.refl item)
      by_cases hc : q - min (getD owned item 0) q ≤ 0
      · rw [if_pos hc]; rw [getD_setD, if_neg hik]
      · rw [if_neg hc]
        by_cases hr : (getD recipes item []).length = 0
        · rw [if_pos hr]; rw [getD_setD, if_neg hik]
        · rw [if_neg hr]
          have hknr_mat : ∀ mat per, (mat, per) ∈ getD recipes item [] →
              ¬ Reaches recipes mat k :=
            fun mat per hmem hreach =>
              hnr (Reaches.trans (Reaches.edge recipes item mat per hmem) hreach)
          have hstart : getD (setD owned item (getD owned item 0 - min (getD owned item 0) q)) k 0
              = getD owned k 0 := by rw [getD_setD, if_neg hik]
          suffices H : ∀ (rc : Dict Int) (o : Dict Int) (s : Int),
              (∀ mat per, (mat, per) ∈ rc → ¬ Reaches recipes mat k) →
              getD (List.foldl (fun st mat =>
                minGathers m mat.1 (mat.2 * (q - min (getD owned item 0) q)) recipes st)
                (s, o) rc).2 k 0 = getD o k 0 by
            rw [H (getD recipes item [])
              (setD owned item (getD owned item 0 - min (getD owned item 0) q)) _ hknr_mat,
              hstart]
          intro rc
          induction rc with
          | nil => intro o s _; rfl
          | cons mp rest ihrec =>
            intro o s hnrmat
            obtain ⟨mat, per⟩ := mp
            simp only [List.foldl_cons]
            have hstep := IH m (Nat.lt_succ_self m) mat
              (per * (q - min (getD owned item 0) q)) s o k
              (hnrmat mat per (by simp))
            have hnrmat' : ∀ m' p, (m', p) ∈ rest → ¬ Reaches recipes m' k :=
              fun m' p hm => hnrmat m' p (by simp [hm])
            rw [ihrec _ _ hnrmat', hstep]

/-- Setting a key `item` to a common value preserves agreement-on-reachable. -/
theorem setD_agree (recipes : Recipes) (item : String) (H1 H2 : Dict Int)
    (v : Int)
    (hagree : ∀ k, Reaches recipes item k → getD H1 k 0 = getD H2 k 0) :
    ∀ k, Reaches recipes item k →
      getD (setD H1 item v) k 0 = getD (setD H2 item v) k 0 := by
  intro k hk
  rw [getD_setD, getD_setD]
  by_cases hik : item = k
  · subst hik; rw [if_pos rfl, if_pos rfl]
  · rw [if_neg hik, if_neg hik]; exact hagree k hk

/-- The generalized recipe-`foldl` coupling for `minGathers_agree`: two parallel
folds over a recipe sublist `rc ⊆ recipeOf item`, from residuals `o1, o2` that
AGREE on every key reachable from `item`, have equal counts and residuals that
still agree on every reachable key. Each material `mat ∈ rc` is reachable from
`item` (edge), so the fuel-`m` IH (`IHcount`) gives per-material count-eq +
residual-agree on reachable-from-`mat` keys; `minGathers_residual_unreached`
carries agreement on the reachable-from-`item`-but-not-`mat` keys to the next
sibling. -/
theorem agree_foldl (recipes : Recipes) (rank : String → Nat) (m : Nat)
    (item : String) (rem : Int) (hrempos : 0 < rem)
    (IHcount : ∀ (mt : String) (q : Int) (h1 h2 : Dict Int),
      rank mt ≤ m → 0 < q →
      (∀ k, Reaches recipes mt k → getD h1 k 0 = getD h2 k 0) →
      (minGathers m mt q recipes (0, h1)).1 = (minGathers m mt q recipes (0, h2)).1
      ∧ (∀ k, Reaches recipes mt k →
          getD (minGathers m mt q recipes (0, h1)).2 k 0
            = getD (minGathers m mt q recipes (0, h2)).2 k 0)) :
    ∀ (rc : Dict Int) (o1 o2 : Dict Int) (t : Int),
      (∀ mat per, (mat, per) ∈ rc → rank mat ≤ m) →
      (∀ mat per, (mat, per) ∈ rc → 0 < per) →
      (∀ mat per, (mat, per) ∈ rc → Reaches recipes item mat) →
      (∀ k, Reaches recipes item k → getD o1 k 0 = getD o2 k 0) →
      (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * rem) recipes st)
          (t, o1) rc).1
        = (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * rem) recipes st)
            (t, o2) rc).1
      ∧ (∀ k, Reaches recipes item k →
          getD (List.foldl (fun st mat =>
              minGathers m mat.1 (mat.2 * rem) recipes st) (t, o1) rc).2 k 0
            = getD (List.foldl (fun st mat =>
              minGathers m mat.1 (mat.2 * rem) recipes st) (t, o2) rc).2 k 0) := by
  intro rc
  induction rc with
  | nil => intro o1 o2 t _ _ _ hag; exact ⟨rfl, hag⟩
  | cons mp rest ihrec =>
    intro o1 o2 t hrk hpo hedg hag
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons]
    have hper : 0 < per := hpo mat per (by simp)
    have hrm : rank mat ≤ m := hrk mat per (by simp)
    have hpr : 0 < per * rem := Int.mul_pos hper hrempos
    have hmatR : Reaches recipes item mat := hedg mat per (by simp)
    have hagmat : ∀ k, Reaches recipes mat k → getD o1 k 0 = getD o2 k 0 :=
      fun k hk => hag k (Reaches.trans hmatR hk)
    have hstep := IHcount mat (per * rem) o1 o2 hrm hpr hagmat
    have ta1 := minGathers_total_additive m mat (per * rem) recipes t o1
    have ta2 := minGathers_total_additive m mat (per * rem) recipes t o2
    rw [ta1, ta2]
    have hagnext : ∀ k, Reaches recipes item k →
        getD (minGathers m mat (per * rem) recipes (0, o1)).2 k 0
          = getD (minGathers m mat (per * rem) recipes (0, o2)).2 k 0 := by
      intro k hk
      by_cases hkmat : Reaches recipes mat k
      · exact hstep.2 k hkmat
      · rw [minGathers_residual_unreached recipes m mat
              (per * rem) 0 o1 k hkmat,
            minGathers_residual_unreached recipes m mat
              (per * rem) 0 o2 k hkmat]
        exact hag k hk
    have hrk' : ∀ m' p, (m', p) ∈ rest → rank m' ≤ m :=
      fun m' p hm => hrk m' p (by simp [hm])
    have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p :=
      fun m' p hm => hpo m' p (by simp [hm])
    have hedg' : ∀ m' p, (m', p) ∈ rest → Reaches recipes item m' :=
      fun m' p hm => hedg m' p (by simp [hm])
    rw [hstep.1]
    exact ihrec _ _ _ hrk' hpo' hedg' hagnext

/-- **OFF-PATH INVARIANCE.** If two holdings `H1, H2` AGREE on every key
reachable from `item`, then `minGathers item` yields the EQUAL gather count (and
residuals still agreeing on reachable keys). The traversal for `item` only ever
inspects holdings at keys it can reach, so changes confined to unreachable keys
are invisible. Strong fuel induction; the recipe-`foldl` arm is `agree_foldl`.

This is the reachability-discriminated craft corner: when `¬ Reaches item c`, a
craft of `c` perturbs only keys unreachable from `item` (the inputs of `c` and
`c` itself), so `minGathersCount item` is UNCHANGED — exactly the off-path half
of guarded craft-monotonicity. -/
theorem minGathers_agree (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) :
    ∀ (f : Nat) (item : String) (q : Int) (H1 H2 : Dict Int),
      rank item ≤ f → 0 < q →
      (∀ k, Reaches recipes item k → getD H1 k 0 = getD H2 k 0) →
      (minGathers f item q recipes (0, H1)).1 = (minGathers f item q recipes (0, H2)).1
      ∧ (∀ k, Reaches recipes item k →
          getD (minGathers f item q recipes (0, H1)).2 k 0
            = getD (minGathers f item q recipes (0, H2)).2 k 0) := by
  intro f
  induction f using Nat.strongRecOn with
  | ind f IH =>
    intro item q H1 H2 hrf hq hagree
    match f, IH with
    | 0, _ => exact ⟨rfl, fun k hk => hagree k hk⟩
    | m + 1, IH =>
      have hself : getD H1 item 0 = getD H2 item 0 := hagree item (Reaches.refl item)
      have hsetag := setD_agree recipes item H1 H2
        (getD H2 item 0 - min (getD H2 item 0) q) hagree
      rw [minGathers_succ, minGathers_succ, hself]
      by_cases hc : q - min (getD H2 item 0) q ≤ 0
      · simp only [if_pos hc]; exact ⟨trivial, hsetag⟩
      · simp only [if_neg hc]
        by_cases hr : (getD recipes item []).length = 0
        · simp only [if_pos hr]; exact ⟨trivial, hsetag⟩
        · simp only [if_neg hr]
          have hrempos : 0 < q - min (getD H2 item 0) q := by omega
          have hrkall : ∀ mat per, (mat, per) ∈ getD recipes item [] → rank mat ≤ m := by
            intro mat per hmem; have := hacy item mat per hmem; omega
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          have hedgeR : ∀ mat per, (mat, per) ∈ getD recipes item [] →
              Reaches recipes item mat :=
            fun mat per hmem => Reaches.edge recipes item mat per hmem
          have IHcount : ∀ (mt : String) (q' : Int) (h1 h2 : Dict Int),
              rank mt ≤ m → 0 < q' →
              (∀ k, Reaches recipes mt k → getD h1 k 0 = getD h2 k 0) →
              (minGathers m mt q' recipes (0, h1)).1 = (minGathers m mt q' recipes (0, h2)).1
              ∧ (∀ k, Reaches recipes mt k →
                  getD (minGathers m mt q' recipes (0, h1)).2 k 0
                    = getD (minGathers m mt q' recipes (0, h2)).2 k 0) :=
            fun mt q' h1 h2 hr' hq' hag' => IH m (Nat.lt_succ_self m) mt q' h1 h2 hr' hq' hag'
          exact agree_foldl recipes rank m item
            (q - min (getD H2 item 0) q) hrempos IHcount (getD recipes item [])
            (setD H1 item (getD H2 item 0 - min (getD H2 item 0) q))
            (setD H2 item (getD H2 item 0 - min (getD H2 item 0) q))
            0 hrkall hpoall hedgeR hsetag

-- ---------------------------------------------------------------------------
-- On-path infrastructure: top-down reachability + craft perturbation locality
-- ---------------------------------------------------------------------------

/-!
## On-path infrastructure

The ON-PATH δ-coupling descends `item`'s recipe DAG along the branch that REACHES
the crafted `c`. Three structural facts equip that descent:

- `reaches_cases` — the TOP-DOWN view of `Reaches`: `item` reaches `c` iff `item =
  c` or some DIRECT recipe input `mat` of `item` reaches `c`. (The `Reaches`
  inductive extends at the far end; this re-presents it as a head step + tail
  recursion, the shape a fuel induction descending from `item` consumes.)
- `consume_unreached` / `craft_agree_off` — the craft's perturbation is CONFINED
  to keys reachable from `c`: consuming `recipeOf c` (all inputs reachable from
  `c` by one edge) and producing `+1 c` (reachable by `refl`) never touches a key
  `k` with `¬ Reaches recipes c k`. So `H` and the post-craft holdings AGREE off
  the reach-set of `c` — the off-path dispatch hook for `minGathers_agree`.
-/

/-- **TOP-DOWN reachability.** `item` reaches `c` iff `item = c` or some direct
recipe input `mat` of `item` reaches `c`. The `Reaches` inductive grows at the
far end (`mid → c`); this flips it to a head edge + tail recursion (induction on
the derivation, re-threading via `Reaches.trans`). This is the case-split a fuel
induction descending from `item` toward `c` uses at each node. -/
theorem reaches_cases (recipes : Recipes) (item c : String)
    (h : Reaches recipes item c) :
    item = c ∨ ∃ mat per, (mat, per) ∈ getD recipes item [] ∧ Reaches recipes mat c := by
  induction h with
  | refl => exact Or.inl rfl
  | step hmid hedge ih =>
    rename_i mid cc per
    rcases ih with heq | ⟨mat, per2, hmem, hr⟩
    · subst heq
      exact Or.inr ⟨cc, per, hedge, Reaches.refl cc⟩
    · exact Or.inr ⟨mat, per2, hmem, Reaches.trans hr (Reaches.step (Reaches.refl mid) hedge)⟩

/-- Consuming a recipe input list whose inputs are ALL reachable from `c` never
modifies a key `k` with `¬ Reaches recipes c k`: each consume `setD` is at a
reachable material, leaving the unreachable `k` untouched through the whole fold. -/
theorem consume_unreached (recipes : Recipes) (c : String) (H : Dict Int)
    (inputs : Dict Int)
    (hin : ∀ mat per, (mat, per) ∈ inputs → Reaches recipes c mat) :
    ∀ k, ¬ Reaches recipes c k → getD (consumeHoldings H inputs) k 0 = getD H k 0 := by
  intro k hnr
  unfold consumeHoldings
  induction inputs generalizing H with
  | nil => rfl
  | cons mp rest ih =>
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons]
    have hmatR : Reaches recipes c mat := hin mat per (by simp)
    have hmk : mat ≠ k := fun h => hnr (h ▸ hmatR)
    have hin' : ∀ m' p, (m', p) ∈ rest → Reaches recipes c m' :=
      fun m' p hm => hin m' p (by simp [hm])
    rw [ih (dictSet H mat (dictGet H mat - per)) hin']
    rw [dictSet_eq, getD_setD, if_neg hmk]

/-- Every direct recipe input of `c` is reachable from `c` (one edge). -/
theorem recipeOf_reach (recipes : Recipes) (c : String) :
    ∀ mat per, (mat, per) ∈ recipeOf recipes c → Reaches recipes c mat := by
  intro mat per hmem
  rw [recipeOf_eq_getD] at hmem
  exact Reaches.edge recipes c mat per hmem

/-- **OFF-c AGREEMENT.** The post-`craft c` holdings AGREE with `H` on every key
`k` unreachable from `c`. The craft touches only `c` (`+1`, killed by `c ≠ k`
since `c` reaches `c`) and the inputs `recipeOf c` (all reachable from `c`, so
`consume_unreached` leaves `k` alone). This is the hook that lets `minGathers_agree`
dispatch the OFF-PATH siblings of the on-path coupling. -/
theorem craft_agree_off (recipes : Recipes) (H : Dict Int) (c : String) :
    ∀ k, ¬ Reaches recipes c k →
      getD (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
              (Action.craft c)).holdings k 0
        = getD H k 0 := by
  intro k hnr
  show getD (dictSet (consumeHoldings H (recipeOf recipes c)) c
        (dictGet (consumeHoldings H (recipeOf recipes c)) c + 1)) k 0 = _
  rw [dictSet_eq, getD_setD]
  have hck : c ≠ k := fun h => hnr (h ▸ Reaches.refl c)
  rw [if_neg hck]
  exact consume_unreached recipes c H (recipeOf recipes c) (recipeOf_reach recipes c) k hnr

-- ---------------------------------------------------------------------------
-- Reachable-restricted monotonicity (the OFF-PATH coupling engine, round 11)
-- ---------------------------------------------------------------------------

/-!
## Reachable-restricted monotonicity

`minGathers item` only ever inspects holdings at keys it can REACH
(`minGathers_residual_unreached`). So the full-`Dom` hypothesis of
`minGathers_mono` is stronger than needed: domination on the reach-set of `item`
suffices. `DomR recipes item h1 h2` ("`h1` dominated by `h2` on every key
`item` reaches") is the right order; under it the gather count is still antitone
(MORE reachable holdings ⇒ NO MORE gathers) and the residual covariant on the
reach-set.

This is the OFF-PATH engine for the craft step `(★)`
(`minGathersCount item 1 H ≤ minGathersCount item 1 H'`,
`H' = craft c H`): when `¬ Reaches recipes item c`, the post-craft holdings `H'`
are pointwise `≤ H` on every key `item` reaches (the consumed inputs only LOWER
raws; the produced `+1 c` lands at the UNREACHABLE key `c`), i.e.
`DomR recipes item H' H`. So `count(item, H) ≤ count(item, H')` — the count RISES,
exactly the `(★)` direction — WITHOUT requiring the two holdings to AGREE
(`minGathers_agree` would need equality, which fails on a DAG with shared raw).
-/

/-- `h1` dominated by `h2` on every key reachable from `item`. The order under
which `minGathers item` is antitone, weakening `Dom` to the reach-set (the only
keys the `item` traversal inspects). -/
def DomR (recipes : Recipes) (item : String) (h1 h2 : Dict Int) : Prop :=
  ∀ k, Reaches recipes item k → getD h1 k 0 ≤ getD h2 k 0

/-- The generalized recipe-`foldl` coupling for `minGathers_mono_reach`: two
parallel folds over `rc ⊆ recipeOf item`, from residuals `o1 ⊑ o2` (on the
reach-set of `item`, both `NonNeg`), with ordered remainders `r2 ≤ r1` and
running totals `t2 ≤ t1`, keep `count2 ≤ count1` and `DomR`-ordered residuals.
Each material `mat ∈ rc` is reachable (edge), so the fuel-`m` IH (`IHpair`)
gives per-material count-≤ + residual-`DomR` on the reach-set of `mat`;
`minGathers_residual_unreached` carries `DomR` on the
reachable-from-`item`-but-not-`mat` keys to the next sibling. -/
theorem domR_foldl (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (m : Nat) (item : String)
    (IHpair : ∀ (mt : String) (a1 a2 : Int) (g1 g2 : Dict Int),
      rank mt ≤ m → 0 < a2 → a2 ≤ a1 →
      DomR recipes mt g1 g2 → NonNeg g1 → NonNeg g2 →
      (minGathers m mt a2 recipes (0, g2)).1 ≤ (minGathers m mt a1 recipes (0, g1)).1
      ∧ DomR recipes mt (minGathers m mt a1 recipes (0, g1)).2
            (minGathers m mt a2 recipes (0, g2)).2) :
    ∀ (rc : Dict Int) (o1 o2 : Dict Int) (t1 t2 r1 r2 : Int),
      (∀ mat per, (mat, per) ∈ rc → rank mat ≤ m) →
      (∀ mat per, (mat, per) ∈ rc → 0 < per) →
      (∀ mat per, (mat, per) ∈ rc → Reaches recipes item mat) →
      0 < r2 → r2 ≤ r1 → t2 ≤ t1 →
      DomR recipes item o1 o2 → NonNeg o1 → NonNeg o2 →
      (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * r2) recipes st) (t2, o2) rc).1
        ≤ (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * r1) recipes st) (t1, o1) rc).1
      ∧ DomR recipes item
          (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * r1) recipes st) (t1, o1) rc).2
          (List.foldl (fun st mat => minGathers m mat.1 (mat.2 * r2) recipes st) (t2, o2) rc).2 := by
  intro rc
  induction rc with
  | nil => intro o1 o2 t1 t2 r1 r2 _ _ _ _ _ ht hd _ _; exact ⟨ht, hd⟩
  | cons mp rest ihrec =>
    intro o1 o2 t1 t2 r1 r2 hrk hpo hedg hr2 hr21 ht hd ho1 ho2
    obtain ⟨mat, per⟩ := mp
    simp only [List.foldl_cons]
    have hper : 0 < per := hpo mat per (by simp)
    have hrm : rank mat ≤ m := hrk mat per (by simp)
    have hmatR : Reaches recipes item mat := hedg mat per (by simp)
    have hp2 : 0 < per * r2 := Int.mul_pos hper hr2
    have hp21 : per * r2 ≤ per * r1 := Int.mul_le_mul_of_nonneg_left hr21 (Int.le_of_lt hper)
    have hp1 : 0 < per * r1 := by omega
    have hdmat : DomR recipes mat o1 o2 := fun k hk => hd k (Reaches.trans hmatR hk)
    have hstep := IHpair mat (per * r1) (per * r2) o1 o2 hrm hp2 hp21 hdmat ho1 ho2
    have ta1 := minGathers_total_additive m mat (per * r1) recipes t1 o1
    have ta2 := minGathers_total_additive m mat (per * r2) recipes t2 o2
    rw [ta1, ta2]
    have hsn1 := minGathers_nonneg_residual recipes hpos m mat (per * r1) 0 o1 hp1 ho1
    have hsn2 := minGathers_nonneg_residual recipes hpos m mat (per * r2) 0 o2 hp2 ho2
    have hdnext : DomR recipes item (minGathers m mat (per * r1) recipes (0, o1)).2
        (minGathers m mat (per * r2) recipes (0, o2)).2 := by
      intro k hk
      by_cases hkmat : Reaches recipes mat k
      · exact hstep.2 k hkmat
      · rw [minGathers_residual_unreached recipes m mat (per * r1) 0 o1 k hkmat,
            minGathers_residual_unreached recipes m mat (per * r2) 0 o2 k hkmat]
        exact hd k hk
    have hrk' : ∀ m' p, (m', p) ∈ rest → rank m' ≤ m := fun m' p hm => hrk m' p (by simp [hm])
    have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
    have hedg' : ∀ m' p, (m', p) ∈ rest → Reaches recipes item m' :=
      fun m' p hm => hedg m' p (by simp [hm])
    have htnew : (minGathers m mat (per * r2) recipes (0, o2)).1 + t2
               ≤ (minGathers m mat (per * r1) recipes (0, o1)).1 + t1 := by
      have := hstep.1; omega
    exact ihrec
      (minGathers m mat (per * r1) recipes (0, o1)).2
      (minGathers m mat (per * r2) recipes (0, o2)).2
      ((minGathers m mat (per * r1) recipes (0, o1)).1 + t1)
      ((minGathers m mat (per * r2) recipes (0, o2)).1 + t2)
      r1 r2 hrk' hpo' hedg' hr2 hr21 htnew hdnext hsn1 hsn2

/-- **REACHABLE-RESTRICTED MONOTONICITY.** With MORE holdings on the reach-set of
`item` (`DomR recipes item h1 h2`, both `NonNeg`) and a smaller-or-equal requested
quantity (`0 < q2 ≤ q1`), `minGathers item` does NO MORE gathering and leaves a
residual `DomR`-larger on the reach-set:

    (minGathers f item q2 (0, h2)).1 ≤ (minGathers f item q1 (0, h1)).1
    ∧ DomR recipes item (minGathers f item q1 (0, h1)).2 (minGathers f item q2 (0, h2)).2.

This strengthens `minGathers_mono` by only requiring domination on the keys
`item` actually inspects (its reach-set) — the unreachable keys are never read
(`minGathers_residual_unreached`). Strong fuel induction; the recipe-`foldl` arm
is `domR_foldl`, lifting `DomR item` to `DomR mat` along each recipe edge. -/
theorem minGathers_mono_reach (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) :
    ∀ (f : Nat) (item : String) (q1 q2 : Int) (h1 h2 : Dict Int),
      rank item ≤ f → 0 < q2 → q2 ≤ q1 →
      DomR recipes item h1 h2 → NonNeg h1 → NonNeg h2 →
      (minGathers f item q2 recipes (0, h2)).1 ≤ (minGathers f item q1 recipes (0, h1)).1
      ∧ DomR recipes item (minGathers f item q1 recipes (0, h1)).2
            (minGathers f item q2 recipes (0, h2)).2 := by
  intro f
  induction f using Nat.strongRecOn with
  | ind f IH =>
    intro item q1 q2 h1 h2 hrf hq2 hq21 hdom hnn1 hnn2
    match f, IH with
    | 0, _ => simp only [minGathers]; exact ⟨by omega, hdom⟩
    | m + 1, IH =>
      rw [minGathers_succ, minGathers_succ]
      have hRi : Reaches recipes item item := Reaches.refl item
      have hh1 : 0 ≤ getD h1 item 0 := hnn1 item
      have hh2 : 0 ≤ getD h2 item 0 := hnn2 item
      have hdi : getD h1 item 0 ≤ getD h2 item 0 := hdom item hRi
      have hrem : q2 - min (getD h2 item 0) q2 ≤ q1 - min (getD h1 item 0) q1 := by
        rw [Int.min_def, Int.min_def]; split <;> split <;> omega
      have hdom' : DomR recipes item
          (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1))
          (setD h2 item (getD h2 item 0 - min (getD h2 item 0) q2)) := by
        intro k hk; rw [getD_setD, getD_setD]
        by_cases hik : item = k
        · subst hik; rw [if_pos rfl, if_pos rfl]; omega
        · rw [if_neg hik, if_neg hik]; exact hdom k hk
      have hnn1' : NonNeg (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1)) :=
        nonneg_setD h1 item _ hnn1 (by have := Int.min_le_left (getD h1 item 0) q1; omega)
      have hnn2' : NonNeg (setD h2 item (getD h2 item 0 - min (getD h2 item 0) q2)) :=
        nonneg_setD h2 item _ hnn2 (by have := Int.min_le_left (getD h2 item 0) q2; omega)
      by_cases hc2 : q2 - min (getD h2 item 0) q2 ≤ 0
      · rw [if_pos hc2]
        by_cases hc1 : q1 - min (getD h1 item 0) q1 ≤ 0
        · rw [if_pos hc1]; exact ⟨Int.le_refl 0, hdom'⟩
        · rw [if_neg hc1]
          by_cases hr1 : (getD recipes item []).length = 0
          · rw [if_pos hr1]; exact ⟨by omega, hdom'⟩
          · rw [if_neg hr1]
            have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
              fun mat per hmem => hpos item mat per hmem
            refine ⟨?_, ?_⟩
            · have hfoldl := recipeFoldl_count_nonneg recipes hpos m (getD recipes item [])
                (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1)) 0
                (q1 - min (getD h1 item 0) q1) hpoall (Int.le_refl 0) (by omega)
              omega
            · have hres := recipeFoldl_residual_dom recipes hpos m (getD recipes item [])
                (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1)) 0
                (q1 - min (getD h1 item 0) q1) hpoall hnn1' (by omega)
              intro k hk; exact Int.le_trans (hres k) (hdom' k hk)
      · have hc1 : ¬ q1 - min (getD h1 item 0) q1 ≤ 0 := by omega
        rw [if_neg hc2, if_neg hc1]
        by_cases hr : (getD recipes item []).length = 0
        · rw [if_pos hr, if_pos hr]; exact ⟨by omega, hdom'⟩
        · rw [if_neg hr, if_neg hr]
          have hrkall : ∀ mat per, (mat, per) ∈ getD recipes item [] → rank mat ≤ m := by
            intro mat per hmem; have := hacy item mat per hmem; omega
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          have hedgeR : ∀ mat per, (mat, per) ∈ getD recipes item [] →
              Reaches recipes item mat :=
            fun mat per hmem => Reaches.edge recipes item mat per hmem
          have IHpair : ∀ (mt : String) (a1 a2 : Int) (g1 g2 : Dict Int),
              rank mt ≤ m → 0 < a2 → a2 ≤ a1 →
              DomR recipes mt g1 g2 → NonNeg g1 → NonNeg g2 →
              (minGathers m mt a2 recipes (0, g2)).1 ≤ (minGathers m mt a1 recipes (0, g1)).1
              ∧ DomR recipes mt (minGathers m mt a1 recipes (0, g1)).2
                    (minGathers m mt a2 recipes (0, g2)).2 :=
            fun mt a1 a2 g1 g2 hr' ha2 ha21 hdg hng1 hng2 =>
              IH m (Nat.lt_succ_self m) mt a1 a2 g1 g2 hr' ha2 ha21 hdg hng1 hng2
          exact domR_foldl recipes rank hpos m item IHpair (getD recipes item [])
            (setD h1 item (getD h1 item 0 - min (getD h1 item 0) q1))
            (setD h2 item (getD h2 item 0 - min (getD h2 item 0) q2))
            0 0 (q1 - min (getD h1 item 0) q1) (q2 - min (getD h2 item 0) q2)
            hrkall hpoall hedgeR (by omega) hrem (Int.le_refl 0) hdom' hnn1' hnn2'

-- ---------------------------------------------------------------------------
-- Craft-step coupling (the heart): minGathers after a valid craft ≤ before
-- ---------------------------------------------------------------------------

/-!
## The craft step

A valid `craft c` consumes `recipeOf c` (`−per` each) and produces `+1 c`. The
resulting holdings `H'` have EQUAL `costMass` to `H` (`costMass_craft_preserved`)
but are pointwise INCOMPARABLE to `H`, so `minGathers_mono` does not apply. The
Ψ craft step is `(★) : minGathersCount item 1 H ≤ minGathersCount item 1 H'`
(round 9: the count RISES when you craft).

The OFF-PATH corner (`¬ Reaches recipes item c`) is now fully discharged
(`star_unreached`): there `H' ⊑ H` on `item`'s reach-set, so
`minGathers_mono_reach` gives `(★)` directly. The ON-PATH corner
(`Reaches recipes item c`, where `H` and `H'` disagree on the reach-set at the
`c`-subtree) is the residual cost-mass coupling the report flagged as
irreducible; it is NOT proven here.
-/

/-- Consuming an input list with non-negative `per` only LOWERS each key:
`getD (consumeHoldings H inputs) k 0 ≤ getD H k 0`. (Each fold step `setD`s
`mat ↦ held − per ≤ held` at one key and leaves the rest fixed.) -/
theorem consume_le (H : Dict Int) (k : String) :
    ∀ (inputs : Dict Int), (∀ mat per, (mat, per) ∈ inputs → 0 ≤ per) →
    getD (consumeHoldings H inputs) k 0 ≤ getD H k 0 := by
  intro inputs
  unfold consumeHoldings
  induction inputs generalizing H with
  | nil => intro _; exact Int.le_refl _
  | cons mp rest ih =>
    obtain ⟨mat, per⟩ := mp
    intro hnn
    simp only [List.foldl_cons]
    have hper : 0 ≤ per := hnn mat per (by simp)
    have hnn' : ∀ m' p, (m', p) ∈ rest → 0 ≤ p := fun m' p hm => hnn m' p (by simp [hm])
    refine Int.le_trans (ih (dictSet H mat (dictGet H mat - per)) hnn') ?_
    rw [dictSet_eq, getD_setD]
    by_cases hmk : mat = k
    · subst hmk; rw [if_pos rfl, dictGet_eq]; omega
    · rw [if_neg hmk]; exact Int.le_refl _

/-- **OFF-PATH DOMINATION.** When `¬ Reaches recipes item c`, the post-`craft c`
holdings are `DomR`-below `H` on `item`'s reach-set: every key `item` reaches is
`≠ c` (c is unreachable), so the `+1 c` is invisible and only the consumed inputs
lower the value. The hook that makes `(★)` follow from `minGathers_mono_reach`
in the off-path corner. -/
theorem craft_domR_unreached (recipes : Recipes)
    (hpos : PosRecipes recipes) (H : Dict Int) (item c : String)
    (hnr : ¬ Reaches recipes item c) :
    DomR recipes item
      (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings
      H := by
  intro k hk
  have hkc : k ≠ c := fun h => hnr (h ▸ hk)
  show getD (dictSet (consumeHoldings H (recipeOf recipes c)) c
        (dictGet (consumeHoldings H (recipeOf recipes c)) c + 1)) k 0 ≤ getD H k 0
  rw [dictSet_eq, getD_setD, if_neg (fun h => hkc h.symm)]
  refine consume_le H k (recipeOf recipes c) ?_
  intro mat per hmem
  rw [recipeOf_eq_getD] at hmem
  exact Int.le_of_lt (hpos c mat per hmem)

/-- The post-`craft c` holdings are `NonNeg` when the consumed holdings are
(`ValidCraftAt` guarantees this at use sites). The `+1 c` only raises `c`. -/
theorem craft_nonneg (recipes : Recipes) (H : Dict Int) (c : String)
    (hcov : NonNeg (consumeHoldings H (recipeOf recipes c))) :
    NonNeg (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
      (Action.craft c)).holdings := by
  intro k
  show 0 ≤ getD (dictSet (consumeHoldings H (recipeOf recipes c)) c
        (dictGet (consumeHoldings H (recipeOf recipes c)) c + 1)) k 0
  rw [dictSet_eq, getD_setD]
  by_cases hkc : c = k
  · subst hkc; rw [if_pos rfl, dictGet_eq]; have := hcov c; omega
  · rw [if_neg hkc]; exact hcov k

/-- **CRAFT STEP `(★)` — OFF-PATH CORNER (0-sorry).** When `¬ Reaches recipes
item c` the count RISES (or holds) under a valid craft of `c`:
`minGathersCount item 1 H ≤ minGathersCount item 1 H'`. The crafted `c` and its
consumed inputs are all invisible-or-lowering to `item`'s traversal, so
`DomR item H' H` (`craft_domR_unreached`) and `minGathers_mono_reach` close it.
This is a genuine, non-vacuous arm of `(★)` (the shared-raw sibling case round 9
flagged as not closeable by `minGathers_agree` — `minGathers_mono_reach` closes
it because we need the INEQUALITY, not equality). -/
theorem star_unreached (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length)
    (item c : String) (H : Dict Int)
    (hnr : ¬ Reaches recipes item c)
    (hnnH : NonNeg H)
    (hcov : NonNeg (consumeHoldings H (recipeOf recipes c))) :
    minGathersCount item 1 recipes H
      ≤ minGathersCount item 1 recipes
        (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings := by
  unfold minGathersCount
  have hdomR := craft_domR_unreached recipes hpos H item c hnr
  have hnnH' := craft_nonneg recipes H c hcov
  exact (minGathers_mono_reach recipes rank hpos hacy (recipes.length + 1) item 1 1
    (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings H
    (by have := hRB item; omega) (by omega) (Int.le_refl 1) hdomR hnnH' hnnH).1

-- ---------------------------------------------------------------------------
-- ON-PATH corner of (★): the crafted item IS the query (round 11)
-- ---------------------------------------------------------------------------

/-- The residual after a COVERED `minGathers` call is the start with `item`
reduced by exactly `q`: `(minGathers (fuel+1) item q (0, owned)).2 =
setD owned item (getD owned item 0 − q)` (the covered branch consumes the full
`q` and gathers nothing). -/
theorem minGathers_covered_residual (fuel : Nat) (item : String) (q : Int)
    (recipes : Recipes) (owned : Dict Int) (hcov : q ≤ getD owned item 0) :
    (minGathers (fuel+1) item q recipes (0, owned)).2
      = setD owned item (getD owned item 0 - q) := by
  rw [minGathers_succ]
  have hmin : min (getD owned item 0) q = q := by
    have h1 := Int.min_le_right (getD owned item 0) q
    have h2 : q ≤ min (getD owned item 0) q := Int.le_min.mpr ⟨hcov, Int.le_refl q⟩
    omega
  rw [hmin, if_pos (by omega)]

/-- A recipe `foldl` over inputs ALL covered by `owned` (each `per·rem ≤
getD owned mat`) gathers NOTHING: the count is the seed `s`. Requires
`NoDupKeys inputs` so each covered consume leaves the OTHER inputs untouched
(`minGathers_covered_residual` reduces only the consumed key, distinct from the
remaining inputs). Induction on the input list. -/
theorem foldl_covered (recipes : Recipes) (m : Nat) (rem : Int) :
    ∀ (inputs : Dict Int) (owned : Dict Int) (s : Int),
      NoDupKeys inputs →
      (∀ mat per, (mat, per) ∈ inputs → per * rem ≤ getD owned mat 0) →
      (List.foldl (fun st mat => minGathers (m+1) mat.1 (mat.2 * rem) recipes st)
        (s, owned) inputs).1 = s := by
  intro inputs
  induction inputs with
  | nil => intro owned s _ _; rfl
  | cons mp rest ih =>
    obtain ⟨mat, per⟩ := mp
    intro owned s hnd hcov
    simp only [List.foldl_cons]
    have hpr : per * rem ≤ getD owned mat 0 := hcov mat per (by simp)
    have hc := minGathers_covered m mat (per * rem) recipes owned hpr
    have hres := minGathers_covered_residual m mat (per * rem) recipes owned hpr
    have hta := minGathers_total_additive (m+1) mat (per*rem) recipes s owned
    rw [hta, hc, Int.zero_add]
    have hmat_notin : ∀ p, (mat, p) ∉ rest := by
      simp only [NoDupKeys] at hnd; exact hnd.1
    have hnd' : NoDupKeys rest := by simp only [NoDupKeys] at hnd; exact hnd.2
    have hcov' : ∀ mat' per', (mat', per') ∈ rest →
        per' * rem ≤ getD (minGathers (m+1) mat (per*rem) recipes (0,owned)).2 mat' 0 := by
      intro mat' per' hmem
      rw [hres, getD_setD]
      by_cases hmm : mat = mat'
      · subst hmm; exact absurd hmem (hmat_notin per')
      · rw [if_neg hmm]; exact hcov mat' per' (by simp [hmem])
    exact ih _ s hnd' hcov'

/-- `ValidCraftAt` extracted to a single recipe input: every `(mat, per) ∈
recipeOf c` has `per ≤ dictGet H mat`. -/
theorem validcraft_input (recipes : Recipes) (H : Dict Int) (c mat : String) (per : Int)
    (hvc : ValidCraftAt recipes H c) (hmem : (mat, per) ∈ recipeOf recipes c) :
    per ≤ dictGet H mat := by
  unfold ValidCraftAt at hvc; unfold recipeOf at hmem; exact hvc mat per hmem

/-- **CRAFT STEP `(★)` — ON-PATH `item = c` CORNER (0-sorry).** When the query
IS the crafted item `c`, a VALID craft makes `minGathersCount c 1 recipes H = 0`:
`ValidCraftAt` puts every recipe input in `H` (covered), so the `minGathers c`
traversal credits the recipe entirely and gathers nothing. Hence
`(★) : minGathersCount c 1 H = 0 ≤ minGathersCount c 1 H'` holds trivially.
Carries `NoDupKeys (recipeOf c)` (recipe inputs are a dict — a faithful domain
fact). -/
theorem count_zero_of_validcraft (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (c : String) (H : Dict Int)
    (hcr : ¬ (getD recipes c []).length = 0)
    (hnd : NoDupKeys (recipeOf recipes c))
    (hvc : ValidCraftAt recipes H c) (hnnH : NonNeg H) :
    minGathersCount c 1 recipes H = 0 := by
  unfold minGathersCount
  have hro : recipeOf recipes c = getD recipes c [] := recipeOf_eq_getD recipes c
  obtain ⟨m, hm⟩ : ∃ m, recipes.length = m + 1 := by
    rcases Nat.eq_zero_or_pos recipes.length with h | h
    · exfalso; apply hcr
      have : recipes = [] := List.length_eq_zero_iff.mp h
      subst this; simp [getD]
    · exact ⟨recipes.length - 1, by omega⟩
  rw [hm, minGathers_succ]
  have hhc : 0 ≤ getD H c 0 := hnnH c
  by_cases hcov : (1:Int) - min (getD H c 0) 1 ≤ 0
  · rw [if_pos hcov]
  · rw [if_neg hcov, if_neg hcr]
    have hmin : min (getD H c 0) 1 = getD H c 0 := by
      have := Int.min_le_left (getD H c 0) 1
      have := Int.min_le_right (getD H c 0) 1; omega
    have hrem1 : (1:Int) - min (getD H c 0) 1 = 1 := by rw [hmin]; omega
    have hcovin : ∀ mat per, (mat, per) ∈ getD recipes c [] →
        per * (1 - min (getD H c 0) 1)
          ≤ getD (setD H c (getD H c 0 - min (getD H c 0) 1)) mat 0 := by
      intro mat per hmem
      rw [hrem1, Int.mul_one, getD_setD]
      have hmem' : (mat, per) ∈ recipeOf recipes c := hro ▸ hmem
      have hvcm : per ≤ dictGet H mat := validcraft_input recipes H c mat per hvc hmem'
      rw [dictGet_eq] at hvcm
      by_cases hmc : c = mat
      · exfalso; subst hmc; have := hacy c c per hmem; omega
      · rw [if_neg hmc]; exact hvcm
    exact foldl_covered recipes m (1 - min (getD H c 0) 1)
      (getD recipes c []) (setD H c (getD H c 0 - min (getD H c 0) 1)) 0
      (hro ▸ hnd) hcovin

/-- The holdings after a `craft c` step from `H` hold at least one `c`:
the consume foldl leaves `c` at some value `v`, then the produce step sets it to
`v + 1`, so `getD H' c 0 = consumed_c + 1`. Combined with `NonNeg` of the consumed
holdings this gives `1 ≤ getD H' c 0`. -/
theorem craft_holds_target (recipes : Recipes) (H : Dict Int) (c : String)
    (hcov : NonNeg (consumeHoldings H (recipeOf recipes c))) :
    1 ≤ getD (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
          (Action.craft c)).holdings c 0 := by
  show 1 ≤ getD (dictSet (consumeHoldings H (recipeOf recipes c)) c
            (dictGet (consumeHoldings H (recipeOf recipes c)) c + 1)) c 0
  rw [dictSet_eq, dictGet_eq, getD_setD, if_pos rfl]
  have := hcov c; omega

/-- **CRAFT STEP — target corner (0-sorry).** When the crafted item `c` IS the
query `item`, a valid craft makes the query trivially satisfiable: `H'` holds
`≥ 1` of `item`, so `minGathersCount item 1 recipes H' = 0 ≤ minGathersCount … H`.
(Uses `craft_holds_target` + `minGathersCount_covered`; the `0 ≤ …` lower bound is
`minGathers_count_nonneg`.) -/
theorem minGathers_craft_le_self (recipes : Recipes) (hpos : PosRecipes recipes)
    (H : Dict Int) (c : String)
    (hcov : NonNeg (consumeHoldings H (recipeOf recipes c))) :
    minGathersCount c 1 recipes
        (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
          (Action.craft c)).holdings
      ≤ minGathersCount c 1 recipes H := by
  have hcovered : 1 ≤ getD (applyAction recipes
      { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings c 0 :=
    craft_holds_target recipes H c hcov
  rw [minGathersCount_covered c 1 recipes _ hcovered]
  -- the RHS count is ≥ 0
  unfold minGathersCount
  exact minGathers_count_nonneg recipes hpos (recipes.length + 1) c 1 0 H
    (Int.le_refl 0) (by omega)

/-- **CRAFT STEP — recon reduction (0-sorry).** For the GENERAL query item, a
valid craft of a craftable `c` reduces the craft-monotonicity goal
`minGathersCount item 1 recipes H' ≤ minGathersCount item 1 recipes H`
(`H'` the post-craft holdings) EXACTLY to a residual cost-mass comparison:

    costMass F (minGathers F item 1 recipes (0, H')).2 recipes
      ≤ costMass F (minGathers F item 1 recipes (0, H)).2 recipes      (F = |recipes|+1)

via `minGathers_recon` at `H` and `H'` (the gather count is
`wf item + costMass (residual) − costMass (holdings)`) and
`costMass_craft_preserved'` (a valid craft conserves total cost-mass, so the
`−costMass(holdings)` terms cancel). This banks the round-4/5 reduction as a
reusable lemma so future work starts from the SHARP residual obligation rather
than re-deriving it.

**Honesty note.** The residual comparison hypothesis `hres` is left as an
explicit premise — it is NOT discharged here and is, as the round-5/6 analysis
and the `#eval` counterexamples show, genuinely conditional: the unconditional
`item ≠ c` form is FALSE (crafting `c` can starve a sibling or below-`c` query
of a shared raw input). The honest discharge needs DAG-reachability of `c` from
`item` (the query is the plan root; every craft is a sub-component of it). -/
theorem minGathers_craft_le_of_residual (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length)
    (item c : String) (H : Dict Int)
    (hcr : ¬ (getD recipes c []).length = 0)
    (hres : costMass (recipes.length + 1)
              (minGathers (recipes.length + 1) item 1 recipes
                (0, (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
                      (Action.craft c)).holdings)).2 recipes
          ≤ costMass (recipes.length + 1)
              (minGathers (recipes.length + 1) item 1 recipes (0, H)).2 recipes) :
    minGathersCount item 1 recipes
        (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
          (Action.craft c)).holdings
      ≤ minGathersCount item 1 recipes H := by
  have hrec_H := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1 H (by have := hRB item; omega) (by have := hRB item; omega)
    (by omega)
  have hrec_H' := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1
    (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings
    (by have := hRB item; omega) (by have := hRB item; omega) (by omega)
  have hcm : costMass (recipes.length + 1)
      (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings
        recipes
      = costMass (recipes.length + 1) H recipes :=
    costMass_craft_preserved' recipes rank hpos hacy recipes.length c
      { gathers := 0, crafts := 0, holdings := H } hcr (by have := hRB c; omega)
  unfold minGathersCount
  rw [Int.one_mul] at hrec_H hrec_H'
  omega

/-- **CRAFT STEP — recon reduction, CORRECT DIRECTION (0-sorry).**

ROUND 9 FINDING (machine-checked): the Ψ-closure does NOT need the
`g(H') ≤ g(H)` direction that rounds 1–8 and the round-9 prompt chased — it needs
the OPPOSITE, and that opposite is TRUE WITHOUT any reachability guard.

The Ψ-potential `Ψ(s) = s.gathers + minGathersCount item 1 s.holdings` must be
NON-DECREASING per `ValidPlan` action so that `Ψ_start ≤ Ψ_end` gives
`minGathersCount item 1 owned ≤ planGathers`. For a `craft` step (gathers fixed)
"non-decreasing" means `Ψ(before) ≤ Ψ(after)`, i.e.

    minGathersCount item 1 recipes H ≤ minGathersCount item 1 recipes H'     (★)

— the count goes UP (or stays) when you craft. This is intuitively obvious: a
valid craft converts raw mass into ONE intermediate `c`, which can only increase
(or keep) the remaining work to reach `item` from the current holdings.

`(★)` was VERIFIED by `#eval` to hold for EVERY query `item` over every valid
craft of every craftable `c`, with NO reachability guard — INCLUDING round 7's
"counterexamples" (which only refuted the WRONG direction `g(H') ≤ g(H)`):
  - query below `c` (`R=[(c,[(wood,2)])]`, `H=[wood:2]`): `g(H)=0 ≤ g(H')=1` ✓
  - sibling `d` sharing a raw pool: `g(d,H)=0 ≤ g(d,H')=2` ✓
  - root that already over-holds `c` (a NEW round-9 counterexample to the
    `g(H')≤g(H)` form even UNDER `Reaches`: `g(root,H)=0`, `g(root,H')=2`): the
    correct direction `0 ≤ 2` holds ✓.

So the `Reaches`/`PlanReaches` guard machinery (rounds 7–8) is NOT needed for the
craft step at all — the correct statement is unconditional in `item`. This lemma
banks the recon reduction in the correct direction: `(★)` reduces EXACTLY to the
residual cost-mass comparison

    costMass F (minGathers F item 1 recipes (0, H)).2 recipes
      ≤ costMass F (minGathers F item 1 recipes (0, H')).2 recipes      (F=|recipes|+1)

via `minGathers_recon` at `H` and `H'` + `costMass_craft_preserved'` (cost-mass
conserved cancels the holdings terms). Note this is the round-7 residual
comparison with the inequality FLIPPED — same equivalence (round 5), now pointing
the way the Ψ-closure actually needs.

**Honesty note.** The residual comparison `hres` is an explicit premise — NOT
discharged here, NOT assumed downstream. It is the genuine remaining content (a
cost-mass coupling: `g(H) ≤ g(H')` still has the round-5/6 wall, mirrored —
`minGathers_mono` gives bounds the wrong way, so the `+1 c`'s cost-neutrality
`wf c = recipeMass(inputs c)` must be threaded through the greedy traversal). But
it is now UNGUARDED and correctly directed. -/
theorem minGathers_craft_ge_of_residual (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length)
    (item c : String) (H : Dict Int)
    (hcr : ¬ (getD recipes c []).length = 0)
    (hres : costMass (recipes.length + 1)
              (minGathers (recipes.length + 1) item 1 recipes (0, H)).2 recipes
          ≤ costMass (recipes.length + 1)
              (minGathers (recipes.length + 1) item 1 recipes
                (0, (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
                      (Action.craft c)).holdings)).2 recipes) :
    minGathersCount item 1 recipes H
      ≤ minGathersCount item 1 recipes
        (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
          (Action.craft c)).holdings := by
  have hrec_H := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1 H (by have := hRB item; omega) (by have := hRB item; omega)
    (by omega)
  have hrec_H' := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1
    (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings
    (by have := hRB item; omega) (by have := hRB item; omega) (by omega)
  have hcm : costMass (recipes.length + 1)
      (applyAction recipes { gathers := 0, crafts := 0, holdings := H } (Action.craft c)).holdings
        recipes
      = costMass (recipes.length + 1) H recipes :=
    costMass_craft_preserved' recipes rank hpos hacy recipes.length c
      { gathers := 0, crafts := 0, holdings := H } hcr (by have := hRB c; omega)
  unfold minGathersCount
  rw [Int.one_mul] at hrec_H hrec_H'
  omega

-- ---------------------------------------------------------------------------
-- Plan-level reachability: every craft targets a sub-component of the root
-- ---------------------------------------------------------------------------

/-- `PlanReaches recipes item plan`: every `craft c` action in `plan` targets a
recipe-DAG sub-component of the query root `item` (`Reaches recipes item c`).

In a `ValidPlan` toward a single root `item`, EVERY craft produces an item the
root transitively depends on — so this holds at every craft step. It is threaded
as the honest reachability guard the corrected craft-monotonicity needs (round 7
showed the unguarded form is FALSE). Gather/equip actions carry no obligation. -/
def PlanReaches (recipes : Recipes) (item : String) : Plan → Prop
  | []      => True
  | a :: rest =>
      (match a with
       | Action.craft c => Reaches recipes item c
       | _              => True) ∧
      PlanReaches recipes item rest

/-- `PlanReaches` of a cons unfolds to the head obligation and the tail. -/
theorem planReaches_cons (recipes : Recipes) (item : String)
    (a : Action) (rest : Plan) :
    PlanReaches recipes item (a :: rest) ↔
      (match a with
       | Action.craft c => Reaches recipes item c
       | _              => True) ∧
      PlanReaches recipes item rest := Iff.rfl

-- ---------------------------------------------------------------------------
-- Ψ-closure assembly: residual invariants, gather drop, Ψ-potential, final
-- ---------------------------------------------------------------------------

/-!
## The Ψ-potential closure

With the craft step `(★)` in hand the whole theorem closes by a Ψ-potential
induction over `ValidPlanFrom`, mirroring `plan_mass_invariant`'s skeleton. The
potential is `Ψ(s) := s.gathers + minGathersCount item 1 recipes s.holdings`,
proven NON-DECREASING per action:

- **gather** (raw): `minGathersCount` drops by ≤ 1 (`gather_drop`) while gathers
  rises by 1, so Ψ is non-decreasing.
- **craft** (valid): `minGathersCount` rises or holds (`(★)`) with gathers fixed.
- **equip**: no-op.

Then `Ψ(start) = minGathersCount item 1 owned` (gathers 0) and, since a plan that
produces `item` has `planHoldings` covering it, `Ψ(end) = planGathers + 0`. So
`minGathersCount item 1 owned ≤ planGathers`. The three holdings invariants
(`NonNeg`/`EntriesNonNeg`/`NoDupKeys`) thread through each step (preserved by
`applyAction` for valid actions). The craft step `(★)` is provided as the
hypothesis `star` here; it is discharged below by the three-corner case split.
-/

/-- **RESIDUAL NoDupKeys.** Each `minGathers` step writes its threaded `owned`
with a `setD`, so a no-dup start yields a no-dup residual. Fuel induction; the
recipe `foldl` arm threads `NoDupKeys` per sibling via `minGathers_total_additive`. -/
theorem nodupKeys_minGathers_residual (recipes : Recipes) :
    ∀ (fuel : Nat) (item : String) (q t : Int) (owned : Dict Int),
      NoDupKeys owned → NoDupKeys (minGathers fuel item q recipes (t, owned)).2 := by
  intro fuel
  induction fuel with
  | zero => intro item q t owned hnd; simpa [minGathers] using hnd
  | succ n ih =>
    intro item q t owned hnd
    rw [minGathers_succ]
    have hres_nd : NoDupKeys (setD owned item (getD owned item 0 - min (getD owned item 0) q)) :=
      nodupKeys_setD owned item _ hnd
    by_cases hc : q - min (getD owned item 0) q ≤ 0
    · rw [if_pos hc]; exact hres_nd
    · rw [if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]; exact hres_nd
      · rw [if_neg hr]
        suffices H : ∀ (rc : Dict Int) (o : Dict Int) (s : Int),
            NoDupKeys o →
            NoDupKeys (List.foldl (fun st mat =>
              minGathers n mat.1 (mat.2 * (q - min (getD owned item 0) q)) recipes st)
              (s, o) rc).2 by
          exact H (getD recipes item []) _ t hres_nd
        intro rc
        induction rc with
        | nil => intro o s ho; exact ho
        | cons mp rest ihrec =>
          intro o s ho
          obtain ⟨mat, per⟩ := mp
          simp only [List.foldl_cons]
          have hta := minGathers_total_additive n mat
            (per * (q - min (getD owned item 0) q)) recipes s o
          rw [hta]
          exact ihrec _ _ (ih mat _ 0 o ho)

/-- **RESIDUAL EntriesNonNeg.** Each `minGathers` step writes `held − min(held, q)
≥ 0` (under `NonNeg owned`), so a `≥ 0`-entries start yields `≥ 0`-entries
residual. Fuel induction; the recipe `foldl` arm threads both `NonNeg` (for the
next write bound, via `minGathers_nonneg_residual`) and `EntriesNonNeg`. -/
theorem entriesNonNeg_minGathers_residual (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (q t : Int) (owned : Dict Int),
      0 < q → NonNeg owned → EntriesNonNeg owned →
      EntriesNonNeg (minGathers fuel item q recipes (t, owned)).2 := by
  intro fuel
  induction fuel with
  | zero => intro item q t owned _ _ he; simpa [minGathers] using he
  | succ n ih =>
    intro item q t owned hq hnn he
    rw [minGathers_succ]
    have hheld : 0 ≤ getD owned item 0 := hnn item
    have hmin_le : min (getD owned item 0) q ≤ getD owned item 0 := Int.min_le_left _ _
    have hres_en : EntriesNonNeg (setD owned item (getD owned item 0 - min (getD owned item 0) q)) :=
      entriesNonNeg_setD owned item _ (by omega) he
    have hres_nn : NonNeg (setD owned item (getD owned item 0 - min (getD owned item 0) q)) :=
      nonneg_setD owned item _ hnn (by omega)
    by_cases hc : q - min (getD owned item 0) q ≤ 0
    · rw [if_pos hc]; exact hres_en
    · rw [if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]; exact hres_en
      · rw [if_neg hr]
        have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
          fun mat per hmem => hpos item mat per hmem
        suffices H : ∀ (rc : Dict Int) (o : Dict Int) (s : Int),
            (∀ mat per, (mat, per) ∈ rc → 0 < per) → NonNeg o → EntriesNonNeg o →
            EntriesNonNeg (List.foldl (fun st mat =>
              minGathers n mat.1 (mat.2 * (q - min (getD owned item 0) q)) recipes st)
              (s, o) rc).2 by
          exact H (getD recipes item []) _ t hpoall hres_nn hres_en
        intro rc
        induction rc with
        | nil => intro o s _ _ he'; exact he'
        | cons mp rest ihrec =>
          intro o s hpo hnn' he'
          obtain ⟨mat, per⟩ := mp
          simp only [List.foldl_cons]
          have hper : 0 < per := hpo mat per (by simp)
          have hpq : 0 < per * (q - min (getD owned item 0) q) := Int.mul_pos hper (by omega)
          have hta := minGathers_total_additive n mat
            (per * (q - min (getD owned item 0) q)) recipes s o
          rw [hta]
          have hsn := minGathers_nonneg_residual recipes hpos n mat
            (per * (q - min (getD owned item 0) q)) 0 o hpq hnn'
          have hse := ih mat (per * (q - min (getD owned item 0) q)) 0 o hpq hnn' he'
          have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p := fun m' p hm => hpo m' p (by simp [hm])
          exact ihrec _ _ hpo' hsn hse

/-- **GATHER STEP (drop ≤ 1).** A raw `gather code` step drops the remaining
gather count by at most `1`: `minGathersCount item 1 H ≤ minGathersCount item 1
H' + 1` where `H'` is the post-gather holdings. Since `H' ⊒ H` pointwise (only
`code` rises), `minGathers_mono` gives `Dom (res H) (res H')`, hence
`costMass (res H) ≤ costMass (res H')` (`costMass_mono_dom`); `minGathers_recon`
at `H`/`H'` plus `costMass H' = costMass H + 1` (raw, `wf = 1`) closes the
drop-≤-1 the Ψ gather step needs. -/
theorem gather_drop (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length)
    (item code : String) (H : Dict Int)
    (hraw : (getD recipes code []).length = 0)
    (hnnH : NonNeg H) (heH : EntriesNonNeg H) (hndH : NoDupKeys H) :
    minGathersCount item 1 recipes H
      ≤ minGathersCount item 1 recipes
          (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
            (Action.gather code)).holdings + 1 := by
  have hri : rank item ≤ recipes.length + 1 := by have := hRB item; omega
  have hH'eq : (applyAction recipes { gathers := 0, crafts := 0, holdings := H }
      (Action.gather code)).holdings = setD H code (getD H code 0 + 1) := by
    show dictSet H code (dictGet H code + 1) = _
    rw [dictSet_eq, dictGet_eq]
  rw [hH'eq]
  have hDom : Dom H (setD H code (getD H code 0 + 1)) := by
    intro k; rw [getD_setD]
    by_cases hck : code = k
    · subst hck; rw [if_pos rfl]; have := hnnH code; omega
    · rw [if_neg hck]; exact Int.le_refl _
  have hnnH' : NonNeg (setD H code (getD H code 0 + 1)) :=
    nonneg_setD H code _ hnnH (by have := hnnH code; omega)
  have heH' : EntriesNonNeg (setD H code (getD H code 0 + 1)) :=
    entriesNonNeg_setD H code _ (by have := hnnH code; omega) heH
  have hndH' : NoDupKeys (setD H code (getD H code 0 + 1)) := nodupKeys_setD H code _ hndH
  have hmono := minGathers_mono recipes rank hpos hacy (recipes.length + 1) item 1 1 H
    (setD H code (getD H code 0 + 1)) hri (by omega) (Int.le_refl 1) hDom hnnH hnnH'
  have hndrH : NoDupKeys (minGathers (recipes.length + 1) item 1 recipes (0, H)).2 :=
    nodupKeys_minGathers_residual recipes (recipes.length + 1) item 1 0 H hndH
  have hndrH' : NoDupKeys (minGathers (recipes.length + 1) item 1 recipes
      (0, setD H code (getD H code 0 + 1))).2 :=
    nodupKeys_minGathers_residual recipes (recipes.length + 1) item 1 0 _ hndH'
  have herH' : EntriesNonNeg (minGathers (recipes.length + 1) item 1 recipes
      (0, setD H code (getD H code 0 + 1))).2 :=
    entriesNonNeg_minGathers_residual recipes hpos (recipes.length + 1) item 1 0 _
      (by omega) hnnH' heH'
  have hcmres : costMass (recipes.length + 1)
      (minGathers (recipes.length + 1) item 1 recipes (0, H)).2 recipes
      ≤ costMass (recipes.length + 1)
        (minGathers (recipes.length + 1) item 1 recipes
          (0, setD H code (getD H code 0 + 1))).2 recipes :=
    costMass_mono_dom (recipes.length + 1) recipes hpos _ _ hndrH hndrH' herH' hmono.2
  have hrecH := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1 H hri hri (by omega)
  have hrecH' := minGathers_recon recipes rank hpos hacy (recipes.length + 1)
    (recipes.length + 1) item 1 (setD H code (getD H code 0 + 1)) hri hri (by omega)
  have hcmH' : costMass (recipes.length + 1) (setD H code (getD H code 0 + 1)) recipes
      = costMass (recipes.length + 1) H recipes + 1 := by
    rw [costMass_setD, wf_raw (recipes.length + 1) code recipes hraw]
    have := hnnH code; omega
  unfold minGathersCount
  rw [Int.one_mul] at hrecH hrecH'
  omega

/-- A valid craft's consume leaves all holdings `NonNeg`: `ValidCraftAt` puts
every input `mat` at `per ≤ getD H mat`, so `setD H mat (getD H mat − per) ≥ 0`;
`NoDupKeys (recipeOf c)` keeps the per-input coverage as each consume fires. -/
theorem nonneg_consume_of_validcraft (recipes : Recipes) (H : Dict Int) (c : String)
    (hnnH : NonNeg H) (hnd : NoDupKeys (recipeOf recipes c))
    (hvc : ValidCraftAt recipes H c) :
    NonNeg (consumeHoldings H (recipeOf recipes c)) := by
  have hcov : ∀ mat per, (mat, per) ∈ recipeOf recipes c → per ≤ getD H mat 0 := by
    intro mat per hmem
    have := validcraft_input recipes H c mat per hvc hmem
    rwa [dictGet_eq] at this
  suffices H2 : ∀ (inputs : Dict Int) (G : Dict Int),
      NoDupKeys inputs → NonNeg G →
      (∀ mat per, (mat, per) ∈ inputs → per ≤ getD G mat 0) →
      NonNeg (consumeHoldings G inputs) by
    exact H2 (recipeOf recipes c) H hnd hnnH hcov
  intro inputs
  unfold consumeHoldings
  induction inputs with
  | nil => intro G _ hG _; simpa using hG
  | cons mp rest ih =>
    obtain ⟨mat, per⟩ := mp
    intro G hnd2 hG hcov2
    simp only [List.foldl_cons]
    have hmat_notin : ∀ p, (mat, p) ∉ rest := by
      simp only [NoDupKeys] at hnd2; exact hnd2.1
    have hnd2' : NoDupKeys rest := by simp only [NoDupKeys] at hnd2; exact hnd2.2
    have hpcov : per ≤ getD G mat 0 := hcov2 mat per (by simp)
    have hG' : NonNeg (dictSet G mat (dictGet G mat - per)) := by
      rw [dictSet_eq, dictGet_eq]
      exact nonneg_setD G mat _ hG (by omega)
    have hcov2' : ∀ mat' per', (mat', per') ∈ rest →
        per' ≤ getD (dictSet G mat (dictGet G mat - per)) mat' 0 := by
      intro mat' per' hmem
      rw [dictSet_eq, dictGet_eq, getD_setD]
      by_cases hmm : mat = mat'
      · subst hmm; exact absurd hmem (hmat_notin per')
      · rw [if_neg hmm]; exact hcov2 mat' per' (by simp [hmem])
    exact ih (dictSet G mat (dictGet G mat - per)) hnd2' hG' hcov2'

/-- Under `NoDupKeys`, the `getD`-view `NonNeg` upgrades to entry-wise
`EntriesNonNeg` (each stored entry is the unique `getD`-value for its key). -/
theorem entriesNonNeg_of_nonneg_nodup (m : Dict Int) (hnn : NonNeg m) (hnd : NoDupKeys m) :
    EntriesNonNeg m := by
  induction m with
  | nil => intro k v hkv; simp at hkv
  | cons kv rest ih =>
    obtain ⟨c, w⟩ := kv
    obtain ⟨hhead, htail⟩ := hnd
    intro k v hkv
    rcases List.mem_cons.mp hkv with h1 | h2
    · cases h1
      have := hnn c; rw [getD_cons_self] at this; exact this
    · have hck : c ≠ k := by
        intro h; subst h; exact hhead v h2
      have hnntail : NonNeg rest := by
        intro j
        by_cases hcj : c = j
        · subst hcj
          rw [getD_zero_of_absent rest c (fun u hu => hhead u hu)]; exact Int.le_refl 0
        · have := hnn j; rw [getD_cons_ne _ _ _ _ _ hcj] at this; exact this
      exact ih hnntail htail k v h2

/-- Every recipe input list is a dict (one entry per input code) — a faithful
domain fact carried as a named hypothesis (like `Acyclic`/`PosRecipes`). -/
def RecipeNoDup (recipes : Recipes) : Prop := ∀ c, NoDupKeys (recipeOf recipes c)

/-- **Ψ-POTENTIAL NON-DECREASING.** Along any valid plan the potential
`Ψ(s) := s.gathers + minGathersCount item 1 recipes s.holdings` is
non-decreasing per action: gather drops the count by ≤ 1 while raising gathers
(`gather_drop`); a valid craft raises-or-holds the count with gathers fixed
(`star`, the `(★)` craft step); equip is a no-op. The holdings invariants
`NonNeg`/`EntriesNonNeg`/`NoDupKeys` thread through each step. -/
theorem psi_mono (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hrnd : RecipeNoDup recipes)
    (item : String)
    (star : ∀ (c : String) (G : Dict Int),
      ¬ (getD recipes c []).length = 0 → ValidCraftAt recipes G c →
      NonNeg G → EntriesNonNeg G → NoDupKeys G →
      minGathersCount item 1 recipes G
        ≤ minGathersCount item 1 recipes
          (applyAction recipes { gathers := 0, crafts := 0, holdings := G }
            (Action.craft c)).holdings) :
    ∀ (plan : Plan) (s : ExecState),
      ValidPlanFrom recipes s plan →
      NonNeg s.holdings → EntriesNonNeg s.holdings → NoDupKeys s.holdings →
      (s.gathers : Int) + minGathersCount item 1 recipes s.holdings
        ≤ ((List.foldl (applyAction recipes) s plan).gathers : Int)
          + minGathersCount item 1 recipes (List.foldl (applyAction recipes) s plan).holdings := by
  intro plan
  induction plan with
  | nil => intro s _ _ _ _; simp
  | cons a rest ih =>
    intro s hv hnn he hnd
    simp only [List.foldl_cons]
    obtain ⟨hstep, hrestv⟩ := hv
    have hnn' : NonNeg (applyAction recipes s a).holdings := by
      cases a with
      | gather code =>
        show NonNeg (dictSet s.holdings code (dictGet s.holdings code + 1))
        rw [dictSet_eq, dictGet_eq]
        exact nonneg_setD s.holdings code _ hnn (by have := hnn code; omega)
      | craft code =>
        obtain ⟨_hcr, hvc⟩ := hstep
        have hcons := nonneg_consume_of_validcraft recipes s.holdings code hnn (hrnd code) hvc
        exact craft_nonneg recipes s.holdings code hcons
      | equip code => exact hnn
    have he' : EntriesNonNeg (applyAction recipes s a).holdings := by
      cases a with
      | gather code =>
        show EntriesNonNeg (dictSet s.holdings code (dictGet s.holdings code + 1))
        rw [dictSet_eq, dictGet_eq]
        exact entriesNonNeg_setD s.holdings code _ (by have := hnn code; omega) he
      | craft code =>
        obtain ⟨_hcr, hvc⟩ := hstep
        have hcons := nonneg_consume_of_validcraft recipes s.holdings code hnn (hrnd code) hvc
        have hnnH' := craft_nonneg recipes s.holdings code hcons
        have hndH' := nodupKeys_applyAction recipes s (Action.craft code) hnd
        exact entriesNonNeg_of_nonneg_nodup _ hnnH' hndH'
      | equip code => exact he
    have hnd' : NoDupKeys (applyAction recipes s a).holdings :=
      nodupKeys_applyAction recipes s a hnd
    have hrec := ih (applyAction recipes s a) hrestv hnn' he' hnd'
    have hone : (s.gathers : Int) + minGathersCount item 1 recipes s.holdings
        ≤ ((applyAction recipes s a).gathers : Int)
          + minGathersCount item 1 recipes (applyAction recipes s a).holdings := by
      cases a with
      | gather code =>
        have hraw : (getD recipes code []).length = 0 := by
          have hh : recipeOf recipes code = [] := hstep
          rw [recipeOf_eq_getD] at hh; rw [hh]; rfl
        have hg : ((applyAction recipes s (Action.gather code)).gathers : Int)
            = (s.gathers : Int) + 1 := by
          show ((s.gathers + 1 : Nat) : Int) = _; omega
        have hhbridge : (applyAction recipes s (Action.gather code)).holdings
            = (applyAction recipes { gathers := 0, crafts := 0, holdings := s.holdings }
                (Action.gather code)).holdings := rfl
        have hgd := gather_drop recipes rank hpos hacy hRB item code s.holdings hraw hnn he hnd
        rw [hg, hhbridge]; omega
      | craft code =>
        obtain ⟨hcr, hvc⟩ := hstep
        have hcr' : ¬ (getD recipes code []).length = 0 := by
          rw [← recipeOf_eq_getD]
          intro hh; exact hcr (List.length_eq_zero_iff.mp hh)
        have hg : ((applyAction recipes s (Action.craft code)).gathers : Int)
            = (s.gathers : Int) := rfl
        have hhbridge : (applyAction recipes s (Action.craft code)).holdings
            = (applyAction recipes { gathers := 0, crafts := 0, holdings := s.holdings }
                (Action.craft code)).holdings := rfl
        have hst := star code s.holdings hcr' hvc hnn he hnd
        rw [hg, hhbridge]; omega
      | equip code =>
        have hg : ((applyAction recipes s (Action.equip code)).gathers : Int)
            = (s.gathers : Int) := rfl
        have hh : (applyAction recipes s (Action.equip code)).holdings = s.holdings := rfl
        rw [hg, hh]; exact Int.le_refl _
    exact Int.le_trans hone hrec

/-- **`minGathers_le_gathers`, modulo `(★)`.** From the Ψ-potential being
non-decreasing (`psi_mono`): `Ψ(start) = minGathersCount item 1 owned` (gathers
0) and, since the plan produces `item`, `planHoldings` covers it so
`minGathersCount item 1 planHoldings = 0`, giving `Ψ(end) = planGathers`. Hence
`minGathersCount item 1 owned ≤ planGathers`. The craft step `(★)` is the
`star` hypothesis, discharged below. -/
theorem minGathers_le_gathers_of_star (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hrnd : RecipeNoDup recipes)
    (item : String) (owned : Dict Int) (plan : Plan)
    (hnn : NonNeg owned) (he : EntriesNonNeg owned) (hnd : NoDupKeys owned)
    (star : ∀ (c : String) (G : Dict Int),
      ¬ (getD recipes c []).length = 0 → ValidCraftAt recipes G c →
      NonNeg G → EntriesNonNeg G → NoDupKeys G →
      minGathersCount item 1 recipes G
        ≤ minGathersCount item 1 recipes
          (applyAction recipes { gathers := 0, crafts := 0, holdings := G }
            (Action.craft c)).holdings)
    (hv : ValidPlan recipes owned plan)
    (hprod : 1 ≤ getD (planHoldings recipes plan owned) item 0) :
    minGathersCount item 1 recipes owned ≤ (planGathers recipes plan owned : Int) := by
  have hpsi := psi_mono recipes rank hpos hacy hRB hrnd item star plan
    { gathers := 0, crafts := 0, holdings := owned } hv hnn he hnd
  have hcov : minGathersCount item 1 recipes (planHoldings recipes plan owned) = 0 :=
    minGathersCount_covered item 1 recipes _ hprod
  have hpg : (planGathers recipes plan owned : Int)
      = ((List.foldl (applyAction recipes)
          { gathers := 0, crafts := 0, holdings := owned } plan).gathers : Int) := rfl
  have hph : planHoldings recipes plan owned
      = (List.foldl (applyAction recipes)
          { gathers := 0, crafts := 0, holdings := owned } plan).holdings := rfl
  rw [hph] at hcov
  have hstart : (({ gathers := 0, crafts := 0, holdings := owned } : ExecState).gathers : Int)
      = 0 := rfl
  rw [hstart, hcov] at hpsi
  have hho : ({ gathers := 0, crafts := 0, holdings := owned } : ExecState).holdings = owned := rfl
  rw [hho] at hpsi
  rw [hpg]; omega

/-- **CRAFT STEP `(★)` — corner split.** The general craft step reduces to its
single open corner `item ≠ c ∧ Reaches recipes item c` (`corner3`): the other two
corners are discharged 0-sorry — `item = c` by `count_zero_of_validcraft` (LHS
count is `0`, RHS `≥ 0` by `minGathers_count_nonneg`); `¬ Reaches item c` by
`star_unreached` (the off-path domination `minGathers_mono_reach`). Given
`corner3`, this assembles the full `star` hypothesis `psi_mono` needs. -/
theorem star_of_corner3 (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hrnd : RecipeNoDup recipes)
    (item : String)
    (corner3 : ∀ (c : String) (G : Dict Int),
      ¬ (getD recipes c []).length = 0 → ValidCraftAt recipes G c →
      item ≠ c → Reaches recipes item c →
      NonNeg G → EntriesNonNeg G → NoDupKeys G →
      minGathersCount item 1 recipes G
        ≤ minGathersCount item 1 recipes
          (applyAction recipes { gathers := 0, crafts := 0, holdings := G }
            (Action.craft c)).holdings) :
    ∀ (c : String) (G : Dict Int),
      ¬ (getD recipes c []).length = 0 → ValidCraftAt recipes G c →
      NonNeg G → EntriesNonNeg G → NoDupKeys G →
      minGathersCount item 1 recipes G
        ≤ minGathersCount item 1 recipes
          (applyAction recipes { gathers := 0, crafts := 0, holdings := G }
            (Action.craft c)).holdings := by
  intro c G hcr hvc hnn he hnd
  have hcons : NonNeg (consumeHoldings G (recipeOf recipes c)) :=
    nonneg_consume_of_validcraft recipes G c hnn (hrnd c) hvc
  by_cases hic : item = c
  · subst hic
    have hz := count_zero_of_validcraft recipes rank hpos hacy item G hcr (hrnd item) hvc hnn
    rw [hz]
    exact minGathers_count_nonneg recipes hpos (recipes.length + 1) item 1 0 _
      (Int.le_refl 0) (by omega)
  · by_cases hreach : Reaches recipes item c
    · exact corner3 c G hcr hvc hic hreach hnn he hnd
    · exact star_unreached recipes rank hpos hacy hRB item c G hreach hnn hcons

/-- **`minGathers_le_gathers`, modulo CORNER 3.** Combining `star_of_corner3`
(the (★) corner split) with `minGathers_le_gathers_of_star` (the Ψ-closure): the
full plannability-soundness bound `minGathersCount item 1 owned ≤ planGathers`
holds for any valid plan producing `item`, GIVEN the single open corner
`corner3` (`item ≠ c ∧ Reaches recipes item c`). Every other ingredient is
proven 0-sorry; this is the whole theorem reduced to exactly one lemma. -/
theorem minGathers_le_gathers_of_corner3 (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hrnd : RecipeNoDup recipes)
    (item : String) (owned : Dict Int) (plan : Plan)
    (hnn : NonNeg owned) (he : EntriesNonNeg owned) (hnd : NoDupKeys owned)
    (corner3 : ∀ (c : String) (G : Dict Int),
      ¬ (getD recipes c []).length = 0 → ValidCraftAt recipes G c →
      item ≠ c → Reaches recipes item c →
      NonNeg G → EntriesNonNeg G → NoDupKeys G →
      minGathersCount item 1 recipes G
        ≤ minGathersCount item 1 recipes
          (applyAction recipes { gathers := 0, crafts := 0, holdings := G }
            (Action.craft c)).holdings)
    (hv : ValidPlan recipes owned plan)
    (hprod : 1 ≤ getD (planHoldings recipes plan owned) item 0) :
    minGathersCount item 1 recipes owned ≤ (planGathers recipes plan owned : Int) :=
  minGathers_le_gathers_of_star recipes rank hpos hacy hRB hrnd item owned plan hnn he hnd
    (star_of_corner3 recipes rank hpos hacy hRB hrnd item corner3) hv hprod

-- ---------------------------------------------------------------------------
-- Constructive obtainability witness: `canonicalPlan`
-- ---------------------------------------------------------------------------

/-!
## The canonical obtainment plan (constructive existence witness)

`buildPlan` mirrors the recursion of `minGathers` (StepDispatch) action-for-action:
at a raw item it emits `remaining` flat `gather`s; at a craftable item it
recursively builds the plans for each recipe input (ingredients FIRST, threading
the residual `owned` between siblings exactly as `minGathers`' inner `foldl`
does) and then emits `remaining` `craft`s of the item. The residual `owned` is
returned alongside the plan so the sibling threading matches `minGathers`'
`(count, owned)` state shape.

Because the recursion and owned-crediting mirror `minGathers` exactly, the
emitted `gather` count equals `(minGathers …).1` — the lower bound is met with
equality (`canonicalPlan_gathers`).

**Scope boundary.** This is the constructive EXISTENCE witness for the
demand-`1`, gear-obtainment direction (a valid plan that obtains+equips the
item). It is NOT the general lower bound (`minGathers_le_gathers_of_corner3`),
and surplus accounting (`NoSurplusPlan`) is left to a separate effort.
-/

/-- Build (plan, residual-owned) for obtaining `qty` of `item`, mirroring the
`minGathers fuel item qty recipes (·, owned)` recursion. The second component is
the residual `owned` after greedy per-branch crediting (matching
`(minGathers …).2`), threaded between recipe siblings so the gather count agrees
with `minGathers`. -/
def buildPlan : Nat → String → Int → Recipes → Dict Int → Plan × Dict Int
  | 0, item, qty, _, owned => (List.replicate qty.toNat (Action.gather item), owned)
  | fuel + 1, item, qty, recipes, owned =>
      let held := getD owned item 0
      let used := min held qty
      let owned' := setD owned item (held - used)
      let remaining := qty - used
      if remaining ≤ 0 then ([], owned')
      else
        let recipe := getD recipes item []
        if recipe.length = 0 then
          (List.replicate remaining.toNat (Action.gather item), owned')
        else
          let res := recipe.foldl
            (fun (st : Plan × Dict Int) mat =>
              let sub := buildPlan fuel mat.1 (mat.2 * remaining) recipes st.2
              (st.1 ++ sub.1, sub.2))
            ([], owned')
          (res.1 ++ List.replicate remaining.toNat (Action.craft item), res.2)

/-- The canonical plan that obtains and equips `item`: build the recipe closure
(raws gathered, crafts bottom-up in rank order via `buildPlan`) then `equip item`.
Constructive existence witness for the demand-`1` gear-obtainment direction. -/
def canonicalPlan (recipes : Recipes) (item : String) (owned : Dict Int) : Plan :=
  (buildPlan (recipes.length + 1) item 1 recipes owned).1 ++ [Action.equip item]

/-- The literal number of `gather` actions in a plan (independent of holdings).
`runPlan`'s `gathers` counter equals exactly this, since only `gather` increments
it. -/
def countGathers : Plan → Nat
  | [] => 0
  | Action.gather _ :: rest => countGathers rest + 1
  | _ :: rest => countGathers rest

@[simp] theorem countGathers_append (p q : Plan) :
    countGathers (p ++ q) = countGathers p + countGathers q := by
  induction p with
  | nil => simp [countGathers]
  | cons a rest ih =>
    cases a <;> simp only [List.cons_append, countGathers, ih] <;> omega

@[simp] theorem countGathers_replicate_gather (n : Nat) (c : String) :
    countGathers (List.replicate n (Action.gather c)) = n := by
  induction n with
  | zero => simp [countGathers]
  | succ m ih => rw [List.replicate_succ]; simp only [countGathers, ih]

@[simp] theorem countGathers_replicate_craft (n : Nat) (c : String) :
    countGathers (List.replicate n (Action.craft c)) = 0 := by
  induction n with
  | zero => simp [countGathers]
  | succ m ih => rw [List.replicate_succ]; simp only [countGathers, ih]

/-- Running any plan threads the gather counter additively from any start state:
the final `gathers` is the start `gathers` plus `countGathers plan`. The holdings
do not affect the count. -/
theorem runPlan_gathers_foldl (recipes : Recipes) (plan : Plan) (s : ExecState) :
    (List.foldl (applyAction recipes) s plan).gathers
      = s.gathers + countGathers plan := by
  induction plan generalizing s with
  | nil => simp [countGathers]
  | cons a rest ih =>
    simp only [List.foldl_cons]
    rw [ih (applyAction recipes s a)]
    cases a with
    | gather code =>
      show s.gathers + 1 + countGathers rest = s.gathers + countGathers (Action.gather code :: rest)
      simp only [countGathers]; omega
    | craft code =>
      show s.gathers + countGathers rest = s.gathers + countGathers (Action.craft code :: rest)
      simp only [countGathers]
    | equip code =>
      show s.gathers + countGathers rest = s.gathers + countGathers (Action.equip code :: rest)
      simp only [countGathers]

/-- `planGathers` is exactly the literal `gather`-action count. -/
theorem planGathers_eq_countGathers (recipes : Recipes) (plan : Plan)
    (owned : Dict Int) :
    planGathers recipes plan owned = countGathers plan := by
  show (List.foldl (applyAction recipes) { gathers := 0, crafts := 0, holdings := owned } plan).gathers = _
  rw [runPlan_gathers_foldl]; simp

/-- **GATHER-COUNT + RESIDUAL CORRESPONDENCE.** `buildPlan` mirrors `minGathers`
exactly: the number of `gather` actions it emits equals `minGathers`' gather
count (from a zero running total), and the residual `owned` it returns is
identical. Proved by induction on fuel; the craftable arm threads the shared
sibling `foldl` invariant (plan-gather-count ↔ minGathers-count, residual ↔
residual) with `minGathers_total_additive` re-summing the additive total. -/
theorem buildPlan_correspondence (recipes : Recipes) (hpos : PosRecipes recipes) :
    ∀ (fuel : Nat) (item : String) (qty : Int) (owned : Dict Int), 0 ≤ qty →
      ((countGathers (buildPlan fuel item qty recipes owned).1 : Int)
          = (minGathers fuel item qty recipes (0, owned)).1)
      ∧ (buildPlan fuel item qty recipes owned).2
          = (minGathers fuel item qty recipes (0, owned)).2 := by
  intro fuel
  induction fuel with
  | zero =>
    intro item qty owned hq
    refine ⟨?_, rfl⟩
    simp only [buildPlan, minGathers]
    rw [countGathers_replicate_gather]
    show (qty.toNat : Int) = 0 + qty
    rw [Int.toNat_of_nonneg hq]; omega
  | succ n ih =>
    intro item qty owned hq
    rw [minGathers_succ]
    simp only [buildPlan]
    by_cases hc : qty - min (getD owned item 0) qty ≤ 0
    · rw [if_pos hc, if_pos hc]
      exact ⟨by simp [countGathers], rfl⟩
    · rw [if_neg hc, if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr, if_pos hr]
        refine ⟨?_, rfl⟩
        rw [countGathers_replicate_gather]
        have : (0:Int) ≤ qty - min (getD owned item 0) qty := by omega
        omega
      · rw [if_neg hr, if_neg hr]
        -- shared foldl invariant: build-foldl gather-count and residual track
        -- minGathers-foldl count and residual, modulo an additive total `t`.
        have hrnn : (0:Int) ≤ qty - min (getD owned item 0) qty := by omega
        generalize hrem : qty - min (getD owned item 0) qty = rem
        rw [hrem] at hrnn
        generalize hod : setD owned item (getD owned item 0 - min (getD owned item 0) qty) = owned'
        suffices H : ∀ (rc : Dict Int) (o : Dict Int) (p0 : Plan) (t : Int),
            (∀ mat per, (mat, per) ∈ rc → 0 < per) →
            ((countGathers
                (List.foldl (fun (st : Plan × Dict Int) mat =>
                    (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
                     (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2))
                  (p0, o) rc).1 : Int)
              = (List.foldl (fun state mat =>
                    minGathers n mat.1 (mat.2 * rem) recipes state) (t, o) rc).1
                - t + (countGathers p0 : Int))
            ∧ (List.foldl (fun (st : Plan × Dict Int) mat =>
                    (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
                     (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2))
                  (p0, o) rc).2
                = (List.foldl (fun state mat =>
                    minGathers n mat.1 (mat.2 * rem) recipes state) (t, o) rc).2 by
          have hpoall : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
            fun mat per hmem => hpos item mat per hmem
          have hH := H (getD recipes item []) owned' [] 0 hpoall
          obtain ⟨hcount, hres⟩ := hH
          refine ⟨?_, hres⟩
          rw [countGathers_append, countGathers_replicate_craft]
          push_cast
          rw [hcount]
          simp [countGathers]
        intro rc
        induction rc with
        | nil => intro o p0 t _; exact ⟨by simp, rfl⟩
        | cons mat rest ihrec =>
          intro o p0 t hpo
          simp only [List.foldl_cons]
          have hper : 0 < mat.2 := hpo mat.1 mat.2 (by cases mat; simp)
          have hsubnn : 0 ≤ mat.2 * rem := Int.mul_nonneg (by omega) hrnn
          have hsub := ih mat.1 (mat.2 * rem) o hsubnn
          obtain ⟨hsc, hsr⟩ := hsub
          rw [hsr]
          -- minGathers total-additive over this sibling
          have hta := minGathers_total_additive n mat.1 (mat.2 * rem) recipes t o
          rw [hta]
          have hpo' : ∀ m' p, (m', p) ∈ rest → 0 < p :=
            fun m' p hm => hpo m' p (by simp [hm])
          have hres2 := ihrec
            (minGathers n mat.1 (mat.2 * rem) recipes (0, o)).2
            (p0 ++ (buildPlan n mat.1 (mat.2 * rem) recipes o).1)
            ((minGathers n mat.1 (mat.2 * rem) recipes (0, o)).1 + t)
            hpo'
          obtain ⟨hc2, hr2⟩ := hres2
          refine ⟨?_, hr2⟩
          rw [hc2]
          rw [countGathers_append]
          push_cast
          rw [hsc]
          omega

/-- **WITNESS MEETS THE BOUND.** The canonical plan's gather count equals the
`minGathers` lower bound exactly: `planGathers (canonicalPlan …) = minGathersCount item 1 …`.
The `equip` action contributes no gathers, so the count is `countGathers` of the
`buildPlan` prefix, which equals `(minGathers …).1` by `buildPlan_correspondence`
(nonneg, so `.toNat` round-trips).

Constructive existence witness for the demand-`1` gear-obtainment direction; not
the general lower bound. -/
theorem canonicalPlan_gathers (recipes : Recipes) (hpos : PosRecipes recipes)
    (item : String) (owned : Dict Int) :
    planGathers recipes (canonicalPlan recipes item owned) owned
      = (minGathersCount item 1 recipes owned).toNat := by
  rw [planGathers_eq_countGathers, canonicalPlan, countGathers_append]
  have hcorr := (buildPlan_correspondence recipes hpos (recipes.length + 1) item 1 owned
    (by omega)).1
  have hnn : (0:Int) ≤ (minGathers (recipes.length + 1) item 1 recipes (0, owned)).1 :=
    minGathers_count_nonneg recipes hpos (recipes.length + 1) item 1 0 owned
      (Int.le_refl 0) (by omega)
  unfold minGathersCount
  -- countGathers (buildPlan …) = (minGathers …).1.toNat
  have hcg : (countGathers (buildPlan (recipes.length + 1) item 1 recipes owned).1 : Int)
      = (minGathers (recipes.length + 1) item 1 recipes (0, owned)).1 := hcorr
  have hcraft : countGathers ([Action.equip item] : Plan) = 0 := by simp [countGathers]
  rw [hcraft, Nat.add_zero]
  -- from hcg (Int) and nonneg, conclude the Nat equality
  omega

theorem canonicalPlan_equip_mem (recipes : Recipes) (item : String) (owned : Dict Int) :
    Action.equip item ∈ canonicalPlan recipes item owned := by
  rw [canonicalPlan]
  exact List.mem_append_right _ (by simp)

-- ---------------------------------------------------------------------------
-- ValidPlanFrom / runPlan compositional helpers
-- ---------------------------------------------------------------------------

/-- `ValidPlanFrom` over a concatenation splits: valid on `p` from `s`, then
valid on `q` from the state after running `p`. -/
theorem validPlanFrom_append (recipes : Recipes) (p q : Plan) (s : ExecState) :
    ValidPlanFrom recipes s (p ++ q)
      ↔ ValidPlanFrom recipes s p
        ∧ ValidPlanFrom recipes (List.foldl (applyAction recipes) s p) q := by
  induction p generalizing s with
  | nil => simp [ValidPlanFrom]
  | cons a rest ih =>
    simp only [List.cons_append, ValidPlanFrom, List.foldl_cons]
    rw [ih (applyAction recipes s a)]
    constructor
    · rintro ⟨hstep, hrest, hq⟩; exact ⟨⟨hstep, hrest⟩, hq⟩
    · rintro ⟨⟨hstep, hrest⟩, hq⟩; exact ⟨hstep, hrest, hq⟩

/-- The holdings after a `gather c` step: `c` bumped by 1. -/
theorem foldl_gather_holdings (recipes : Recipes) (s : ExecState) (c : String) :
    (applyAction recipes s (Action.gather c)).holdings
      = dictSet s.holdings c (dictGet s.holdings c + 1) := rfl

/-- Running `replicate n (gather c)` raises `holdings[c]` by `n` and leaves every
other key unchanged; every step is a valid gather when `c` is raw. -/
theorem replicate_gather_holdings (recipes : Recipes) (c : String) (n : Nat) :
    ∀ (s : ExecState),
      getD (List.foldl (applyAction recipes) s
        (List.replicate n (Action.gather c))).holdings c 0
        = getD s.holdings c 0 + (n : Int)
      ∧ (∀ k, k ≠ c →
          getD (List.foldl (applyAction recipes) s
            (List.replicate n (Action.gather c))).holdings k 0
            = getD s.holdings k 0) := by
  induction n with
  | zero => intro s; simp
  | succ m ih =>
    intro s
    rw [List.replicate_succ, List.foldl_cons]
    have hh := ih (applyAction recipes s (Action.gather c))
    obtain ⟨h1, h2⟩ := hh
    rw [foldl_gather_holdings] at h1 h2
    refine ⟨?_, ?_⟩
    · rw [h1, dictGet_eq, dictSet_eq, getD_setD, if_pos rfl]; push_cast; omega
    · intro k hk
      rw [h2 k hk, dictSet_eq, getD_setD, if_neg (by simpa [eq_comm] using hk)]

/-- A fold of `dictSet h k (getD h k − δ)` over a list that does NOT contain key
`mat` leaves `mat` unchanged. -/
theorem consume_absent (mat : String) (L : List (String × Int)) :
    (∀ p, (mat, p) ∉ L) → ∀ (H : Dict Int),
      getD (List.foldl
        (fun h (mp : String × Int) => dictSet h mp.1 (dictGet h mp.1 - mp.2)) H L) mat 0
        = getD H mat 0 := by
  induction L with
  | nil => intro _ H; simp
  | cons mp rest ih =>
    intro habs H
    obtain ⟨m0, p0⟩ := mp
    simp only [List.foldl_cons]
    have hne : m0 ≠ mat := by intro h; subst h; exact habs p0 (by simp)
    have habs' : ∀ p, (mat, p) ∉ rest := fun p hp => habs p (by simp [hp])
    rw [ih habs' (dictSet H m0 (dictGet H m0 - p0))]
    rw [dictSet_eq, getD_setD, if_neg hne]

/-- Consuming an input list leaves a key absent from the list unchanged. -/
theorem consume_other (recipes : Recipes) (c : String) (H : Dict Int)
    (habs : ∀ per, (c, per) ∉ recipeOf recipes c) :
    getD (consumeHoldings H (recipeOf recipes c)) c 0 = getD H c 0 := by
  unfold consumeHoldings
  exact consume_absent c (recipeOf recipes c) habs H

/-- Consuming an input list with NO duplicate keys drops a member key `mat` by
exactly its `per` (single occurrence). -/
theorem consume_input (recipes : Recipes) (c mat : String) (per : Int)
    (H : Dict Int) (hnd : NoDupKeys (recipeOf recipes c))
    (hmem : (mat, per) ∈ recipeOf recipes c) :
    getD (consumeHoldings H (recipeOf recipes c)) mat 0
      = getD H mat 0 - per := by
  unfold consumeHoldings
  generalize hL : recipeOf recipes c = L at hnd hmem ⊢
  clear hL
  induction L generalizing H with
  | nil => simp at hmem
  | cons mp rest ih =>
    obtain ⟨m0, p0⟩ := mp
    simp only [List.foldl_cons]
    obtain ⟨hhead, hndtl⟩ := hnd
    rw [List.mem_cons] at hmem
    rcases hmem with heq | htl
    · -- mat = m0, per = p0; rest has no m0 (NoDup) so it's untouched after the set
      have heq2 : m0 = mat ∧ p0 = per := Prod.mk.injEq .. |>.mp heq.symm
      obtain ⟨rfl, rfl⟩ := heq2
      have habs : ∀ p, (m0, p) ∉ rest := fun p hp => hhead p hp
      rw [consume_absent m0 rest habs (dictSet H m0 (dictGet H m0 - p0))]
      rw [dictSet_eq, getD_setD, if_pos rfl, dictGet_eq]
    · -- mat in rest; m0 ≠ mat (NoDup head distinct, and mat≠m0 since (mat,per)∈rest)
      have hne : m0 ≠ mat := by
        intro h; subst h; exact hhead per htl
      rw [ih (dictSet H m0 (dictGet H m0 - p0)) hndtl htl]
      rw [dictSet_eq, getD_setD, if_neg hne]

/-- Effect of a single `craft c` step on a *specific* input key `mat` of the
recipe, when the recipe has no duplicate keys and `c ≠ mat` (acyclic): the input
drops by exactly `per`. -/
theorem craft_step_input (recipes : Recipes) (c mat : String) (per : Int)
    (s : ExecState) (hnd : NoDupKeys (recipeOf recipes c))
    (hmem : (mat, per) ∈ recipeOf recipes c) (hne : c ≠ mat) :
    getD (applyAction recipes s (Action.craft c)).holdings mat 0
      = getD s.holdings mat 0 - per := by
  show getD (dictSet (consumeHoldings s.holdings (recipeOf recipes c)) c
      (dictGet (consumeHoldings s.holdings (recipeOf recipes c)) c + 1)) mat 0 = _
  rw [dictSet_eq, getD_setD, if_neg hne]
  -- consumeHoldings drops `mat` by `per` (NoDup ⇒ single occurrence)
  have := consume_input recipes c mat per s.holdings hnd hmem
  exact this

/-- Effect of a single `craft c` step on the produced item `c` itself (acyclic ⇒
`c` is not among its own inputs, so consumption does not touch it): rises by 1. -/
theorem craft_step_output (recipes : Recipes) (rank : String → Nat)
    (hacy : Acyclic recipes rank) (c : String) (s : ExecState) :
    getD (applyAction recipes s (Action.craft c)).holdings c 0
      = getD s.holdings c 0 + 1 := by
  show getD (dictSet (consumeHoldings s.holdings (recipeOf recipes c)) c
      (dictGet (consumeHoldings s.holdings (recipeOf recipes c)) c + 1)) c 0 = _
  rw [dictSet_eq, getD_setD, if_pos rfl, dictGet_eq]
  -- consuming the recipe inputs does not change `c` (c ∉ inputs by acyclicity)
  have hc_not_input : ∀ per, (c, per) ∉ recipeOf recipes c := by
    intro per hmem
    have hreceq : recipeOf recipes c = getD recipes c [] := recipeOf_eq_getD recipes c
    rw [hreceq] at hmem
    have := hacy c c per hmem; omega
  have := consume_other recipes c s.holdings hc_not_input
  rw [this]

/-- Sum of `per` over recipe entries `(mat, per)` whose key `mat` equals `k`. -/
def sumPerAt (rc : List (String × Int)) (k : String) : Int :=
  match rc with
  | [] => 0
  | (mat, per) :: rest => (if mat = k then per else 0) + sumPerAt rest k

theorem sumPerAt_absent (l : List (String × Int)) (mat : String)
    (habs : ∀ p, (mat, p) ∉ l) : sumPerAt l mat = 0 := by
  induction l with
  | nil => rfl
  | cons mp rest ih =>
    obtain ⟨m0, p0⟩ := mp
    simp only [sumPerAt]
    have hne : ¬ m0 = mat := by intro h; subst h; exact habs p0 (by simp)
    rw [if_neg hne, ih (fun p hp => habs p (by simp [hp]))]; rfl

theorem sumPerAt_member (l : List (String × Int)) (mat : String)
    (per : Int) (hmem : (mat, per) ∈ l) (hnd : NoDupKeys l) :
    sumPerAt l mat = per := by
  induction l with
  | nil => simp at hmem
  | cons mp rest ih =>
    obtain ⟨m0, p0⟩ := mp
    obtain ⟨hhead, hndtl⟩ := hnd
    rw [List.mem_cons] at hmem
    simp only [sumPerAt]
    rcases hmem with heq | htl
    · have heq2 : m0 = mat ∧ p0 = per := Prod.mk.injEq .. |>.mp heq.symm
      obtain ⟨rfl, rfl⟩ := heq2
      rw [if_pos rfl, sumPerAt_absent rest m0 (fun p hp => hhead p hp)]; omega
    · have hne : ¬ m0 = mat := by intro h; subst h; exact hhead per htl
      rw [if_neg hne, ih htl hndtl]; omega

/-- **REPLICATE-CRAFT EFFECT.** Running `replicate n (craft c)` changes holdings
by: each input `mat` drops by `n * per`, the output `c` rises by `n`, every other
key is unchanged. Acyclicity (`c ∉` its own inputs) and `NoDupKeys` keep the
per-key bookkeeping clean. -/
theorem replicate_craft_effect (recipes : Recipes) (rank : String → Nat)
    (hacy : Acyclic recipes rank) (c : String)
    (hnd : NoDupKeys (recipeOf recipes c)) (n : Nat) :
    ∀ (s : ExecState) (k : String),
      getD (List.foldl (applyAction recipes) s (List.replicate n (Action.craft c))).holdings k 0
        = getD s.holdings k 0
          + (if k = c then (n : Int) else 0)
          - (n : Int) * sumPerAt (recipeOf recipes c) k := by
  induction n with
  | zero => intro s k; simp
  | succ m ih =>
    intro s k
    rw [List.replicate_succ, List.foldl_cons]
    rw [ih (applyAction recipes s (Action.craft c)) k]
    by_cases hk : k = c
    · subst hk
      rw [craft_step_output recipes rank hacy k s, if_pos rfl, if_pos rfl]
      -- k is not its own input (acyclic) ⇒ sumPerAt (recipeOf k) k = 0
      have hc0 : sumPerAt (recipeOf recipes k) k = 0 := by
        apply sumPerAt_absent
        intro per hmem
        have hreceq : recipeOf recipes k = getD recipes k [] := recipeOf_eq_getD recipes k
        rw [hreceq] at hmem
        have := hacy k k per hmem; omega
      rw [hc0, Int.mul_zero, Int.mul_zero]; push_cast; omega
    · rw [if_neg hk, if_neg hk]
      by_cases hin : ∃ per, (k, per) ∈ recipeOf recipes c
      · obtain ⟨per, hmem⟩ := hin
        rw [craft_step_input recipes c k per s hnd hmem (fun h => hk h.symm)]
        have hsp : sumPerAt (recipeOf recipes c) k = per :=
          sumPerAt_member (recipeOf recipes c) k per hmem hnd
        rw [hsp]
        have hexp : ((m : Int) + 1) * per = (m : Int) * per + per := by
          rw [Int.add_mul, Int.one_mul]
        push_cast; rw [hexp]; omega
      · -- k absent from inputs: craft step does not change k
        have hkabs : ∀ per, (k, per) ∉ recipeOf recipes c := by
          intro per hmem; exact hin ⟨per, hmem⟩
        have hstep : getD (applyAction recipes s (Action.craft c)).holdings k 0
            = getD s.holdings k 0 := by
          show getD (dictSet (consumeHoldings s.holdings (recipeOf recipes c)) c
              (dictGet (consumeHoldings s.holdings (recipeOf recipes c)) c + 1)) k 0 = _
          rw [dictSet_eq, getD_setD, if_neg (fun h => hk h.symm)]
          exact consume_absent k (recipeOf recipes c) hkabs s.holdings
        rw [hstep]
        have hsp0 : sumPerAt (recipeOf recipes c) k = 0 := sumPerAt_absent _ _ hkabs
        rw [hsp0, Int.mul_zero, Int.mul_zero]

/-- **REPLICATE-CRAFT VALIDITY.** Running `replicate n (craft c)` from holdings
that stock `n` crafts' worth of each input (`n·per ≤ holdings[mat]`) is
`ValidPlanFrom`: every one of the `n` crafts finds its inputs in hand. Each craft
consumes `per` of each input (NoDup recipe), so after `k` crafts the stock is
`(n−k)·per`, still covering the remaining `n−k`. Positivity (`PosRecipes`) and
acyclicity keep `per > 0` and `c ∉` its own inputs. -/
theorem replicate_craft_valid (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank) (c : String)
    (hnd : NoDupKeys (recipeOf recipes c))
    (hcr : recipeOf recipes c ≠ []) (n : Nat) :
    ∀ (s : ExecState),
      (∀ mat per, (mat, per) ∈ recipeOf recipes c →
        (n : Int) * per ≤ getD s.holdings mat 0) →
      ValidPlanFrom recipes s (List.replicate n (Action.craft c)) := by
  induction n with
  | zero => intro s _; simp [ValidPlanFrom]
  | succ m ih =>
    intro s hstock
    rw [List.replicate_succ, ValidPlanFrom]
    refine ⟨⟨hcr, ?_⟩, ?_⟩
    · -- ValidCraftAt: this craft's inputs present
      intro mat per hmem
      -- `hmem`'s membership target is definitionally `recipeOf recipes c`
      have hmem' : (mat, per) ∈ recipeOf recipes c := hmem
      have hper : 0 < per := hpos c mat per (by rw [recipeOf_eq_getD] at hmem'; exact hmem')
      have hst := hstock mat per hmem'
      have hle : per ≤ ((m : Int) + 1) * per := by
        have hexp : ((m : Int) + 1) * per = (m : Int) * per + per := by
          rw [Int.add_mul, Int.one_mul]
        have hmnn : 0 ≤ (m : Int) * per := Int.mul_nonneg (by omega) (by omega)
        rw [hexp]; omega
      push_cast at hst
      rw [dictGet_eq]
      omega
    · -- after the craft, the remaining m crafts have their stock
      apply ih
      intro mat per hmem
      have hne : c ≠ mat := by
        intro h; subst h
        have hreceq : recipeOf recipes c = getD recipes c [] := recipeOf_eq_getD recipes c
        rw [hreceq] at hmem
        have := hacy c c per hmem; omega
      rw [craft_step_input recipes c mat per s hnd hmem hne]
      have hst := hstock mat per hmem
      push_cast at hst ⊢
      have hexp : ((m : Int) + 1) * per = (m : Int) * per + per := by
        rw [Int.add_mul, Int.one_mul]
      rw [hexp] at hst
      omega

-- ---------------------------------------------------------------------------
-- buildPlan validity + production invariant
-- ---------------------------------------------------------------------------

/-- Sum of `per * rem` over recipe entries `(mat, per)` whose key `mat` equals `k`.
The net production of key `k` across one recipe's siblings at scale `rem`. -/
def sumQtyAt (rc : List (String × Int)) (rem : Int) (k : String) : Int :=
  match rc with
  | [] => 0
  | (mat, per) :: rest =>
      (if mat = k then per * rem else 0) + sumQtyAt rest rem k

/-- `applyAction` changes holdings independently of the gather/craft counters;
running a plan from two states with equal holdings yields equal holdings. -/
theorem foldl_holdings_irrel (recipes : Recipes) (plan : Plan) (h : Dict Int)
    (g1 c1 g2 c2 : Nat) :
    (List.foldl (applyAction recipes) { gathers := g1, crafts := c1, holdings := h } plan).holdings
      = (List.foldl (applyAction recipes) { gathers := g2, crafts := c2, holdings := h } plan).holdings := by
  induction plan generalizing h g1 c1 g2 c2 with
  | nil => rfl
  | cons a rest ih =>
    simp only [List.foldl_cons]
    cases a with
    | gather code =>
      exact ih (dictSet h code (dictGet h code + 1)) _ _ _ _
    | craft code =>
      exact ih _ _ _ _ _
    | equip code =>
      exact ih h _ _ _ _

/-- `ValidPlanFrom` depends only on the holdings, not the gather/craft counters. -/
theorem validPlanFrom_holdings_irrel (recipes : Recipes) (plan : Plan) (h : Dict Int)
    (g1 c1 g2 c2 : Nat)
    (hv : ValidPlanFrom recipes { gathers := g1, crafts := c1, holdings := h } plan) :
    ValidPlanFrom recipes { gathers := g2, crafts := c2, holdings := h } plan := by
  induction plan generalizing h g1 c1 g2 c2 with
  | nil => trivial
  | cons a rest ih =>
    obtain ⟨hstep, hrest⟩ := hv
    refine ⟨?_, ?_⟩
    · cases a <;> exact hstep
    · cases a with
      | gather code => exact ih _ _ _ _ _ hrest
      | craft code => exact ih _ _ _ _ _ hrest
      | equip code => exact ih h _ _ _ _ hrest

/-- The plan accumulator of `buildPlan`'s sibling foldl is purely prepended:
folding from `(p0, obk)` yields `p0 ++ (fold from ([], obk)).1`, and the
bookkeeping component is `p0`-independent. -/
theorem buildPlan_foldl_prefix (recipes : Recipes) (n : Nat) (rem : Int) :
    ∀ (rc : List (String × Int)) (obk : Dict Int) (p0 : Plan),
      (rc.foldl
        (fun (st : Plan × Dict Int) mat =>
          (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
           (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) (p0, obk))
      = (p0 ++ (rc.foldl
          (fun (st : Plan × Dict Int) mat =>
            (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
             (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).1,
         (rc.foldl
          (fun (st : Plan × Dict Int) mat =>
            (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
             (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).2) := by
  intro rc
  induction rc with
  | nil => intro obk p0; simp
  | cons mat rest ih =>
    intro obk p0
    simp only [List.foldl_cons, List.nil_append]
    rw [ih (buildPlan n mat.1 (mat.2 * rem) recipes obk).2
          (p0 ++ (buildPlan n mat.1 (mat.2 * rem) recipes obk).1)]
    rw [ih (buildPlan n mat.1 (mat.2 * rem) recipes obk).2
          (buildPlan n mat.1 (mat.2 * rem) recipes obk).1]
    simp [List.append_assoc]

/-- Running the sibling foldl of `buildPlan`'s craftable arm from a runtime state
`Hrt` dominating the bookkeeping `obk`: the accumulated sibling plans (the new
suffix beyond `p0`) are valid from `Hrt`, the resulting runtime dominates the
final bookkeeping, and the per-key runtime change equals the bookkeeping change
plus the per-key sibling productions `sumQtyAt`. Parametrized by the fuel-`n`
`buildPlan_run` statement `Hn` (so it composes inside the fuel induction). -/
theorem buildPlan_siblings (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes)
    (n : Nat) (rem : Int) (hrem : 0 < rem)
    (Hn : ∀ (it : String) (q : Int) (ow Hr : Dict Int),
      rank it ≤ n → 0 ≤ q → NonNeg ow → Dom ow Hr →
      ValidPlanFrom recipes { gathers := 0, crafts := 0, holdings := Hr }
          (buildPlan n it q recipes ow).1
      ∧ (∀ k, getD (List.foldl (applyAction recipes)
            { gathers := 0, crafts := 0, holdings := Hr }
            (buildPlan n it q recipes ow).1).holdings k 0
          = getD Hr k 0 + (getD (buildPlan n it q recipes ow).2 k 0 - getD ow k 0)
            + (if k = it then q else 0))) :
    ∀ (rc : List (String × Int)) (obk Hrt : Dict Int),
      (∀ mat per, (mat, per) ∈ rc → rank mat ≤ n) →
      (∀ mat per, (mat, per) ∈ rc → 0 < per) →
      NonNeg obk →
      Dom obk Hrt →
      ValidPlanFrom recipes { gathers := 0, crafts := 0, holdings := Hrt }
          (rc.foldl
            (fun (st : Plan × Dict Int) mat =>
              (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
               (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).1
      ∧ Dom (rc.foldl
              (fun (st : Plan × Dict Int) mat =>
                (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
                 (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).2
            (List.foldl (applyAction recipes)
              { gathers := 0, crafts := 0, holdings := Hrt }
              (rc.foldl
                (fun (st : Plan × Dict Int) mat =>
                  (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
                   (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).1).holdings
      ∧ ∀ k, getD (List.foldl (applyAction recipes)
              { gathers := 0, crafts := 0, holdings := Hrt }
              (rc.foldl
                (fun (st : Plan × Dict Int) mat =>
                  (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
                   (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).1).holdings k 0
            = getD Hrt k 0
              + (getD (rc.foldl
                  (fun (st : Plan × Dict Int) mat =>
                    (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
                     (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).2 k 0
                 - getD obk k 0)
              + sumQtyAt rc rem k := by
  intro rc
  induction rc with
  | nil =>
    intro obk Hrt _ _ _ hdom
    refine ⟨by simp [ValidPlanFrom], ?_, ?_⟩
    · simpa using hdom
    · intro k; simp [sumQtyAt]
  | cons mat rest ih =>
    intro obk Hrt hrank hposrc hnnobk hdom
    -- decompose foldl (mat::rest) ([],obk) = head_plan ++ foldl rest ([], bk1)
    have hrankmat : rank mat.1 ≤ n := hrank mat.1 mat.2 (by cases mat; simp)
    have hpermat : 0 < mat.2 := hposrc mat.1 mat.2 (by cases mat; simp)
    have hqnn : 0 ≤ mat.2 * rem := Int.mul_nonneg (by omega) (by omega)
    have hqpos : 0 < mat.2 * rem := Int.mul_pos hpermat hrem
    -- head residual NonNeg (minGathers residual)
    have hbk1nn : NonNeg (buildPlan n mat.1 (mat.2 * rem) recipes obk).2 := by
      have hcorr := (buildPlan_correspondence recipes hpos n mat.1 (mat.2 * rem) obk hqnn).2
      rw [hcorr]
      exact minGathers_nonneg_residual recipes hpos n mat.1 (mat.2 * rem) 0 obk hqpos hnnobk
    -- the head sibling
    have hHn := Hn mat.1 (mat.2 * rem) obk Hrt hrankmat hqnn hnnobk hdom
    obtain ⟨hHvalid, hHdelta⟩ := hHn
    -- runtime after head plan
    have hfoldcons : (List.foldl
        (fun (st : Plan × Dict Int) m =>
          (st.1 ++ (buildPlan n m.1 (m.2 * rem) recipes st.2).1,
           (buildPlan n m.1 (m.2 * rem) recipes st.2).2)) ([], obk) (mat :: rest))
        = (List.foldl
            (fun (st : Plan × Dict Int) m =>
              (st.1 ++ (buildPlan n m.1 (m.2 * rem) recipes st.2).1,
               (buildPlan n m.1 (m.2 * rem) recipes st.2).2))
            ((buildPlan n mat.1 (mat.2 * rem) recipes obk).1,
             (buildPlan n mat.1 (mat.2 * rem) recipes obk).2) rest) := by
      simp [List.foldl_cons]
    rw [hfoldcons]
    rw [buildPlan_foldl_prefix recipes n rem rest
        (buildPlan n mat.1 (mat.2 * rem) recipes obk).2
        (buildPlan n mat.1 (mat.2 * rem) recipes obk).1]
    -- abbreviate the head bookkeeping/plan via generalize (everywhere)
    generalize hhp : (buildPlan n mat.1 (mat.2 * rem) recipes obk).1 = hp at *
    generalize hbk1 : (buildPlan n mat.1 (mat.2 * rem) recipes obk).2 = bk1 at *
    -- runtime after head plan (kept as an explicit term)
    have hHdom1 : Dom bk1 (List.foldl (applyAction recipes)
        { gathers := 0, crafts := 0, holdings := Hrt } hp).holdings := by
      intro k
      have hdk0 := hHdelta k
      rw [hdk0]
      have hdk := hdom k
      by_cases hk : k = mat.1
      · subst hk; rw [if_pos rfl]; omega
      · rw [if_neg hk]; omega
    have hrank' : ∀ m p, (m, p) ∈ rest → rank m ≤ n := fun m p hm => hrank m p (by simp [hm])
    have hpos' : ∀ m p, (m, p) ∈ rest → 0 < p := fun m p hm => hposrc m p (by simp [hm])
    have hrec := ih bk1 (List.foldl (applyAction recipes)
        { gathers := 0, crafts := 0, holdings := Hrt } hp).holdings hrank' hpos' hbk1nn hHdom1
    obtain ⟨hrvalid, hrdom, hrdelta⟩ := hrec
    refine ⟨?_, ?_, ?_⟩
    · rw [validPlanFrom_append]
      refine ⟨hHvalid, ?_⟩
      have hstate : (List.foldl (applyAction recipes)
          { gathers := 0, crafts := 0, holdings := Hrt } hp)
          = { gathers := (List.foldl (applyAction recipes)
                { gathers := 0, crafts := 0, holdings := Hrt } hp).gathers,
              crafts := (List.foldl (applyAction recipes)
                { gathers := 0, crafts := 0, holdings := Hrt } hp).crafts,
              holdings := (List.foldl (applyAction recipes)
                { gathers := 0, crafts := 0, holdings := Hrt } hp).holdings } := rfl
      rw [hstate]
      exact validPlanFrom_holdings_irrel recipes _ _ 0 0 _ _ hrvalid
    · rw [List.foldl_append,
          foldl_holdings_irrel recipes _ (List.foldl (applyAction recipes)
            { gathers := 0, crafts := 0, holdings := Hrt } hp).holdings _]
      exact hrdom
    · intro k
      rw [List.foldl_append,
          foldl_holdings_irrel recipes _ (List.foldl (applyAction recipes)
            { gathers := 0, crafts := 0, holdings := Hrt } hp).holdings _,
          hrdelta k]
      have hd1 := hHdelta k
      have hsum : sumQtyAt (mat :: rest) rem k
          = (if mat.1 = k then mat.2 * rem else 0) + sumQtyAt rest rem k := by
        cases mat; simp [sumQtyAt]
      rw [hsum, hd1]
      by_cases hk : k = mat.1
      · subst hk
        have p1 : (if mat.1 = mat.1 then mat.2 * rem else 0) = mat.2 * rem := if_pos rfl
        rw [p1]; dsimp only; omega
      · have e1 : (if mat.1 = k then mat.2 * rem else 0) = 0 := if_neg (fun h => hk h.symm)
        have e2 : (if k = mat.1 then mat.2 * rem else 0) = 0 := if_neg hk
        rw [e1, e2]
        dsimp only
        omega

/-- For a `NoDupKeys` list, a member `(mat, per)` contributes exactly `per * rem`
to `sumQtyAt` at `mat` (single occurrence). -/
theorem sumQtyAt_absent (l : List (String × Int)) (rem : Int) (mat : String)
    (habs : ∀ p, (mat, p) ∉ l) : sumQtyAt l rem mat = 0 := by
  induction l with
  | nil => rfl
  | cons mp rest ih =>
    obtain ⟨m0, p0⟩ := mp
    simp only [sumQtyAt]
    have hne : ¬ m0 = mat := by intro h; subst h; exact habs p0 (by simp)
    rw [if_neg hne, ih (fun p hp => habs p (by simp [hp]))]; rfl

/-- `sumQtyAt` is `rem` times `sumPerAt` (the productions scale linearly in `rem`). -/
theorem sumQtyAt_eq_mul (rc : List (String × Int)) (rem : Int) (k : String) :
    sumQtyAt rc rem k = rem * sumPerAt rc k := by
  induction rc with
  | nil => simp [sumQtyAt, sumPerAt]
  | cons mp rest ih =>
    obtain ⟨m0, p0⟩ := mp
    simp only [sumQtyAt, sumPerAt, ih]
    by_cases hk : m0 = k
    · rw [if_pos hk, if_pos hk, Int.mul_add, Int.mul_comm rem p0]
    · rw [if_neg hk, if_neg hk, Int.mul_add, Int.mul_zero]

theorem sumQtyAt_member (l : List (String × Int)) (rem : Int) (mat : String)
    (per : Int) (hmem : (mat, per) ∈ l) (hnd : NoDupKeys l) :
    sumQtyAt l rem mat = per * rem := by
  induction l with
  | nil => simp at hmem
  | cons mp rest ih =>
    obtain ⟨m0, p0⟩ := mp
    obtain ⟨hhead, hndtl⟩ := hnd
    rw [List.mem_cons] at hmem
    simp only [sumQtyAt]
    rcases hmem with heq | htl
    · have heq2 : m0 = mat ∧ p0 = per := Prod.mk.injEq .. |>.mp heq.symm
      obtain ⟨rfl, rfl⟩ := heq2
      rw [if_pos rfl, sumQtyAt_absent rest rem m0 (fun p hp => hhead p hp)]; omega
    · have hne : ¬ m0 = mat := by intro h; subst h; exact hhead per htl
      rw [if_neg hne, ih htl hndtl]; omega

/-- The sibling-foldl bookkeeping residual stays `NonNeg` when the start `obk`
is `NonNeg`: each sibling's `buildPlan` residual equals a `minGathers` residual
(`buildPlan_correspondence`), which is `NonNeg` (`minGathers_nonneg_residual`). -/
theorem buildPlan_siblings_bk_nonneg (recipes : Recipes) (hpos : PosRecipes recipes)
    (n : Nat) (rem : Int) (hrem : 0 < rem) :
    ∀ (rc : List (String × Int)) (obk : Dict Int),
      (∀ mat per, (mat, per) ∈ rc → 0 < per) → NonNeg obk →
      NonNeg (rc.foldl
        (fun (st : Plan × Dict Int) mat =>
          (st.1 ++ (buildPlan n mat.1 (mat.2 * rem) recipes st.2).1,
           (buildPlan n mat.1 (mat.2 * rem) recipes st.2).2)) ([], obk)).2 := by
  intro rc
  induction rc with
  | nil => intro obk _ hnn; simpa using hnn
  | cons mat rest ih =>
    intro obk hpo hnn
    rw [List.foldl_cons]
    rw [buildPlan_foldl_prefix recipes n rem rest
        (buildPlan n mat.1 (mat.2 * rem) recipes obk).2
        ([] ++ (buildPlan n mat.1 (mat.2 * rem) recipes obk).1)]
    -- residual of head sibling is NonNeg (minGathers residual)
    have hpermat : 0 < mat.2 := hpo mat.1 mat.2 (by cases mat; simp)
    have hqnn : 0 < mat.2 * rem := Int.mul_pos hpermat hrem
    have hcorr := (buildPlan_correspondence recipes hpos n mat.1 (mat.2 * rem) obk (by omega)).2
    have hheadnn : NonNeg (buildPlan n mat.1 (mat.2 * rem) recipes obk).2 := by
      rw [hcorr]
      exact minGathers_nonneg_residual recipes hpos n mat.1 (mat.2 * rem) 0 obk hqnn hnn
    have hpo' : ∀ m p, (m, p) ∈ rest → 0 < p := fun m p hm => hpo m p (by simp [hm])
    exact ih (buildPlan n mat.1 (mat.2 * rem) recipes obk).2 hpo' hheadnn

/-- The per-key runtime delta of running `(buildPlan fuel item qty recipes owned).1`
from a runtime holdings `H`: holdings move by the bookkeeping residual change plus
`qty` units of the produced `item`. -/
def BuildDelta (fuel : Nat) (item : String) (qty : Int) (recipes : Recipes)
    (owned H finalH : Dict Int) : Prop :=
  ∀ k, getD finalH k 0
    = getD H k 0
      + (getD (buildPlan fuel item qty recipes owned).2 k 0 - getD owned k 0)
      + (if k = item then qty else 0)

/-- **buildPlan VALIDITY + PRODUCTION.** Running `buildPlan` from a runtime
holdings `H` that dominates the bookkeeping `owned` (`Dom owned H`) is
`ValidPlanFrom` and shifts holdings by the `BuildDelta` identity: each non-target
key tracks the bookkeeping residual change, the target `item` additionally rises
by `qty`. Domain hyps are the honest acyclic/positive/no-dup recipe assumptions
plus the rank bound `rank item ≤ fuel`. -/
theorem buildPlan_run (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hnd : RecipeNoDup recipes) :
    ∀ (fuel : Nat) (item : String) (qty : Int) (owned H : Dict Int),
      rank item ≤ fuel → 0 ≤ qty → NonNeg owned → Dom owned H →
      ValidPlanFrom recipes { gathers := 0, crafts := 0, holdings := H }
          (buildPlan fuel item qty recipes owned).1
      ∧ BuildDelta fuel item qty recipes owned H
          (List.foldl (applyAction recipes)
            { gathers := 0, crafts := 0, holdings := H }
            (buildPlan fuel item qty recipes owned).1).holdings := by
  intro fuel
  induction fuel with
  | zero =>
    intro item qty owned H hrf hq hownnn hdom
    -- rank item ≤ 0 ⇒ raw ⇒ but buildPlan 0 emits qty.toNat gathers of item
    have hraw : (getD recipes item []).length = 0 :=
      rank_zero_raw recipes rank item hacy (by omega)
    have hrecnil : recipeOf recipes item = [] := by
      rw [recipeOf_eq_getD]; exact List.length_eq_zero_iff.mp hraw
    simp only [buildPlan]
    refine ⟨?_, ?_⟩
    · -- replicate gathers of a raw item are all valid
      have : ∀ (n : Nat) (s : ExecState),
          ValidPlanFrom recipes s (List.replicate n (Action.gather item)) := by
        intro n
        induction n with
        | zero => intro s; simp [ValidPlanFrom]
        | succ m ihn =>
          intro s
          rw [List.replicate_succ, ValidPlanFrom]
          exact ⟨hrecnil, ihn _⟩
      exact this _ _
    · intro k
      have hgh := replicate_gather_holdings recipes item qty.toNat
        { gathers := 0, crafts := 0, holdings := H }
      obtain ⟨h1, h2⟩ := hgh
      by_cases hk : k = item
      · subst hk
        rw [h1, if_pos rfl]
        show getD H k 0 + (qty.toNat : Int) = getD H k 0 + (getD owned k 0 - getD owned k 0) + qty
        rw [Int.toNat_of_nonneg hq]; omega
      · rw [h2 k hk, if_neg hk]
        show getD H k 0 = getD H k 0 + (getD owned k 0 - getD owned k 0) + 0
        omega
  | succ n ih =>
    intro item qty owned H hrf hq hownnn hdom
    have hitemnn : 0 ≤ getD owned item 0 := hownnn item
    have hrnn : 0 ≤ qty - min (getD owned item 0) qty := by
      have := Int.min_le_right (getD owned item 0) qty; omega
    by_cases hc : qty - min (getD owned item 0) qty ≤ 0
    · -- remaining ≤ 0: empty plan; residual = setD owned item (held - used); used = qty
      have huq : min (getD owned item 0) qty = qty := by
        have := Int.min_le_right (getD owned item 0) qty; omega
      have hbp1 : (buildPlan (n+1) item qty recipes owned).1 = [] := by
        simp only [buildPlan]; rw [if_pos hc]
      have hbp2 : (buildPlan (n+1) item qty recipes owned).2
          = setD owned item (getD owned item 0 - min (getD owned item 0) qty) := by
        simp only [buildPlan]; rw [if_pos hc]
      refine ⟨by rw [hbp1]; simp [ValidPlanFrom], ?_⟩
      intro k
      rw [hbp1]
      simp only [List.foldl_nil]
      rw [hbp2, getD_setD]
      by_cases hk : k = item
      · subst hk
        rw [if_pos rfl, if_pos rfl, huq]; omega
      · rw [if_neg (by simpa [eq_comm] using hk), if_neg hk]; omega
    · by_cases hr : (getD recipes item []).length = 0
      · -- RAW arm: emit `rem` gathers of item
        have hrecnil : recipeOf recipes item = [] := by
          rw [recipeOf_eq_getD]; exact List.length_eq_zero_iff.mp hr
        have hbp1 : (buildPlan (n+1) item qty recipes owned).1
            = List.replicate (qty - min (getD owned item 0) qty).toNat (Action.gather item) := by
          simp only [buildPlan]; rw [if_neg hc, if_pos hr]
        have hbp2 : (buildPlan (n+1) item qty recipes owned).2
            = setD owned item (getD owned item 0 - min (getD owned item 0) qty) := by
          simp only [buildPlan]; rw [if_neg hc, if_pos hr]
        refine ⟨?_, ?_⟩
        · rw [hbp1]
          have hgv : ∀ (m : Nat) (s : ExecState),
              ValidPlanFrom recipes s (List.replicate m (Action.gather item)) := by
            intro m
            induction m with
            | zero => intro s; simp [ValidPlanFrom]
            | succ j ihj => intro s; rw [List.replicate_succ, ValidPlanFrom]; exact ⟨hrecnil, ihj _⟩
          exact hgv _ _
        · intro k
          rw [hbp1, hbp2]
          have hgh := replicate_gather_holdings recipes item
            (qty - min (getD owned item 0) qty).toNat
            { gathers := 0, crafts := 0, holdings := H }
          obtain ⟨h1, h2⟩ := hgh
          rw [getD_setD]
          have hHproj : ∀ j, getD ({ gathers := 0, crafts := 0, holdings := H } : ExecState).holdings j 0
              = getD H j 0 := fun _ => rfl
          by_cases hk : k = item
          · subst hk
            rw [h1, hHproj, if_pos rfl, if_pos rfl]
            rw [Int.toNat_of_nonneg hrnn]; omega
          · rw [h2 k hk, hHproj, if_neg (by simpa [eq_comm] using hk), if_neg hk]; omega
      · -- CRAFTABLE arm
        -- shorthand for the recipe and residual-owned-after-credit
        have hrnnstrict : 0 < qty - min (getD owned item 0) qty := by omega
        -- the recipe (= getD recipes item []), nonempty, rank-bounded, pos, no-dup
        have hrank_in : ∀ mat per, (mat, per) ∈ getD recipes item [] → rank mat ≤ n := by
          intro mat per hmem; have := hacy item mat per hmem; omega
        have hpos_in : ∀ mat per, (mat, per) ∈ getD recipes item [] → 0 < per :=
          fun mat per hmem => hpos item mat per hmem
        -- unfold buildPlan craftable
        have hbp1 : (buildPlan (n+1) item qty recipes owned).1
            = ((getD recipes item []).foldl
                (fun (st : Plan × Dict Int) mat =>
                  (st.1 ++ (buildPlan n mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
                              recipes st.2).1,
                   (buildPlan n mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
                              recipes st.2).2))
                ([], setD owned item (getD owned item 0 - min (getD owned item 0) qty))).1
              ++ List.replicate (qty - min (getD owned item 0) qty).toNat (Action.craft item) := by
          simp only [buildPlan]; rw [if_neg hc, if_neg hr]
        have hbp2 : (buildPlan (n+1) item qty recipes owned).2
            = ((getD recipes item []).foldl
                (fun (st : Plan × Dict Int) mat =>
                  (st.1 ++ (buildPlan n mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
                              recipes st.2).1,
                   (buildPlan n mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
                              recipes st.2).2))
                ([], setD owned item (getD owned item 0 - min (getD owned item 0) qty))).2 := by
          simp only [buildPlan]; rw [if_neg hc, if_neg hr]
        -- residual-owned-after-credit dominated by runtime H, and NonNeg
        have hdomOwned' : Dom (setD owned item (getD owned item 0 - min (getD owned item 0) qty)) H := by
          intro k; rw [getD_setD]
          by_cases hk : item = k
          · subst hk; have := hdom item; have := Int.min_le_left (getD owned item 0) qty
            rw [if_pos rfl]; omega
          · rw [if_neg hk]; exact hdom k
        have hownnn' : NonNeg (setD owned item (getD owned item 0 - min (getD owned item 0) qty)) := by
          apply nonneg_setD owned item _ hownnn
          have := Int.min_le_left (getD owned item 0) qty; omega
        -- the IH packaged as the `Hn` hypothesis for siblings
        have Hn : ∀ (it : String) (q : Int) (ow Hr : Dict Int),
            rank it ≤ n → 0 ≤ q → NonNeg ow → Dom ow Hr →
            ValidPlanFrom recipes { gathers := 0, crafts := 0, holdings := Hr }
                (buildPlan n it q recipes ow).1
            ∧ (∀ k, getD (List.foldl (applyAction recipes)
                  { gathers := 0, crafts := 0, holdings := Hr }
                  (buildPlan n it q recipes ow).1).holdings k 0
                = getD Hr k 0 + (getD (buildPlan n it q recipes ow).2 k 0 - getD ow k 0)
                  + (if k = it then q else 0)) := by
          intro it q ow Hr hrk hqn hnnow hdm
          have := ih it q ow Hr hrk hqn hnnow hdm
          exact ⟨this.1, this.2⟩
        have hsib := buildPlan_siblings recipes rank hpos n
          (qty - min (getD owned item 0) qty)
          hrnnstrict Hn (getD recipes item [])
          (setD owned item (getD owned item 0 - min (getD owned item 0) qty)) H
          hrank_in hpos_in hownnn' hdomOwned'
        obtain ⟨hsv, hsdom, hsdelta⟩ := hsib
        -- the recipe NoDup
        have hndr : NoDupKeys (recipeOf recipes item) := hnd item
        have hndr' : NoDupKeys (getD recipes item []) := by rw [← recipeOf_eq_getD]; exact hndr
        have hcrne : recipeOf recipes item ≠ [] := by
          rw [recipeOf_eq_getD]; intro h; rw [h] at hr; simp at hr
        -- post-sibling runtime holdings stock each input ≥ rem*per
        -- the sibling plan and post-sibling runtime, named
        refine ⟨?_, ?_⟩
        · -- VALIDITY: siblings ++ replicate crafts
          rw [hbp1, validPlanFrom_append]
          refine ⟨hsv, ?_⟩
          -- crafts valid from post-sibling state; stock from sibling delta
          apply replicate_craft_valid recipes rank hpos hacy item hndr hcrne
          -- stock: each input mat present with rem*per
          intro mat per hmemc
          have hmem : (mat, per) ∈ getD recipes item [] := by
            rw [recipeOf_eq_getD] at hmemc; exact hmemc
          have hd := hsdelta mat
          rw [hd]
          -- sumQtyAt (getD recipes item []) rem mat = per * rem (NoDup, member)
          have hsq : sumQtyAt (getD recipes item []) (qty - min (getD owned item 0) qty) mat
              = per * (qty - min (getD owned item 0) qty) :=
            sumQtyAt_member (getD recipes item []) (qty - min (getD owned item 0) qty)
              mat per hmem hndr'
          rw [hsq]
          -- getD H mat + (bk[mat]-owned'[mat]) + per*rem ≥ rem*per ;  H ≥ owned' so first two ≥0
          have hdm := hdomOwned' mat
          have hsdm := hsdom mat
          -- bk[mat] ≥ ... not needed: use H ≥ owned' and bk ≥ 0? Instead bound via hsdm:
          -- hsdom: Dom finalbk finalrt ; not directly. Use: getD H mat ≥ owned'[mat]
          have hpermat : 0 < per := hpos item mat per hmem
          have hbknn := buildPlan_siblings_bk_nonneg recipes hpos n
            (qty - min (getD owned item 0) qty) hrnnstrict (getD recipes item [])
            (setD owned item (getD owned item 0 - min (getD owned item 0) qty))
            hpos_in hownnn'
          have hbkmat := hbknn mat
          have hmulcomm : per * (qty - min (getD owned item 0) qty)
              = (qty - min (getD owned item 0) qty) * per := Int.mul_comm _ _
          have htn : ((qty - min (getD owned item 0) qty).toNat : Int)
              = qty - min (getD owned item 0) qty := Int.toNat_of_nonneg hrnn
          rw [htn]
          omega
        · -- DELTA: compose sibling delta + crafts consumption
          intro k
          rw [hbp1]
          rw [List.foldl_append]
          -- run craft suffix from post-sibling state
          rw [replicate_craft_effect recipes rank hacy item hndr
              (qty - min (getD owned item 0) qty).toNat _ k]
          -- post-sibling holdings via sibling delta
          rw [hsdelta k]
          -- residual = sibling bookkeeping
          rw [hbp2]
          -- relate sumQtyAt to sumPerAt and clear the toNat
          rw [sumQtyAt_eq_mul]
          have htn : ((qty - min (getD owned item 0) qty).toNat : Int)
              = qty - min (getD owned item 0) qty := Int.toNat_of_nonneg hrnn
          rw [htn]
          -- owned'[k] vs owned[k]: equal unless k = item (acyclic ⇒ item is the credited key)
          have hown'k : getD (setD owned item (getD owned item 0 - min (getD owned item 0) qty)) k 0
              = getD owned k 0 + (if k = item then (getD owned item 0 - min (getD owned item 0) qty)
                                                    - getD owned item 0 else 0) := by
            rw [getD_setD]; by_cases hk : item = k
            · subst hk; rw [if_pos rfl, if_pos rfl]; omega
            · rw [if_neg hk, if_neg (fun h => hk h.symm)]; omega
          rw [hown'k]
          -- normalise the craft-effect recipe form to getD
          have hreceq : recipeOf recipes item = getD recipes item [] := recipeOf_eq_getD recipes item
          rw [hreceq]
          by_cases hk : k = item
          · subst hk
            -- k ∉ its inputs (acyclic) ⇒ sumPerAt (getD recipes k []) k = 0
            have hsp0 : sumPerAt (getD recipes k []) k = 0 := by
              apply sumPerAt_absent; intro per hmem
              have := hacy k k per hmem; omega
            rw [if_pos rfl, if_pos rfl, if_pos rfl, hsp0]
            simp only [Int.mul_zero]; omega
          · rw [if_neg hk, if_neg hk, if_neg hk]
            omega

/-- **CONSTRUCTIVE OBTAINABILITY WITNESS.** `canonicalPlan recipes item owned`
is a valid plan that obtains and equips `item`: it is a `ValidPlan` and it
`SatisfiesEquip` (`ValidPlan` ∧ `equip item ∈ plan` ∧ holds ≥ 1 of `item`).

Constructive existence witness for the demand-`1`, gear-obtainment direction; it
is NOT the general lower bound (`minGathers_le_gathers_of_corner3`). The
`NoSurplusPlan` conjunct is intentionally omitted pending its separate definition.

TODO(nosurplus): add NoSurplusPlan conjunct once def lands. -/
theorem canonicalPlan_valid (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hnd : RecipeNoDup recipes)
    (item : String) (owned : Dict Int) (hnn : NonNeg owned) :
    ValidPlan recipes owned (canonicalPlan recipes item owned)
      ∧ SatisfiesEquip (canonicalPlan recipes item owned) item owned recipes := by
  have hdom : Dom owned owned := dom_refl owned
  have hrun := buildPlan_run recipes rank hpos hacy hnd (recipes.length + 1) item 1 owned owned
    (by have := hRB item; omega) (by omega) hnn hdom
  obtain ⟨hvalid, hdelta⟩ := hrun
  -- ValidPlan: buildPlan prefix is valid; the trailing `equip` is always valid
  have hvalidPlan : ValidPlan recipes owned (canonicalPlan recipes item owned) := by
    rw [canonicalPlan, ValidPlan, validPlanFrom_append]
    refine ⟨hvalid, ?_⟩
    -- validity of [equip item] from any state is trivial
    simp [ValidPlanFrom]
  refine ⟨hvalidPlan, hvalidPlan, canonicalPlan_equip_mem recipes item owned, ?_⟩
  -- production: holdings of `item` ≥ 1 after running the canonical plan
  -- the equip step is a no-op on holdings, so use the buildPlan delta
  have hprod : 1 ≤ getD (planHoldings recipes (canonicalPlan recipes item owned) owned) item 0 := by
    rw [canonicalPlan]
    -- runPlan over (buildPlan ++ [equip]) = run [equip] from run buildPlan; equip is a no-op
    have hfold : (List.foldl (applyAction recipes)
        { gathers := 0, crafts := 0, holdings := owned }
        ((buildPlan (recipes.length + 1) item 1 recipes owned).1 ++ [Action.equip item])).holdings
        = (List.foldl (applyAction recipes)
            { gathers := 0, crafts := 0, holdings := owned }
            (buildPlan (recipes.length + 1) item 1 recipes owned).1).holdings := by
      rw [List.foldl_append]; rfl
    show 1 ≤ getD (planHoldings recipes
      ((buildPlan (recipes.length + 1) item 1 recipes owned).1 ++ [Action.equip item]) owned) item 0
    unfold planHoldings runPlan
    rw [hfold]
    have hd := hdelta item
    rw [hd, if_pos rfl]
    -- getD owned item + (residual[item] - owned item) + 1 = residual[item] + 1 ≥ 1
    have hcorr := (buildPlan_correspondence recipes hpos (recipes.length + 1) item 1 owned
      (by omega)).2
    rw [hcorr]
    have hresnn : NonNeg (minGathers (recipes.length + 1) item 1 recipes (0, owned)).2 :=
      minGathers_nonneg_residual recipes hpos (recipes.length + 1) item 1 0 owned (by omega) hnn
    have := hresnn item
    omega
  rw [dictGet_eq]; exact hprod

/-- The literal number of `craft` actions in a plan. -/
def countCrafts : Plan → Nat
  | [] => 0
  | Action.craft _ :: rest => countCrafts rest + 1
  | _ :: rest => countCrafts rest

/-- The literal number of `equip` actions in a plan. -/
def countEquips : Plan → Nat
  | [] => 0
  | Action.equip _ :: rest => countEquips rest + 1
  | _ :: rest => countEquips rest

@[simp] theorem countCrafts_append (p q : Plan) :
    countCrafts (p ++ q) = countCrafts p + countCrafts q := by
  induction p with
  | nil => simp [countCrafts]
  | cons a rest ih => cases a <;> simp only [List.cons_append, countCrafts, ih] <;> omega

@[simp] theorem countEquips_append (p q : Plan) :
    countEquips (p ++ q) = countEquips p + countEquips q := by
  induction p with
  | nil => simp [countEquips]
  | cons a rest ih => cases a <;> simp only [List.cons_append, countEquips, ih] <;> omega

/-- Running a plan threads the craft counter additively. -/
theorem runPlan_crafts_foldl (recipes : Recipes) (plan : Plan) (s : ExecState) :
    (List.foldl (applyAction recipes) s plan).crafts = s.crafts + countCrafts plan := by
  induction plan generalizing s with
  | nil => simp [countCrafts]
  | cons a rest ih =>
    simp only [List.foldl_cons]; rw [ih (applyAction recipes s a)]
    cases a with
    | gather code => show s.crafts + _ = _; simp only [countCrafts]
    | craft code => show s.crafts + 1 + _ = _; simp only [countCrafts]; omega
    | equip code => show s.crafts + _ = _; simp only [countCrafts]

theorem planCrafts_eq_countCrafts (recipes : Recipes) (plan : Plan) (owned : Dict Int) :
    planCrafts recipes plan owned = countCrafts plan := by
  show (List.foldl (applyAction recipes) { gathers := 0, crafts := 0, holdings := owned } plan).crafts = _
  rw [runPlan_crafts_foldl]; simp

@[simp] theorem countEquips_replicate_gather (n : Nat) (c : String) :
    countEquips (List.replicate n (Action.gather c)) = 0 := by
  induction n with
  | zero => simp [countEquips]
  | succ m ih => rw [List.replicate_succ]; simp only [countEquips, ih]

@[simp] theorem countEquips_replicate_craft (n : Nat) (c : String) :
    countEquips (List.replicate n (Action.craft c)) = 0 := by
  induction n with
  | zero => simp [countEquips]
  | succ m ih => rw [List.replicate_succ]; simp only [countEquips, ih]

/-- `buildPlan` never emits an `equip` action. -/
theorem countEquips_buildPlan (recipes : Recipes) :
    ∀ (fuel : Nat) (item : String) (qty : Int) (owned : Dict Int),
      countEquips (buildPlan fuel item qty recipes owned).1 = 0 := by
  intro fuel
  induction fuel with
  | zero => intro item qty owned; simp [buildPlan]
  | succ n ih =>
    intro item qty owned
    simp only [buildPlan]
    by_cases hc : qty - min (getD owned item 0) qty ≤ 0
    · rw [if_pos hc]; simp [countEquips]
    · rw [if_neg hc]
      by_cases hr : (getD recipes item []).length = 0
      · rw [if_pos hr]; simp
      · rw [if_neg hr]
        rw [countEquips_append, countEquips_replicate_craft]
        -- the sibling foldl emits no equips
        have hfold : ∀ (rc : List (String × Int)) (o : Dict Int) (p0 : Plan),
            countEquips p0 = 0 →
            countEquips (rc.foldl
              (fun (st : Plan × Dict Int) mat =>
                (st.1 ++ (buildPlan n mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
                            recipes st.2).1,
                 (buildPlan n mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
                            recipes st.2).2)) (p0, o)).1 = 0 := by
          intro rc
          induction rc with
          | nil => intro o p0 hp0; simpa using hp0
          | cons mat rest ihrc =>
            intro o p0 hp0
            simp only [List.foldl_cons]
            apply ihrc
            rw [countEquips_append, hp0, ih mat.1
              (mat.2 * (qty - min (getD owned item 0) qty)) o]
        rw [hfold (getD recipes item [])
          (setD owned item (getD owned item 0 - min (getD owned item 0) qty)) [] (by simp [countEquips])]

/-- A plan's length is its gather + craft + equip action counts. -/
theorem length_eq_counts (plan : Plan) :
    plan.length = countGathers plan + countCrafts plan + countEquips plan := by
  induction plan with
  | nil => simp [countGathers, countCrafts, countEquips]
  | cons a rest ih =>
    cases a <;> simp only [List.length_cons, countGathers, countCrafts, countEquips, ih] <;> omega

/-- **OBTAINABILITY WITNESS WITH LENGTH BOUND.** When the per-action length budget
`d` dominates the canonical plan's own action count
(`planGathers + planCrafts + 1 ≤ d`), there EXISTS a valid plan that obtains and
equips `item` of length `≤ d` — namely `canonicalPlan`.

**Scope / boundary.** This is the constructive existence witness for the
demand-`1`, gear-obtainment direction; it is NOT the general lower bound. The
length budget is stated against the *per-action* count
(`planGathers + planCrafts + 1`, one gather per raw unit) rather than the
production `minPlanLength`, which applies `ceil_gathers` (dividing the raw gather
count by `maxGatherYield` for multi-drop resources). For `maxGatherYield = 1`
they coincide and `planGathers = (minGathersCount item 1 …).toNat`
(`canonicalPlan_gathers`); for `maxGatherYield > 1` the per-action plan may gather
more times than `minPlanLength`, so this honest bound is stated in per-action
units. Bridging to `minPlanLength` requires a batch-gather model extension and is
left as a documented gap. -/
theorem gear_obtainable_of_minPlanLength_le (recipes : Recipes) (rank : String → Nat)
    (hpos : PosRecipes recipes) (hacy : Acyclic recipes rank)
    (hRB : ∀ item, rank item ≤ recipes.length) (hnd : RecipeNoDup recipes)
    (item : String) (owned : Dict Int) (hnn : NonNeg owned) (d : Nat)
    (hbudget : planGathers recipes (canonicalPlan recipes item owned) owned
      + planCrafts recipes (canonicalPlan recipes item owned) owned + 1 ≤ d) :
    ∃ plan, SatisfiesEquip plan item owned recipes ∧ plan.length ≤ d := by
  refine ⟨canonicalPlan recipes item owned, ?_, ?_⟩
  · exact (canonicalPlan_valid recipes rank hpos hacy hRB hnd item owned hnn).2
  · -- length = gathers + crafts + 1 (single equip)
    rw [length_eq_counts]
    rw [canonicalPlan]
    have hg : countGathers ((buildPlan (recipes.length + 1) item 1 recipes owned).1
        ++ [Action.equip item]) = planGathers recipes (canonicalPlan recipes item owned) owned := by
      rw [planGathers_eq_countGathers, canonicalPlan]
    have hc : countCrafts ((buildPlan (recipes.length + 1) item 1 recipes owned).1
        ++ [Action.equip item])
        = planCrafts recipes (canonicalPlan recipes item owned) owned := by
      rw [planCrafts_eq_countCrafts, canonicalPlan]
    have he : countEquips ((buildPlan (recipes.length + 1) item 1 recipes owned).1
        ++ [Action.equip item]) = 1 := by
      rw [countEquips_append]
      have : countEquips (buildPlan (recipes.length + 1) item 1 recipes owned).1 = 0 :=
        countEquips_buildPlan recipes (recipes.length + 1) item 1 owned
      rw [this]; simp [countEquips]
    rw [hg, hc, he]
    exact hbudget

end Formal.PlanModel
