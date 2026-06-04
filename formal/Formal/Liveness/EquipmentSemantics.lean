import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Mathlib.Tactic

/-! # EquipmentSemantics — Item 4b

Helper `equipAt` and per-action lemmas for the new equipment composition
field added in Item 4b.

  • `equipAt eq slot` — first item code in `eq` whose slot matches, or
    `none` if absent. Mirrors `state.equipment.get(slot)`.
  • Per-action equipment invariance and mutation lemmas:
    - `.equip` cons-prepends `(slot, code)` per equipTarget.
    - `.unequip` filters out unequipTarget slot.
    - `.optimizeLoadout` composes both.
    - All 24 other ActionKinds preserve `equipment`.

NO new axioms.
-/

namespace Formal.Liveness.EquipmentSemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure

/-- First item code in the equipment list whose slot matches; none
    when the slot has nothing equipped. -/
def equipAt : List (String × String) → String → Option String
  | [], _ => none
  | (slot, code) :: rest, query =>
    if slot = query then some code else equipAt rest query

@[simp] theorem equipAt_nil (slot : String) : equipAt [] slot = none := rfl

theorem equipAt_cons_match (slot code : String)
    (rest : List (String × String)) :
    equipAt ((slot, code) :: rest) slot = some code := by
  show (if slot = slot then some code else equipAt rest slot) = some code
  simp

theorem equipAt_cons_mismatch (slot other code : String)
    (rest : List (String × String)) (h : slot ≠ other) :
    equipAt ((slot, code) :: rest) other = equipAt rest other := by
  show (if slot = other then some code else equipAt rest other) = equipAt rest other
  simp [h]

/-- Every action EXCEPT `.equip`/`.unequip`/`.optimizeLoadout` preserves
    `equipment`. -/
theorem applyActionKind_equipment_invariant_except_equipment_actions
    (k : ActionKind) (s : State)
    (hne_eq : k ≠ .equip)
    (hne_un : k ≠ .unequip)
    (hne_opt : k ≠ .optimizeLoadout) :
    (applyActionKind k s).equipment = s.equipment := by
  cases k with
  | equip => exact absurd rfl hne_eq
  | unequip => exact absurd rfl hne_un
  | optimizeLoadout => exact absurd rfl hne_opt
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).equipment = s.equipment
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).equipment = s.equipment
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- `.equip` with no equipTarget preserves equipment. -/
theorem equip_equipment_when_none (s : State)
    (h : s.equipTarget = none) :
    (applyActionKind .equip s).equipment = s.equipment := by
  show (match s.equipTarget with
        | some (slot, code) => (slot, code) :: s.equipment
        | none => s.equipment) = s.equipment
  rw [h]

/-- `.equip` with equipTarget = some (slot, code) cons-prepends. -/
theorem equip_equipment_when_some (s : State) (slot code : String)
    (h : s.equipTarget = some (slot, code)) :
    (applyActionKind .equip s).equipment = (slot, code) :: s.equipment := by
  show (match s.equipTarget with
        | some (slot', code') => (slot', code') :: s.equipment
        | none => s.equipment) = (slot, code) :: s.equipment
  rw [h]

/-- After `.equip` with target (slot, code), equipAt at that slot is the
    new code. -/
theorem equip_equipAt_target (s : State) (slot code : String)
    (h : s.equipTarget = some (slot, code)) :
    equipAt (applyActionKind .equip s).equipment slot = some code := by
  rw [equip_equipment_when_some s slot code h]
  exact equipAt_cons_match slot code s.equipment

/-- `.unequip` with no unequipTarget preserves equipment. -/
theorem unequip_equipment_when_none (s : State)
    (h : s.unequipTarget = none) :
    (applyActionKind .unequip s).equipment = s.equipment := by
  show (match s.unequipTarget with
        | some slot => s.equipment.filter (fun p => p.1 ≠ slot)
        | none => s.equipment) = s.equipment
  rw [h]

/-- `.unequip` with unequipTarget = some slot filters out that slot. -/
theorem unequip_equipment_when_some (s : State) (slot : String)
    (h : s.unequipTarget = some slot) :
    (applyActionKind .unequip s).equipment
    = s.equipment.filter (fun p => p.1 ≠ slot) := by
  show (match s.unequipTarget with
        | some slot' => s.equipment.filter (fun p => p.1 ≠ slot')
        | none => s.equipment)
       = s.equipment.filter (fun p => p.1 ≠ slot)
  rw [h]

end Formal.Liveness.EquipmentSemantics
