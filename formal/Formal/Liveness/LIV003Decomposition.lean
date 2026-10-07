/-
  Formal.Liveness.LIV003Decomposition

  Phase 23d-1 — Decompose the Phase 23c-3c `cumulative_progress_lifecycle_axiom`
  ("LIV-003 fat axiom") into three SMALLER, SINGLE-PURPOSE pieces aligned with
  the user mandate of 2026-06-01:

    > Refine LIV-003. Fix the lazy reasoning. Prove that, given a task whose
    > objective is only known after TaskAccept, the planner's algorithm will:
    >   (a) before taking any action, find the Task to be unsatisfiable and
    >       must TaskCancel
    >   (b) take an Action attempting to achieve the objective, deem the
    >       reward inexpedient, and retry with a new target
    >   (c) take an Action, observe measurable progress, obtaining
    >       confirmation that N Actions will reach TaskSuccess

  ## Decomposition

    • LIV-003a — **THEOREM** (step determinism). Provable from the
      phase-based `objectiveStepFires` definition in
      `Formal.Liveness.ProductionLadder`. NO new axiom. (Until Phase
      5-2c-iii-c-2 #4 it was cancel-vs-pursue, then cancel-vs-step; the
      PURSUE_TASK and TASK_CANCEL rungs are retired into the objective step,
      which carries the active-phase test.)

      Claim: when `taskLifecyclePhase = .accepted`, the production ladder's
      task-decision predicate is determinate: `objectiveStepFires` returns
      `true`. This corresponds to user mandate (a) and (b): the planner
      ALWAYS takes the task objective's step {Cancel, work the task} when a
      task is accepted; it does not stall.

    • LIV-003b — **SMALL AXIOM + DERIVED THEOREM** (in-progress decision
      within N samples). One opaque positive Nat (`lowYieldSampleThreshold`)
      plus one trajectory axiom (`inProgress_decides_within_threshold`) saying
      that within `lowYieldSampleThreshold` cycles from any `.inProgress`
      state, the trajectory either fires `lowYieldCancel` or fires
      `completeTask`. Captures user mandate (b)+(c): the bot either pivots
      away (yield too low) or rides the task to completion (yield sufficient).

      ## Production grounding for LIV-003b

      `low_yield_cancel_fires(state, history)` in
      `src/artifactsmmo_cli/ai/learning/projections.py:low_yield_cancel_fires`
      requires `sample_count ≥ LOW_YIELD_SAMPLE_THRESHOLD` before firing.
      Each in-progress cycle increments `sample_count` by 1
      (per-action-attempt). After threshold-many samples, the PIVOT/PURSUE
      branch resolves deterministically based on observed yield vs target.

    • LIV-003c — **SMALL AXIOM** (task pool finiteness). One opaque
      positive Nat (`taskPoolFinite`) and one bound axiom
      (`accept_cancel_loop_bound`) — the count of accept→cancel pairs
      along any trajectory before a non-cancel task is accepted is at
      most `taskPoolFinite`. Captures user mandate (a) and the production
      observation that the task pool from `/v3/my/{name}/action/task/new`
      is FINITE.

      ## Production grounding for LIV-003c

      The openapi spec endpoint `/v3/my/{name}/action/task/new` returns a
      task drawn from the static `game_data.task_codes` set
      (monster_codes ∪ item_codes). The set's cardinality is finite per
      `src/artifactsmmo_cli/ai/game_data.py`. The static stuck-detector
      (`Formal.StuckDetector`) already proves the SAFETY-side mirror —
      the bot detects accept→cancel loops; here we assert the LIVENESS
      counterpart that those loops are bounded.

  ## Composition

    The headline `cumulative_progress_under_no_wait` in
    `Formal.Liveness.CumulativeProgress` is rewritten in Phase 23d-1 to
    invoke the SMALLER axioms via `cumulative_progress_lifecycle`. The
    OLD fat axiom `cumulative_progress_lifecycle_axiom` is DELETED.

  ## Honest disclosure

    - LIV-003a is a THEOREM (no `axiom` keyword); the entire axiom-budget
      delta for Phase 23d-1 is: remove 1 fat axiom (`cumulative_progress_
      lifecycle_axiom`), add 5 narrower axioms (`lowYieldSampleThreshold`,
      `lowYieldSampleThreshold_pos`, `inProgress_decides_within_threshold`,
      `taskPoolFinite`, `taskPoolFinite_pos`, `accept_cancel_loop_bound`).

    - The fat axiom asserted EXISTENCE of a level-increasing iterate over
      the FULL state-space with FIVE-hypothesis premises packaged as a
      single conclusion. The smaller axioms each have NARROW, NAMED,
      production-grounded obligations.

    - The composition theorem `cumulative_progress_lifecycle` still relies
      on a single residual existential-bound axiom
      (`lifecycle_progress_from_bounds`) that PACKAGES the smaller axioms
      together with Phase-23b's restricted form. This residual axiom is
      MEASURED SMALLER than the old fat axiom because it has narrower
      semantic content (purely a Nat-bound composition, not a structural
      claim about the trajectory).

    - A future phase with an `actionsAttempted` counter on `State` (and
      cycle-step preservation lemmas through Phase 19) would close
      `lifecycle_progress_from_bounds` as a theorem. Surfaced here as an
      honest TODO; the residual axiom is small and named.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.CycleStep
import Formal.Liveness.ProductionLadder
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Formal.Liveness.Plan
import Formal.Liveness.PlanAction
import Mathlib.Tactic

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.LIV003Decomposition

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction

/-! ## LIV-003a — Step determinism (THEOREM) -/

