import Formal.Liveness.FightFairnessP
import Formal.Liveness.LifecycleBound7
import Formal.Liveness.LevelFiftyReachable
import Mathlib.Tactic

/-! # LevelFiftyReachableP — Brick 5: level-50 reachability for the refreshed cycle

The capstone of the perception-refresh model extension. `LevelFiftyReachable.
ai_reaches_level_fifty` proves level-50 reachability for the PURE cycle `cycleStep`
from `GlobalInvariants`, whose `hfightFires` field is an ASSUMED runtime fairness
obligation (the planner keeps fighting via a combat objective infinitely often).
Brick 4 (`FightFairnessP`) discharged the refreshed analog `hfightFiresP` from the
scheduling residual `BlockersQuietBelowCapInfinitelyOftenP` ALONE — the combat
persistence is now PROVEN IN-MODEL (Brick 3), not assumed.

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
open Formal.Liveness.FightFairnessP

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

/-! ## The fight position lands on the refreshed state

At a fight position `k`, `hfightFiresP` reports the fight ladder fires on
`perceptionRefresh (cycleStepPN k s)`. Combined with `cycleStepPN_succ_outer` and
the definitional `cycleStepP = cycleStep ∘ perceptionRefresh`, the `(k+1)`-th state
is `applyActionKind .fight (perceptionRefresh (cycleStepPN k s))`. -/

/-- At a fight position, `cycleStepPN (k+1) s` runs `.fight` on the refreshed
state `perceptionRefresh (cycleStepPN k s)`. Composes `cycleStepPN_succ_outer`,
the `cycleStepP` definition, and `cycleStep_eq_fight_when_fightCycleFires` applied
to the refreshed selection state. -/
theorem cycleStepPN_succ_eq_fight_refreshed (s : State) (k : Nat)
    (hfire : productionLadder (perceptionRefresh (cycleStepPN k s)) = some .bankUnlock
        ∨ productionLadder (perceptionRefresh (cycleStepPN k s)) = some .reachUnlockLevel
        ∨ (productionLadder (perceptionRefresh (cycleStepPN k s)) = some .objectiveStep
            ∧ (perceptionRefresh (cycleStepPN k s)).objectiveStepIsFight = true)) :
    cycleStepPN (k+1) s
      = applyActionKind .fight (perceptionRefresh (cycleStepPN k s)) := by
  rw [cycleStepPN_succ_outer k s]
  show cycleStep (perceptionRefresh (cycleStepPN k s))
      = applyActionKind .fight (perceptionRefresh (cycleStepPN k s))
  exact cycleStep_eq_fight_when_fightCycleFires (perceptionRefresh (cycleStepPN k s)) hfire

/-! ## xp accumulation under no-level-advance — the `cycleStepP` engine

Mirrors `LifecycleBound7.xp_accumulates_when_level_constant`. At a fight position
`k₁`, the fight runs on `perceptionRefresh (cycleStepPN k₁ s)`; `perceptionRefresh`
preserves xp and level, so when the level is constant the fight grows `xp` by
exactly `10` on the refreshed state, hence on `cycleStepPN (k₁+1) s`. -/

