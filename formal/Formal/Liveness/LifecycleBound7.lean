import Formal.Liveness.LIV003Decomposition
import Formal.Liveness.LifecycleBound6
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Formal.Liveness.Measure
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Formal.Liveness.ApplyXpLevelPreservation
import Formal.Liveness.CycleStepCharacterization
import Formal.Liveness.XpMonotonicity
import Mathlib.Tactic

/-! # LifecycleBound7 — Item 1g-B2 contradiction core

Discharges `lifecycle_progress_from_bounds` as a theorem, completing
Item 1g's full structural argument. Uses Classical.choice (allowed
under liveness axiom budget) to extract fight positions from the
hfightFires hypothesis.

Key theorem:
  • `lifecycle_progress_from_bounds_proven` — same signature as the
    axiom in `LIV003Decomposition`, but PROVED.

Strategy:
  1. By contradiction: assume `∀ k, (cycleStepN k s).level = s.level`.
  2. Show via induction: for any n, ∃ k, (cycleStepN k s).xp ≥ s.xp + 10*n.
     Each induction step uses hfightFires to advance to a fresh fight
     position, where .fight grows xp by 10 (XpMonotonicity).
  3. Choose n := xpToNextLevel s.level. Then xp ≥ xpToNextLevel s.level.
  4. By hfightFires, next fight position has xp ≥ threshold. Apply
     .fight: rollover fires (xp + 10 ≥ threshold ∧ level < 50).
     Level advances → contradiction.

NO new axioms beyond LIV-001 + Classical.choice (within liveness allow-list).
-/

namespace Formal.Liveness.LifecycleBound7

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.LifecycleBound6
open Formal.Liveness.ApplyXpLevelPreservation
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.XpMonotonicity
open Formal.Liveness.LIV003Decomposition

/-- **xp accumulation under no-level-advance**.

    If level is constant along the trajectory, then for every `n`,
    there exists some position `k` where xp has grown by at least `10*n`. -/
theorem xp_accumulates_when_level_constant
    (s : State)
    (hno : ∀ k, (cycleStepN k s).level = s.level)
    (hfightFires : ∀ N, ∃ k ≥ N,
        productionLadder (cycleStepN k s) = some .bankUnlock
        ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel)
    (n : Nat) :
    ∃ k, (cycleStepN k s).xp ≥ s.xp + 10 * n := by
  induction n with
  | zero =>
    refine ⟨0, ?_⟩
    rw [cycleStepN_zero]
    omega
  | succ m ih =>
    obtain ⟨k₀, hk₀⟩ := ih
    -- Get fight position k₁ ≥ k₀ + 1.
    obtain ⟨k₁, hk₁ge, hk₁fire⟩ := hfightFires (k₀ + 1)
    -- xp monotone from k₀ to k₁ via constant-level trajectory.
    -- (cycleStepN k₁ s).xp ≥ (cycleStepN k₀ s).xp.
    have hmono_k₀_k₁ : (cycleStepN k₁ s).xp ≥ (cycleStepN k₀ s).xp := by
      -- Decompose: cycleStepN k₁ s = cycleStepN (k₁ - k₀) (cycleStepN k₀ s).
      have hreindex : cycleStepN k₁ s = cycleStepN (k₁ - k₀) (cycleStepN k₀ s) := by
        rw [← cycleStepN_add k₀ (k₁ - k₀) s]
        congr 1
        omega
      rw [hreindex]
      -- Apply throughout-monotonicity at s' := cycleStepN k₀ s with
      -- constant-level hypothesis derived from hno.
      apply cycleStepN_xp_ge_when_level_eq_throughout
      intro j _hj
      -- Want: (cycleStepN j (cycleStepN k₀ s)).level = (cycleStepN k₀ s).level.
      rw [← cycleStepN_add k₀ j s]
      rw [hno (k₀ + j), hno k₀]
    -- At k₁, fight ladder fires → cycleStep applies .fight.
    have hk₁eq : cycleStep (cycleStepN k₁ s) = applyActionKind .fight (cycleStepN k₁ s) :=
      cycleStep_eq_fight_when_fightFires (cycleStepN k₁ s) hk₁fire
    -- cycleStepN (k₁+1) s = cycleStep (cycleStepN k₁ s).
    have hk₁succ : cycleStepN (k₁+1) s = applyActionKind .fight (cycleStepN k₁ s) := by
      rw [cycleStepN_succ_outer k₁ s, hk₁eq]
    -- Level at k₁+1 = level at k₁ (both equal s.level by hno).
    have hlvl_k₁ : (cycleStepN k₁ s).level = s.level := hno k₁
    have hlvl_succ : (cycleStepN (k₁+1) s).level = s.level := hno (k₁+1)
    -- From hk₁succ, applyActionKind .fight (cycleStepN k₁ s) has level = s.level.
    have hfight_lvl_eq :
        (applyActionKind .fight (cycleStepN k₁ s)).level = (cycleStepN k₁ s).level := by
      rw [hk₁succ] at hlvl_succ
      rw [hlvl_succ, hlvl_k₁]
    -- So fight grew xp by exactly 10.
    have hfight_xp :
        (applyActionKind .fight (cycleStepN k₁ s)).xp = (cycleStepN k₁ s).xp + 10 :=
      fight_xp_eq_add_ten_when_level_eq (cycleStepN k₁ s) hfight_lvl_eq
    refine ⟨k₁ + 1, ?_⟩
    rw [hk₁succ, hfight_xp]
    omega

