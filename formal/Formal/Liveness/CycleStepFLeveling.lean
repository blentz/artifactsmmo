import Formal.Liveness.CycleStepFIteration

/-! # CycleStepFLeveling — Workstream A Phase-1 Brick 3d-b: the `cycleStepF`
level-advance engine.

Re-derives the level-advance engine for the FAITHFUL cycle `cycleStepF`, mirroring
`LevelFiftyReachableP`'s `xp_accumulates_when_level_constant_P` /
`level_advances_onceP` with `cycleStepP ↦ cycleStepF`. Reuses the Brick-3d-a
plumbing (`cycleStepFN_add`, `cycleStepFN_succ_outer`, the level/xp monotonicity).

The ONE new wrinkle versus the `cycleStepP` engine: at a fight position the faithful
cycle runs `cycleStepF t = pressureDelta j (cycleStep (perceptionRefresh t))` — the
fight, THEN the inventory-pressure bump. `pressureDelta` preserves `xp` and `level`
(Brick 2), so the fight's `+10` xp / rollover transfers through it UNCHANGED — the
landing lemma below gives the `xp`/`level` equalities the accumulation reads (it
does NOT need full state equality, because pressure is the only thing `pressureDelta`
moves and the engine never reads it).

`hfightFiresF` is the fight-firing residual for the faithful trajectory (the analog
of `hfightFiresP`); Brick 3d-c will discharge it from the REDUCED 10-blocker
residual (`PressureBurst.nonPressureBlockers`) + `Drainability.RuntimeInvariant` via
the bounded-burst argument. Here it is consumed as a hypothesis.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed. -/

namespace Formal.Liveness.CycleStepFLeveling

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.CycleStep
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.XpMonotonicity
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.CycleStepF
open Formal.Liveness.InventoryDynamics
open Formal.Liveness.CycleStepFIteration

/-! ## The fight-firing residual for the faithful cycle -/

/-- **`hfightFiresF`** — the fight-firing obligation over the faithful trajectory.
    Mirrors `hfightFiresP` with `cycleStepPN ↦ cycleStepFN`: infinitely often the
    refreshed selection state `perceptionRefresh (cycleStepFN k s)` selects a
    bank-bootstrap fight or a committed combat objective. Brick 3d-c discharges it
    from the reduced 10-blocker residual + `RuntimeInvariant`. -/
