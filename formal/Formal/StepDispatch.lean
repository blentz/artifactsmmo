-- @concept: core, planner @property: totality, safety, reachability

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
  | reachSkillLevel : (skill : Int) → (level : Int) → MetaGoal
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
* `ReachSkillLevel(skill, level)` → `LevelSkill(skill, level)`
* `ReachCharLevel(level)` with `combatMonster = some _` → `GrindCharacterXP`
* `ReachCharLevel(level)` with `combatMonster = none` → `None` (safe fail).
-/
def stepDispatch (ctx : DispatchContext) : MetaGoal → Option GoalClass
  | MetaGoal.obtainItem code true =>
      if ctx.targetReachable then some (GoalClass.upgradeEquipment code)
      else some (GoalClass.gatherMaterials code 1)
  | MetaGoal.obtainItem code false =>
      some (GoalClass.gatherMaterials code 1)
  | MetaGoal.reachSkillLevel skill level =>
      some (GoalClass.levelSkill skill level)
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
  | reachSkillLevel skill level => simp [stepDispatch]
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

/-- ReachSkillLevel dispatches to LevelSkill. -/
theorem dispatch_reach_skill_goes_to_level_skill (ctx : DispatchContext)
    (skill level : Int) :
    stepDispatch ctx (MetaGoal.reachSkillLevel skill level) =
      some (GoalClass.levelSkill skill level) := rfl

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

/-- A ReachSkillLevel step never dispatches to a non-skill goal class. -/
theorem reach_skill_only_routes_to_level_skill (ctx : DispatchContext)
    (skill level : Int) :
    ∀ g, stepDispatch ctx (MetaGoal.reachSkillLevel skill level) = some g →
      g = GoalClass.levelSkill skill level := by
  intros g hG
  rw [dispatch_reach_skill_goes_to_level_skill] at hG
  exact (Option.some_inj.mp hG).symm

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

We model `minGathers` exactly as `min_gathers.py`/`ShoppingList.rawReq`: credit
the item's holdings, then for the deficit gather it (raw: empty recipe) or recurse
into the sub-recipe at `per_unit * deficit`. `Recipe`/`deficit` are reused from
ShoppingList's shape (redeclared here to keep StepDispatch self-contained and
mathlib-free). -/

/-- A recipe environment: item → its `(sub_mat, per_unit)` ingredient list. -/
abbrev Recipe := Nat → List (Nat × Nat)

/-- Per-node deficit after crediting `have` held copies (truncated `Nat.sub`). -/
def gdeficit (qty «have» : Nat) : Nat := qty - «have»

mutual
  /-- Lower bound on gathers to obtain `qty` of `item` crediting `owned`.
  Mirrors `min_gathers`/`rawReq`: out of fuel ⇒ account the deficit as raw. -/
  def minGathers (owned : Nat → Nat) (r : Recipe) : Nat → Nat → Nat → Nat
    | 0, _, qty => qty
    | fuel + 1, item, qty =>
      match r item with
      | []   => gdeficit qty (owned item)
      | mats => sumGathers owned r fuel mats (gdeficit qty (owned item))
  /-- Sum sub-material gathers at `per_unit * deficit`. -/
  def sumGathers (owned : Nat → Nat) (r : Recipe) (fuel : Nat) :
      List (Nat × Nat) → Nat → Nat
    | [], _ => 0
    | (sub, per) :: rest, d => minGathers owned r fuel sub (per * d) + sumGathers owned r fuel rest d
end

/-- A RAW item (empty recipe) at positive fuel: `minGathers == deficit == qty`
when nothing is owned — the FLAT gather cost the deepest-step route relies on. -/
theorem minGathers_raw (owned : Nat → Nat) (r : Recipe) (item qty fuel : Nat)
    (hraw : r item = []) :
    minGathers owned r (fuel + 1) item qty = gdeficit qty (owned item) := by
  simp [minGathers, hraw]

/-- A RAW item with no holdings: `minGathers == qty` exactly (flat). -/
theorem minGathers_raw_unowned (r : Recipe) (item qty fuel : Nat)
    (hraw : r item = []) :
    minGathers (fun _ => 0) r (fuel + 1) item qty = qty := by
  rw [minGathers_raw _ r item qty fuel hraw]; simp [gdeficit]

/-- The pure routing decision, mirroring `gather_step_target`:
route to the root when its gather cost fits the budget, else the deepest step. -/
def gatherTarget (owned : Nat → Nat) (r : Recipe) (fuel : Nat)
    (rootItem stepItem stepQty equipMaxDepth : Nat) : Nat × Nat :=
  if minGathers owned r fuel rootItem 1 ≤ equipMaxDepth then (rootItem, 1)
  else (stepItem, stepQty)

/-- SOUNDNESS (route-only-when-over-budget): the deeper `step` is chosen ONLY
when the root's gather cost STRICTLY exceeds the equippable depth budget. So a
depth-reachable root is never abandoned — exactly the Piece-C honesty bar
(no false-infeasible that drops a doable objective). -/
theorem gatherTarget_step_only_when_root_over_budget
    (owned : Nat → Nat) (r : Recipe) (fuel rootItem stepItem stepQty equipMaxDepth : Nat)
    (h : gatherTarget owned r fuel rootItem stepItem stepQty equipMaxDepth = (stepItem, stepQty))
    (hne : (stepItem, stepQty) ≠ (rootItem, 1)) :
    equipMaxDepth < minGathers owned r fuel rootItem 1 := by
  unfold gatherTarget at h
  by_cases hb : minGathers owned r fuel rootItem 1 ≤ equipMaxDepth
  · rw [if_pos hb] at h; exact absurd h hne.symm
  · exact Nat.lt_of_not_le hb

/-- SOUNDNESS (root-kept-when-feasible): when the root's gather cost fits the
budget the decision keeps the root target (the caller plans the short craft+equip
chain). -/
theorem gatherTarget_root_when_feasible
    (owned : Nat → Nat) (r : Recipe) (fuel rootItem stepItem stepQty equipMaxDepth : Nat)
    (h : minGathers owned r fuel rootItem 1 ≤ equipMaxDepth) :
    gatherTarget owned r fuel rootItem stepItem stepQty equipMaxDepth = (rootItem, 1) := by
  unfold gatherTarget; simp [h]

/-- SOUNDNESS (never-harder): when the deepest `step` is a RAW leaf with no
holdings, the routed target's gather cost (`stepQty`) is NOT larger than the root
gather cost we declined — routing trades DOWN to a flatter sub-target, never up to
a harder one. Pins that the fix can't pick a worse target than the root.

Hypotheses: the step is the root's transitive base (`stepQty ≤
minGathers(root)`, which holds because the deepest step's quantity is the
expanded raw requirement) and we are in the over-budget branch. -/
theorem gatherTarget_step_not_harder_than_root
    (owned : Nat → Nat) (r : Recipe) (fuel rootItem stepItem stepQty : Nat)
    (hstep : r stepItem = [])
    (hcost : stepQty ≤ minGathers owned r fuel rootItem 1)
    (hfuel : 0 < fuel) :
    minGathers owned r fuel stepItem stepQty ≤ minGathers owned r fuel rootItem 1 := by
  obtain ⟨n, rfl⟩ := Nat.exists_eq_add_of_lt hfuel
  rw [Nat.zero_add] at hcost ⊢
  rw [minGathers_raw owned r stepItem stepQty n hstep]
  exact Nat.le_trans (Nat.sub_le _ _) hcost

end Formal.StepDispatch
