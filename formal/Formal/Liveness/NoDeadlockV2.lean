/-
  Formal.Liveness.NoDeadlockV2

  Phase 20e-v2 step 2 — production-granularity no-deadlock headline,
  UNCONDITIONAL form.

  Theorem `productionLadder_total`:

      ∀ s, productionLadder s ≠ none

  i.e. production's StrategyArbiter ladder walk ALWAYS finds a firing
  means — no production deadlock at the dispatch level, with NO
  load-bearing invariants.

  ## Production fix backing this headline

  Phase 20e-v2 step 1 added `WaitGoal` (`src/artifactsmmo_cli/ai/goals/wait.py`)
  as the last entry in `DISCRETIONARY_ORDER`
  (`src/artifactsmmo_cli/ai/tiers/means.py:42-49`), with
  `_fires(MeansKind.WAIT, ...) = True` unconditionally
  (`means.py:115-119`). Step 2 mirrors that fix in Lean: the
  `MeansKind.wait` constructor is added to `allInLadderOrder` last, and
  `fires .wait s = true` for every `s`. The ladder walk therefore always
  returns at least `some .wait`, regardless of any state shape.

  ## Retraction record

  The previous conditional headline `productionLadder_total_under_invariants`
  required `LadderTotalInvariants` (a `taskValid` server-contract clause and
  a `pursueFiresWhenInProgress` production-side clause). Both invariants
  are now obsolete: the unconditional fix is structurally simpler and
  matches the production code. `LadderTotalInvariants` and the conditional
  theorem are deleted in this step. The unconditional theorem subsumes
  both witnesses (`acceptTask`, `completeTask`, `pursueTask`) — the
  fall-through to `wait` handles every other shape.

  No new `axiom` keyword introduced. Axioms ⊆ {propext, Classical.choice,
  Quot.sound}.

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

/-! ## Membership / fires-implies-non-none helper -/

/-- If a `k` in `allInLadderOrder` fires, the ladder walk returns `some _`. -/
theorem productionLadder_ne_none_of_fires
    {s : State} {k : MeansKind}
    (hmem : k ∈ allInLadderOrder)
    (hfires : fires k s = true) :
    productionLadder s ≠ none := by
  unfold productionLadder
  intro hnone
  rw [List.findSome?_eq_none_iff] at hnone
  have hbody : (if fires k s then some k else none) = none := by
    have := hnone k hmem
    simpa using this
  simp [hfires] at hbody

/-! ## Per-witness membership facts (decidable, by `decide`) -/

theorem wait_mem_ladder : (.wait : MeansKind) ∈ allInLadderOrder := by
  unfold allInLadderOrder; decide

/-! ## Headline theorem — UNCONDITIONAL -/

/-- Production's ladder walk always returns a firing means.
    Unconditional: the `wait` last-resort means fires for every `s`. -/
theorem productionLadder_total (s : State) : productionLadder s ≠ none := by
  refine productionLadder_ne_none_of_fires wait_mem_ladder ?_
  -- `fires .wait s = waitFires s = true`.
  change waitFires s = true
  unfold waitFires
  rfl

/-- Existential restatement: a firing means exists. Unconditional. -/
theorem exists_firing_means (s : State) : ∃ k, productionLadder s = some k := by
  have hne := productionLadder_total s
  cases h : productionLadder s with
  | none => exact (hne h).elim
  | some k => exact ⟨k, rfl⟩

end Formal.Liveness.NoDeadlockV2
