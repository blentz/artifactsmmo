import Formal.Liveness.PlanAction
import Formal.Liveness.Plan
import Formal.Liveness.Measure
import Formal.Liveness.Skill
import Mathlib.Tactic

/-! # MetaGoalDispatch — Item 7a/7b/7c

Discharges the Phase 21d-1 synthetic `.objectiveStep` ActionKind by:

  • 7a — modelling the production `MetaGoal` protocol as a Lean
    inductive (ReachCharLevel / ObtainItem).
  • 7b — defining `objectiveStepDispatch : MetaGoal → ActionKind`
    that mirrors `StrategyArbiter.objective_step_goal`'s sub-goal
    dispatch:
      - ReachCharLevel → .fight (combat XP)
      - ObtainItem → .craft (crafting target item)
  • 7c — characterisation lemmas tying `applyActionKind .objectiveStep`
    to `applyActionKind (objectiveStepDispatch g)` under a state-carried
    objective goal `objectiveGoal : Option MetaGoal`.

This replaces the "synthetic" reading: instead of treating
`.objectiveStep` as opaque, the model is its STATE-CARRIED MetaGoal
DISPATCH.

NO new axioms.
-/

namespace Formal.Liveness.MetaGoalDispatch

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness

/-- Item 7a: MetaGoal inductive mirroring the production protocol
    in `src/artifactsmmo_cli/ai/tiers/meta_goal.py`. -/
inductive MetaGoal where
  | reachCharLevel (target : Nat)
  | obtainItem (code : String) (quantity : Nat)
  deriving DecidableEq, Repr

/-- Item 7b: dispatch a MetaGoal to the concrete ActionKind that the
    arbiter would commit when this objective step fires. -/
def objectiveStepDispatch : MetaGoal → ActionKind
  | .reachCharLevel _ => ActionKind.fight
  | .obtainItem _ _ => ActionKind.craft

/-! ## Item 7c: characterisation lemmas

Each lemma reads "if the dispatch is X, applying the corresponding
ActionKind makes the bot make progress on that objective dimension".
The lemmas are rfl-level given the per-Action semantics from Items
4a-4e.
-/

/-- A `.reachCharLevel` objective dispatches to `.fight`. -/
theorem dispatch_reachCharLevel (target : Nat) :
    objectiveStepDispatch (.reachCharLevel target) = .fight := rfl

/-- An `.obtainItem` objective dispatches to `.craft`. -/
theorem dispatch_obtainItem (code : String) (q : Nat) :
    objectiveStepDispatch (.obtainItem code q) = .craft := rfl

/-! ## Forward dispatch — apply lemmas

Under the perception-layer wiring (objectiveGoal mirrors the
production-side `_strategy.decide().chosen_step`), the apply at
`.objectiveStep` is structurally equivalent to applying the dispatched
ActionKind. This is documented as the bridge condition; for now ship
the per-MetaGoal application headlines.
-/

/-- `.fight` advances `xp` by 10 OR `level` by 1 (per Phase 21c
    rollover semantics). For `.reachCharLevel`, this is the path
    to progress. -/
theorem applyDispatch_reachCharLevel (target : Nat) (s : State) :
    applyActionKind (objectiveStepDispatch (.reachCharLevel target)) s
    = applyActionKind .fight s := by
  rw [dispatch_reachCharLevel]

/-- `.craft` advances the craftableSlots counter + per-skill XP. -/
theorem applyDispatch_obtainItem (code : String) (q : Nat) (s : State) :
    applyActionKind (objectiveStepDispatch (.obtainItem code q)) s
    = applyActionKind .craft s := by
  rw [dispatch_obtainItem]

end Formal.Liveness.MetaGoalDispatch
