-- @concept: combat, monsters @property: reachability, no-deadlock
import Formal.CombatTargetExistence
import Formal.StepDispatch
import Formal.ActionApplicability

/-!
# Formal.LivenessChain

**The capstone: bootstrap combat fires when the grind target exists.**

This module composes G3 (`CombatTargetExistence`), G4
(`ActionApplicability`), and G5 (`StepDispatch`) into a single end-to-end
liveness theorem:

> If the grind target exists — the gear objective names `m*` and its `L*`
> is held — AND the FightAction predicate holds, AND no task overrides the
> target, then the chain
>   grind target → step dispatch → action applicability
> resolves to a fightable FightAction on `m*`.

This is the formal closure of the 2026-06-06 trace surface (a target the
dispatcher or the action layer then refused). Plan C Task 4 restated it
over the two-arm grind target: the windowed picker it used to compose was
deleted, and with it the claim that ANY winnable XP-positive catalogue
monster yields a fight — by design (spec 2026-10-18 §2.4) no fight is
chosen for XP while a piece of `L*` is missing.

Phase G6 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.LivenessChain
open Formal.CombatTargetExistence Formal.StepDispatch Formal.ActionApplicability

/-! ## The composed input bundle. -/

/-- Inputs that, together, are sufficient for the chain to emit a
FightAction. Every condition is locally provable in its own G-module;
this structure is the join point. -/
structure LivenessInputs where
  /-- The gear objective's target monster `m*` (or `none`). -/
  pathTarget  : Option Int
  /-- Whether `L*` is held (the objective's `held`, no fleet piece waiting). -/
  pathHeld    : Bool
  fightInputs : FightInputs
  /-- The bootstrap root's char-level target — the value carried by the
      ReachCharLevel(level) step the strategy engine produces. -/
  bootstrapLevel : Int

/-! ## The chain. -/

/-- The composition: grind target → dispatch → applicability. Returns
`some FightAction` when all three gates pass. -/
def chainEmitsFight (i : LivenessInputs) (hasTask : Bool) (taskTarget : Option Int) : Option Int :=
  -- 1. Grind target: the task's monster, else a held `m*` (or `none`).
  let pickTarget : Option Int :=
    if hasTask then
      taskTarget  -- task forces target
    else
      winnableFarmTarget none i.pathTarget i.pathHeld
  match pickTarget with
  | none => none
  | some monster =>
      -- 2. Dispatch the bootstrap step against the chosen target.
      let ctx : DispatchContext := { combatMonster := some monster, targetReachable := true }
      match stepDispatch ctx (MetaGoal.reachCharLevel i.bootstrapLevel) with
      | some (GoalClass.grindCharacterXP m) =>
          -- 3. Check FightAction applicability for that monster.
          if fightApplicable i.fightInputs then some m else none
      | _ => none

/-! ## Liveness invariant. -/

/-- **The headline theorem**. Given:
* the grind target exists (`m*` named, `L*` held — G3 condition),
* no active task overrides it,
* the FightAction predicate holds (G4 condition),

then the chain emits a FightAction on `m*` — no `none` is possible from any
of the three layers. -/
theorem chain_emits_fight_when_target_exists_and_applicable
    (i : LivenessInputs) (m : Int)
    (hPath : i.pathTarget = some m)
    (hHeld : i.pathHeld = true)
    (hApp  : fightApplicable i.fightInputs = true) :
    chainEmitsFight i false none = some m := by
  unfold chainEmitsFight
  simp only [Bool.false_eq_true, if_false]
  rw [hPath, hHeld, winnableFarmTarget_falls_through_no_task]
  show (match stepDispatch { combatMonster := some m, targetReachable := true } (MetaGoal.reachCharLevel i.bootstrapLevel) with
     | some (GoalClass.grindCharacterXP m) =>
         if fightApplicable i.fightInputs = true then some m else none
     | _ => none) = some m
  rw [dispatch_reach_char_with_target_goes_to_grind]
  simp [hApp]

/-! ## Inverse: when the chain DOES return none, surface which gate. -/

/-- If the chain returns `none` and no task is active, then either there is
no grind target (no `m*`, or its `L*` not held), or the FightAction
predicate fails. The dispatcher cannot be the culprit (G5's safe-fail
guarantee). -/
theorem chain_none_implies_target_or_applicability_blocked
    (i : LivenessInputs)
    (hNone : chainEmitsFight i false none = none) :
    (i.pathTarget = none ∨ i.pathHeld = false) ∨
    fightApplicable i.fightInputs = false := by
  unfold chainEmitsFight at hNone
  simp only [Bool.false_eq_true, if_false] at hNone
  cases hPick : winnableFarmTarget none i.pathTarget i.pathHeld with
  | none =>
    left
    exact winnableFarmTarget_none_no_task i.pathTarget i.pathHeld hPick
  | some monster =>
    right
    rw [hPick] at hNone
    simp only at hNone
    rw [dispatch_reach_char_with_target_goes_to_grind] at hNone
    cases hF : fightApplicable i.fightInputs with
    | false => rfl
    | true => rw [hF] at hNone; simp at hNone

/-- Non-vacuity witness: the headline's hypotheses are jointly satisfiable —
a held `m*` and a concrete applicable fight (the inputs of
`ActionApplicability.winnable_inWindow_imp_fightApplicable_nonvacuous`). -/
theorem chain_emits_fight_nonvacuous :
    chainEmitsFight
      { pathTarget := some 4, pathHeld := true, bootstrapLevel := 7,
        fightInputs := { hasLocations := true, inventoryFree := 1, hp := 100,
                         maxHp := 100, playerLevel := 5, monsterLevel := 5,
                         minFreeSlots := 1, xpPerKill := 10 } }
      false none = some 4 :=
  chain_emits_fight_when_target_exists_and_applicable _ 4 rfl rfl (by decide)

end Formal.LivenessChain
