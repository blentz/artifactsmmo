import Formal.Liveness.BlockerSettled
import Formal.Liveness.GameDataFixture

/-! # SettledWitness — `Settled` is satisfiable (anti-vacuity, O5.2)

`ai_reaches_level_fifty_of_settled` is only meaningful if `Settled` is inhabited —
otherwise the capstone would be vacuously true on a `False` hypothesis. We exhibit a
concrete witness: the live `fixtureFreshState` (bank already accessible, full hp,
empty inventory, level ≥ bankRequiredLevel) with the task parked at `.none` and a
combat objective committed. This proves `Settled` is consistent, so the
`Settled`-gated reachability is a genuine implication, not a vacuity.

NO new axioms.
-/

namespace Formal.Liveness.SettledWitness

open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.BlockerSettled
open Formal.Liveness.GameDataFixture

/-- A concrete `Settled` state: the fresh fixture, task parked, combat objective on. -/
noncomputable def settledWitness : State :=
  { fixtureFreshState with
      taskLifecyclePhase := .none
      objectiveStepFires := true
      objectiveStepIsFight := true }

/-- `Settled` is satisfiable. -/
theorem settledWitness_isSettled : Settled settledWitness := by
  refine ⟨?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_, ?_⟩ <;>
    first | rfl | decide

/-- **A concrete, hypothesis-free level-50 reachability** (modulo only LIV-001). The
    witness discharges BOTH spawn config-positivity (`taskExchangeMinCoins = 1`,
    `nextExpansionCost = 1`) AND `Settled`, so `ai_reaches_level_fifty_of_settled`
    closes with no remaining hypotheses: from this real state the planner provably
    iterates `cycleStep` to level 50. This is a fully-grounded instance of the
    capstone — the honest, non-vacuous payoff of the O5.2 work. -/
theorem settledWitness_reaches_fifty :
    ∃ k, (cycleStepN k settledWitness).level ≥ 50 :=
  ai_reaches_level_fifty_of_settled settledWitness (by decide) (by decide)
    settledWitness_isSettled

end Formal.Liveness.SettledWitness