/-- **Lifecycle progress from bounds — PROVEN**.

    Same signature as `lifecycle_progress_from_bounds` axiom; replaces
    the axiom as the consumer-facing implementation. -/
theorem lifecycle_progress_from_bounds_proven
    (s : State) (cycleStepN' : Nat → State → State)
    (hsucc : ∀ n s', cycleStepN' (n+1) s' = cycleStepN' n (cycleStep s'))
    (hzero : ∀ s', cycleStepN' 0 s' = s')
    (hlvl : s.level < 50)
    (_hnowait : ∀ k, productionLadder (cycleStepN' k s) ≠ some .wait)
    (_hex : ∀ k, productionLadder (cycleStepN' k s) = some .taskExchange →
                  (cycleStepN' k s).taskExchangeMinCoins > 0)
    (_hbe : ∀ k, productionLadder (cycleStepN' k s) = some .bankExpand →
                  (cycleStepN' k s).nextExpansionCost > 0)
    (_hperc : ∀ k k', productionLadder (cycleStepN' k s) = some k' →
                       (k' = .bankUnlock ∨ k' = .reachUnlockLevel) →
                       (cycleStepN' k s).xp < xpToNextLevel (cycleStepN' k s).level
                       ∧ (cycleStepN' k s).level < 50)
    (hfightFires : ∀ N, ∃ k ≥ N,
        productionLadder (cycleStepN' k s) = some .bankUnlock
        ∨ productionLadder (cycleStepN' k s) = some .reachUnlockLevel) :
    ∃ k, (cycleStepN' k s).level > s.level := by
  -- Step 1: replace cycleStepN' with the concrete cycleStepN. Under
  -- the strengthened hzero (universal in s'), they agree at every point.
  have hpoint : ∀ n (s' : State), cycleStepN' n s' = cycleStepN n s' := by
    intro n
    induction n with
    | zero =>
      intro s'; rw [hzero, cycleStepN_zero]
    | succ k ih =>
      intro s'
      rw [hsucc k s', ih (cycleStep s'), cycleStepN_succ k s']
  -- Step 2: re-express hfightFires in concrete cycleStepN form.
  have hfightFiresConc :
      ∀ N, ∃ k ≥ N,
        productionLadder (cycleStepN k s) = some .bankUnlock
        ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel := by
    intro N
    obtain ⟨k, hkN, hkfire⟩ := hfightFires N
    refine ⟨k, hkN, ?_⟩
    rw [← hpoint k s]; exact hkfire
  -- Step 3: contradiction.
  by_contra hno
  push Not at hno
  -- hno after push_neg: ∀ k, (cycleStepN' k s).level ≤ s.level.
  -- Convert to concrete cycleStepN form via hpoint.
  have hnoConc : ∀ k, (cycleStepN k s).level ≤ s.level := by
    intro k
    have := hno k
    rwa [hpoint k s] at this
  -- Combine with cycleStepN_level_ge to get level = s.level.
  have hlvl_eq : ∀ k, (cycleStepN k s).level = s.level := by
    intro k
    have hge := cycleStepN_level_ge s k
    have hle := hnoConc k
    omega
  -- Get unbounded xp via xp_accumulates_when_level_constant.
  -- Choose n := xpToNextLevel s.level (positive by LIV-001).
  set M := xpToNextLevel s.level with hM_def
  have hM_pos : M > 0 := xpToNextLevel_pos s.level hlvl
  obtain ⟨k, hk⟩ := xp_accumulates_when_level_constant s hlvl_eq hfightFiresConc M
  -- (cycleStepN k s).xp ≥ s.xp + 10 * M ≥ 10 * M ≥ M.
  have hxp_at_k : (cycleStepN k s).xp ≥ M := by
    have h1 : 10 * M ≥ M := by omega
    have h2 : s.xp + 10 * M ≥ 10 * M := by omega
    omega
  -- Get fight position k' ≥ k+1.
  obtain ⟨k', hk'ge, hk'fire⟩ := hfightFiresConc (k + 1)
  -- xp at k' ≥ xp at k ≥ M (via monotonicity under constant level).
  have hmono_k_k' : (cycleStepN k' s).xp ≥ (cycleStepN k s).xp := by
    have hreindex : cycleStepN k' s = cycleStepN (k' - k) (cycleStepN k s) := by
      rw [← cycleStepN_add k (k' - k) s]
      congr 1; omega
    rw [hreindex]
    apply cycleStepN_xp_ge_when_level_eq_throughout
    intro j _
    rw [← cycleStepN_add k j s, hlvl_eq (k + j), hlvl_eq k]
  -- xp at k' ≥ M = xpToNextLevel s.level.
  have hxp_k' : (cycleStepN k' s).xp ≥ M := by omega
  -- Level at k' = s.level < 50.
  have hlvl_k' : (cycleStepN k' s).level = s.level := hlvl_eq k'
  have hlvl_k'_lt50 : (cycleStepN k' s).level < 50 := by rw [hlvl_k']; exact hlvl
  -- cycleStep at k' applies .fight.
  have hk'eq :
      cycleStep (cycleStepN k' s) = applyActionKind .fight (cycleStepN k' s) :=
    cycleStep_eq_fight_when_fightFires (cycleStepN k' s) hk'fire
  -- cycleStepN (k'+1) s = applyActionKind .fight (cycleStepN k' s).
  have hk'succ : cycleStepN (k'+1) s = applyActionKind .fight (cycleStepN k' s) := by
    rw [cycleStepN_succ_outer k' s, hk'eq]
  -- The fight rollover triggers: xp + 10 ≥ M = xpToNextLevel s.level, level < 50.
  have hwill : (decide ((cycleStepN k' s).xp + 10 ≥ xpToNextLevel (cycleStepN k' s).level)
                 && decide ((cycleStepN k' s).level < 50)) = true := by
    rw [hlvl_k']
    have hxp_thresh : (cycleStepN k' s).xp + 10 ≥ M := by omega
    have hxp_dec : decide ((cycleStepN k' s).xp + 10 ≥ M) = true := by
      simp [hxp_thresh]
    have hlvl_dec : decide (s.level < 50) = true := by simp [hlvl]
    rw [hxp_dec, hlvl_dec]; rfl
  -- Fight applies the rollover branch: level := s.level + 1.
  have hfight_lvl : (applyActionKind .fight (cycleStepN k' s)).level
                      = (cycleStepN k' s).level + 1 := by
    simp only [applyActionKind]
    rw [if_pos hwill]
  -- Combined: (cycleStepN (k'+1) s).level = s.level + 1 > s.level.
  have hk'_succ_lvl : (cycleStepN (k'+1) s).level = s.level + 1 := by
    rw [hk'succ, hfight_lvl, hlvl_k']
  have hcontra : (cycleStepN (k'+1) s).level ≤ s.level := hnoConc (k'+1)
  rw [hk'_succ_lvl] at hcontra
  omega

end Formal.Liveness.LifecycleBound7
