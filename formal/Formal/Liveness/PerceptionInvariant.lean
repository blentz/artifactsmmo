import Formal.Liveness.CycleStep
import Formal.Liveness.Measure
import Formal.Liveness.Plan
import Formal.Liveness.CumulativeProgress
import Mathlib.Tactic

/-! # PerceptionInvariant — the xp-within-band invariant (O5.2 keystone, 2026-06-16)

The fight-driving liveness lemmas (`progressMeans_decreases_extMeasure_or_advances_level`,
the bank-bootstrap cases) need the PERCEPTION invariant `s.xp < xpToNextLevel s.level`
to show a `+10`-xp fight strictly shrinks the xp-distance to the next level. Today
that fact is THREADED as a per-trajectory hypothesis (`hperc'`). This module discharges
it the same way `GameDataInvariance` discharged hex/hbe: as a `cycleStep`-PRESERVED
invariant, so a single spawn fact propagates to every reachable state.

`XpInBand s := s.level < 50 → s.xp < xpToNextLevel s.level`. The `level < 50` guard is
needed because `xpToNextLevel_pos` (LIV-001) only asserts positivity below the cap; at
`level = 50` the bot has already won and the antecedent is vacuous.

Why it is the O5.2 keystone: it removes the obstruction that blocked routing a general
char-leveling FIGHT through `objectiveStep` (a combat objective's first action) — once
the perception invariant is a free consequence of spawn, the objectiveStep-fight
measure-decrease replicates the existing `reachUnlockLevel` argument with no new
runtime obligation. See docs/PLAN_obligation5_scope.md (O5.2).

NO new axioms (standard set + LIV-001 `xpToNextLevel(_pos)` only).
-/

namespace Formal.Liveness.PerceptionInvariant

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress

/-- The perception invariant: while below the level cap, xp has not yet reached the
    threshold to the next level (the perception layer rolls over on cross). -/
def XpInBand (s : State) : Prop := s.level < 50 → s.xp < xpToNextLevel s.level

/-- Every single `applyActionKind` preserves `XpInBand`. Only `.fight` and
    `.completeTask` touch `xp`/`level`; each either rolls over (post xp = 0 <
    xpToNextLevel of the new level, by LIV-001) or stays under threshold. All other
    action kinds leave `xp` and `level` untouched (record updates over other fields),
    so the invariant is preserved definitionally. -/
theorem applyActionKind_preserves_XpInBand (a : ActionKind) (s : State)
    (h : XpInBand s) : XpInBand (applyActionKind a s) := by
  cases a
  case fight =>
    intro hlt
    by_cases hwill : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                       && decide (s.level < 50)) = true
    · -- Rollover: post.level = s.level + 1, post.xp = 0.
      have hlvl : (applyActionKind .fight s).level = s.level + 1 := by
        simp only [applyActionKind]; simp [hwill]
      have hxp : (applyActionKind .fight s).xp = 0 := by
        simp only [applyActionKind]; simp [hwill]
      rw [hlvl] at hlt
      rw [hxp, hlvl]
      exact xpToNextLevel_pos (s.level + 1) hlt
    · -- No rollover: post.level = s.level, post.xp = s.xp + 10 < xpToNextLevel.
      have hwillf : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) = false := by
        cases hbv : (decide (s.xp + 10 ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) with
        | true => exact absurd hbv hwill
        | false => rfl
      have hlvl : (applyActionKind .fight s).level = s.level := by
        simp only [applyActionKind]; simp [hwillf]
      have hxp : (applyActionKind .fight s).xp = s.xp + 10 := by
        simp only [applyActionKind]; simp [hwillf]
      rw [hlvl] at hlt
      rw [hxp, hlvl]
      -- From hwillf and s.level < 50: decide (xp+10 ≥ xpToNextLevel) = false.
      have hge : ¬ (s.xp + 10 ≥ xpToNextLevel s.level) := by
        rcases Bool.and_eq_false_iff.mp hwillf with h1 | h2
        · simpa using h1
        · simp only [decide_eq_false_iff_not] at h2; omega
      omega
  case completeTask =>
    intro hlt
    by_cases hwill : (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
                       && decide (s.level < 50)) = true
    · have hlvl : (applyActionKind .completeTask s).level = s.level + 1 := by
        simp only [applyActionKind]; simp [hwill]
      have hxp : (applyActionKind .completeTask s).xp = 0 := by
        simp only [applyActionKind]; simp [hwill]
      rw [hlvl] at hlt
      rw [hxp, hlvl]
      exact xpToNextLevel_pos (s.level + 1) hlt
    · have hwillf : (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) = false := by
        cases hbv : (decide (s.xp + taskCompleteXpEstimate ≥ xpToNextLevel s.level)
                      && decide (s.level < 50)) with
        | true => exact absurd hbv hwill
        | false => rfl
      have hlvl : (applyActionKind .completeTask s).level = s.level := by
        simp only [applyActionKind]; simp [hwillf]
      have hxp : (applyActionKind .completeTask s).xp
                  = s.xp + taskCompleteXpEstimate := by
        simp only [applyActionKind]; simp [hwillf]
      rw [hlvl] at hlt
      rw [hxp, hlvl]
      have := h hlt
      simp only [taskCompleteXpEstimate]
      omega
  -- `.move` / `.mapTransition` have a top-level `match s.moveTarget` (not a
  -- `{s with …}` wrapper), so xp/level are not defeq to s's without splitting.
  case move =>
    intro hlt
    have hlvl : (applyActionKind .move s).level = s.level := by
      simp only [applyActionKind]; cases s.moveTarget <;> rfl
    have hxp : (applyActionKind .move s).xp = s.xp := by
      simp only [applyActionKind]; cases s.moveTarget <;> rfl
    rw [hlvl] at hlt; rw [hxp, hlvl]; exact h hlt
  case mapTransition =>
    intro hlt
    have hlvl : (applyActionKind .mapTransition s).level = s.level := by
      simp only [applyActionKind]; cases s.moveTarget <;> rfl
    have hxp : (applyActionKind .mapTransition s).xp = s.xp := by
      simp only [applyActionKind]; cases s.moveTarget <;> rfl
    rw [hlvl] at hlt; rw [hxp, hlvl]; exact h hlt
  -- All remaining action kinds leave xp and level untouched (record updates over
  -- other fields), so `XpInBand` is preserved definitionally.
  all_goals exact h

/-- `cycleStep` preserves `XpInBand` (it applies some `applyActionKind`, or is the
    identity on the impossible `none`/empty-plan branches). -/
theorem cycleStep_preserves_XpInBand (s : State) (h : XpInBand s) :
    XpInBand (cycleStep s) := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact applyActionKind_preserves_XpInBand _ s h

/-- `XpInBand` propagates along the whole `cycleStepN` trajectory from a single
    spawn fact. This is the discharge mechanism: prove `XpInBand` once at spawn,
    get it everywhere — no per-trajectory `hperc'` hypothesis needed. -/
theorem cycleStepN_preserves_XpInBand :
    ∀ (n : Nat) (s : State), XpInBand s → XpInBand (cycleStepN n s)
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact cycleStepN_preserves_XpInBand n (cycleStep s)
        (cycleStep_preserves_XpInBand s h)

/-- Spawn discharge: a fresh character (`level = 1`, `xp = 0`) satisfies `XpInBand`
    because `xpToNextLevel 1 > 0` by LIV-001. Hence the invariant holds along the
    ENTIRE trajectory from spawn, with no runtime hypothesis. -/
theorem spawn_XpInBand (s : State) (hlvl : s.level = 1) (hxp : s.xp = 0) :
    XpInBand s := by
  intro _
  rw [hlvl, hxp]
  exact xpToNextLevel_pos 1 (by omega)

end Formal.Liveness.PerceptionInvariant