/-- **xp accumulation under no-level-advance, for `cycleStepP`.** If level is
constant along the refreshed trajectory, then for every `n` some position `k` has
`xp` grown by at least `10*n`. The `cycleStepP` analog of
`LifecycleBound7.xp_accumulates_when_level_constant`, consuming `hfightFiresP`. -/
theorem xp_accumulates_when_level_constant_P
    (s : State)
    (hno : ∀ k, (cycleStepPN k s).level = s.level)
    (hfp : hfightFiresP s)
    (n : Nat) :
    ∃ k, (cycleStepPN k s).xp ≥ s.xp + 10 * n := by
  induction n with
  | zero =>
    refine ⟨0, ?_⟩
    rw [cycleStepPN_zero]; omega
  | succ m ih =>
    obtain ⟨k₀, hk₀⟩ := ih
    -- Get fight position k₁ ≥ k₀ + 1 (on the refreshed selection state).
    obtain ⟨k₁, hk₁ge, hk₁fire⟩ := hfp (k₀ + 1)
    -- xp monotone from k₀ to k₁ via the constant-level refreshed trajectory.
    have hmono_k₀_k₁ : (cycleStepPN k₁ s).xp ≥ (cycleStepPN k₀ s).xp := by
      have hreindex : cycleStepPN k₁ s = cycleStepPN (k₁ - k₀) (cycleStepPN k₀ s) := by
        rw [← cycleStepPN_add k₀ (k₁ - k₀) s]
        congr 1; omega
      rw [hreindex]
      apply cycleStepPN_xp_ge_when_level_eq_throughout
      intro j _hj
      rw [← cycleStepPN_add k₀ j s, hno (k₀ + j), hno k₀]
    -- At k₁, the fight runs on perceptionRefresh (cycleStepPN k₁ s).
    have hk₁succ : cycleStepPN (k₁+1) s
        = applyActionKind .fight (perceptionRefresh (cycleStepPN k₁ s)) :=
      cycleStepPN_succ_eq_fight_refreshed s k₁ hk₁fire
    -- The refreshed selection state shares xp and level with cycleStepPN k₁ s.
    have href_lvl : (perceptionRefresh (cycleStepPN k₁ s)).level = s.level := by
      rw [perceptionRefresh_level]; exact hno k₁
    have hsucc_lvl : (cycleStepPN (k₁+1) s).level = s.level := hno (k₁+1)
    -- The fight did NOT roll over: post-fight level = refreshed-state level.
    have hfight_lvl_eq :
        (applyActionKind .fight (perceptionRefresh (cycleStepPN k₁ s))).level
          = (perceptionRefresh (cycleStepPN k₁ s)).level := by
      rw [hk₁succ] at hsucc_lvl
      rw [hsucc_lvl, href_lvl]
    -- So the fight grew xp by exactly 10 (on the refreshed state).
    have hfight_xp :
        (applyActionKind .fight (perceptionRefresh (cycleStepPN k₁ s))).xp
          = (perceptionRefresh (cycleStepPN k₁ s)).xp + 10 :=
      fight_xp_eq_add_ten_when_level_eq (perceptionRefresh (cycleStepPN k₁ s)) hfight_lvl_eq
    refine ⟨k₁ + 1, ?_⟩
    rw [hk₁succ, hfight_xp, perceptionRefresh_xp]
    omega

/-! ## Level advances once — the by-contradiction re-derivation

Mirrors `LifecycleBound7.lifecycle_progress_from_bounds_proven`'s contradiction
structure, but DIRECTLY for `cycleStepP` (no `cycleStepN'` reduction — that engine
requires the inner step to be `cycleStep`, which `cycleStepP` is not). Assume the
level never advances → it is constant (with `cycleStepPN_level_ge`) → xp
accumulates past `xpToNextLevel s.level` (the engine above) → at the next fight
position the rollover fires (`xp + 10 ≥ threshold ∧ level < 50`), advancing the
level — contradiction. -/

