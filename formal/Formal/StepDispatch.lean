-- @concept: core, planner @property: totality

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

end Formal.StepDispatch
