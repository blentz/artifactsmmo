-- @concept: planner, plan, action @property: lower-bound, soundness
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
-- Craft-step coupling (the heart): minGathers after a valid craft ≤ before
-- ---------------------------------------------------------------------------

/-!
## The craft step

A valid `craft c` consumes `recipeOf c` (`−per` each) and produces `+1 c`. The
resulting holdings `H'` have EQUAL `costMass` to `H` (`costMass_craft_preserved`)
but are pointwise INCOMPARABLE to `H`, so `minGathers_mono` does not apply. The
craft step of Ψ-monotonicity is `g(H') ≤ g(H)` where `g(x) = minGathersCount`.

The cleanest fully-provable corner is when the crafted item IS the query item:
then `H'` already covers it (holds ≥ 1), so its count is `0`, trivially `≤ g(H)`.
The general corner (query item ≠ crafted item) is the residual simultaneous
coupling the report has flagged as irreducible; it is NOT proven here.
-/

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

end Formal.PlanModel
