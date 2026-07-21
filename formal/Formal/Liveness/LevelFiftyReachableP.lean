import Formal.Liveness.LifecycleBound7
import Formal.Liveness.PerceptionRefresh
import Formal.Liveness.CycleStepP
import Mathlib.Tactic

/-! # LevelFiftyReachableP — Brick 5: level-50 reachability for the refreshed cycle

HISTORICAL CONTEXT (the modules named here are gone). This was the capstone of the
perception-refresh model extension, built on `LevelFiftyReachable.
ai_reaches_level_fifty` — level-50 reachability for the PURE cycle `cycleStep` from
`GlobalInvariants`, whose `hfightFires` field was an ASSUMED runtime fairness
obligation. Brick 4 (`FightFairnessP`) discharged the refreshed analog `hfightFiresP`
from `BlockersQuietBelowCapInfinitelyOftenP` alone.

`FightFairnessP` was deleted 2026-06-19 with the vacuous tower; `LevelFiftyReachable`
was retired 2026-07-20 with the superseded cycleStepN cluster. **This module survives
ONLY for its iteration/monotonicity helpers** (`cycleStepPN_add`, `cycleStepP_level_ge`,
and friends), which `CycleStepFIteration` — and thus the live F/D/E descent towers —
still consume. Its own capstone is long gone. Current result:
`GearedDescent.ai_reaches_fifty_geared`.

This module re-derives the level-advance engine and the level-50 capstone for the
REFRESHED cycle `cycleStepP = cycleStep ∘ perceptionRefresh`, consuming
`hfightFiresP`. The result, `ai_reaches_level_fiftyP`, rests on the HONEST
Option-A residual set:

* **`hnowait` / `hex` / `hbe` analogs** — the no-`.wait` + config-non-degeneracy
  invariants, restated over `cycleStepPN`/the refreshed selection states.
* **`hfightFiresP`** — which Brick 4 reduces to
  `BlockersQuietBelowCapInfinitelyOftenP` alone (CombatPersistent in-model).
* **`WinnableAcrossBand`** — baked into `perceptionRefresh`'s arming faithfulness.
* **LIV-001** — the server xp-curve axiom.

## Why the existing engine is NOT reusable (the corrected finding)

