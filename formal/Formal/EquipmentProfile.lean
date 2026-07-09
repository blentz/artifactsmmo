-- @concept: equipment-profile @property: safety, validity, totality
/- Formal/EquipmentProfile.lean
   Mirrors src/artifactsmmo_cli/ai/tiers/equipment_profile.py's selector
   (spec docs/superpowers/specs/2026-07-08-equipment-profiles-design.md §2).
   Bound to the Python selector by the EQUIPMENT_PROFILE_MUTATIONS group
   (formal/diff/mutate.py). -/
namespace Formal.EquipmentProfile

inductive RootCategory | charLevel | skills | gear
deriving DecidableEq, Repr

inductive ProfileKind | combat | utility
deriving DecidableEq, Repr

def isUtilityObjective : RootCategory → Bool
  | .skills => true
  | .charLevel => false
  | .gear => false

def profileFor (cat : RootCategory) (bandAdequate : Bool) : ProfileKind :=
  if !bandAdequate then .combat
  else if isUtilityObjective cat then .utility
  else .combat

/-- PLAN-GATE INVARIANT: combat-inadequate ⇒ COMBAT, for every root
category. This is the combat floor the whole design rests on. -/
theorem planGate_forces_combat (cat : RootCategory) :
    profileFor cat false = .combat := by
  cases cat <;> rfl

/-- Utility is chosen ONLY when adequate AND the objective is utility. -/
theorem utility_iff (cat : RootCategory) (adequate : Bool) :
    profileFor cat adequate = .utility ↔
      (adequate = true ∧ isUtilityObjective cat = true) := by
  cases adequate <;> cases cat <;> simp [profileFor, isUtilityObjective]

/-- Totality is structural (profileFor is a total function over the finite
enum product); this example pins every one of the 6 cases explicitly so a
future edit that broke a case fails the build. -/
example :
    profileFor .skills true = .utility ∧
    profileFor .charLevel true = .combat ∧
    profileFor .gear true = .combat ∧
    profileFor .skills false = .combat ∧
    profileFor .charLevel false = .combat ∧
    profileFor .gear false = .combat := by
  decide

end Formal.EquipmentProfile
