import Formal.Liveness.BlockerSettled
import Formal.Liveness.GameDataInvariance
import Mathlib.Tactic

/-! # SettledReach — reaching `Settled`, and the perception frontier (O5.2)

Two results that pin down exactly what remains for full level-50 reachability:

1. **`reach_fifty_of_eventually_settled`** — if the trajectory EVER reaches a
   `Settled` state, the planner reaches level 50. The config-positivity carries
   from spawn (those fields are `cycleStepN`-invariant), so the WHOLE obligation
   reduces to the single reachability fact `∃K, Settled (cycleStepN K s)`.

2. **`Settled_unreachable_without_perception`** — the honest O5.4 frontier: in the
   pure `cycleStep` MODEL, `objectiveStepFires` is NEVER set `true` by any action
   (only ever cleared — verified against `Plan.lean`). So if it is `false` at spawn
   it stays `false`, and `Settled` (which requires a committed combat objective) is
   UNREACHABLE. ⇒ reaching `Settled` fundamentally requires PERCEPTION to supply the
   combat objective; it is not producible by the model's pure transition. This is
   exactly the O5.4 select/perception binding obligation, now PROVEN rather than
   asserted — the model honestly cannot fabricate the planner's goal commitment.

NO new axioms (standard set + LIV-001 via the imports).
-/

namespace Formal.Liveness.SettledReach

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.GameDataInvariance
open Formal.Liveness.BlockerSettled

/-- **Reaching `Settled` suffices.** Config-positivity is `cycleStepN`-invariant, so
    an eventually-`Settled` trajectory reaches level 50 — the entire obligation
    collapses to `∃K, Settled (cycleStepN K s)`. -/
theorem reach_fifty_of_eventually_settled (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (K : Nat) (h : Settled (cycleStepN K s)) :
    ∃ k, (cycleStepN k s).level ≥ 50 := by
  have htecK : (cycleStepN K s).taskExchangeMinCoins > 0 := by
    rw [cycleStepN_taskExchangeMinCoins_invariant]; exact htec
  have hnecK : (cycleStepN K s).nextExpansionCost > 0 := by
    rw [cycleStepN_nextExpansionCost_invariant]; exact hnec
  obtain ⟨k', hk'⟩ := ai_reaches_level_fifty_of_settled (cycleStepN K s) htecK hnecK h
  exact ⟨K + k', by rw [cycleStepN_add]; exact hk'⟩

/-! ## The perception frontier: `objectiveStepFires` is never set true in-model -/

theorem objectiveStepFires_false_apply (a : ActionKind) (s : State)
    (h : s.objectiveStepFires = false) :
    (applyActionKind a s).objectiveStepFires = false := by
  cases a
  case move => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  case mapTransition => simp only [applyActionKind]; rcases s.moveTarget with _ | ⟨tx, ty⟩ <;> exact h
  all_goals first | exact h | (simp [applyActionKind])

theorem objectiveStepFires_false_cycleStep (s : State) (h : s.objectiveStepFires = false) :
    (cycleStep s).objectiveStepFires = false := by
  unfold cycleStep
  split
  · exact h
  · split
    · exact h
    · exact objectiveStepFires_false_apply _ s h

theorem objectiveStepFires_false_cycleStepN :
    ∀ (n : Nat) (s : State), s.objectiveStepFires = false →
      (cycleStepN n s).objectiveStepFires = false
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact objectiveStepFires_false_cycleStepN n (cycleStep s)
        (objectiveStepFires_false_cycleStep s h)

/-- **The O5.4 perception frontier.** If no combat objective is committed at spawn
    (`objectiveStepFires = false`), the pure model NEVER reaches a `Settled` state —
    because no action turns `objectiveStepFires` on. Reaching `Settled` (and hence
    level 50 via the general leveling path) therefore REQUIRES perception to supply
    the combat objective: it is not producible by the model's transition alone. -/
theorem Settled_unreachable_without_perception (s : State)
    (h : s.objectiveStepFires = false) (n : Nat) :
    ¬ Settled (cycleStepN n s) := by
  intro hset
  have hfalse := objectiveStepFires_false_cycleStepN n s h
  rw [hset.objFires] at hfalse
  exact Bool.noConfusion hfalse

end Formal.Liveness.SettledReach
