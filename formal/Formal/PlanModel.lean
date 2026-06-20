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
every `craft` action in `plan` has its recipe inputs present in the current
holdings at the moment it executes.

Defined recursively over the plan list, threading state forward one step at a
time (same shape as `runPlan` / `List.foldl`). This makes the Task-5 induction
match: unfold one `foldl` step, case-split on the action, for `craft` extract
the `ValidCraftAt` hypothesis, then continue on the tail. -/
def ValidPlanFrom (recipes : List (String × List (String × Int)))
    (s : ExecState) : Plan → Prop
  | []      => True
  | a :: rest =>
      (match a with
       | Action.craft code  => ValidCraftAt recipes s.holdings code
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
  -- Specifically, `10 ≤ dictGet [] "feather"` = `10 ≤ 0` is false.
  intro h
  have := h "feather" 10 (by simp)
  simp [dictGet] at this

end Formal.PlanModel
