/-
  Formal.Liveness.RestProgress

  Phase-19c deliverable. Models `RestAction.is_applicable` and
  `RestAction.apply` from `src/artifactsmmo_cli/ai/actions/rest.py` and
  proves that, on every applicable Rest, the lex measure strictly
  decreases.

  ## Production reference (verified 2026-05-30 against rest.py:15)

  `is_applicable(state, gd)`:
    * `state.hp < state.max_hp`

  `apply(state, gd)`:
    * `hp := state.max_hp`
    * `cooldown_expires := None`  (irrelevant to the measure)

  ## Load-bearing hypotheses on the headline lemma — HONEST disclosure

    * `happ` — `restIsApplicable s = true`, i.e. `s.hp < s.maxHp`. This
       hypothesis is BOTH the applicability guard AND the productivity
       guard: an "applicable" Rest is always productive because
       applicability already requires `hp < maxHp`. No additional
       perception invariant is needed.

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure

namespace Formal.Liveness.RestProgress

open Formal.Liveness.Measure

/-! ## Faithful model of `RestAction.is_applicable` -/

/-- Mirrors `is_applicable` in `rest.py`. -/
def restIsApplicable (s : State) : Bool := decide (s.hp < s.maxHp)

/-! ## Faithful model of `RestAction.apply` -/

/-- Mirrors `apply` in `rest.py`: full heal. -/
def restApply (s : State) : State := { s with hp := s.maxHp }

/-! ## Aux: `restApply` preserves higher-priority slots -/

@[simp] theorem restApply_level (s : State) : (restApply s).level = s.level := rfl
@[simp] theorem restApply_xp (s : State) : (restApply s).xp = s.xp := rfl
@[simp] theorem restApply_taskTotal (s : State) :
    (restApply s).taskTotal = s.taskTotal := rfl
@[simp] theorem restApply_taskProgress (s : State) :
    (restApply s).taskProgress = s.taskProgress := rfl
@[simp] theorem restApply_projectedSkillXpDelta (s : State) :
    (restApply s).projectedSkillXpDelta = s.projectedSkillXpDelta := rfl
@[simp] theorem restApply_targetSkillXp (s : State) :
    (restApply s).targetSkillXp = s.targetSkillXp := rfl
@[simp] theorem restApply_inventoryUsed (s : State) :
    (restApply s).inventoryUsed = s.inventoryUsed := rfl
@[simp] theorem restApply_inventoryMax (s : State) :
    (restApply s).inventoryMax = s.inventoryMax := rfl

/-! ## Headline progress lemma -/

/--
  **Applicable Rest strictly decreases the lex measure.**

  Load-bearing hypothesis (honest disclosure):
    * `happ` — `restIsApplicable s = true`, i.e. `s.hp < s.maxHp`. Both
       applicability and productivity in one.

  Conclusion: `measureLt (measure (restApply s)) (measure s)`.

  Proof route: slots 1-5 unchanged; slot 6 (`hpDeficit`) drops from
  `maxHp - hp > 0` to `0`.
-/
theorem rest_decreases_measure
    (s : State) (happ : restIsApplicable s = true) :
    measureLt (Measure.measure (restApply s)) (Measure.measure s) := by
  have h_hp_lt : s.hp < s.maxHp := by
    unfold restIsApplicable at happ
    exact of_decide_eq_true happ
  have hLevel :
      (Measure.measure (restApply s)).levelDeficit
        = (Measure.measure s).levelDeficit := by
    unfold Measure.measure; rfl
  have hXp :
      (Measure.measure (restApply s)).xpDeficit
        = (Measure.measure s).xpDeficit := by
    unfold Measure.measure; rfl
  have hTask :
      (Measure.measure (restApply s)).taskCycles
        = (Measure.measure s).taskCycles := by
    unfold Measure.measure; rfl
  have hSkill :
      (Measure.measure (restApply s)).skillXpDeficitProjected
        = (Measure.measure s).skillXpDeficitProjected := by
    unfold Measure.measure; rfl
  have hBank :
      (Measure.measure (restApply s)).bankPressure
        = (Measure.measure s).bankPressure := by
    unfold Measure.measure; rfl
  have hHp :
      (Measure.measure (restApply s)).hpDeficit
        < (Measure.measure s).hpDeficit := by
    show s.maxHp - s.maxHp < s.maxHp - s.hp
    omega
  exact measureLt_of_hpDeficit_dec hLevel hXp hTask hSkill hBank hHp

end Formal.Liveness.RestProgress
