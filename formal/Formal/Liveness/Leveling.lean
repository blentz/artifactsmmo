import Formal.Liveness.WarmupCleared
import Formal.Liveness.SettledReach
import Mathlib.Tactic

/-! # Leveling — the REACHABLE steady-state invariant (O5.2 warm-up brick 2)

`Settled` (BlockerSettled) required `phase = .none`, which a FEASIBLE accepted task
never reaches (it parks at `.accepted`; the bot still levels). `Leveling` is the
weaker, REACHABLE invariant: `MechCleared` (the 9 monotone conditions) + a PARKED
task + a committed combat objective. A parked task is either `.none` or
`.accepted`-with-feasible — exactly the phases at which the three task-phase blockers
(completeTask / lowYieldCancel / taskCancel) are quiet, and which `.fight` preserves
(it touches neither `phase` nor `taskFeasibleProjected`, and `phase ≠ inProgress`
keeps `lowYieldCancel` quiet despite the `actionsAttempted` bump).

So `Leveling` ⇒ all 14 blockers quiet ⇒ `objectiveStep` selected ⇒ `.fight` ⇒
`Leveling` preserved. A single `Leveling` state discharges
`CombatObjectiveFairlyScheduled` and (with config-positivity) level-50 reachability —
the SAME payoff as `Settled`, but on a state the warm-up can actually reach.

NO new axioms (standard set + LIV-001 via the imports).
-/

set_option linter.dupNamespace false

namespace Formal.Liveness.Leveling

open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress
open Formal.Liveness.CycleStepCharacterization
open Formal.Liveness.FightFairness
open Formal.Liveness.BlockerSettled
open Formal.Liveness.WarmupCleared
open Formal.Liveness.SettledReach

/-- A task parked where the three task-phase blockers are quiet: either no task, or a
    feasible accepted task (which never advances while `objectiveStep` preempts
    `pursueTask`). NOT `.inProgress` (there `lowYieldCancel` can arm). -/
def TaskParked (s : State) : Prop :=
  s.taskLifecyclePhase = .none
  ∨ (s.taskLifecyclePhase = .accepted ∧ s.taskFeasibleProjected = true)

/-- The reachable steady state: monotone core cleared, task parked, combat objective on. -/
structure Leveling (s : State) : Prop where
  mech     : MechCleared s
  parked   : TaskParked s
  objFires : s.objectiveStepFires = true
  objFight : s.objectiveStepIsFight = true

/-- A parked task keeps the three task-phase blockers quiet. -/
theorem TaskParked_blockers_quiet (s : State) (h : TaskParked s) :
    fires .completeTask s = false ∧ fires .lowYieldCancel s = false
      ∧ fires .taskCancel s = false := by
  rcases h with hn | ⟨ha, hf⟩
  · refine ⟨?_, ?_, ?_⟩ <;>
      simp [fires, completeTaskFires, lowYieldCancelFires, taskCancelFires, hn]
  · refine ⟨?_, ?_, ?_⟩ <;>
      simp [fires, completeTaskFires, lowYieldCancelFires, taskCancelFires, ha, hf]

/-- At a `Leveling` state every higher-priority blocker is quiet (11 from the
    monotone core, 3 from the parked task). -/
theorem Leveling_blockers_quiet (s : State) (h : Leveling s) :
    ∀ b ∈ objectiveStepBlockers, fires b s = false := by
  obtain ⟨htc, hlyc, htcan⟩ := TaskParked_blockers_quiet s h.parked
  have hm := h.mech
  intro b hb
  fin_cases hb
  · simp only [fires, hpCriticalFires]
    rcases Nat.eq_zero_or_pos s.maxHp with hz | hpos
    · simp [hz]
    · have hlt : ¬ (CRITICAL_HP_DEN * s.hp < CRITICAL_HP_NUM * s.maxHp) := by
        rw [hm.hpFull]; simp only [CRITICAL_HP_DEN, CRITICAL_HP_NUM]; omega
      simp [hlt]
  · simp [fires, restForCombatFires, hm.hpFull]
  · simp [fires, bankUnlockFires, hm.bank]
  · simp only [fires, reachUnlockLevelFires]
    have hge : ¬ (s.level < s.bankRequiredLevel) := by have := hm.leveled; omega
    simp [hge]
  · simp [fires, discardCriticalFires, hm.overstock]
  · simp [fires, ProductionLadder.craftReliefFires, hm.craft]
  · simp [fires, depositFullFires, hm.deposits]
  · simp [fires, discardHighFires, hm.overstock]
  · simp [fires, ProductionLadder.gearReviewFires, hm.gear]
  · simp [fires, claimPendingFires, hm.pending]
  · exact htc
  · simp [fires, sellPressuredFires, hm.sellable]
  · exact hlyc
  · exact htcan

