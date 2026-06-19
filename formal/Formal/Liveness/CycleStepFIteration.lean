import Formal.Liveness.CycleStepF
import Formal.Liveness.LevelFiftyReachableP

/-! # CycleStepFIteration — Workstream A Phase-1 Brick 3d-a: the `cycleStepF`
iteration + monotonicity plumbing.

The faithful-cycle capstone (`ai_reaches_level_fiftyF`, Brick 3d) must RE-DERIVE the
level-advance engine for `cycleStepF`, exactly as `LevelFiftyReachableP` re-derived
it for `cycleStepP` (the engine is not reusable: `LifecycleBound7`'s `cycleStepN'`
reduction requires the inner step to be `cycleStep`, which neither `cycleStepP` nor
`cycleStepF` is). This module is the mechanical FOUNDATION of that re-derivation —
the iteration laws and the level/xp monotonicity facts — which the eventual
contradiction argument (`level_advances_onceF`) consumes.

Crucially these need NO measure and NO well-foundedness: the level-advance engine
reaches 50 by **xp accumulation** (count fights, cross `xpToNextLevel`), not by lex
descent. So the claim/`pendingCount` WF complication is confined to the LATER
bounded-burst termination (proving the fights fire i.o.), and is absent here.

Every fact transfers off the Brick-3a per-step bridges (`cycleStepF` agrees with
`cycleStepP` on `level`/`xp`) plus the established `cycleStepP` monotonicity
(`LevelFiftyReachableP.cycleStepP_level_ge` / `cycleStepP_xp_ge_when_level_eq`). The
iteration laws mirror `cycleStepPN_add` / `cycleStepPN_succ_outer` verbatim with
`cycleStepP` ↦ `cycleStepF`.

NOTE on divergence: `cycleStepFN n s ≠ cycleStepPN n s` over multiple steps (pressure
feeds back into selection), so these are NATIVE `cycleStepF` facts — they reuse the
PER-STEP bridges at each `cycleStepFN k s`, never an `…N`-level equality.

Additive only; axioms ⊆ {propext, Classical.choice, Quot.sound, LIV-001}. Liveness
namespace — Mathlib allowed (inherited via `LevelFiftyReachableP`). -/

namespace Formal.Liveness.CycleStepFIteration

open Formal.Liveness.Measure
open Formal.Liveness.CycleStep
open Formal.Liveness.PerceptionRefresh
open Formal.Liveness.CycleStepP
open Formal.Liveness.CycleStepF
open Formal.Liveness.LevelFiftyReachableP

/-! ## Iteration laws for `cycleStepFN` (the `cycleStepPN_add` / `_succ_outer`
analogs). Identical proofs with the inner step renamed. -/

/-- Composition law for `cycleStepFN`. Mirrors `cycleStepPN_add`. -/
theorem cycleStepFN_add (m n : Nat) (s : State) :
    cycleStepFN (m + n) s = cycleStepFN n (cycleStepFN m s) := by
  induction m generalizing s with
  | zero =>
    show cycleStepFN (0 + n) s = cycleStepFN n (cycleStepFN 0 s)
    rw [cycleStepFN_zero, Nat.zero_add]
  | succ j ih =>
    show cycleStepFN ((j + 1) + n) s = cycleStepFN n (cycleStepFN (j + 1) s)
    rw [show (j + 1) + n = (j + n) + 1 from by omega]
    rw [cycleStepFN_succ (j + n) s]
    rw [cycleStepFN_succ j s]
    exact ih (cycleStepF s)

/-- Right-side recurrence: `cycleStepFN (n+1) s = cycleStepF (cycleStepFN n s)`.
    Mirrors `cycleStepPN_succ_outer`. -/
theorem cycleStepFN_succ_outer (n : Nat) (s : State) :
    cycleStepFN (n+1) s = cycleStepF (cycleStepFN n s) := by
  rw [cycleStepFN_add n 1 s]
  show cycleStepFN 1 (cycleStepFN n s) = cycleStepF (cycleStepFN n s)
  rw [cycleStepFN_succ 0 (cycleStepFN n s), cycleStepFN_zero]

/-! ## Level monotonicity

`cycleStepF` agrees with `cycleStepP` on `level` (Brick-3a bridge) and `cycleStepP`
never lowers it, so neither does `cycleStepF`; iterate. -/

/-- One `cycleStepF` never lowers `level`. Bridges `cycleStepF_level` through
    `cycleStepP_level_ge`. -/
theorem cycleStepF_level_ge (s : State) : (cycleStepF s).level ≥ s.level := by
  rw [cycleStepF_level]; exact cycleStepP_level_ge s

/-- Iterated `cycleStepF` never lowers `level`. Mirrors `cycleStepPN_level_ge`. -/
theorem cycleStepFN_level_ge (s : State) (n : Nat) :
    (cycleStepFN n s).level ≥ s.level := by
  induction n generalizing s with
  | zero => rw [cycleStepFN_zero]
  | succ k ih =>
    rw [cycleStepFN_succ]
    have h1 : (cycleStepF s).level ≥ s.level := cycleStepF_level_ge s
    have h2 : (cycleStepFN k (cycleStepF s)).level ≥ (cycleStepF s).level :=
      ih (cycleStepF s)
    omega

/-! ## Xp monotonicity under constant level

`cycleStepF` agrees with `cycleStepP` on BOTH `xp` and `level`, so the constant-
level xp-monotonicity of `cycleStepP` lifts to `cycleStepF`. -/

/-- Single-step `cycleStepF` xp monotonicity under constant level. Transfers
    `cycleStepP_xp_ge_when_level_eq` through the `xp`/`level` bridges. -/
theorem cycleStepF_xp_ge_when_level_eq (s : State)
    (h : (cycleStepF s).level = s.level) :
    (cycleStepF s).xp ≥ s.xp := by
  rw [cycleStepF_xp]
  apply cycleStepP_xp_ge_when_level_eq
  rw [← cycleStepF_level]; exact h

/-- Iterated `cycleStepF` xp monotonicity under constant level across the whole
    prefix. Mirrors `cycleStepPN_xp_ge_when_level_eq_throughout`. -/
theorem cycleStepFN_xp_ge_when_level_eq_throughout (s : State) (n : Nat)
    (h : ∀ k ≤ n, (cycleStepFN k s).level = s.level) :
    (cycleStepFN n s).xp ≥ s.xp := by
  induction n with
  | zero => rw [cycleStepFN_zero]
  | succ k ih =>
    have hsucc_lvl_orig : (cycleStepFN (k+1) s).level = s.level := h (k+1) (Nat.le_refl _)
    have hk_lvl : (cycleStepFN k s).level = s.level := h k (Nat.le_succ _)
    rw [cycleStepFN_succ_outer k s] at hsucc_lvl_orig
    have hstep_lvl :
        (cycleStepF (cycleStepFN k s)).level = (cycleStepFN k s).level := by
      rw [hsucc_lvl_orig, hk_lvl]
    have hstep_xp :
        (cycleStepF (cycleStepFN k s)).xp ≥ (cycleStepFN k s).xp :=
      cycleStepF_xp_ge_when_level_eq (cycleStepFN k s) hstep_lvl
    have hk_xp := ih (fun j hj => h j (Nat.le_succ_of_le hj))
    rw [cycleStepFN_succ_outer k s]
    omega

end Formal.Liveness.CycleStepFIteration
