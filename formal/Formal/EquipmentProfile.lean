-- @concept: equipment-profile @property: safety, validity, totality
/- Formal/EquipmentProfile.lean
   Mirrors src/artifactsmmo_cli/ai/tiers/equipment_profile.py's selector
   (spec docs/superpowers/specs/2026-07-08-equipment-profiles-design.md §2).
   Bound to the Python selector by the EQUIPMENT_PROFILE_MUTATIONS group
   (formal/diff/mutate.py). -/
namespace Formal.EquipmentProfile

inductive RootCategory | charLevel | gear
deriving DecidableEq, Repr

inductive ProfileKind | combat | utility
deriving DecidableEq, Repr

/-- Utility axis retired in epic P3: skill-level roots — the only former
utility-axis pursuit — grind planner-natively via the LevelSkill action, so no
strategy root is utility-axis anymore. `is_utility_objective` is a constant
`false`. -/
def isUtilityObjective : RootCategory → Bool
  | .charLevel => false
  | .gear => false

/-- `profile_for` is a constant COMBAT for every root and adequacy (utility axis
retired in P3b — an item's own combat/utility nature is decided by the scorer,
not this selector). Pure/total. -/
def profileFor (_cat : RootCategory) (_bandAdequate : Bool) : ProfileKind :=
  .combat

/-- PLAN-GATE INVARIANT: combat-inadequate ⇒ COMBAT, for every root category.
Now a corollary of the constant selector, retained as the combat floor the whole
design rests on. -/
theorem planGate_forces_combat (cat : RootCategory) :
    profileFor cat false = .combat := rfl

/-- The selector NEVER chooses UTILITY: every root is COMBAT-axis (the retired
utility axis). -/
theorem never_utility (cat : RootCategory) (adequate : Bool) :
    profileFor cat adequate ≠ .utility := by
  show ProfileKind.combat ≠ ProfileKind.utility
  decide

/-- `is_utility_objective` is a constant `false` — no root is utility-axis. -/
theorem isUtilityObjective_false (cat : RootCategory) :
    isUtilityObjective cat = false := by
  cases cat <;> rfl

/-- The constant selector pins every one of the 4 remaining cases explicitly so
a future edit that broke the constant COMBAT selector fails the build. -/
example :
    profileFor .charLevel true = .combat ∧
    profileFor .gear true = .combat ∧
    profileFor .charLevel false = .combat ∧
    profileFor .gear false = .combat := by
  decide

end Formal.EquipmentProfile
