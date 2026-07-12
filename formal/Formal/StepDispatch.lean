-- @concept: core, planner @property: totality, safety, reachability
import Formal.ShoppingList

/-!
# Formal.StepDispatch

**Composition theorem for `objective_step_goal`'s MetaGoal → GoalClass dispatch.**

The Python `objective_step_goal` (strategy_driver.py:157-180) takes a
strategy-engine `chosen_step : MetaGoal` and returns a concrete `Goal`
instance. The arbiter then uses that goal as its objective-step
candidate. If the dispatch is wrong (a step routed to the wrong goal
class, or routed to `None` when a goal class exists, or vice versa),
the arbiter falls through to the discretionary tier — exactly the
2026-06-06 trace failure mode.

This module:

1. Models `MetaGoal` as a Lean inductive matching the Python type.
2. Models `GoalClass` as a Lean inductive of the runtime goal types.
3. Specifies `stepDispatch` and proves it is **total** (no `MetaGoal`
   variant has undefined behavior), **deterministic** (same input ⇒
   same output), and **safe-failing** (ReachCharLevel + no combat
   target ⇒ `None`).

Phase G5 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.StepDispatch

/-! ## Type model. -/

/-- A meta-goal: the strategy-engine's notion of progress unit. -/
inductive MetaGoal where
  | obtainItem : (code : Int) → (isEquippable : Bool) → MetaGoal
  | reachCharLevel : (level : Int) → MetaGoal
deriving Repr, DecidableEq

/-- The runtime goal class produced by `objective_step_goal`. -/
inductive GoalClass where
  | upgradeEquipment : (code : Int) → GoalClass
  | gatherMaterials  : (code : Int) → (quantity : Int) → GoalClass
  | levelSkill       : (skill : Int) → (target : Int) → GoalClass
  | grindCharacterXP : (monster : Int) → GoalClass
deriving Repr, DecidableEq

/-- The dispatch context.

* `combatMonster` might be `None` (no winnable target) which gates the
  ReachCharLevel branch to a safe-fail.
* `targetReachable` mirrors `UpgradeEquipmentGoal.is_plannable` for an
  equippable ObtainItem target: `true` when the target is depth-REACHABLE
  (its materials are in hand or craftable within `max_depth`), `false`
  when depth-UNREACHABLE (`min_gathers(code) > max_depth` — materials not
  yet gathered). It gates the equippable ObtainItem branch between the
  craft+equip UpgradeEquipment goal and the GatherMaterials fallback that
  drives the gather so materials accumulate. -/
structure DispatchContext where
  combatMonster : Option Int
  targetReachable : Bool

/-! ## The dispatch function. -/

/-- Mirrors `objective_step_goal` exactly:

* `ObtainItem(code, equippable=true)` with `targetReachable = true`
  → `UpgradeEquipment(code)` (the craft+equip);
