/-
  Formal.Liveness.FightProgress

  Phase-19b deliverable #2 (see `docs/PLAN_liveness.md`, Phase 19 / Tier 1).

  This module models `FightAction.is_applicable` and `FightAction.apply`
  from `src/artifactsmmo_cli/ai/actions/combat.py` and proves that, on
  every applicable Fight, the lex measure strictly decreases.

  ## Production reference (verified 2026-05-30 against combat.py:35)

  `is_applicable(state, gd)`:
    * `state.inventory_free >= 1`
    * `state.hp_percent > 0.3`
    * `max(1, state.level - 1) <= monster_level <= state.level + 2`
    * `LOCATIONS` non-empty (omitted here — we assume a target exists)

  The `best_eq.level >= monster_level - 1` gear pre-filter was REMOVED
  2026-06-29 in lockstep with Python (commits 0cd5407b, 5de3ce42).

  `apply(state, gd)`:
    * `xp += 10`                                  (fixed planner projection)
    * `hp := max 1 (hp - max_hp / 5)`             (heuristic damage)
    * `task_progress += 1` if `task_type == "monsters" && task_code == monster_code`
    * `cooldown_expires := None`                  (irrelevant to the measure)
    * `(x, y) := nearest target location`         (irrelevant to the measure)

  Note `apply` does NOT increment `level`; level-up is purely server-side
  and only enters the planner via perception (out of Phase 19b's scope).

  ## Load-bearing hypotheses on the headline lemma — HONEST disclosure

  The lemma `fight_decreases_measure` carries one non-trivial hypothesis
  beyond `fightIsApplicable`:

    `inv : s.xp < xpToNextLevel s.level`

  This is the **perception invariant**: the planner's projected state is
  in sync with the server, so xp has not yet crossed the level boundary.
  If `xp >= xpToNextLevel level`, the server has already responded with a
  level-up that the perception layer is responsible for integrating; the
  projector's `apply` (which only does `xp += 10`) cannot bridge that gap.

  The perception invariant itself is NOT proved here — it is the
  responsibility of Phase 22's cycle model. We disclose it as a load-bearing
  hypothesis on this lemma, per `feedback_proofs_tell_false_stories`.

  Liveness namespace — Mathlib axioms allowed.
-/
import Formal.Liveness.Measure

namespace Formal.Liveness.FightProgress

open Formal.Liveness.Measure
open Formal.Liveness.Measure.State (inventoryFree hpAboveMinFightFraction)

/-! ## Faithful model of `FightAction.is_applicable` -/

/-- Mirrors `is_applicable` in `combat.py`. `monsterLevel` is passed in
    (it corresponds to `gd.monster_level(...)`). We do not model `locations`
    being non-empty — callers must establish that.

    The gear pre-filter (`best_eq.level >= monster_level - 1`) was REMOVED
    2026-06-29 in lockstep with Python `FightAction.is_applicable` (commits
    0cd5407b, 5de3ce42): it starved combat when no owned gear met the
    window. Dropping a conjunct strictly WEAKENS the guard, so every
    downstream lemma needs one fewer hypothesis. -/
def fightIsApplicable
    (s : State) (monsterLevel : Nat) : Bool :=
  -- inventory_free >= 1
  s.inventoryFree ≥ 1
  -- hp_percent > 0.3
  && s.hpAboveMinFightFraction
  -- max(1, level - 1) <= monsterLevel
  && max 1 (s.level - 1) ≤ monsterLevel
  -- monsterLevel <= level + 2
  && monsterLevel ≤ s.level + 2

/-! ## Faithful model of `FightAction.apply`

    Position and `cooldown_expires` are omitted — the minimal `State` does
    not track them and they do not enter the measure. -/

/-- Mirrors `apply` in `combat.py`. `monsterMatchesTask` corresponds to
    `state.task_type == "monsters" and state.task_code == self.monster_code`.

    `xp += 10` matches `combat.py`'s fixed planner-side projection (NOT the
    server's actual xp grant — that comes through perception). -/
def fightApply (s : State) (monsterMatchesTask : Bool) : State :=
  { s with
      xp           := s.xp + 10
      hp           := max 1 (s.hp - s.maxHp / 5)
      taskProgress :=
        if monsterMatchesTask then s.taskProgress + 1 else s.taskProgress }

/-! ## Aux: `fightApply` preserves `level` -/

@[simp] theorem fightApply_level (s : State) (b : Bool) :
    (fightApply s b).level = s.level := rfl

/-! ## Headline progress lemma -/

-- The headline lemma carries `happ` and `hlvl` as load-bearing hypotheses
-- (disclosed in the docstring) even though the proof body uses only `inv`
-- arithmetically. They are part of the lemma's *intended* surface — Phase
-- 19c's headline `step_decreases_or_levels` over `ProgressAction` will
-- pattern-match on `fightIsApplicable` and discharge it.
set_option linter.unusedVariables false

/--
  **Fight strictly decreases the lex measure.**

  Load-bearing hypotheses (honest disclosure):
    * `happ`  — `fightIsApplicable s ml be = true`. Required because we
       have not modelled `LOCATIONS`; without applicability the action
       wouldn't be issued. We do not use `happ` in the arithmetic — it is
       carried for caller convenience and parity with the Python guard.
    * `hlvl`  — `s.level < 50`. Needed to invoke `xpToNextLevel_pos`.
    * `inv`   — `s.xp < xpToNextLevel s.level`. The **perception invariant**
       (see module docstring). Without this, `xp + 10 > xpToNextLevel level`
       is possible and the projector's apply (which does not increment
       `level`) would not strictly decrease `xpDeficit`.

  Conclusion: `measureLt (measure (fightApply s b)) (measure s)`.

  The proof goes through the `xpDeficit` component, with `levelDeficit`
  unchanged (since `fightApply` does not touch `level`).
-/
theorem fight_decreases_measure
    (s : State) (ml : Nat) (b : Bool)
    (happ : fightIsApplicable s ml = true)
    (hlvl : s.level < 50)
    (inv  : s.xp < xpToNextLevel s.level) :
    measureLt (Measure.measure (fightApply s b)) (Measure.measure s) := by
  -- happ is carried for clients; not used arithmetically here.
  -- The level components match because fightApply does not touch level.
  have hLevelEq :
      (Measure.measure (fightApply s b)).levelDeficit
        = (Measure.measure s).levelDeficit := by
    unfold Measure.measure fightApply; rfl
  -- xpDeficit strictly decreases: `(xpToNext - (xp + 10)) < (xpToNext - xp)`
  -- holds whenever `xp < xpToNext` and `0 < 10`. Nat subtraction saturates
  -- when xp + 10 > xpToNext, but even then the LHS = 0 < RHS since
  -- `inv : xp < xpToNext` means RHS ≥ 1.
  have hXp : (Measure.measure (fightApply s b)).xpDeficit
              < (Measure.measure s).xpDeficit := by
    show xpToNextLevel s.level - (s.xp + 10) < xpToNextLevel s.level - s.xp
    omega
  exact measureLt_of_xpDeficit_dec hLevelEq hXp

end Formal.Liveness.FightProgress
