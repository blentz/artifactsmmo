import Formal.Liveness.ProductionLadder
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Formal.Liveness.BlockerSelection
import Mathlib.Tactic

/-! # BootstrapReach — B-0: reach `bankRequiredLevel` in-model (SELECT-reach)

The transience-core finding (docs/PLAN_select_reach.md): a chore flag set at a
low-level spawn cannot clear until `level ≥ bankRequiredLevel`, because
`reachUnlockLevel` (ladder idx 3, a FIGHT means) fires UNCONDITIONALLY while
`level < bankRequiredLevel` (gap ≤ 5) and preempts every chore blocker. The
silver lining: that same unconditional firing makes the bootstrap window
SELF-DRIVING — `hfightFires` is FREE there (reachUnlockLevel supplies the
disjunct), so reaching `bankRequiredLevel` is provable IN-MODEL, without the
perception/`hperc` assumption.

This module is B-0. Proven here (gate-green, axioms = {propext, Quot.sound,
xpToNextLevel}):
* `reachUnlockLevel_fires_in_window` — in the under-bankRequiredLevel window the
  fight gate fires (the unconditional disjunct).
* `reachUnlockLevel_selected_in_window` — once the three higher slots are quiet,
  the fight gate is the SELECTED means.
* `cycleStep_fights_of_reachUnlockLevel` — selection ⟹ the cycle runs `.fight`.
* `fightKind_decreases_measure` — `applyActionKind .fight` strictly descends the
  lex measure with ONLY `level < 50`. Unlike `FightProgress.fight_decreases_
  measure` (no rollover, needs the perception invariant `xp < xpToNextLevel`),
  the ladder's `.fight` apply MODELS the level-up rollover, so the decrease is
  unconditional below the cap (level rolls over → levelDeficit drops; else xp
  accumulates strictly below threshold → xpDeficit drops). No perception
  hypothesis.
* `window_step_decreases_measure` — the per-cycle descent: in the window with the
  higher slots quiet, ONE `cycleStep` strictly decreases the measure. This is the
  INDUCTIVE STEP of the bounded descent.

Remaining B-0 structure (the descent assembly; tracked in
docs/PLAN_select_reach.md):
1. **Quiet-prefix persistence.** `window_step_decreases_measure` needs the three
   higher slots quiet at each step. `applyActionKind .fight` PRESERVES `hp`/
   `maxHp` (it only writes level/xp/bankAccessible/actionsAttempted), so
   hpCritical/restForCombat stay quiet; bankUnlock only ever retires (sets
   `bankAccessible := true`). Prove a window-invariant `W s` preserved by
   `cycleStep` while `level < bankRequiredLevel`.
2. `reaches_bankRequiredLevel` — well-founded recursion on the measure
   (`measureLt_wellFounded`) using `window_step_decreases_measure` + (1):
   `∃k, (cycleStepN k s).level ≥ s.bankRequiredLevel`. Then
   `reachUnlockLevel_quiet_forever` / `bankUnlock_quiet_forever` retire idx 2-3
   permanently — the fight gate is gone and the chore window opens.