* `ObtainItem(code, equippable=true)` with `targetReachable = false`
  → `GatherMaterials(code, 1)` (drive the gather so materials accumulate;
  UpgradeEquipment fires once they're in hand);
* `ObtainItem(code, equippable=false)` → `GatherMaterials(code, 1)`
* `ReachCharLevel(level)` with `combatMonster = some _` → `GrindCharacterXP`
* `ReachCharLevel(level)` with `combatMonster = none` → `None` (safe fail).
-/
def stepDispatch (ctx : DispatchContext) : MetaGoal → Option GoalClass
  | MetaGoal.obtainItem code true =>
      if ctx.targetReachable then some (GoalClass.upgradeEquipment code)
      else some (GoalClass.gatherMaterials code 1)
  | MetaGoal.obtainItem code false =>
      some (GoalClass.gatherMaterials code 1)
  | MetaGoal.reachCharLevel _ =>
      match ctx.combatMonster with
      | some monster => some (GoalClass.grindCharacterXP monster)
      | none => none

/-! ## Totality and determinism. -/

/-- The dispatch is total: every MetaGoal variant produces a value
(possibly `none` for the safe-fail case). -/
theorem stepDispatch_total (ctx : DispatchContext) (step : MetaGoal) :
    stepDispatch ctx step = none ∨ ∃ g, stepDispatch ctx step = some g := by
  cases step with
  | obtainItem code eq =>
    cases eq <;> simp only [stepDispatch] <;> cases ctx.targetReachable <;> simp
  | reachCharLevel level =>
    simp [stepDispatch]
    cases ctx.combatMonster with
    | none => left; rfl
    | some m => right; exact ⟨_, rfl⟩

/-- Deterministic: same input ⇒ same output. (Trivially true by
function totality.) -/
theorem stepDispatch_deterministic (ctx : DispatchContext) (step : MetaGoal) :
    ∀ result1 result2,
      stepDispatch ctx step = result1 →
      stepDispatch ctx step = result2 →
      result1 = result2 := by
  intros r1 r2 h1 h2
  rw [← h1, ← h2]

/-! ## Per-branch correctness. -/

/-- Equippable ObtainItem with a depth-REACHABLE target dispatches to
UpgradeEquipment (the craft+equip). -/
theorem dispatch_obtain_equippable_goes_to_upgrade (ctx : DispatchContext)
    (h : ctx.targetReachable = true) (code : Int) :
    stepDispatch ctx (MetaGoal.obtainItem code true) =
      some (GoalClass.upgradeEquipment code) := by
  simp [stepDispatch, h]

/-- Equippable ObtainItem with a depth-UNREACHABLE target dispatches to
GatherMaterials — the fallback that drives the gather so the target's
recipe materials accumulate across cycles; UpgradeEquipment fires once
they're in hand. -/
theorem dispatch_obtain_equippable_unreachable_goes_to_gather
    (ctx : DispatchContext) (h : ctx.targetReachable = false) (code : Int) :
    stepDispatch ctx (MetaGoal.obtainItem code true) =
      some (GoalClass.gatherMaterials code 1) := by
  simp [stepDispatch, h]

/-- Non-equippable ObtainItem dispatches to GatherMaterials. -/
theorem dispatch_obtain_nonequippable_goes_to_gather (ctx : DispatchContext)
    (code : Int) :
    stepDispatch ctx (MetaGoal.obtainItem code false) =
      some (GoalClass.gatherMaterials code 1) := rfl

/-- ReachCharLevel with a combat target dispatches to GrindCharacterXP. -/
theorem dispatch_reach_char_with_target_goes_to_grind (level monster : Int) :
    stepDispatch { combatMonster := some monster, targetReachable := true }
      (MetaGoal.reachCharLevel level) =
      some (GoalClass.grindCharacterXP monster) := rfl

/-- **Safe-fail**: ReachCharLevel with NO combat target returns `none`. The
arbiter sees this as "no objective step available" and falls to
discretionary. The Python contract requires this — without it, the step
goal would be `GrindCharacterXP(<undefined>)` which would crash the
planner. -/
theorem dispatch_reach_char_no_target_safe_fails (level : Int) :
    stepDispatch { combatMonster := none, targetReachable := true }
      (MetaGoal.reachCharLevel level) =
      none := rfl

/-! ## Uniqueness of routing. -/

/-- An ObtainItem step never dispatches to a non-Obtain goal class. -/
theorem obtain_only_routes_to_obtain_classes (ctx : DispatchContext)
    (code : Int) (eq : Bool) :
    ∀ g, stepDispatch ctx (MetaGoal.obtainItem code eq) = some g →
      (∃ c, g = GoalClass.upgradeEquipment c) ∨
      (∃ c q, g = GoalClass.gatherMaterials c q) := by
  intros g hG
  cases eq with
  | true =>
    -- The equippable branch is conditional on `ctx.targetReachable`:
    -- reachable ⇒ UpgradeEquipment, unreachable ⇒ GatherMaterials. Both
    -- are obtain-classes, so the disjunction holds either way.
    cases hR : ctx.targetReachable with
    | true =>
      rw [dispatch_obtain_equippable_goes_to_upgrade ctx hR] at hG
      cases hG
      left; exact ⟨code, rfl⟩
    | false =>
      rw [dispatch_obtain_equippable_unreachable_goes_to_gather ctx hR] at hG
      cases hG
      right; exact ⟨code, 1, rfl⟩
  | false =>
    rw [dispatch_obtain_nonequippable_goes_to_gather] at hG
    cases hG
    right; exact ⟨code, 1, rfl⟩

/-- A ReachCharLevel step never dispatches to a non-char goal class. -/
theorem reach_char_only_routes_to_grind (ctx : DispatchContext) (level : Int) :
    ∀ g, stepDispatch ctx (MetaGoal.reachCharLevel level) = some g →
      ∃ m, g = GoalClass.grindCharacterXP m := by
  intros g hG
  unfold stepDispatch at hG
  cases hCM : ctx.combatMonster with
  | none =>
    rw [hCM] at hG
    exact absurd hG (by simp)
  | some monster =>
    rw [hCM] at hG
    cases hG
    exact ⟨monster, rfl⟩

/-! ## Budget-feasible gather target for a depth-unreachable equippable root.

Models `src/artifactsmmo_cli/ai/gather_step_target.py` (`gather_step_target`),
the Piece-C feasibility decision wired into `objective_step_goal`.

When the strategy's chosen root is an equippable whose full craft chain is
depth-UNREACHABLE (`min_gathers(root) > equip_max_depth` — the proven
`UpgradeEquipmentGoal.is_plannable` gate), the prior fallback drove
`GatherMaterials(root, root's DIRECT recipe)`. For a from-scratch DEEP chain that
goal's plan must gather `min_gathers(root)` raw units THROUGH a multi-level
recipe and the GOAP search EXPLODES (live: 1M+ nodes, 90s timeout, plan_len 0).
The fix routes to the strategy's DEEPEST actionable `step` (the raw base
material) — a FLAT gather (`minGathers == qty`) that plans within budget and makes
incremental progress.

