/-
  Formal.Liveness.NoDeadlockV2

  Phase 20c-v2 — production-granularity no-deadlock headline.

  Theorem `productionLadder_total_under_invariants`:

      ∀ s, LadderTotalInvariants s → productionLadder s ≠ none

  i.e. under load-bearing modelling invariants on `State`, production's
  StrategyArbiter ladder walk (`Formal.Liveness.ProductionLadder.productionLadder`)
  ALWAYS finds a firing means — no production deadlock at the dispatch level.

  ## Headline form

  This is INTEGRITY form 2 (conditional headline with explicit invariants),
  NOT form 1 (unconditional). The unconditional headline is FALSE under
  faithful production semantics: the deadlock state

      s.taskCode.isSome ∧ s.taskTotal > 0 ∧ s.taskProgress < s.taskTotal
      ∧ s.pursueTaskFires = false
      ∧ <every other 16 _fires predicate is false>

  is structurally constructible in the Lean `State` (the opaque Bools can
  all be false independently). Whether it is reachable in production is a
  separate question that the Phase 20d-v2 differential / production-side
  audit must answer. Disclosing the invariants here keeps the headline
  honest — the invariants are not buried in a structure and silently
  assumed; they are part of the theorem statement.

  ## Load-bearing invariants

  `LadderTotalInvariants` bundles two clauses, each citing its production /
  server source:

  1. `taskValid`: `s.taskCode.isSome → s.taskTotal > 0`.

     Server contract on paired task fields. Per openapi.spec
     `/v3/characters/{name}` (see `artifactsmmo-api-client` generated
     `character_schema.task` / `task_total`), `task` and `task_total` are
     populated together — a character either has no task (both null/zero)
     or has an active task with a nonzero total. Production observes this
     by perceive (`src/.../perceive.py`); the AI never synthesises a
     phantom task.

     This is the same structural invariant that earlier Phase 20c-1
     (retracted) used. We re-introduce it as a State invariant here rather
     than baking it into the `State` structure itself, so the load-bearing
     commitment is visible in the theorem statement.

  2. `pursueFiresWhenInProgress`: when `taskCode.isSome ∧
     taskProgress < taskTotal`, the opaque Bool `s.pursueTaskFires` must
     be `true`.

     Production rationale: when the player has a task in progress (not
     yet complete) and no higher-priority means fires, `PursueTaskGoal`
     is the discretionary means that drives task progress. Production's
     `PursueTaskGoal._fires` (means.py:85-90) consolidates the gating;
     in the ladder-fallthrough case (no completion, no overstock, no
     bank pressure, no sell pressure, etc.), it returns `True`. If
     production's `_fires` returned False in this state, the AI would
     genuinely deadlock — Phase 20d-v2's differential MUST exercise this
     invariant and surface any state where production violates it.

  No new `axiom` keyword is introduced. The invariants are propositions
  on `State` that callers must discharge; the proof exposes the precise
  modelling commitment rather than hiding it.

  ## Theorem-internal case structure

  `productionLadder s = none` iff every `fires k s = false` for
  `k ∈ allInLadderOrder`. We exhibit a firing witness:

    * `s.taskCode.isNone`              ↦  `.acceptTask`   (acceptTaskFires)
    * `s.taskCode.isSome`,
      `taskProgress ≥ taskTotal`,
      `taskTotal > 0` (by `taskValid`) ↦  `.completeTask` (completeTaskFires)
    * `s.taskCode.isSome`,
      `taskProgress < taskTotal`        ↦  `.pursueTask`  (pursueTaskFires,
                                                           by invariant)

  All three witnesses appear in `allInLadderOrder`, so `findSome?` returns
  some-something (not necessarily the witness, but ≠ none).

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.ProductionLadder

set_option linter.dupNamespace false
set_option linter.unusedVariables false

namespace Formal.Liveness.NoDeadlockV2

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder

/-! ## Load-bearing modelling invariants -/

/-- Bundled invariants required for `productionLadder` totality.
    See module docstring for the per-clause production / server citation. -/
