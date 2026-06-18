import Formal.Liveness.ProductionLadder
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Formal.Liveness.BlockerSelection
import Formal.Liveness.BlockerMonotone
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
* `window_step_decreases_measure` — the per-cycle descent: in the window with
  hpCritical/restForCombat quiet, ONE `cycleStep` strictly decreases the measure.
* `cycleStep_fights_in_window` — robust window-fight: the cycle runs `.fight`
  whether bankUnlock or reachUnlockLevel is selected (both dispatch `[.fight]`),
  so bankUnlock need NOT stay quiet — only hpCritical/restForCombat, which
  `.fight` preserves (`fightKind_preserves_*Fires`).
* `reaches_bankRequiredLevel` — **B-0 CAPSTONE.** Well-founded recursion on the
  lex `Measure` (`measureLt_wellFounded`): from the combat-rest interrupts
  initially quiet + the window bounds, `∃k, (cycleStepN k s).level ≥
  bankRequiredLevel`. NO perception/fairness hypothesis — the `hfightFires`
  disjunct is FREE in the bootstrap window. Axioms = {propext, Quot.sound,
  xpToNextLevel (LIV-001)}.

B-0 COMPLETE (2026-06-18). Next (post-B-0, per docs/PLAN_select_reach.md): the
chore-clear + perception become in-model via the MODEL EXTENSION (a
perception-refresh step re-arming `objectiveStepFires` when the planner head is a
Fight) + the O5.4 SELECT-side DIFFERENTIAL. With `reaches_bankRequiredLevel` in
hand, `reachUnlockLevel_quiet_forever` / `bankUnlock_quiet_forever` then retire
idx 2-3 permanently once `level ≥ bankRequiredLevel` and the bank unlocks —
opening the chore window.

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

/-- **The window always fights — robust to bankUnlock re-arming.** In the
under-`bankRequiredLevel` window with only hpCritical and restForCombat quiet,
`cycleStep` runs `.fight` regardless of whether `bankUnlock` (slot 2) or
`reachUnlockLevel` (slot 3) is the selected means — BOTH dispatch `[.fight]`
(`planFor`). This is the persistence-friendly form: a level-up can RE-ARM
bankUnlock (its fire predicate reads `level`), but that only swaps which fight
gate fires, not whether the cycle fights. Only hpCritical/restForCombat must
stay quiet, and `.fight` preserves `hp`/`maxHp` so they do. -/
theorem cycleStep_fights_in_window (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2) :
    cycleStep s = applyActionKind .fight s := by
  by_cases h2 : fires .bankUnlock s = true
  · -- bankUnlock re-armed: it is selected, and it too dispatches `.fight`.
    unfold cycleStep
    rw [productionLadder_eq_bankUnlock s h0 h1 h2]; rfl
  · -- bankUnlock quiet: reachUnlockLevel is selected.
    have h2' : fires .bankUnlock s = false := by
      simp only [Bool.not_eq_true] at h2; exact h2
    exact cycleStep_fights_of_reachUnlockLevel s
      (reachUnlockLevel_selected_in_window s h0 h1 h2' hbr hlt hgap)

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
with hpCritical and restForCombat quiet, a single `cycleStep` strictly decreases
the lex measure. Composes the robust window-fight lemma
(`cycleStep_fights_in_window` — fights whether bankUnlock or reachUnlockLevel is
selected) with the rollover-aware decrease (`fightKind_decreases_measure`). The
`bankRequiredLevel ≤ 50` hypothesis is the honest server fact — bank unlock
happens well below the level cap — that bridges `level < bankRequiredLevel` to
the `level < 50` the decrease needs.

This is the inductive step of the bounded descent that reaches
`bankRequiredLevel`; the remaining work is the well-founded recursion plus the
persistence of the quiet prefix across the trajectory (the `.fight` apply
preserves `hp`/`maxHp`, so hpCritical/restForCombat stay quiet — bankUnlock need
NOT stay quiet, since it too dispatches `.fight`). -/
theorem window_step_decreases_measure (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0) (hlt : s.level < s.bankRequiredLevel)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2)
    (hcap : s.bankRequiredLevel ≤ 50) :
    measureLt (Measure.measure (cycleStep s)) (Measure.measure s) := by
  rw [cycleStep_fights_in_window s h0 h1 hbr hlt hgap]
  exact fightKind_decreases_measure s (by omega)

/-! ## Descent assembly — well-founded recursion to `bankRequiredLevel` -/

/-- `.fight` never lowers `level` (it either rolls over `level+1` or accumulates
xp at fixed `level`). -/
theorem fightKind_level_ge (s : State) : s.level ≤ (applyActionKind .fight s).level := by
  show s.level ≤ (if (decide (s.xp + 10 ≥ xpToNextLevel s.level) && decide (s.level < 50))
                    then s.level + 1 else s.level)
  split <;> omega