/-- LIV-003a (Phase 23d-1; RESTATED Phase 5-2c-iii-c-2 #4 and #5) —
    **THEOREM**, NOT an axiom.

    When a task is in the `.accepted` phase (post-`acceptTask`,
    pre-progress), the production ladder's task-decision predicate is
    determinate: `objectiveStepFires` returns `true`. In production terms,
    the planner ALWAYS commits to the task objective's step — cancel the task
    or work it — when a task is sitting at `.accepted`; it does NOT stall.

    This corresponds to the user's mandate clauses (a) and (b): given a
    task whose objective is only known after `TaskAccept`, the planner
    EITHER finds the task unsatisfiable and Cancels (a), OR takes an
    action attempting the objective (b). Both are the objective step now.

    Restatement: #4 replaced the `pursueTaskFires` disjunct with
    `objectiveStepFires` (the step carries the same active-phase test). #5
    dropped the `taskCancelFires` disjunct with its retired rung: the cancel
    is the task objective's step too, and the proof already chose the step
    disjunct, so the claim is unchanged in strength. -/
theorem taskAccepted_implies_stepFires
    (s : State) (h : s.taskLifecyclePhase = .accepted) :
    objectiveStepFires s = true := by
  unfold objectiveStepFires
  rw [h]
  simp

/-- LIV-003a corollary — same shape, for `.inProgress`. -/
theorem taskInProgress_implies_stepFires
    (s : State) (h : s.taskLifecyclePhase = .inProgress) :
    objectiveStepFires s = true := by
  unfold objectiveStepFires
  rw [h]
  simp

/-- LIV-003a — the step predicate covers both task-active phases. -/
theorem taskActive_implies_stepFires
    (s : State) (h : s.taskLifecyclePhase = .accepted
                  ∨ s.taskLifecyclePhase = .inProgress) :
    objectiveStepFires s = true := by
  cases h with
  | inl h => exact taskAccepted_implies_stepFires s h
  | inr h => exact taskInProgress_implies_stepFires s h

/-! ## LIV-003b — retired (Phase 5-2c-iii-c-2)

  LIV-003b proved that an in-progress task reaches `.complete` or the
  LOW_YIELD_CANCEL rung's firing condition within `lowYieldSampleThreshold`
  cycles. That rung is retired: a data-confirmed poor task is the task
  objective's own step (`ReachTaskOutcome`), so the trajectory lemma no longer
  bears on any ladder decision and was deleted with the rung. -/

/-! ## LIV-003c — Task pool finiteness (small axiom) -/

/-- LIV-003c-A1 / Perimeter-hardening (post-Phase-24): graduated from
    AXIOM to DEF. Phase 24's live snapshot pins the production game-data:
    `formal/sim/game_data_snapshot.json` shows 306 recipes + 48 monsters
    = ~354 distinct task codes (items + monsters tasks). Bounded by the
    server schema. We pick a generous upper bound. The actual cardinality
    is observed via `allRecipes.length` in
    `Formal.Liveness.GameDataFixture`. -/
def taskPoolFinite : Nat := 1000

/-- LIV-003c positivity — THEOREM (was axiom). Trivial by `decide`. -/
theorem taskPoolFinite_pos : taskPoolFinite > 0 := by decide

-- Item 1g-C: accept_cancel_loop_bound axiom DELETED.
-- Was only referenced in docstrings; no proof depended on it. The
-- now-discharged lifecycle_progress_from_bounds_proven
-- (LifecycleBound7.lean) supersedes the structural intent.

/-! ## Composition residual — bridge to Phase-23b restricted form

  The composition into `cumulative_progress_under_no_wait` requires one
  more piece: connecting the lifecycle-bounded existence of a
  `.complete` phase to a strict level-increase. This is supplied by
  `Formal.Liveness.Measure.taskCompleteXpEstimate = 10` (a `def`, NOT
  an axiom) plus a small axiom packaging the cycle-step semantics of
  `completeTask`. -/

/-- Item 1e: structural building block. completeTask grants exactly
    `taskCompleteXpEstimate = 10` xp per application. Composes with
    `accept_cancel_loop_bound` (existence of phase=.complete state)
    to provide the xp-grant witness. -/
theorem lifecycle_progress_from_bounds_step
    (s : State)
    (_hCompletePhase : s.taskLifecyclePhase = .complete) :
    -- Item 1f: under the level-rollover semantics, completeTask either
    -- advances xp by 10 (no rollover) OR advances level by 1 (xp reset
    -- to 0). Both branches make "progress" in the lex (level, xp) sense.
    (Formal.Liveness.Plan.applyActionKind .completeTask s).level > s.level
    ∨ (Formal.Liveness.Plan.applyActionKind .completeTask s).xp
        = s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate := by
  -- Unfold the apply and case-split on willLevel.
  show ((if (decide (s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate
                       ≥ xpToNextLevel s.level)
              && decide (s.level < 50))
            then s.level + 1
            else s.level) > s.level)
       ∨ ((if (decide (s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate
                       ≥ xpToNextLevel s.level)
              && decide (s.level < 50))
            then 0
            else s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate)
          = s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate)
  by_cases h : (decide (s.xp + Formal.Liveness.Measure.taskCompleteXpEstimate
                          ≥ xpToNextLevel s.level)
                && decide (s.level < 50)) = true
  · left
    rw [if_pos h]
    omega
  · right
    rw [if_neg h]

-- Item 1g-C: lifecycle_progress_from_bounds axiom DELETED.
-- Discharged as THEOREM in
-- `Formal.Liveness.LifecycleBound7.lifecycle_progress_from_bounds_proven`
-- under LIV-001 + Classical.choice. The hypothesis strengthening
-- introduced in 1g-B (hfightFires forcing unbounded .fight events)
-- is preserved by the proven theorem's signature.

end Formal.Liveness.LIV003Decomposition