structure LadderTotalInvariants (s : State) : Prop where
  /-- Server-contract invariant: `task` and `task_total` are paired.
      Openapi `/v3/characters/{name}` schema. -/
  taskValid :
    s.taskCode.isSome = true → s.taskTotal > 0
  /-- Production-side coverage invariant: a task that is in progress
      (not yet complete) triggers `PursueTaskGoal._fires`. -/
  pursueFiresWhenInProgress :
    s.taskCode.isSome = true →
    s.taskProgress < s.taskTotal →
    s.pursueTaskFires = true

/-! ## Membership / fires-implies-non-none helpers -/

/-- If a `k` in `allInLadderOrder` fires, the ladder walk returns `some _`. -/
theorem productionLadder_ne_none_of_fires
    {s : State} {k : MeansKind}
    (hmem : k ∈ allInLadderOrder)
    (hfires : fires k s = true) :
    productionLadder s ≠ none := by
  unfold productionLadder
  -- `List.findSome?` over a `fun k => if fires k s then some k else none`.
  -- If any `k` in the list satisfies the predicate, the result is `some _`.
  -- We prove by induction on the list, tracking the membership hypothesis.
  intro hnone
  -- Convert `findSome? = none` to "for all in list, the body returns none".
  rw [List.findSome?_eq_none_iff] at hnone
  have hbody : (if fires k s then some k else none) = none := by
    have := hnone k hmem
    simpa using this
  -- But fires k s = true ⇒ body = some k ≠ none. Contradiction.
  simp [hfires] at hbody

/-! ## Per-witness membership facts (decidable, by `decide`) -/

theorem acceptTask_mem_ladder : (.acceptTask : MeansKind) ∈ allInLadderOrder := by
  unfold allInLadderOrder; decide

theorem completeTask_mem_ladder : (.completeTask : MeansKind) ∈ allInLadderOrder := by
  unfold allInLadderOrder; decide

theorem pursueTask_mem_ladder : (.pursueTask : MeansKind) ∈ allInLadderOrder := by
  unfold allInLadderOrder; decide

/-! ## Headline theorem -/

/-- Production's ladder walk always returns a firing means, under the
    load-bearing invariants. -/
theorem productionLadder_total_under_invariants
    (s : State) (inv : LadderTotalInvariants s) :
    productionLadder s ≠ none := by
  -- Case-split on whether the character has a task.
  by_cases hcode : s.taskCode.isSome = true
  · -- Has a task; taskValid gives taskTotal > 0.
    have htot_pos : s.taskTotal > 0 := inv.taskValid hcode
    -- Sub-case on progress.
    by_cases hprog : s.taskProgress ≥ s.taskTotal
    · -- COMPLETE_TASK fires.
      refine productionLadder_ne_none_of_fires completeTask_mem_ladder ?_
      change completeTaskFires s = true
      unfold completeTaskFires
      simp [hcode, htot_pos, hprog]
    · -- Progress strictly less ⇒ pursueTask fires by invariant.
      have hprog_lt : s.taskProgress < s.taskTotal := Nat.lt_of_not_ge hprog
      have hpursue : s.pursueTaskFires = true :=
        inv.pursueFiresWhenInProgress hcode hprog_lt
      refine productionLadder_ne_none_of_fires pursueTask_mem_ladder ?_
      change pursueTaskFires s = true
      unfold ProductionLadder.pursueTaskFires
      exact hpursue
  · -- No task ⇒ acceptTask fires.
    refine productionLadder_ne_none_of_fires acceptTask_mem_ladder ?_
    change acceptTaskFires s = true
    unfold acceptTaskFires
    -- hcode : ¬ s.taskCode.isSome = true
    -- Want: s.taskCode.isNone = true
    cases hc : s.taskCode with
    | none => rfl
    | some v =>
      exfalso; apply hcode
      simp [hc]

/-- Existential restatement: a firing means exists.
    Equivalent to the headline via `Option.ne_none_iff_exists'`. -/
theorem exists_firing_means_under_invariants
    (s : State) (inv : LadderTotalInvariants s) :
    ∃ k, productionLadder s = some k := by
  have hne := productionLadder_total_under_invariants s inv
  cases h : productionLadder s with
  | none => exact (hne h).elim
  | some k => exact ⟨k, rfl⟩

end Formal.Liveness.NoDeadlockV2
