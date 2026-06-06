import Formal.CombatTargetExistence
import Formal.StepDispatch
import Formal.ActionApplicability

/-!
# Formal.LivenessChain

**The capstone: bootstrap combat fires when a winnable target exists.**

This module composes the previously-proven G3 (`CombatTargetExistence`),
G4 (`ActionApplicability`), and G5 (`StepDispatch`) modules into a
single end-to-end liveness theorem:

> If the monster catalog contains a monster that is winnable at full HP
> AND that monster satisfies the FightAction level/gear filters AND no
> task overrides the picker, then the chain
>   target picker → step dispatch → action applicability
> resolves to a fightable FightAction.

This is the formal closure of the 2026-06-06 trace surface. The Python
fixes (commits 18576fc, 157b631) eliminated the specific bugs found in
the trace; this theorem makes the chain LIVENESS into a kernel-checked
invariant, so any future regression that re-introduces the bug class
(e.g., a picker that returns None when a winnable target exists, a
dispatcher that routes ReachCharLevel away from GrindCharacterXP) will
fail the gate at build time.

Phase G6 of `docs/PLAN_composition_correctness.md`.
-/

namespace Formal.LivenessChain
open Formal.CombatTargetExistence Formal.StepDispatch Formal.ActionApplicability

/-! ## The composed input bundle. -/

/-- Inputs that, together, are sufficient for the chain to emit a
FightAction. Every condition is locally provable in its own G-module;
this structure is the join point. -/
structure LivenessInputs where
  monsters    : List Monster
  fightInputs : FightInputs
  /-- The opaque winnability oracle (project Python `is_winnable` after
      projecting hp := max_hp). G3 proves the picker existence claim
      against this. -/
  winnable    : WinnableFn
  /-- The bootstrap root's char-level target — the value carried by the
      ReachCharLevel(level) step the strategy engine produces. -/
  bootstrapLevel : Int

/-! ## The chain. -/

/-- The composition: picker → dispatch → applicability. Returns
`some FightAction` when all three gates pass. -/
def chainEmitsFight (i : LivenessInputs) (hasTask : Bool) (taskTarget : Option Int) : Option Int :=
  -- 1. Picker: get a winnable monster (or `none`).
  let pickTarget : Option Int :=
    if hasTask then
      taskTarget  -- task forces target
    else
      winnableFarmTarget none i.winnable i.monsters
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
* a winnable monster exists in the catalog (G3 condition),
* no active task overrides the picker,
* the FightAction predicate holds (G4 condition),

then the chain emits SOME FightAction — no `none` is possible from any
of the three layers.

This is the kernel-checked guarantee that the 2026-06-06 trace failure
mode (bootstrap step plans nothing, falls to PursueTask) cannot recur
inside the modeled abstraction. -/
theorem chain_emits_fight_when_target_exists_and_applicable
    (i : LivenessInputs)
    (hExists  : ∃ m ∈ i.monsters, i.winnable m = true)
    (hApp     : fightApplicable i.fightInputs = true) :
    ∃ monster, chainEmitsFight i false none = some monster := by
  -- Step 1: picker returns some.
  unfold chainEmitsFight
  simp only [Bool.false_eq_true, if_false]
  obtain ⟨code, hPick⟩ :=
    winnableFarmTarget_falls_through_no_task i.winnable i.monsters hExists
  rw [hPick]
  -- Step 2: dispatch is grindCharacterXP code.
  show ∃ monster,
    (match stepDispatch { combatMonster := some code, targetReachable := true } (MetaGoal.reachCharLevel i.bootstrapLevel) with
     | some (GoalClass.grindCharacterXP m) =>
         if fightApplicable i.fightInputs = true then some m else none
     | _ => none) = some monster
  rw [dispatch_reach_char_with_target_goes_to_grind]
  -- Step 3: applicability passes.
  simp [hApp]

/-! ## Inverse: when the chain DOES return none, surface which gate. -/

/-- If the chain returns `none` and no task is active, then either no
winnable target exists, or the FightAction predicate fails. The
dispatcher cannot be the culprit (G5's safe-fail guarantee). -/
theorem chain_none_implies_picker_or_applicability_blocked
    (i : LivenessInputs)
    (hNone : chainEmitsFight i false none = none) :
    (∀ m ∈ i.monsters, i.winnable m = false) ∨
    fightApplicable i.fightInputs = false := by
  unfold chainEmitsFight at hNone
  simp only [Bool.false_eq_true, if_false] at hNone
  cases hPick : winnableFarmTarget none i.winnable i.monsters with
  | none =>
    -- Picker returned none ⇒ no winnable in catalog.
    left
    unfold winnableFarmTarget at hPick
    -- hPick : (pickWinnable winnable monsters).map Monster.code = none
    -- ⇒ pickWinnable winnable monsters = none
    have hPickNone : pickWinnable i.winnable i.monsters = none := by
      cases hPW : pickWinnable i.winnable i.monsters with
      | none => rfl
      | some _ => rw [hPW] at hPick; exact absurd hPick (by simp)
    intro m hm
    have := (pickBest_none_iff_acc_none_and_none_winnable i.winnable i.monsters).mp hPickNone
    exact this m hm
  | some monster =>
    right
    rw [hPick] at hNone
    simp only at hNone
    rw [dispatch_reach_char_with_target_goes_to_grind] at hNone
    cases hF : fightApplicable i.fightInputs with
    | false => rfl
    | true => rw [hF] at hNone; simp at hNone

end Formal.LivenessChain