After B-0: the chore-clear + perception become in-model via the MODEL EXTENSION
(a perception-refresh step re-arming `objectiveStepFires` when the planner head
is a Fight) + the O5.4 SELECT-side DIFFERENTIAL (bind Lean productionLadder +
flag values to production's arbiter.select / perceive). See
docs/PLAN_select_reach.md.

Liveness namespace — Mathlib allowed.
-/

namespace Formal.Liveness.BootstrapReach

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PlanAction
open Formal.Liveness.Plan
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.BlockerSelection

/-- In the bootstrap window (`bankRequiredLevel` set, `level` below it, gap ≤ 5)
the fight gate `reachUnlockLevel` fires unconditionally — the in-model source of
the `hfightFires` disjunct that makes reaching `bankRequiredLevel` provable
without the perception hypothesis. -/
theorem reachUnlockLevel_fires_in_window (s : State)
    (hbr : s.bankRequiredLevel > 0)
    (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    fires .reachUnlockLevel s = true := by
  simp only [fires, reachUnlockLevelFires, Bool.and_eq_true, decide_eq_true_eq]
  exact ⟨⟨hbr, hlt⟩, hgap⟩

/-- In the window, once the three higher slots (hpCritical, restForCombat,
bankUnlock) are quiet, the fight gate is the SELECTED means. -/
theorem reachUnlockLevel_selected_in_window (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    productionLadder s = some .reachUnlockLevel :=
  productionLadder_eq_reachUnlockLevel s h0 h1 h2
    (reachUnlockLevel_fires_in_window s hbr hlt hgap)

/-- When the fight gate is selected, the cycle FIGHTS — the bootstrap window's
self-driving step (`cycleStep` runs `.fight`, which advances xp/level). Mirrors
the `reachUnlockLevel` case of `CycleStep.cycleStep_progress_or_waits`. -/
theorem cycleStep_fights_of_reachUnlockLevel (s : State)
    (hsel : productionLadder s = some .reachUnlockLevel) :
    cycleStep s = applyActionKind .fight s := by
  unfold cycleStep; rw [hsel]; rfl

/-! ## The self-driving fight step strictly descends the measure -/

/-- `applyActionKind .fight` strictly decreases the lex measure whenever the
character is below the level cap. Unlike `FightProgress.fight_decreases_measure`
(no rollover, needs the perception invariant `xp < xpToNextLevel`), the ladder's
`.fight` apply MODELS the level-up rollover, so it decreases the measure with
ONLY `level < 50`: either the level rolls over (`levelDeficit` drops) or xp
accumulates strictly below the threshold (`xpDeficit` drops). This is the
windowed descent's per-step decrease — no perception hypothesis required. -/
theorem fightKind_decreases_measure (s : State) (hlvl : s.level < 50) :
    measureLt (Measure.measure (applyActionKind .fight s)) (Measure.measure s) := by
  by_cases hwill : s.xp + 10 ≥ xpToNextLevel s.level
  · -- rollover: levelDeficit strictly decreases (dominates the lex order).
    have hl : (applyActionKind .fight s).level = s.level + 1 := by
      show (if (decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50))
              then s.level + 1 else s.level) = s.level + 1
      rw [if_pos (by rw [decide_eq_true_eq.mpr hwill, decide_eq_true_eq.mpr hlvl]; rfl :
            (decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50)) = true)]
    refine measureLt_of_levelDeficit_dec ?_
    simp only [Measure.measure, hl]
    omega
  · -- accumulate: levelDeficit fixed, xpDeficit strictly decreases.
    have hcond : (decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50)) = false := by
      simp only [Bool.and_eq_false_iff, decide_eq_false_iff_not]
      exact Or.inl hwill
    have hl : (applyActionKind .fight s).level = s.level := by
      show (if (decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50))
              then s.level + 1 else s.level) = s.level
      rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
    have hx : (applyActionKind .fight s).xp = s.xp + 10 := by
      show (if (decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50))
              then 0 else s.xp + 10) = s.xp + 10
      rw [if_neg (by rw [hcond]; exact Bool.false_ne_true)]
    refine measureLt_of_xpDeficit_dec ?_ ?_
    · simp only [Measure.measure, hl]
    · simp only [Measure.measure, hl, hx]
      omega

/-- **The bootstrap window's per-cycle measure descent.** In the under-
`bankRequiredLevel` window (`bankRequiredLevel` set, `level` below it, gap ≤ 5),
with the three higher slots (hpCritical, restForCombat, bankUnlock) quiet, a
single `cycleStep` strictly decreases the lex measure. Composes the selection
lemma (`reachUnlockLevel` is the selected means), the fight dispatch
(`cycleStep = applyActionKind .fight`), and the rollover-aware decrease
(`fightKind_decreases_measure`). The `bankRequiredLevel ≤ 50` hypothesis is the
honest server fact — bank unlock happens well below the level cap — that
bridges `level < bankRequiredLevel` to the `level < 50` the decrease needs.

This is the inductive step of the bounded descent that reaches
`bankRequiredLevel`; the remaining work is the well-founded recursion plus the
persistence of the quiet prefix across the trajectory (the `.fight` apply
preserves `hp`/`maxHp`, so hpCritical/restForCombat stay quiet; bankUnlock only
retires). -/
theorem window_step_decreases_measure (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (h2 : fires .bankUnlock s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2)
    (hcap : s.bankRequiredLevel ≤ 50) :
    measureLt (Measure.measure (cycleStep s)) (Measure.measure s) := by
  rw [cycleStep_fights_of_reachUnlockLevel s
        (reachUnlockLevel_selected_in_window s h0 h1 h2 hbr hlt hgap)]
  exact fightKind_decreases_measure s (by omega)

end Formal.Liveness.BootstrapReach