/-- **Level advances once, for `cycleStepP`.** From `level < 50` and
`hfightFiresP`, some finite number of refreshed cycles strictly raises `level`.
The `cycleStepP` analog of `LifecycleBound7.lifecycle_progress_from_bounds_proven`
/ `LevelFiftyReachable.level_advances_once`, re-derived in-place. -/
theorem level_advances_onceP (s : State)
    (hlvl : s.level < 50) (hfp : hfightFiresP s) :
    ∃ k, (cycleStepPN k s).level > s.level := by
  by_contra hno
  push Not at hno
  -- hno : ∀ k, (cycleStepPN k s).level ≤ s.level.  Combine with monotonicity.
  have hlvl_eq : ∀ k, (cycleStepPN k s).level = s.level := by
    intro k
    have hge := cycleStepPN_level_ge s k
    have hle := hno k
    omega
  -- Unbounded xp via the accumulation engine; choose n := xpToNextLevel s.level.
  set M := xpToNextLevel s.level with hM_def
  have hM_pos : M > 0 := xpToNextLevel_pos s.level hlvl
  obtain ⟨k, hk⟩ := xp_accumulates_when_level_constant_P s hlvl_eq hfp M
  have hxp_at_k : (cycleStepPN k s).xp ≥ M := by
    have h1 : 10 * M ≥ M := by omega
    omega
  -- Get a fight position k' ≥ k+1.
  obtain ⟨k', hk'ge, hk'fire⟩ := hfp (k + 1)
  -- xp at k' ≥ xp at k ≥ M (monotone under constant level).
  have hmono_k_k' : (cycleStepPN k' s).xp ≥ (cycleStepPN k s).xp := by
    have hreindex : cycleStepPN k' s = cycleStepPN (k' - k) (cycleStepPN k s) := by
      rw [← cycleStepPN_add k (k' - k) s]
      congr 1; omega
    rw [hreindex]
    apply cycleStepPN_xp_ge_when_level_eq_throughout
    intro j _
    rw [← cycleStepPN_add k j s, hlvl_eq (k + j), hlvl_eq k]
  have hxp_k' : (cycleStepPN k' s).xp ≥ M := by omega
  -- The refreshed selection state at k' shares level/xp with cycleStepPN k' s.
  have hlvl_k' : (cycleStepPN k' s).level = s.level := hlvl_eq k'
  have href_lvl : (perceptionRefresh (cycleStepPN k' s)).level = s.level := by
    rw [perceptionRefresh_level]; exact hlvl_k'
  have href_xp : (perceptionRefresh (cycleStepPN k' s)).xp = (cycleStepPN k' s).xp :=
    perceptionRefresh_xp (cycleStepPN k' s)
  -- The (k'+1)-th state is the fight applied to the refreshed selection state.
  have hk'succ : cycleStepPN (k'+1) s
      = applyActionKind .fight (perceptionRefresh (cycleStepPN k' s)) :=
    cycleStepPN_succ_eq_fight_refreshed s k' hk'fire
  -- The rollover fires on the refreshed state: xp + 10 ≥ M = xpToNextLevel level,
  -- and level < 50.
  have hwill :
      (decide ((perceptionRefresh (cycleStepPN k' s)).xp + 10
                 ≥ xpToNextLevel (perceptionRefresh (cycleStepPN k' s)).level)
       && decide ((perceptionRefresh (cycleStepPN k' s)).level < 50)) = true := by
    rw [href_lvl, href_xp]
    have hxp_thresh : (cycleStepPN k' s).xp + 10 ≥ M := by omega
    have hxp_dec : decide ((cycleStepPN k' s).xp + 10 ≥ M) = true := by simp [hxp_thresh]
    have hlvl_dec : decide (s.level < 50) = true := by simp [hlvl]
    rw [hxp_dec, hlvl_dec]; rfl
  -- Fight applies the rollover branch: level := refreshed-level + 1.
  have hfight_lvl :
      (applyActionKind .fight (perceptionRefresh (cycleStepPN k' s))).level
        = (perceptionRefresh (cycleStepPN k' s)).level + 1 := by
    simp only [applyActionKind]
    rw [if_pos hwill]
  have hk'_succ_lvl : (cycleStepPN (k'+1) s).level = s.level + 1 := by
    rw [hk'succ, hfight_lvl, href_lvl]
  have hcontra : (cycleStepPN (k'+1) s).level ≤ s.level := hno (k'+1)
  rw [hk'_succ_lvl] at hcontra
  omega

/-! ## Global invariants for the refreshed cycle -/

/-- Bundle of liveness hypotheses for the REFRESHED cycle, holding at every state
reachable from `s` via `cycleStepPN`. The `hfightFires` field is replaced by
`hfightFiresP` — which Brick 4 discharges from
`BlockersQuietBelowCapInfinitelyOftenP` alone (combat persistence is in-model, not
assumed). The `hex`/`hbe` non-degeneracy fields are stated over the REFRESHED
selection states `perceptionRefresh (cycleStepPN k s)` — the states the cycle
actually selects on — exactly mirroring `hfightFiresP`. -/
structure GlobalInvariantsP (s : State) : Prop where
  hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) ≠ some .wait
  hex : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) = some .taskExchange →
              (perceptionRefresh (cycleStepPN k s)).taskExchangeMinCoins > 0
  hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) = some .bankExpand →
              (perceptionRefresh (cycleStepPN k s)).nextExpansionCost > 0
  hfightFiresP : hfightFiresP s

/-- If `GlobalInvariantsP` holds at `s`, it holds at `cycleStepPN m s` for any `m`.
Mirrors `LevelFiftyReachable.globalInvariants_step`, using the `cycleStepPN_add`
prefix-shift. The refreshed selection states compose because
`perceptionRefresh (cycleStepPN k (cycleStepPN m s))
   = perceptionRefresh (cycleStepPN (m + k) s)`. -/
theorem globalInvariants_stepP (s : State) (m : Nat)
    (h : GlobalInvariantsP s) :
    GlobalInvariantsP (cycleStepPN m s) := by
  refine ⟨?_, ?_, ?_, ?_⟩
  · intro k
    rw [← cycleStepPN_add m k s]
    exact h.hnowait (m + k)
  · intro k hk
    rw [← cycleStepPN_add m k s] at hk
    rw [← cycleStepPN_add m k s]
    exact h.hex (m + k) hk
  · intro k hk
    rw [← cycleStepPN_add m k s] at hk
    rw [← cycleStepPN_add m k s]
    exact h.hbe (m + k) hk
  · -- hfightFiresP prefix-shift: from h's witnesses at N+m, set k := j - m.
    intro N
    obtain ⟨j, hjN, hjFire⟩ := h.hfightFiresP (N + m)
    refine ⟨j - m, by omega, ?_⟩
    have hreindex : cycleStepPN (j - m) (cycleStepPN m s) = cycleStepPN j s := by
      rw [← cycleStepPN_add m (j - m) s]
      congr 1; omega
    rw [hreindex]
    exact hjFire

/-! ## Level-50 reachability for the refreshed cycle -/

/-- Level strictly advances after some bounded number of refreshed cycles. Wraps
`level_advances_onceP` against `GlobalInvariantsP`. Mirrors
`LevelFiftyReachable.level_advances_once`. -/
theorem level_advances_onceP_inv (s : State)
    (hlvl : s.level < 50) (h : GlobalInvariantsP s) :
    ∃ k, (cycleStepPN k s).level > s.level :=
  level_advances_onceP s hlvl h.hfightFiresP

/-- Structural induction on the gap to 50. Mirrors
`LevelFiftyReachable.ai_reaches_level_fifty_aux`. -/
theorem ai_reaches_level_fiftyP_aux :
    ∀ (gap : Nat) (s : State), 50 - s.level = gap →
      GlobalInvariantsP s → ∃ k, (cycleStepPN k s).level ≥ 50 := by
  intro gap
  induction gap using Nat.strong_induction_on with
  | _ g ih =>
    intro s hgap h
    by_cases hlvl50 : s.level ≥ 50
    · exact ⟨0, by rw [cycleStepPN_zero]; exact hlvl50⟩
    · push Not at hlvl50
      obtain ⟨k₁, hk₁⟩ := level_advances_onceP_inv s hlvl50 h
      set s' := cycleStepPN k₁ s with hsdef
      have hs'_inv : GlobalInvariantsP s' := by
        rw [hsdef]; exact globalInvariants_stepP s k₁ h
      have hs'_gap_lt : 50 - s'.level < g := by
        rw [← hgap]; omega
      obtain ⟨k₂, hk₂⟩ := ih (50 - s'.level) hs'_gap_lt s' rfl hs'_inv
      refine ⟨k₁ + k₂, ?_⟩
      rw [cycleStepPN_add, ← hsdef]
      exact hk₂

/-- **Brick-5 capstone — level-50 reachability for the perception-refreshed cycle.**

From `GlobalInvariantsP s`, the refreshed cycle `cycleStepP` iterates finitely many
times to reach `level ≥ 50`. The structural mirror of
`LevelFiftyReachable.ai_reaches_level_fifty`, re-derived for `cycleStepP`.

**The win made explicit.** `GlobalInvariantsP` replaces `GlobalInvariants`' ASSUMED
`hfightFires` with `hfightFiresP`, which Brick 4
(`FightFairnessP.hfightFiresP_of_blockers_quiet`) discharges from
`BlockersQuietBelowCapInfinitelyOftenP` ALONE — the combat persistence
(`CombatPersistent`/the old `hperc`) is PROVEN IN-MODEL (Brick 3), no longer an
assumption. So this capstone rests on the HONEST Option-A residual set:

* `hnowait` / `hex` / `hbe` (the `GlobalInvariantsP` non-degeneracy fields, stated
  over the refreshed selection states),
* `BlockersQuietBelowCapInfinitelyOftenP` (the sole runtime fairness residual,
  feeding `hfightFiresP` via Brick 4),
* `WinnableAcrossBand` (in `perceptionRefresh`'s arming faithfulness), and
* LIV-001 (the server xp-curve axiom).

It does NOT by itself close `BlockersQuietBelowCapInfinitelyOftenP` — that stays the
documented scheduling/transience residual. -/
theorem ai_reaches_level_fiftyP (s : State) (h : GlobalInvariantsP s) :
    ∃ k, (cycleStepPN k s).level ≥ 50 :=
  ai_reaches_level_fiftyP_aux (50 - s.level) s rfl h

/-- **Brick-5 corollary — capstone fed directly by the scheduling residual.**
Bundles the `hfightFiresP` discharge: given the three non-degeneracy invariants and
the scheduling residual `BlockersQuietBelowCapInfinitelyOftenP` (NOT a combat-
persistence assumption — that is Brick-3 in-model), the refreshed cycle reaches
level 50. This is the cleanest statement of the residual set the capstone rests
on. -/
theorem ai_reaches_level_fiftyP_of_blockers_quiet (s : State)
    (hnowait : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) ≠ some .wait)
    (hex : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) = some .taskExchange →
                (perceptionRefresh (cycleStepPN k s)).taskExchangeMinCoins > 0)
    (hbe : ∀ k, productionLadder (perceptionRefresh (cycleStepPN k s)) = some .bankExpand →
                (perceptionRefresh (cycleStepPN k s)).nextExpansionCost > 0)
    (hq : BlockersQuietBelowCapInfinitelyOftenP s) :
    ∃ k, (cycleStepPN k s).level ≥ 50 :=
  ai_reaches_level_fiftyP s
    ⟨hnowait, hex, hbe, hfightFiresP_of_blockers_quiet s hq⟩

end Formal.Liveness.LevelFiftyReachableP
