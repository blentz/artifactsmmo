import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.Skill
import Mathlib.Tactic

/-! # SkillXpSemantics — Item 4e/5

Per-action invariance and mutation lemmas for the new `skillXpDelta`
field added in Item 4e (subsumes Item 5).

  • `skillXp inv s` — total XP delta for skill `s` across the
    `(Skill, Nat)` pair list. Mirrors
    `state.skill_xp_delta.get(skill, 0)`.
  • `applyActionKind_skillXp_invariant_except_gather_craft` — every
    action except `.gather`/`.craft` preserves `skillXpDelta`.
  • Mutation lemmas split on `gatherSkill` / `craftSkill`.

NO new axioms.
-/

namespace Formal.Liveness.SkillXpSemantics

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness

/-- Total XP delta for the given skill across the pair list. -/
def skillXp : List (Skill × Nat) → Skill → Nat
  | [], _ => 0
  | (sk, n) :: rest, query =>
    if sk = query then n + skillXp rest query else skillXp rest query

@[simp] theorem skillXp_nil (sk : Skill) : skillXp [] sk = 0 := rfl

theorem skillXp_cons_match (sk : Skill) (n : Nat)
    (rest : List (Skill × Nat)) :
    skillXp ((sk, n) :: rest) sk = n + skillXp rest sk := by
  show (if sk = sk then n + skillXp rest sk else skillXp rest sk)
       = n + skillXp rest sk
  simp

theorem skillXp_cons_mismatch (sk other : Skill) (n : Nat)
    (rest : List (Skill × Nat)) (h : sk ≠ other) :
    skillXp ((sk, n) :: rest) other = skillXp rest other := by
  show (if sk = other then n + skillXp rest other else skillXp rest other)
       = skillXp rest other
  simp [h]

/-- Every action EXCEPT `.gather`/`.craft` preserves `skillXpDelta`. -/
theorem applyActionKind_skillXp_invariant_except_gather_craft
    (k : ActionKind) (s : State)
    (hne_g : k ≠ .gather) (hne_c : k ≠ .craft) :
    (applyActionKind k s).skillXpDelta = s.skillXpDelta := by
  cases k with
  | gather => exact absurd rfl hne_g
  | craft => exact absurd rfl hne_c
  | move =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).skillXpDelta = s.skillXpDelta
    cases s.moveTarget <;> rfl
  | mapTransition =>
    show (match s.moveTarget with
          | some (tx, ty) => ({s with posX := tx, posY := ty} : State)
          | none => s).skillXpDelta = s.skillXpDelta
    cases s.moveTarget <;> rfl
  | _ => rfl

/-- `.gather` with no gatherSkill preserves the map. -/
theorem gather_skillXp_when_none (s : State) (h : s.gatherSkill = none) :
    (applyActionKind .gather s).skillXpDelta = s.skillXpDelta := by
  show (match s.gatherSkill with
        | some sk => (sk, 1) :: s.skillXpDelta
        | none => s.skillXpDelta) = s.skillXpDelta
  rw [h]

/-- `.gather` with gatherSkill = some sk cons-prepends `(sk, 1)`. -/
theorem gather_skillXp_when_some (s : State) (sk : Skill)
    (h : s.gatherSkill = some sk) :
    (applyActionKind .gather s).skillXpDelta = (sk, 1) :: s.skillXpDelta := by
  show (match s.gatherSkill with
        | some sk' => (sk', 1) :: s.skillXpDelta
        | none => s.skillXpDelta) = (sk, 1) :: s.skillXpDelta
  rw [h]

/-- `.gather` increments `skillXp` for the target skill by exactly 1. -/
theorem gather_skillXp_increments_target (s : State) (sk : Skill)
    (h : s.gatherSkill = some sk) :
    skillXp (applyActionKind .gather s).skillXpDelta sk
    = skillXp s.skillXpDelta sk + 1 := by
  rw [gather_skillXp_when_some s sk h]
  rw [skillXp_cons_match]
  omega

/-- `.craft` with no craftSkill preserves the map. -/
theorem craft_skillXp_when_none (s : State) (h : s.craftSkill = none) :
    (applyActionKind .craft s).skillXpDelta = s.skillXpDelta := by
  show (match s.craftSkill with
        | some sk => (sk, 1) :: s.skillXpDelta
        | none => s.skillXpDelta) = s.skillXpDelta
  rw [h]

/-- `.craft` with craftSkill = some sk cons-prepends `(sk, 1)`. -/
theorem craft_skillXp_when_some (s : State) (sk : Skill)
    (h : s.craftSkill = some sk) :
    (applyActionKind .craft s).skillXpDelta = (sk, 1) :: s.skillXpDelta := by
  show (match s.craftSkill with
        | some sk' => (sk', 1) :: s.skillXpDelta
        | none => s.skillXpDelta) = (sk, 1) :: s.skillXpDelta
  rw [h]

/-- `.craft` increments `skillXp` for the target skill by exactly 1. -/
theorem craft_skillXp_increments_target (s : State) (sk : Skill)
    (h : s.craftSkill = some sk) :
    skillXp (applyActionKind .craft s).skillXpDelta sk
    = skillXp s.skillXpDelta sk + 1 := by
  rw [craft_skillXp_when_some s sk h]
  rw [skillXp_cons_match]
  omega

end Formal.Liveness.SkillXpSemantics