CONSUME SEMANTICS (P3d, docs/PLAN_mechanical_extraction.md): `min_gathers.py`
THREADS a `(total, owned)` state through the recursion and CONSUMES holdings
as it credits them — a unit credited under one parent is NOT available to a
sibling branch. The pre-P3d hand model credited a CONSTANT `owned` function at
every node instead; the two agree on TREE recipes but the constant model
DOUBLE-CREDITS shared stock on DAG-shaped recipes (the same fidelity gap
closed for ShoppingList in P2c). Python's consume accounting is the spec, so
this model mirrors `_min_gathers` statement-for-statement on the shared
extracted encoding (`Formal.ShoppingList.Dict`/`Recipes`/`getD`/`setD`:
String items, Int quantities, insertion-ordered association lists;
fuel-structural recursion seeded `len(recipes) + 1`).
`formal/Formal/Extracted/Bridges6.lean` proves the mechanically extracted
image (`Formal/Extracted/MinGathers.lean`) equal to this model UNIVERSALLY. -/

open Formal.ShoppingList (Dict Recipes getD setD)

/-- Add the gathers for one `(item, qty)` node to the threaded
`(total, owned)` state: credit (and CONSUME) the held copies of `item`, then
gather the remainder (raw: empty/absent recipe) or recurse into the
sub-recipe at `per_unit * remaining`. Out of fuel ⇒ account the node's whole
quantity as raw (conservatively LARGE — a cyclic recipe is uncraftable, so
the unreachability gate stays sound; unreachable on acyclic recipes at the
`minGathersCount` seeding). Mirrors `_min_gathers` statement-for-statement. -/
def minGathers : Nat → String → Int → Recipes → Int × Dict Int → Int × Dict Int
  | 0, _, qty, _, state => (state.1 + qty, state.2)
  | fuel + 1, item, qty, recipes, state =>
    let total := state.1
    let owned := state.2
    let held := getD owned item 0
    let used := min held qty
    let owned := setD owned item (held - used)
    let remaining := qty - used
    if remaining ≤ 0 then (total, owned)
    else
      let recipe := getD recipes item []
      if recipe.length = 0 then (total + remaining, owned)
      else recipe.foldl
        (fun state mat => minGathers fuel mat.1 (mat.2 * remaining) recipes state)
        (total, owned)