/-- At a `Leveling` state the ladder selects `objectiveStep`. -/
theorem Leveling_productionLadder (s : State) (h : Leveling s) :
    productionLadder s = some .objectiveStep := by
  apply productionLadder_eq_objectiveStep_of_unblocked
  · simp [fires, ProductionLadder.objectiveStepFires, h.objFires]
  · exact Leveling_blockers_quiet s h

/-- `.fight` preserves a parked task: it touches neither `phase` nor
    `taskFeasibleProjected`. -/
theorem TaskParked_fight (s : State) (h : TaskParked s) :
    TaskParked (applyActionKind .fight s) := by
  have hphase : (applyActionKind .fight s).taskLifecyclePhase = s.taskLifecyclePhase := by
    simp only [applyActionKind]
  have hfeas : (applyActionKind .fight s).taskFeasibleProjected = s.taskFeasibleProjected := by
    simp only [applyActionKind]
  unfold TaskParked
  rw [hphase, hfeas]
  exact h

/-- `Leveling` is `cycleStep`-invariant: the selected combat objective makes the cycle
    a `.fight`, which preserves the monotone core, the parked task, and perception. -/
theorem Leveling_cycleStep (s : State) (h : Leveling s) : Leveling (cycleStep s) := by
  have hpl : productionLadder s = some .objectiveStep := Leveling_productionLadder s h
  have hcs : cycleStep s = applyActionKind .fight s :=
    cycleStep_eq_fight_when_objectiveStepFight s hpl h.objFight
  rw [hcs]
  refine ⟨?_, ?_, ?_, ?_⟩
  · -- MechCleared preserved (via cycleStep, then rewrite by hcs).
    have := MechCleared_cycleStep s h.mech
    rwa [hcs] at this
  · exact TaskParked_fight s h.parked
  · simp only [applyActionKind]; exact h.objFires
  · simp only [applyActionKind]; exact h.objFight

theorem Leveling_cycleStepN :
    ∀ (n : Nat) (s : State), Leveling s → Leveling (cycleStepN n s)
  | 0, _, h => h
  | n + 1, s, h => by
      rw [cycleStepN_succ]
      exact Leveling_cycleStepN n (cycleStep s) (Leveling_cycleStep s h)

/-- A single `Leveling` state discharges the fairness obligation. -/
theorem combatScheduled_of_leveling (s : State) (h : Leveling s) :
    CombatObjectiveFairlyScheduled s := by
  intro N
  refine ⟨N, le_refl N, ?_, ?_, ?_⟩
  · have hN := Leveling_cycleStepN N s h
    simp [fires, ProductionLadder.objectiveStepFires, hN.objFires]
  · exact (Leveling_cycleStepN N s h).objFight
  · exact Leveling_blockers_quiet (cycleStepN N s) (Leveling_cycleStepN N s h)

/-- **End-to-end from a reachable `Leveling` state.** Config-positivity + `Leveling`
    ⇒ level 50. Same payoff as `Settled`, on a state the warm-up can reach. -/
theorem ai_reaches_level_fifty_of_leveling (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (h : Leveling s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  ai_reaches_level_fifty_from_fair_combat s htec hnec (combatScheduled_of_leveling s h)

end Formal.Liveness.Leveling
