import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Mathlib.Tactic

/-! # PositionSemantics — Item 4c

Per-action invariance and mutation lemmas for the position fields
`posX`/`posY` and the `moveTarget` companion added in Item 4c.

  • `applyActionKind_position_invariant_except_move_actions` — every
    action except `.move`/`.mapTransition` preserves `(posX, posY)`.
  • `move_pos_when_none` / `move_pos_when_some` — split on moveTarget.
  • `mapTransition_pos_when_*` — same shape for `.mapTransition`.

NO new axioms.
-/

namespace Formal.Liveness.PositionSemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure

/-- Every action EXCEPT `.move`/`.mapTransition` preserves `posX`. -/
theorem applyActionKind_posX_invariant_except_move_actions
    (k : ActionKind) (s : State)
    (hne_move : k ≠ .move) (hne_mt : k ≠ .mapTransition) :
    (applyActionKind k s).posX = s.posX := by
  cases k with
  | move => exact absurd rfl hne_move
  | mapTransition => exact absurd rfl hne_mt
  | _ => rfl

/-- Every action EXCEPT `.move`/`.mapTransition` preserves `posY`. -/
theorem applyActionKind_posY_invariant_except_move_actions
    (k : ActionKind) (s : State)
    (hne_move : k ≠ .move) (hne_mt : k ≠ .mapTransition) :
    (applyActionKind k s).posY = s.posY := by
  cases k with
  | move => exact absurd rfl hne_move
  | mapTransition => exact absurd rfl hne_mt
  | _ => rfl

/-- `.move` with no moveTarget preserves position. -/
theorem move_pos_when_none (s : State) (h : s.moveTarget = none) :
    (applyActionKind .move s).posX = s.posX
    ∧ (applyActionKind .move s).posY = s.posY := by
  show (match s.moveTarget with
        | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
        | none => s).posX = s.posX
       ∧ (match s.moveTarget with
        | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
        | none => s).posY = s.posY
  rw [h]
  exact ⟨rfl, rfl⟩

/-- `.move` with moveTarget = some (tx, ty) teleports to (tx, ty). -/
theorem move_pos_when_some (s : State) (tx ty : Nat)
    (h : s.moveTarget = some (tx, ty)) :
    (applyActionKind .move s).posX = tx
    ∧ (applyActionKind .move s).posY = ty := by
  show (match s.moveTarget with
        | some (tx', ty') => ({s with posX := tx', posY := ty'} : State)
        | none => s).posX = tx
       ∧ (match s.moveTarget with
        | some (tx', ty') => ({s with posX := tx', posY := ty'} : State)
        | none => s).posY = ty
  rw [h]
  exact ⟨rfl, rfl⟩

/-- `.mapTransition` with no moveTarget preserves position. -/
theorem mapTransition_pos_when_none (s : State) (h : s.moveTarget = none) :
    (applyActionKind .mapTransition s).posX = s.posX
    ∧ (applyActionKind .mapTransition s).posY = s.posY := by
  show (match s.moveTarget with
        | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
        | none => s).posX = s.posX
       ∧ (match s.moveTarget with
        | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
        | none => s).posY = s.posY
  rw [h]
  exact ⟨rfl, rfl⟩

/-- `.mapTransition` with moveTarget = some (tx, ty) teleports to (tx, ty). -/
theorem mapTransition_pos_when_some (s : State) (tx ty : Nat)
    (h : s.moveTarget = some (tx, ty)) :
    (applyActionKind .mapTransition s).posX = tx
    ∧ (applyActionKind .mapTransition s).posY = ty := by
  show (match s.moveTarget with
        | some (tx', ty') => ({s with posX := tx', posY := ty'} : State)
        | none => s).posX = tx
       ∧ (match s.moveTarget with
        | some (tx', ty') => ({s with posX := tx', posY := ty'} : State)
        | none => s).posY = ty
  rw [h]
  exact ⟨rfl, rfl⟩

end Formal.Liveness.PositionSemantics
