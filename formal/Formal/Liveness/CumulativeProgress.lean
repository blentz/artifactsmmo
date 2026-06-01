/-
  Formal.Liveness.CumulativeProgress

  Phase 23a — Tier 4 part 1. Cumulative progress under "no wait fires".

  ## Pieces

  1. `cycleStepN : Nat → State → State` — iterate `cycleStep` n times.

  2. `cumulative_state_change_under_no_wait` — the WEAKER form of the
     Tier-4 headline shipped in this sub-phase:

         ∀ s, s.level < 50 →
              (∀ k, productionLadder (cycleStepN k s) ≠ some .wait) →
              (∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
                    (cycleStepN k s).taskExchangeMinCoins > 0) →
              ∃ k, cycleStepN k s ≠ s

     Direct corollary of Phase 22a's `cycleStep_progress_or_waits` at
     k = 1. The headline is presented as iteration-friendly rather than
     genuinely cumulative — the strict measure-decrease lemma
     (`cycleStep_measureDecreasesOrWaits`) that would let us chain into
     well-founded induction over `measureLt` is deferred to Phase 23b.

  ## Honest disclosure: weaker form

  The phase brief explicitly authorises shipping the weaker form if the
  stronger measure-decrease lemma proves intractable in one sub-phase.
  We take that fallback.

  Why intractable in 23a's scope:
  - `cycleStep` applies actions from `ActionKind` (16+ constructors), but
    `step_decreases_measure` from Phase 19 only covers four:
    `ProgressAction = Fight | Gather | Deposit | Rest`. Tying these
    together requires either:
      (a) a partial map `ActionKind → Option ProgressAction` plus a
          theorem that the unmapped kinds preserve measure or only
          decrease later levels of the lex order — neither is true in
          general (e.g. `acceptTask` sets `taskCode` but doesn't move
          the lex measure), OR
      (b) a NEW measure ordering tailored to the ActionKind space.
  - Phase 19's `step_decreases_measure` requires `validInvariants`
    hypotheses (e.g. for Fight: `s.level < 50 ∧ s.xp < xpToNextLevel`).
    The cycle abstraction does NOT automatically discharge these — the
    Fight branch of `productionLadder` only checks `bankUnlockFires` or
    `reachUnlockLevel`, neither of which guarantees the perception
    invariant. Discharging is a Phase-22-class invariant-tracking task.

  Phase 23b's job: introduce the `ActionKind → Option ProgressAction`
  bridge and the invariant-tracking that promotes
  `cumulative_state_change_under_no_wait` to
  `cumulative_progress_under_no_wait` (level strictly advances).

  ## Honest disclosure: load-bearing hypotheses

  Both surfaced in the theorem signature:

  1. `(∀ k, productionLadder (cycleStepN k s) ≠ some .wait)` — no wait
     ever fires along the trajectory. If the trajectory falls into a
     wait-only steady state, `cycleStep` is a no-op and the state never
     changes. This matches the production model: WAIT is the
     "nothing actionable" fallback.

  2. `(∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
           (cycleStepN k s).taskExchangeMinCoins > 0)` — the
     `.taskExchange` non-degeneracy hypothesis from Phase 22a, lifted
     pointwise along the trajectory.

  ## Integrity

  - No `sorry`/`admit`/`native_decide`.
  - No new `axiom` keyword.
  - `cycleStepN` is `noncomputable` solely because `cycleStep` is
    (transitive dependency on LIV-001 `xpToNextLevel`).
  - Axioms ⊆ {propext, Classical.choice, Quot.sound, xpToNextLevel}.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.CycleStep
import Formal.Liveness.ProductionLadder
import Formal.Liveness.Measure

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.CumulativeProgress

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep

/-! ## cycleStepN — iterated cycle transition -/

/-- Iterate `cycleStep` n times. Tail-recursive shape so unfolding at
    `n+1` exposes the next state directly. -/
noncomputable def cycleStepN : Nat → State → State
  | 0,     s => s
  | n+1,   s => cycleStepN n (cycleStep s)

@[simp] theorem cycleStepN_zero (s : State) : cycleStepN 0 s = s := rfl

theorem cycleStepN_succ (n : Nat) (s : State) :
    cycleStepN (n+1) s = cycleStepN n (cycleStep s) := rfl

/-! ## Weaker headline — cumulative state change under no-wait -/

/-- WEAKER Tier-4 headline shipped in Phase 23a.

    Under three load-bearing hypotheses (`level < 50`, "no wait ever
    fires", and the `.taskExchange` non-degeneracy lifted pointwise),
    some iterate of `cycleStep` produces a state different from the
    starting one.

    The proof is the iteration-at-`k = 1` corollary of Phase 22a's
    `cycleStep_progress_or_waits`. The `level < 50` hypothesis is not
    used here directly (it's reserved for the Phase-23b strengthening
    that proves the level strictly advances), but is kept in the
    signature for forward-compatibility with the headline.

    Phase 23b's job: replace `≠ s` with `.level > s.level`. -/
theorem cumulative_state_change_under_no_wait
    (s : State)
    (_hlvl : s.level < 50)
    (hnowait : ∀ k, productionLadder (cycleStepN k s) ≠ some .wait)
    (hex : ∀ k, productionLadder (cycleStepN k s) = some .taskExchange →
                (cycleStepN k s).taskExchangeMinCoins > 0) :
    ∃ k, cycleStepN k s ≠ s := by
  -- Apply 22a at k = 0 (state s itself).
  have h22a := cycleStep_progress_or_waits s (hex 0)
  -- Discharge the wait disjunct using hnowait 0.
  have hwait0 : productionLadder s ≠ some .wait := by
    have := hnowait 0
    simpa [cycleStepN] using this
  have hne : cycleStep s ≠ s := by
    cases h22a with
    | inl h => exact h
    | inr h => exact absurd h hwait0
  -- Witness: k = 1.
  refine ⟨1, ?_⟩
  -- cycleStepN 1 s = cycleStepN 0 (cycleStep s) = cycleStep s.
  show cycleStepN 1 s ≠ s
  have hrw : cycleStepN 1 s = cycleStep s := by
    rw [cycleStepN_succ]; rfl
  rw [hrw]
  exact hne

end Formal.Liveness.CumulativeProgress
