import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.Skill
import Mathlib.Tactic

/-! # StateFieldGapSemantics — Item 8

Per-action invariance for the new state fields added in Item 8:
  • skillLevels — per-skill level
  • bankItemsCatalog — bank inventory
  • bankGold — banked gold
  • pendingItemCodes — claimable items
  • npcStock — NPC inventories
  • eventSpawns — active events

All 30 ActionKinds currently preserve these fields (no apply branch
mutates them yet — future sub-items can plug in deposit/.withdraw/
.claimPending/.npcBuy mutations, but for Item 8 the gap closure is
the field addition + invariance for the existing apply table).

NO new axioms.
-/

namespace Formal.Liveness.StateFieldGapSemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness

/-- Every action preserves `skillLevels`. None of the existing apply
    branches mutates the per-skill level map. -/
theorem applyActionKind_skillLevels_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).skillLevels = s.skillLevels := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).skillLevels = s.skillLevels
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).skillLevels = s.skillLevels
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- Every action preserves `bankItemsCatalog`. -/
theorem applyActionKind_bankItemsCatalog_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).bankItemsCatalog = s.bankItemsCatalog := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).bankItemsCatalog = s.bankItemsCatalog
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).bankItemsCatalog = s.bankItemsCatalog
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- Every action preserves `bankGold`. -/
theorem applyActionKind_bankGold_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).bankGold = s.bankGold := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).bankGold = s.bankGold
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).bankGold = s.bankGold
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- Every action preserves `pendingItemCodes`. -/
theorem applyActionKind_pendingItemCodes_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).pendingItemCodes = s.pendingItemCodes := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).pendingItemCodes = s.pendingItemCodes
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).pendingItemCodes = s.pendingItemCodes
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- Every action preserves `npcStock`. -/
theorem applyActionKind_npcStock_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).npcStock = s.npcStock := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).npcStock = s.npcStock
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).npcStock = s.npcStock
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- Every action preserves `eventSpawns`. -/
theorem applyActionKind_eventSpawns_invariant (k : ActionKind) (s : State) :
    (applyActionKind k s).eventSpawns = s.eventSpawns := by
  cases k with
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).eventSpawns = s.eventSpawns
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).eventSpawns = s.eventSpawns
    cases s.moveTarget <;> rfl
  | _ => rfl

end Formal.Liveness.StateFieldGapSemantics
