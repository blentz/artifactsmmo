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

This module is B-0. Foundation laid here:
* `reachUnlockLevel_fires_in_window` — in the under-bankRequiredLevel window the
  fight gate fires (the unconditional disjunct).

Remaining B-0 structure (the bounded measure descent; tracked in
docs/PLAN_select_reach.md):
1. `bootstrap_fightFires_in_window` — `∀ N, ∃ k ≥ N` reachUnlockLevel is SELECTED
   (productionLadder = some .reachUnlockLevel), using `productionLadder_eq_
   reachUnlockLevel` once hp is restored (bounded rest) and bankUnlock retires
   (bounded). This is the windowed `hfightFires` — more tractable than the chore
   fairness because the higher interrupts (hp, bankUnlock) are bounded.
2. `level_advances_in_window` — feed (1) + hnowait/hex/hbe to the proven
   `level_advances_once` engine to get `∃k, level advances` while in the window.
3. `reaches_bankRequiredLevel` — strong induction on `bankRequiredLevel - level`
   (mirror `LevelFiftyReachable.ai_reaches_level_fifty_aux`, gap ≤ 5 bound) using
   (2) → `∃k, (cycleStepN k s).level ≥ s.bankRequiredLevel`. Then
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

end Formal.Liveness.BootstrapReach