/-- The gather lower bound for `qty` of `item` crediting (and consuming)
`owned` — the Python `min_gathers`, fuel seeded with `len(recipes) + 1`. -/
def minGathersCount (item : String) (qty : Int) (recipes : Recipes)
    (owned : Dict Int) : Int :=
  (minGathers (recipes.length + 1) item qty recipes (0, owned)).1

/-- `minGathers` at `fuel + 1`, zeta-expanded (the shape the proofs case on). -/
theorem minGathers_succ (fuel : Nat) (item : String) (qty : Int)
    (recipes : Recipes) (total : Int) (owned : Dict Int) :
    minGathers (fuel + 1) item qty recipes (total, owned) =
      if qty - min (getD owned item 0) qty ≤ 0 then
        (total, setD owned item (getD owned item 0 - min (getD owned item 0) qty))
      else if (getD recipes item []).length = 0 then
        (total + (qty - min (getD owned item 0) qty),
         setD owned item (getD owned item 0 - min (getD owned item 0) qty))
      else
        (getD recipes item []).foldl
          (fun state mat =>
            minGathers fuel mat.1 (mat.2 * (qty - min (getD owned item 0) qty))
              recipes state)
          (total, setD owned item (getD owned item 0 - min (getD owned item 0) qty)) :=
  rfl

/-- A RAW item (empty/absent recipe) at positive fuel from a zero running
total: the gather count is exactly the per-node `Nat.sub` deficit
`Formal.ShoppingList.deficit qty held` — the FLAT gather cost the
deepest-step route relies on. -/
theorem minGathers_raw (fuel : Nat) (item : String) (qty held : Nat)
    (recipes : Recipes) (owned : Dict Int)
    (hraw : (getD recipes item []).length = 0)
    (hheld : getD owned item 0 = (held : Int)) :
    (minGathers (fuel + 1) item (qty : Int) recipes (0, owned)).1
      = ((Formal.ShoppingList.deficit qty held : Nat) : Int) := by
  rw [minGathers_succ, hheld]
  unfold Formal.ShoppingList.deficit
  by_cases hc : (qty : Int) - min (held : Int) (qty : Int) ≤ 0
  · rw [if_pos hc]; show (0 : Int) = _; omega
  · rw [if_neg hc, if_pos hraw]; show (0 : Int) + _ = _; omega

/-- A RAW item with no holdings: the gather count is exactly `qty` (flat). -/
theorem minGathers_raw_unowned (fuel : Nat) (item : String) (qty : Nat)
    (recipes : Recipes) (hraw : (getD recipes item []).length = 0) :
    (minGathers (fuel + 1) item (qty : Int) recipes (0, [])).1 = (qty : Int) := by
  rw [minGathers_raw fuel item qty 0 recipes [] hraw rfl]
  unfold Formal.ShoppingList.deficit
  omega

/-- Ceil-division of raw gather UNITS into gather ACTIONS by the global
per-gather drop maximum `maxYield` (>= 1). Mirrors Python
`gather_floor.ceil_gathers`: `(units + maxYield - 1) / maxYield`. With
`maxYield = 1` it is the identity on `units`, so single-yield resources keep
their exact gather count. A TIGHTER but still SOUND lower bound than `units`
itself, so the over-budget routing stops over-counting multi-yield chains. -/
def ceilGathers (units maxYield : Int) : Int := (units + maxYield - 1) / maxYield

/-- The pure routing decision, mirroring `gather_step_target`:
route to the root when its gather cost (raw units divided into ACTIONS by
`maxYield`) fits the budget, else the deepest step. Like the Python, the unit
cost is the SEEDED `minGathersCount` (`min_gathers` copies `owned` and seeds the
fuel internally). -/
def gatherTarget (recipes : Recipes) (owned : Dict Int) (rootItem stepItem : String)
    (stepQty equipMaxDepth maxYield : Int) : String × Int :=
  if ceilGathers (minGathersCount rootItem 1 recipes owned) maxYield ≤ equipMaxDepth
  then (rootItem, 1)
  else (stepItem, stepQty)

