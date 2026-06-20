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
  * `craft  code` — increment `crafts`,  add 1 to `holdings[code]`
                    (recipe inputs are NOT consumed here; this model provides a
                    LOWER BOUND — it counts craft actions, not input availability;
                    Tasks 5–6 prove the count is sound).
  * `equip  code` — no state change (equip is counted at the `Plan` level via
                    `SatisfiesEquip`, not inside the per-action fold). -/
def applyAction (s : ExecState) (a : Action) : ExecState :=
  match a with
  | Action.gather code =>
      { s with
        gathers  := s.gathers + 1
        holdings := dictSet s.holdings code (dictGet s.holdings code + 1) }
  | Action.craft code =>
      { s with
        crafts   := s.crafts + 1
        holdings := dictSet s.holdings code (dictGet s.holdings code + 1) }
  | Action.equip _ =>
      s

-- ---------------------------------------------------------------------------
-- Plan semantics: produces / satisfies
-- ---------------------------------------------------------------------------

/-- Run a plan from initial holdings `owned`, returning the final `ExecState`.

Uses `List.foldl` (left-to-right, exactly like the extracted cores) so Task-5
induction steps align with `_min_gathers`/`_min_crafts` foldl unfoldings. -/
def runPlan (plan : Plan) (owned : List (String × Int)) : ExecState :=
  List.foldl applyAction { gathers := 0, crafts := 0, holdings := owned } plan

/-- The gather count of running `plan` from `owned`. -/
def planGathers (plan : Plan) (owned : List (String × Int)) : Nat :=
  (runPlan plan owned).gathers

/-- The craft count of running `plan` from `owned`. -/
def planCrafts (plan : Plan) (owned : List (String × Int)) : Nat :=
  (runPlan plan owned).crafts

/-- The final holdings after running `plan` from `owned`. -/
def planHoldings (plan : Plan) (owned : List (String × Int)) : List (String × Int) :=
  (runPlan plan owned).holdings

-- ---------------------------------------------------------------------------
-- SatisfiesEquip
-- ---------------------------------------------------------------------------

/-- `SatisfiesEquip plan item` holds when `plan` contains an `equip item` action
AND the plan yields at least 1 of `item` (from gather or craft actions).

Design choice: we use `equip item ∈ plan` (membership) rather than tracking
prefix-execution order. This is sound for the lower-bound direction: if the plan
equips `item`, it must have produced it first (a real planner cannot equip what
it has not gathered or crafted), so a bound on gathering + crafting + 1 (for the
equip action) bounds the total. The ordering refinement (item produced before
equip) is left to Tasks 5–7 via the `hsat_lb` hypothesis in
`PlannerDepthBound.reachable_not_satisfying_when_lb_exceeds_depth`. -/
def SatisfiesEquip (plan : Plan) (item : String) (owned : List (String × Int)) : Prop :=
  Action.equip item ∈ plan ∧
  1 ≤ dictGet (planHoldings plan owned) item + dictGet owned item

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

end Formal.PlanModel
