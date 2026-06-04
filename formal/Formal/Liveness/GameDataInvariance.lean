import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # GameDataInvariance — Item 2b

Proves that the game-data fields `taskExchangeMinCoins` and
`nextExpansionCost` are PRESERVED across every cycleStep transition.
Foundation for `GlobalInvariants`' Category A (hex, hbe) discharge:
the production-side runtime check at the starting state propagates
structurally along the trajectory.

NO new axioms.
-/

namespace Formal.Liveness.GameDataInvariance

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress

/-- Every action preserves `taskExchangeMinCoins`. No ActionKind modifies it. -/
theorem applyActionKind_taskExchangeMinCoins_invariant
    (k : ActionKind) (s : State) :
    (applyActionKind k s).taskExchangeMinCoins = s.taskExchangeMinCoins := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).taskExchangeMinCoins = s.taskExchangeMinCoins
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).taskExchangeMinCoins = s.taskExchangeMinCoins
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- Every action preserves `nextExpansionCost`. -/
theorem applyActionKind_nextExpansionCost_invariant
    (k : ActionKind) (s : State) :
    (applyActionKind k s).nextExpansionCost = s.nextExpansionCost := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).nextExpansionCost = s.nextExpansionCost
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).nextExpansionCost = s.nextExpansionCost
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- `cycleStep` preserves `taskExchangeMinCoins`. -/
theorem cycleStep_taskExchangeMinCoins_invariant (s : State) :
    (cycleStep s).taskExchangeMinCoins = s.taskExchangeMinCoins := by
  unfold cycleStep
  split
  · rfl
  · split
    · rfl
    · rename_i a _ _
      exact applyActionKind_taskExchangeMinCoins_invariant a s

/-- `cycleStep` preserves `nextExpansionCost`. -/
theorem cycleStep_nextExpansionCost_invariant (s : State) :
    (cycleStep s).nextExpansionCost = s.nextExpansionCost := by
  unfold cycleStep
  split
  · rfl
  · split
    · rfl
    · rename_i a _ _
      exact applyActionKind_nextExpansionCost_invariant a s

/-- Iterated cycleStep preserves `taskExchangeMinCoins`. -/
theorem cycleStepN_taskExchangeMinCoins_invariant (s : State) (n : Nat) :
    (cycleStepN n s).taskExchangeMinCoins = s.taskExchangeMinCoins := by
  induction n generalizing s with
  | zero => rw [cycleStepN_zero]
  | succ k ih =>
    rw [cycleStepN_succ]
    have h1 : (cycleStep s).taskExchangeMinCoins = s.taskExchangeMinCoins :=
      cycleStep_taskExchangeMinCoins_invariant s
    rw [ih (cycleStep s)]
    exact h1

/-- Iterated cycleStep preserves `nextExpansionCost`. -/
theorem cycleStepN_nextExpansionCost_invariant (s : State) (n : Nat) :
    (cycleStepN n s).nextExpansionCost = s.nextExpansionCost := by
  induction n generalizing s with
  | zero => rw [cycleStepN_zero]
  | succ k ih =>
    rw [cycleStepN_succ]
    have h1 : (cycleStep s).nextExpansionCost = s.nextExpansionCost :=
      cycleStep_nextExpansionCost_invariant s
    rw [ih (cycleStep s)]
    exact h1

/-! ## Category A propagation: hex and hbe collapse to state-level facts

  Under these invariants, the trajectory-level hex/hbe of GlobalInvariants
  collapse to a single check at `s` plus structural preservation. That is,
  GlobalInvariants's hex AT STATE s (i.e., `s.taskExchangeMinCoins > 0`)
  propagates to every cycleStepN k s.
-/

/-- **Category A hex propagation**: if `s.taskExchangeMinCoins > 0`,
    then `(cycleStepN k s).taskExchangeMinCoins > 0` for every k. -/
theorem hex_propagation (s : State) (h : s.taskExchangeMinCoins > 0)
    (k : Nat) :
    (cycleStepN k s).taskExchangeMinCoins > 0 := by
  rw [cycleStepN_taskExchangeMinCoins_invariant]
  exact h

/-- **Category A hbe propagation**: if `s.nextExpansionCost > 0`,
    then `(cycleStepN k s).nextExpansionCost > 0` for every k. -/
theorem hbe_propagation (s : State) (h : s.nextExpansionCost > 0)
    (k : Nat) :
    (cycleStepN k s).nextExpansionCost > 0 := by
  rw [cycleStepN_nextExpansionCost_invariant]
  exact h

end Formal.Liveness.GameDataInvariance