/-- `.fight` preserves the hpCritical fire (it reads only `hp`/`maxHp`, which the
ladder's `.fight` apply does not touch). -/
theorem fightKind_preserves_hpCriticalFires (s : State) :
    fires .hpCritical (applyActionKind .fight s) = fires .hpCritical s := rfl

/-- `.fight` preserves the restForCombat fire (it reads `restForCombatReady`/`hp`/
`maxHp`, none of which the ladder's `.fight` apply touches). -/
theorem fightKind_preserves_restForCombatFires (s : State) :
    fires .restForCombat (applyActionKind .fight s) = fires .restForCombat s := rfl

open Formal.Liveness.BlockerMonotone in
/-- **B-0 capstone — the bootstrap window reaches `bankRequiredLevel` in-model.**
Given the combat-rest interrupts initially quiet (hpCritical, restForCombat) and
the window bounds (`bankRequiredLevel` positive, ≤ 50, gap ≤ 5), some finite
number of cycles drives `level` up to `bankRequiredLevel` — with NO perception or
chore-fairness hypothesis. The proof is well-founded recursion on the lex
`Measure` (`measureLt_wellFounded`): each in-window cycle strictly descends the
measure (`window_step_decreases_measure`), the quiet prefix PERSISTS because
`.fight` preserves `hp`/`maxHp`/`restForCombatReady`
(`fightKind_preserves_*Fires`), and `bankRequiredLevel` is invariant
(`bankRequiredLevel_cycleStep`) while the gap only shrinks (`fightKind_level_ge`).
This discharges the `hfightFires` disjunct FOR FREE in the bootstrap window —
the silver lining of the transience-core finding. -/
theorem reaches_bankRequiredLevel (s : State)
    (h0 : fires .hpCritical s = false) (h1 : fires .restForCombat s = false)
    (hbr : s.bankRequiredLevel > 0)
    (hgap : s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2)
    (hcap : s.bankRequiredLevel ≤ 50) :
    ∃ k, (cycleStepN k s).level ≥ s.bankRequiredLevel := by
  let R : State → State → Prop :=
    fun s₁ s₂ => measureLt (Measure.measure s₁) (Measure.measure s₂)
  have hRwf : WellFounded R := InvImage.wf Measure.measure measureLt_wellFounded
  suffices hgen : ∀ t : State,
      fires .hpCritical t = false → fires .restForCombat t = false →
      t.bankRequiredLevel > 0 →
      t.bankRequiredLevel - t.level ≤ MAX_ACHIEVABLE_GAP_LV2 →
      t.bankRequiredLevel ≤ 50 →
      ∃ k, (cycleStepN k t).level ≥ t.bankRequiredLevel by
    exact hgen s h0 h1 hbr hgap hcap
  intro t0
  apply hRwf.induction (C := fun t =>
    fires .hpCritical t = false → fires .restForCombat t = false →
    t.bankRequiredLevel > 0 →
    t.bankRequiredLevel - t.level ≤ MAX_ACHIEVABLE_GAP_LV2 →
    t.bankRequiredLevel ≤ 50 →
    ∃ k, (cycleStepN k t).level ≥ t.bankRequiredLevel) t0
  intro t ih ht0 ht1 htbr htgap htcap
  by_cases hreached : t.level ≥ t.bankRequiredLevel
  · exact ⟨0, hreached⟩
  · replace hreached : t.level < t.bankRequiredLevel := Nat.not_le.mp hreached
    have hfights : cycleStep t = applyActionKind .fight t :=
      cycleStep_fights_in_window t ht0 ht1 htbr hreached htgap
    have hstep : R (cycleStep t) t :=
      window_step_decreases_measure t ht0 ht1 htbr hreached htgap htcap
    have hq0 : fires .hpCritical (cycleStep t) = false := by
      rw [hfights, fightKind_preserves_hpCriticalFires]; exact ht0
    have hq1 : fires .restForCombat (cycleStep t) = false := by
      rw [hfights, fightKind_preserves_restForCombatFires]; exact ht1
    have hbrl : (cycleStep t).bankRequiredLevel = t.bankRequiredLevel :=
      bankRequiredLevel_cycleStep t
    have hlvl_ge : t.level ≤ (cycleStep t).level := by
      rw [hfights]; exact fightKind_level_ge t
    have hbr' : (cycleStep t).bankRequiredLevel > 0 := by rw [hbrl]; exact htbr
    have hcap' : (cycleStep t).bankRequiredLevel ≤ 50 := by rw [hbrl]; exact htcap
    have hgap' :
        (cycleStep t).bankRequiredLevel - (cycleStep t).level ≤ MAX_ACHIEVABLE_GAP_LV2 := by
      rw [hbrl]; omega
    obtain ⟨k, hk⟩ := ih (cycleStep t) hstep hq0 hq1 hbr' hgap' hcap'
    refine ⟨k + 1, ?_⟩
    rw [cycleStepN_succ]
    rw [hbrl] at hk
    exact hk

end Formal.Liveness.BootstrapReach