/-- SOUNDNESS (route-only-when-over-budget): the deeper `step` is chosen ONLY
when the root's gather cost STRICTLY exceeds the equippable depth budget. So a
depth-reachable root is never abandoned — exactly the Piece-C honesty bar
(no false-infeasible that drops a doable objective). -/
theorem gatherTarget_step_only_when_root_over_budget
    (recipes : Recipes) (owned : Dict Int) (rootItem stepItem : String)
    (stepQty equipMaxDepth maxYield : Int)
    (h : gatherTarget recipes owned rootItem stepItem stepQty equipMaxDepth maxYield
      = (stepItem, stepQty))
    (hne : (stepItem, stepQty) ≠ (rootItem, 1)) :
    equipMaxDepth < ceilGathers (minGathersCount rootItem 1 recipes owned) maxYield := by
  unfold gatherTarget at h
  by_cases hb : ceilGathers (minGathersCount rootItem 1 recipes owned) maxYield
      ≤ equipMaxDepth
  · rw [if_pos hb] at h; exact absurd h hne.symm
  · omega

/-- SOUNDNESS (root-kept-when-feasible): when the root's gather cost fits the
budget the decision keeps the root target (the caller plans the short craft+equip
chain). -/
theorem gatherTarget_root_when_feasible
    (recipes : Recipes) (owned : Dict Int) (rootItem stepItem : String)
    (stepQty equipMaxDepth maxYield : Int)
    (h : ceilGathers (minGathersCount rootItem 1 recipes owned) maxYield
      ≤ equipMaxDepth) :
    gatherTarget recipes owned rootItem stepItem stepQty equipMaxDepth maxYield
      = (rootItem, 1) := by
  unfold gatherTarget; simp [h]

/-- SOUNDNESS (never-harder): when the deepest `step` is a RAW leaf, the routed
target's gather cost is NOT larger than the root gather cost we declined —
routing trades DOWN to a flatter sub-target, never up to a harder one. Pins
that the fix can't pick a worse target than the root.

Hypotheses: non-negative step holdings and quantity (production invariants —
counts and expanded requirements), and the step is the root's transitive base
(`stepQty ≤ minGathersCount(root)`, which holds because the deepest step's
quantity is the expanded raw requirement). -/
theorem gatherTarget_step_not_harder_than_root
    (recipes : Recipes) (owned : Dict Int) (rootItem stepItem : String)
    (stepQty : Int)
    (hstep : (getD recipes stepItem []).length = 0)
    (hheld : 0 ≤ getD owned stepItem 0)
    (hq : 0 ≤ stepQty)
    (hcost : stepQty ≤ minGathersCount rootItem 1 recipes owned) :
    minGathersCount stepItem stepQty recipes owned
      ≤ minGathersCount rootItem 1 recipes owned := by
  refine Int.le_trans ?_ hcost
  unfold minGathersCount
  rw [minGathers_succ]
  by_cases hc : stepQty - min (getD owned stepItem 0) stepQty ≤ 0
  · rw [if_pos hc]; show (0 : Int) ≤ stepQty; omega
  · rw [if_neg hc, if_pos hstep]
    show (0 : Int) + (stepQty - min (getD owned stepItem 0) stepQty) ≤ stepQty
    omega

/-- DAG consume-accounting witness (the P2c ShoppingList finding, closed for
`min_gathers` in P3d): two gear parts share the same ore; 2 banked ore cover
only ONE branch. The pre-P3d constant-credit model counted 0 gathers (the ore
credited under BOTH parents); the consume model — like Python — counts 2. -/
example :
    minGathersCount "sword" 1
        [("sword", [("a", 1), ("b", 1)]), ("a", [("ore", 2)]), ("b", [("ore", 2)])]
        [("ore", 2)]
      = 2 := by decide

/-- DAG diamond witness: both paths need 2 of the shared raw `m`; the 2 held
units cover the FIRST path only, leaving 2 real gathers (constant credit said
0). -/
example :
    minGathersCount "root" 1
        [("root", [("x", 1), ("y", 1)]), ("x", [("m", 2)]), ("y", [("m", 2)])]
        [("m", 2)]
      = 2 := by decide

end Formal.StepDispatch