def hfightFiresF (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
      productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankUnlock
    ∨ productionLadder (perceptionRefresh (cycleStepFN k s)) = some .reachUnlockLevel
    ∨ (productionLadder (perceptionRefresh (cycleStepFN k s)) = some .objectiveStep
        ∧ (perceptionRefresh (cycleStepFN k s)).objectiveStepIsFight = true)

/-! ## Fight-landing — at a fight position the faithful cycle's xp/level are the
fight's, through `pressureDelta`. -/

/-- At a fight position, `cycleStepFN (k+1) s` shares `xp` and `level` with the
    fight applied to the refreshed selection state `perceptionRefresh (cycleStepFN k
    s)`. `cycleStepF` runs `pressureDelta j (cycleStep r)` where `cycleStep r`
    is the fight; `pressureDelta` preserves `xp`/`level`, so they pass through. -/
theorem cycleStepFN_succ_fight_xp_level (s : State) (k : Nat)
    (hfire : productionLadder (perceptionRefresh (cycleStepFN k s)) = some .bankUnlock
        ∨ productionLadder (perceptionRefresh (cycleStepFN k s)) = some .reachUnlockLevel
        ∨ (productionLadder (perceptionRefresh (cycleStepFN k s)) = some .objectiveStep
            ∧ (perceptionRefresh (cycleStepFN k s)).objectiveStepIsFight = true)) :
    (cycleStepFN (k+1) s).xp
        = (applyActionKind .fight (perceptionRefresh (cycleStepFN k s))).xp
      ∧ (cycleStepFN (k+1) s).level
        = (applyActionKind .fight (perceptionRefresh (cycleStepFN k s))).level := by
  -- The ladder selects SOME fight means j on the refreshed selection state.
  have hsome : ∃ j, productionLadder (perceptionRefresh (cycleStepFN k s)) = some j := by
    rcases hfire with h | h | ⟨h, _⟩ <;> exact ⟨_, h⟩
  obtain ⟨j, hj⟩ := hsome
  -- cycleStepP (cycleStepFN k s) = cycleStep (perceptionRefresh …) = the fight.
  have hcp : cycleStepP (cycleStepFN k s)
      = applyActionKind .fight (perceptionRefresh (cycleStepFN k s)) := by
    show cycleStep (perceptionRefresh (cycleStepFN k s))
        = applyActionKind .fight (perceptionRefresh (cycleStepFN k s))
    exact cycleStep_eq_fight_when_fightCycleFires (perceptionRefresh (cycleStepFN k s)) hfire
  -- cycleStepF (cycleStepFN k s) = pressureDelta j (cycleStepP (cycleStepFN k s)).
  have hcf : cycleStepF (cycleStepFN k s)
      = pressureDelta j (cycleStepP (cycleStepFN k s)) := by
    unfold cycleStepF; rw [hj]
  rw [cycleStepFN_succ_outer k s, hcf, hcp]
  exact ⟨pressureDelta_xp j _, pressureDelta_level j _⟩

/-! ## xp accumulation under no-level-advance — the `cycleStepF` engine -/

/-- **xp accumulation under no-level-advance, for `cycleStepF`.** If level is
    constant along the faithful trajectory, for every `n` some position has `xp`
    grown by at least `10*n`. The `cycleStepF` analog of
    `LevelFiftyReachableP.xp_accumulates_when_level_constant_P`, consuming
    `hfightFiresF`. -/
theorem xp_accumulates_when_level_constant_F (s : State)
    (hno : ∀ k, (cycleStepFN k s).level = s.level)
    (hfp : hfightFiresF s) (n : Nat) :
    ∃ k, (cycleStepFN k s).xp ≥ s.xp + 10 * n := by
  induction n with
  | zero => exact ⟨0, by rw [cycleStepFN_zero]; omega⟩
  | succ m ih =>
    obtain ⟨k₀, hk₀⟩ := ih
    obtain ⟨k₁, hk₁ge, hk₁fire⟩ := hfp (k₀ + 1)
    -- xp monotone from k₀ to k₁ via the constant-level trajectory.
    have hmono_k₀_k₁ : (cycleStepFN k₁ s).xp ≥ (cycleStepFN k₀ s).xp := by
      have hreindex : cycleStepFN k₁ s = cycleStepFN (k₁ - k₀) (cycleStepFN k₀ s) := by
        rw [← cycleStepFN_add k₀ (k₁ - k₀) s]; congr 1; omega
      rw [hreindex]
      apply cycleStepFN_xp_ge_when_level_eq_throughout
      intro j _
      rw [← cycleStepFN_add k₀ j s, hno (k₀ + j), hno k₀]
    -- Landing: cycleStepFN (k₁+1) s shares xp/level with the fight.
    obtain ⟨hxp_succ, hlvl_succ⟩ := cycleStepFN_succ_fight_xp_level s k₁ hk₁fire
    have href_lvl : (perceptionRefresh (cycleStepFN k₁ s)).level = s.level := by
      rw [perceptionRefresh_level]; exact hno k₁
    have hsucc_lvl : (cycleStepFN (k₁+1) s).level = s.level := hno (k₁+1)
    -- The fight did NOT roll over: post-fight level = refreshed-state level.
    have hfight_lvl_eq :
        (applyActionKind .fight (perceptionRefresh (cycleStepFN k₁ s))).level
          = (perceptionRefresh (cycleStepFN k₁ s)).level := by
      omega
    have hfight_xp :
        (applyActionKind .fight (perceptionRefresh (cycleStepFN k₁ s))).xp
          = (perceptionRefresh (cycleStepFN k₁ s)).xp + 10 :=
      fight_xp_eq_add_ten_when_level_eq (perceptionRefresh (cycleStepFN k₁ s)) hfight_lvl_eq
    refine ⟨k₁ + 1, ?_⟩
    rw [hxp_succ, hfight_xp, perceptionRefresh_xp]
    omega

/-! ## Level advances once — the by-contradiction re-derivation -/

/-- **Level advances once, for `cycleStepF`.** From `level < 50` and `hfightFiresF`,
    some finite number of faithful cycles strictly raises `level`. The `cycleStepF`
    analog of `LevelFiftyReachableP.level_advances_onceP`. -/
theorem level_advances_onceF (s : State)
    (hlvl : s.level < 50) (hfp : hfightFiresF s) :
    ∃ k, (cycleStepFN k s).level > s.level := by
  by_contra hno
  push Not at hno
  have hlvl_eq : ∀ k, (cycleStepFN k s).level = s.level := by
    intro k
    have hge := cycleStepFN_level_ge s k
    have hle := hno k
    omega
  set M := xpToNextLevel s.level with hM_def
  have hM_pos : M > 0 := xpToNextLevel_pos s.level hlvl
  obtain ⟨k, hk⟩ := xp_accumulates_when_level_constant_F s hlvl_eq hfp M
  have hxp_at_k : (cycleStepFN k s).xp ≥ M := by
    have h1 : 10 * M ≥ M := by omega
    omega
  obtain ⟨k', hk'ge, hk'fire⟩ := hfp (k + 1)
  have hmono_k_k' : (cycleStepFN k' s).xp ≥ (cycleStepFN k s).xp := by
    have hreindex : cycleStepFN k' s = cycleStepFN (k' - k) (cycleStepFN k s) := by
      rw [← cycleStepFN_add k (k' - k) s]; congr 1; omega
    rw [hreindex]
    apply cycleStepFN_xp_ge_when_level_eq_throughout
    intro j _
    rw [← cycleStepFN_add k j s, hlvl_eq (k + j), hlvl_eq k]
  have hxp_k' : (cycleStepFN k' s).xp ≥ M := by omega
  have hlvl_k' : (cycleStepFN k' s).level = s.level := hlvl_eq k'
  have href_lvl : (perceptionRefresh (cycleStepFN k' s)).level = s.level := by
    rw [perceptionRefresh_level]; exact hlvl_k'
  have href_xp : (perceptionRefresh (cycleStepFN k' s)).xp = (cycleStepFN k' s).xp :=
    perceptionRefresh_xp (cycleStepFN k' s)
  -- Landing at k'.
  obtain ⟨hxp_succ, hlvl_succ⟩ := cycleStepFN_succ_fight_xp_level s k' hk'fire
  -- The rollover fires on the refreshed state: xp + 10 ≥ M, level < 50.
  have hwill :
      (decide ((perceptionRefresh (cycleStepFN k' s)).xp + 10
                 ≥ xpToNextLevel (perceptionRefresh (cycleStepFN k' s)).level)
       && decide ((perceptionRefresh (cycleStepFN k' s)).level < 50)) = true := by
    rw [href_lvl, href_xp]
    have hxp_thresh : (cycleStepFN k' s).xp + 10 ≥ M := by omega
    have hxp_dec : decide ((cycleStepFN k' s).xp + 10 ≥ M) = true := by simp [hxp_thresh]
    have hlvl_dec : decide (s.level < 50) = true := by simp [hlvl]
    rw [hxp_dec, hlvl_dec]; rfl
  -- Fight applies the rollover branch: level := refreshed-level + 1.
  have hfight_lvl :
      (applyActionKind .fight (perceptionRefresh (cycleStepFN k' s))).level
        = (perceptionRefresh (cycleStepFN k' s)).level + 1 := by
    simp only [applyActionKind]
    rw [if_pos hwill]
  -- So cycleStepFN (k'+1) s has level = s.level + 1, contradicting hno.
  have hk'_succ_lvl : (cycleStepFN (k'+1) s).level = s.level + 1 := by
    rw [hlvl_succ, hfight_lvl, href_lvl]
  have hcontra : (cycleStepFN (k'+1) s).level ≤ s.level := hno (k'+1)
  rw [hk'_succ_lvl] at hcontra
  omega

end Formal.Liveness.CycleStepFLeveling
