import Formal.Liveness.CycleStepF
import Formal.Liveness.MeasureDescent
import Formal.Liveness.BootstrapReach

/-! # LevelingDescent — the NON-VACUOUS faithful reach-50 (discharging the vacuity).

The removed i.o.-fairness capstones were vacuous (`docs/REVIEW_levelfifty_vacuity.md`; their `level < 50`-i.o.
residual contradicts monotone level + the goal). `MeasureDescent` gave the honest
engine: reach 50 from a per-cycle lex-measure DESCENT. This module discharges that
engine's hypothesis for the LEVELING means.

`cycleStepF_fight_descends`: when the faithful cycle FIGHTS at a below-cap state, it
strictly decreases the measure. A fight either rolls the level over (`levelDeficit` ↓,
pos 1) or accumulates xp (`xpDeficit` ↓, pos 2) — components that depend ONLY on
`level`/`xp`, which `pressureDelta` PRESERVES (so the fill the faithful cycle adds to
the bag, raising `bankPressure` at pos 5, is lex-DOMINATED). Re-proves the
rollover/accumulate split of `BootstrapReach.fightKind_decreases_measure` directly for
`cycleStepF` via the Brick-3a level/xp bridges.

`cycleStepF_reaches_fifty_of_fights`: from `FightsBelowCap` — "every below-50 faithful
cycle fights" — the faithful cycle reaches level 50, via the `MeasureDescent` engine.

## Why this is NON-VACUOUS (unlike the removed i.o.-fairness residual)

`FightsBelowCap` is a per-step LOCAL condition (at each below-50 step the cycle fights),
NOT an `∀N ∃k≥N … ∧ level<50` i.o. property. It is satisfiable JOINTLY with the goal
(`fights_below_cap_satisfiable_with_goal` exhibits a witness) and is non-circular
(fighting each step → the measure descends → 50 is reached; it does NOT assume 50). Its
FAILURE is exactly a cycle that does NOT fight — a chore / claim / gear-review / task
-management step. Those are the `step_decreases_measure`-out-of-scope means
(`ProgressAction`); bounding their fuel so they too descend a (richer) measure is the
remaining O5-termination work. This capstone is the honest, non-vacuous backbone that
remainder slots into.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness ns. -/

namespace Formal.Liveness.LevelingDescent

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.CycleStep
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.CycleStepF
open Formal.Liveness.CycleStepFIteration
open Formal.Liveness.BootstrapReach
open Formal.Liveness.MeasureDescent

/-- **A faithful fight cycle strictly descends the measure.** When the ladder selects a
    fight on the refreshed selection state (`bankUnlock` / `reachUnlockLevel` / a combat
    `objectiveStep`) and `level < 50`, `cycleStepF` decreases the lex measure via
    `levelDeficit` (rollover) or `xpDeficit` (accumulate) — the `bankPressure` rise from
    the loot fill is lex-dominated. -/
