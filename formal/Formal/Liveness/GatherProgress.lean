/-
  Formal.Liveness.GatherProgress

  Phase-19c deliverable. Models `GatherAction.is_applicable` and
  `GatherAction.apply` from `src/artifactsmmo_cli/ai/actions/gathering.py`
  and proves that, on every productive Gather (one with a skill
  requirement, where the active LevelSkillGoal's target xp strictly
  exceeds the projected skill xp delta), the lex measure strictly
  decreases.

  ## Production reference (verified 2026-05-30 against gathering.py:40)

  `is_applicable(state, gd)`:
    * `self.locations` non-empty  (omitted here — caller establishes)
    * `gather_is_applicable_pure(inv, _MIN_FREE_SLOTS=3)`
    * if `skill_req = (skill, level)` is present:
        `state.skills.get(skill, 1) >= level`

  `apply(state, gd)`:
    * inventory[drop_item] += 1                  (inventoryUsed += 1)
    * if `skill_req` present:
        projected_skill_xp_delta[skill_name] += 1
    * (x, y), cooldown_expires updated — irrelevant to the measure

  Note `apply` does NOT increment `task_progress`. See the production
  comment at `gathering.py:59`: only `TaskTradeAction` advances task
  progress, because the server only counts items when DELIVERED to the
  taskmaster. Modelling Gather as +taskProgress is the bug that motivated
  splitting `projected_skill_xp_delta` from the server-snapshot baseline.

  ## Load-bearing hypotheses on the headline lemma — HONEST disclosure

    * `happ`  — `gatherIsApplicable s skillReq minFree = true`. Carried
       for caller parity; the proof body uses the measure-arithmetic
       hypotheses directly.
    * `hprog` — `s.targetSkillXp > s.projectedSkillXpDelta`. The gather is
       PRODUCTIVE: the active LevelSkillGoal still has room to advance.
       Without this, `targetSkillXp - (delta + 1)` and `targetSkillXp -
       delta` are both zero (Nat saturation) and the measure does not
       decrease.
    * `hskill` — `skill.isSome`. When no skill requirement exists (e.g.
       the tutorial resource at L1), Gather only grows inventory and the
       measure does NOT decrease. Such resources are out of scope for the
       Tier-1 progress proof — they are still safe (handled by other
       guards) but they don't witness liveness.

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure

namespace Formal.Liveness.GatherProgress

open Formal.Liveness.Measure
open Formal.Liveness.Measure.State (inventoryFree)

/-! ## Faithful model of `GatherAction.is_applicable` -/

/-- Mirrors `is_applicable` in `gathering.py`. `skillReq` is the
    `Option (String × Nat)` returned by `game_data.resource_skill_level`;
    `minFree` is `_MIN_FREE_SLOTS = 3`. When `skillReq.isSome`, we model
    the skill-level prerequisite as already satisfied at the call site
    (the caller passes a state whose `level` covers the requirement) —
    we don't track per-skill levels in the minimal Tier-1 `State`. -/
def gatherIsApplicable
    (s : State) (_skillReq : Option (String × Nat)) (minFree : Nat) : Bool :=
  decide (s.inventoryFree ≥ minFree)

/-! ## Faithful model of `GatherAction.apply` -/

/-- Mirrors `apply` in `gathering.py`. `_drop` is the dropped item code
    (we don't track per-item inventory in the minimal `State`, just the
    used-count). `skill` is the optional skill name. -/
def gatherApply (s : State) (_drop : String) (skill : Option String) : State :=
  { s with
      inventoryUsed         := s.inventoryUsed + 1
      projectedSkillXpDelta :=
        match skill with
        | none   => s.projectedSkillXpDelta
        | some _ => s.projectedSkillXpDelta + 1 }

/-! ## Aux: `gatherApply` preserves higher-priority slots -/

@[simp] theorem gatherApply_level (s : State) (d : String) (sk : Option String) :
    (gatherApply s d sk).level = s.level := by
  cases sk <;> rfl

@[simp] theorem gatherApply_xp (s : State) (d : String) (sk : Option String) :
    (gatherApply s d sk).xp = s.xp := by
  cases sk <;> rfl

@[simp] theorem gatherApply_taskTotal (s : State) (d : String) (sk : Option String) :
    (gatherApply s d sk).taskTotal = s.taskTotal := by
  cases sk <;> rfl

@[simp] theorem gatherApply_taskProgress (s : State) (d : String) (sk : Option String) :
    (gatherApply s d sk).taskProgress = s.taskProgress := by
  cases sk <;> rfl

@[simp] theorem gatherApply_targetSkillXp (s : State) (d : String) (sk : Option String) :
    (gatherApply s d sk).targetSkillXp = s.targetSkillXp := by
  cases sk <;> rfl

/-! ## Headline progress lemma -/

set_option linter.unusedVariables false

/--
  **Productive Gather strictly decreases the lex measure.**

  Load-bearing hypotheses (honest disclosure — see module docstring):
    * `happ`   — applicability guard, carried for parity.
    * `hprog`  — `s.targetSkillXp > s.projectedSkillXpDelta` — the
       LevelSkillGoal still has room. Without this, slot 4 saturates.
    * `hskill` — `skill.isSome`. Skill-less resources don't witness
       progress (out of scope).

  Conclusion: `measureLt (measure (gatherApply s d skill)) (measure s)`.

  Proof route: slots 1-3 (`levelDeficit`, `xpDeficit`, `taskCycles`)
  unchanged; slot 4 (`skillXpDeficitProjected`) strictly decreases.
-/
theorem gather_decreases_measure
    (s : State) (skillReq : Option (String × Nat)) (minFree : Nat)
    (drop : String) (skill : Option String)
    (happ   : gatherIsApplicable s skillReq minFree = true)
    (hprog  : s.targetSkillXp > s.projectedSkillXpDelta)
    (hskill : skill.isSome) :
    measureLt (Measure.measure (gatherApply s drop skill))
              (Measure.measure s) := by
  -- Extract concrete skill name.
  cases skill with
  | none      => simp [Option.isSome] at hskill
  | some name =>
    -- Slots 1-3 unchanged because gatherApply only touches inventoryUsed
    -- and projectedSkillXpDelta.
    have hLevel :
        (Measure.measure (gatherApply s drop (some name))).levelDeficit
          = (Measure.measure s).levelDeficit := by
      unfold Measure.measure; rfl
    have hXp :
        (Measure.measure (gatherApply s drop (some name))).xpDeficit
          = (Measure.measure s).xpDeficit := by
      unfold Measure.measure; rfl
    have hTask :
        (Measure.measure (gatherApply s drop (some name))).taskCycles
          = (Measure.measure s).taskCycles := by
      unfold Measure.measure; rfl
    -- Slot 4: skillXpDeficitProjected = targetSkillXp - (delta + 1) <
    --                                   targetSkillXp - delta
    have hSkill :
        (Measure.measure (gatherApply s drop (some name))).skillXpDeficitProjected
          < (Measure.measure s).skillXpDeficitProjected := by
      show s.targetSkillXp - (s.projectedSkillXpDelta + 1)
            < s.targetSkillXp - s.projectedSkillXpDelta
      omega
    exact measureLt_of_skillXpDeficit_dec hLevel hXp hTask hSkill

end Formal.Liveness.GatherProgress