`LifecycleBound7.lifecycle_progress_from_bounds_proven` reduces its abstract
`cycleStepN'` to the CONCRETE `cycleStepN` via `hpoint`, which requires
`hsucc : cycleStepN' (n+1) s' = cycleStepN' n (cycleStep s')` — the INNER step must
be `cycleStep`. `cycleStepPN`'s inner step is `cycleStepP = cycleStep ∘
perceptionRefresh ≠ cycleStep`, so `cycleStepPN` is NOT pointwise-equal to
`cycleStepN` and CANNOT instantiate the engine. The level-advance argument is
therefore RE-DERIVED here for `cycleStepP`, reusing the state-generic helpers
(`cycleStep_eq_fight_when_fightCycleFires`, `fight_xp_eq_add_ten_when_level_eq`)
applied to the refreshed states `perceptionRefresh (cycleStepPN k s)`, and proving
fresh `cycleStepP` analogs of the iteration helpers (`cycleStepPN_add`,
`cycleStepPN_succ_outer`, the throughout-xp-monotonicity, level monotonicity).

No new axioms beyond the LevelFiftyReachable set. Liveness namespace — Mathlib
allowed.
-/

namespace Formal.Liveness.LevelFiftyReachableP

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.PlanAction
open Formal.Liveness.Plan
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.ApplyXpLevelPreservation
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.XpMonotonicity
open Formal.Liveness.LifecycleBound6
open Formal.Liveness.LifecycleBound7
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP

/-! ## Iteration helpers for `cycleStepPN` (the `cycleStepN_add`/`_succ_outer`
analogs). These mirror `CumulativeProgress.cycleStepN_add` /
`XpMonotonicity.cycleStepN_succ_outer` verbatim, with `cycleStep` replaced by
`cycleStepP`. -/

/-- Composition law for `cycleStepPN`. Mirrors `CumulativeProgress.cycleStepN_add`. -/
theorem cycleStepPN_add (m n : Nat) (s : State) :
    cycleStepPN (m + n) s = cycleStepPN n (cycleStepPN m s) := by
  induction m generalizing s with
  | zero =>
    show cycleStepPN (0 + n) s = cycleStepPN n (cycleStepPN 0 s)
    rw [cycleStepPN_zero, Nat.zero_add]
  | succ j ih =>
    show cycleStepPN ((j + 1) + n) s = cycleStepPN n (cycleStepPN (j + 1) s)
    rw [show (j + 1) + n = (j + n) + 1 from by omega]
    rw [cycleStepPN_succ (j + n) s]
    rw [cycleStepPN_succ j s]
    exact ih (cycleStepP s)

/-- Right-side recurrence: `cycleStepPN (n+1) s = cycleStepP (cycleStepPN n s)`.
Mirrors `XpMonotonicity.cycleStepN_succ_outer`. -/
theorem cycleStepPN_succ_outer (n : Nat) (s : State) :
    cycleStepPN (n+1) s = cycleStepP (cycleStepPN n s) := by
  rw [cycleStepPN_add n 1 s]
  show cycleStepPN 1 (cycleStepPN n s) = cycleStepP (cycleStepPN n s)
  rw [cycleStepPN_succ 0 (cycleStepPN n s), cycleStepPN_zero]

/-! ## `cycleStepP` level monotonicity

`cycleStepP s = cycleStep (perceptionRefresh s)`, the refresh preserves `level`,
and `cycleStep` never lowers it (`cycleStep_level_ge`). So `cycleStepP` never
lowers `level`; iterate. Mirrors `LifecycleBound6.cycleStepN_level_ge`. -/

/-- One `cycleStepP` never lowers `level`. -/
theorem cycleStepP_level_ge (s : State) : (cycleStepP s).level ≥ s.level := by
  unfold cycleStepP
  calc (cycleStep (perceptionRefresh s)).level
      ≥ (perceptionRefresh s).level := cycleStep_level_ge (perceptionRefresh s)
    _ = s.level := perceptionRefresh_level s

/-- Iterated `cycleStepP` preserves the level-non-decreasing invariant. Mirrors
`LifecycleBound6.cycleStepN_level_ge`. -/
theorem cycleStepPN_level_ge (s : State) (n : Nat) :
    (cycleStepPN n s).level ≥ s.level := by
  induction n generalizing s with
  | zero => rw [cycleStepPN_zero]
  | succ k ih =>
    rw [cycleStepPN_succ]
    have h1 : (cycleStepP s).level ≥ s.level := cycleStepP_level_ge s
    have h2 : (cycleStepPN k (cycleStepP s)).level ≥ (cycleStepP s).level :=
      ih (cycleStepP s)
    omega

/-! ## `cycleStepP` xp monotonicity under constant level

`cycleStepP s = cycleStep (perceptionRefresh s)`. The refresh preserves BOTH xp
and level, so an xp-monotone `cycleStep` step on the refreshed state lifts to an
xp-monotone `cycleStepP` step. Mirrors `XpMonotonicity.cycleStep_xp_ge_when_level_
eq` / `cycleStepN_xp_ge_when_level_eq_throughout`. -/

/-- Single-step `cycleStepP` xp monotonicity under constant level. Bridges
`cycleStep_xp_ge_when_level_eq` on `perceptionRefresh s` (the refresh preserves
xp/level, so the level-constancy and xp-bound transfer through it). -/
theorem cycleStepP_xp_ge_when_level_eq (s : State)
    (h : (cycleStepP s).level = s.level) :
    (cycleStepP s).xp ≥ s.xp := by
  unfold cycleStepP at h ⊢
  -- Convert level-constancy to the refreshed state (refresh preserves level).
  have hlvl : (cycleStep (perceptionRefresh s)).level = (perceptionRefresh s).level := by
    rw [h, perceptionRefresh_level]
  have hxp : (cycleStep (perceptionRefresh s)).xp ≥ (perceptionRefresh s).xp :=
    cycleStep_xp_ge_when_level_eq (perceptionRefresh s) hlvl
  rwa [perceptionRefresh_xp] at hxp

/-- Iterated `cycleStepP` xp monotonicity under constant level across the WHOLE
prefix. If `level` is constant at every position from `0` to `n`, then `xp` is
monotone non-decreasing. Mirrors `XpMonotonicity.cycleStepN_xp_ge_when_level_eq_
throughout`. -/
theorem cycleStepPN_xp_ge_when_level_eq_throughout (s : State) (n : Nat)
    (h : ∀ k ≤ n, (cycleStepPN k s).level = s.level) :
    (cycleStepPN n s).xp ≥ s.xp := by
  induction n with
  | zero => rw [cycleStepPN_zero]
  | succ k ih =>
    have hsucc_lvl_orig : (cycleStepPN (k+1) s).level = s.level := h (k+1) (Nat.le_refl _)
    have hk_lvl : (cycleStepPN k s).level = s.level := h k (Nat.le_succ _)
    rw [cycleStepPN_succ_outer k s] at hsucc_lvl_orig
    have hstep_lvl :
        (cycleStepP (cycleStepPN k s)).level = (cycleStepPN k s).level := by
      rw [hsucc_lvl_orig, hk_lvl]
    have hstep_xp :
        (cycleStepP (cycleStepPN k s)).xp ≥ (cycleStepPN k s).xp :=
      cycleStepP_xp_ge_when_level_eq (cycleStepPN k s) hstep_lvl
    have hk_xp := ih (fun j hj => h j (Nat.le_succ_of_le hj))
    rw [cycleStepPN_succ_outer k s]
    omega


/-! ## Vacuous capstone REMOVED (2026-06-19).

This module previously re-derived the `cycleStepP` level-advance engine
(`cycleStepPN_succ_eq_fight_refreshed`, `xp_accumulates_when_level_constant_P`,
`level_advances_onceP`) and the level-50 capstone (`GlobalInvariantsP`,
`ai_reaches_level_fiftyP`). `ResidualVacuity` kernel-proved those rested on an
UNSATISFIABLE residual (`hfightFiresP`/`BlockersQuietBelowCapInfinitelyOftenP` force
`level < 50` infinitely often, contradicting monotone level + the reach-50 goal), so
the capstone was vacuously true. It is removed; the non-vacuous replacement is
`Formal.Liveness.LevelingDescent.cycleStepF_reaches_fifty_of_fights` (reach 50 from a
per-cycle measure DESCENT via `MeasureDescent`). What remains here are the REUSABLE
iteration + monotonicity helpers (`cycleStepPN_add`, `cycleStepP_level_ge`,
`cycleStepP_xp_ge_when_level_eq`, …) that `CycleStepFIteration` consumes. -/

end Formal.Liveness.LevelFiftyReachableP