theorem cycleStepF_fight_descends (s : State) (hlvl : s.level < 50)
    (hfire : productionLadder (perceptionRefresh s) = some .bankUnlock
        ∨ productionLadder (perceptionRefresh s) = some .reachUnlockLevel
        ∨ (productionLadder (perceptionRefresh s) = some .objectiveStep
            ∧ (perceptionRefresh s).objectiveStepIsFight = true)) :
    measureLt (Measure.measure (cycleStepF s)) (Measure.measure s) := by
  -- cycleStepF shares level/xp with `.fight` applied to the refreshed selection state.
  have hcp : cycleStepP s = applyActionKind .fight (perceptionRefresh s) := by
    show cycleStep (perceptionRefresh s) = applyActionKind .fight (perceptionRefresh s)
    exact cycleStep_eq_fight_when_fightCycleFires (perceptionRefresh s) hfire
  have hFl : (cycleStepF s).level = (applyActionKind .fight (perceptionRefresh s)).level := by
    rw [cycleStepF_level, hcp]
  have hFx : (cycleStepF s).xp = (applyActionKind .fight (perceptionRefresh s)).xp := by
    rw [cycleStepF_xp, hcp]
  have hrl : (perceptionRefresh s).level = s.level := perceptionRefresh_level s
  have hrx : (perceptionRefresh s).xp = s.xp := perceptionRefresh_xp s
  -- The rollover Bool on the refreshed state, in terms of s's level/xp.
  by_cases hwill : s.xp + 10 ≥ xpToNextLevel s.level
  · -- Rollover: fight level = refreshed-level + 1 = s.level + 1, so levelDeficit drops.
    have hcond : (decide ((perceptionRefresh s).xp + 10 ≥ xpToNextLevel (perceptionRefresh s).level)
                  && decide ((perceptionRefresh s).level < 50)) = true := by
      rw [hrl, hrx, decide_eq_true_eq.mpr hwill, decide_eq_true_eq.mpr hlvl]; rfl
    have hfl : (applyActionKind .fight (perceptionRefresh s)).level = s.level + 1 := by
      simp only [applyActionKind]; rw [if_pos hcond, hrl]
    refine measureLt_of_levelDeficit_dec ?_
    simp only [Measure.measure, hFl, hfl]
    omega
  · -- Accumulate: level fixed, xp += 10, so xpDeficit drops.
    have hcond : (decide ((perceptionRefresh s).xp + 10 ≥ xpToNextLevel (perceptionRefresh s).level)
                  && decide ((perceptionRefresh s).level < 50)) = false := by
      rw [hrl, hrx]
      simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
      exact Or.inl hwill
    have hfl : (applyActionKind .fight (perceptionRefresh s)).level = s.level := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrl]
    have hfx : (applyActionKind .fight (perceptionRefresh s)).xp = s.xp + 10 := by
      simp only [applyActionKind]; rw [if_neg (by rw [hcond]; exact Bool.false_ne_true), hrx]
    refine measureLt_of_xpDeficit_dec ?_ ?_
    · simp only [Measure.measure, hFl, hfl]
    · simp only [Measure.measure, hFl, hFx, hfl, hfx]
      omega

/-- **`FightsBelowCap`** — the honest, non-vacuous leveling residual: every below-50
    faithful cycle fights (the ladder selects a fight on its refreshed selection state).
    A per-step LOCAL condition (cf. the removed, vacuous i.o.-fairness residual); its failure is a
    non-fighting (chore/claim/gear/task) cycle. -/
def FightsBelowCap (s : State) : Prop :=
  ∀ k, (cycleStepFN k s).level < 50 →
      productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankUnlock
    ∨ productionLadder (perceptionRefresh (cycleStepFN k s)) = some .reachUnlockLevel
    ∨ (productionLadder (perceptionRefresh (cycleStepFN k s)) = some .objectiveStep
        ∧ (perceptionRefresh (cycleStepFN k s)).objectiveStepIsFight = true)

/-- **The non-vacuous faithful capstone.** From `FightsBelowCap`, the faithful cycle
    reaches level 50 — by per-cycle measure descent (`cycleStepF_fight_descends` at each
    below-50 step) fed to the `MeasureDescent` well-founded engine. No i.o. residual, no
    `→ 0`-drain, no vacuity. -/
theorem cycleStepF_reaches_fifty_of_fights (s : State) (h : FightsBelowCap s) :
    ∃ k, (cycleStepFN k s).level ≥ 50 := by
  apply cycleStepF_reaches_fifty_of_descent
  intro k hk
  have hstep := cycleStepF_fight_descends (cycleStepFN k s) hk (h k hk)
  rwa [← cycleStepFN_succ_outer k s] at hstep

/-- **Non-vacuity check.** `FightsBelowCap` is jointly satisfiable WITH the goal — the
    degenerate `≥ 50` witness (the residual holds vacuously, the goal at `k = 0`).
    Distinguishes this formulation from the vacuous i.o. one
    (kernel-proved in `docs/REVIEW_levelfifty_vacuity.md`), whose residual provably never
    coexists with the goal. -/
theorem fights_below_cap_satisfiable_with_goal (s : State) (h : s.level ≥ 50) :
    FightsBelowCap s ∧ ∃ k, (cycleStepFN k s).level ≥ 50 := by
  refine ⟨fun k hk => absurd hk (by have := cycleStepFN_level_ge s k; omega), 0, ?_⟩
  rw [cycleStepFN_zero]; exact h

end Formal.Liveness.LevelingDescent
