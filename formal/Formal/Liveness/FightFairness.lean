import Formal.Liveness.ProductionLadder
import Formal.Liveness.CycleStep
import Formal.Liveness.CumulativeProgress
import Formal.Liveness.ReducedReachability
import Mathlib.Tactic

/-! # FightFairness — discharging `hfightFires` (O5.2 fairness, 2026-06-16)

`GlobalInvariants.hfightFires` (LevelFiftyReachable) is now SATISFIABLE thanks to
the combat-objective disjunct `objectiveStep ∧ objectiveStepIsFight` (Increment 3).
This module reduces it to a single, PRECISE runtime fairness property and proves
the reduction:

1. **Selection mechanics** (`productionLadder_eq_objectiveStep_of_unblocked`):
   when a combat objective fires (`fires .objectiveStep`) and NO higher-priority
   means fires (`objectiveStepBlockers` all quiet), the ladder SELECTS
   `objectiveStep` — so the cycle fights. This is pure `findSome?` mechanics over
   `allInLadderOrder`, fully proved.

2. **Fairness reduction** (`hfightFires_of_combat_scheduled`): if a combat
   objective is fairly scheduled — active, combat-typed, and unblocked infinitely
   often — then `hfightFires` holds. This names the EXACT remaining runtime
   obligation (`CombatObjectiveFairlyScheduled`) as a Lean Prop and discharges the
   capstone's `hfightFires` from it.

What remains (the genuine deep liveness, named exactly): proving
`CombatObjectiveFairlyScheduled` from a concrete spawn — i.e. the
`objectiveStepBlockers` (guards + the early task means) are QUIET infinitely often
(each makes bounded measure / lifecycle progress, so they cannot block the combat
objective forever) AND the planner keeps a combat objective active while level<50.
That is the blockers-are-transient argument; see docs/PLAN_obligation5_scope.md.

NO new axioms (standard set + LIV-001 via the imports' `cycleStepN`).
-/

namespace Formal.Liveness.FightFairness

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.ProductionLadder
open Formal.Liveness.CycleStep
open Formal.Liveness.CumulativeProgress

/-- The means strictly ahead of `objectiveStep` (idx 0–13) in `allInLadderOrder`.
    `productionLadder` returns the FIRST firing means, so `objectiveStep` (idx 14)
    is selected exactly when all of these are quiet and it fires. -/
def objectiveStepBlockers : List MeansKind :=
  [.hpCritical, .restForCombat, .bankUnlock, .reachUnlockLevel,
   .discardCritical, .craftRelief, .depositFull, .discardHigh, .gearReview,
   .claimPending, .completeTask, .sellPressured, .lowYieldCancel, .taskCancel]

/-- The means at/after `objectiveStep` (idx 14–22). -/
def objectiveStepSuffix : List MeansKind :=
  [.pursueTask, .acceptTask, .taskExchange, .maintainConsumables, .sellIdle, .recycleSurplus,
   .bankExpand, .wait]

/-- `allInLadderOrder` factors around `objectiveStep`. -/
theorem ladder_split_objectiveStep :
    allInLadderOrder = objectiveStepBlockers ++ MeansKind.objectiveStep :: objectiveStepSuffix := by
  decide

/-- **Selection mechanics.** When the combat objective fires and every
    higher-priority means is quiet, `productionLadder` selects `objectiveStep`. -/
theorem productionLadder_eq_objectiveStep_of_unblocked (s : State)
    (hfire : fires .objectiveStep s = true)
    (hblock : ∀ k ∈ objectiveStepBlockers, fires k s = false) :
    productionLadder s = some .objectiveStep := by
  unfold productionLadder
  rw [ladder_split_objectiveStep, List.findSome?_append]
  -- The blocker prefix yields none (all quiet).
  have hpre : objectiveStepBlockers.findSome?
      (fun k => if fires k s then some k else none) = none := by
    rw [List.findSome?_eq_none_iff]
    intro x hx
    simp [hblock x hx]
  rw [hpre, Option.none_or, List.findSome?_cons]
  simp [hfire]

/-- **The fairness obligation, as a Lean Prop.** A combat objective is *fairly
    scheduled* from `s` when, infinitely often, it fires, is combat-typed, and is
    unblocked by every higher-priority means. This is the precise runtime property
    the capstone's `hfightFires` reduces to. -/
def CombatObjectiveFairlyScheduled (s : State) : Prop :=
  ∀ N, ∃ k ≥ N,
    fires .objectiveStep (cycleStepN k s) = true
    ∧ (cycleStepN k s).objectiveStepIsFight = true
    ∧ (∀ k' ∈ objectiveStepBlockers, fires k' (cycleStepN k s) = false)

/-- **Fairness reduction.** `CombatObjectiveFairlyScheduled` discharges the
    capstone's `hfightFires` (the 3-way fight-firing disjunction). At each
    scheduled position the selection lemma turns the active-and-unblocked combat
    objective into `productionLadder = some objectiveStep`, and the combat-type
    flag supplies the `objectiveStepIsFight` conjunct. -/
theorem hfightFires_of_combat_scheduled (s : State)
    (h : CombatObjectiveFairlyScheduled s) :
    ∀ N, ∃ k ≥ N,
      productionLadder (cycleStepN k s) = some .bankUnlock
      ∨ productionLadder (cycleStepN k s) = some .reachUnlockLevel
      ∨ (productionLadder (cycleStepN k s) = some .objectiveStep
          ∧ (cycleStepN k s).objectiveStepIsFight = true) := by
  intro N
  obtain ⟨k, hkN, hfire, hisf, hblock⟩ := h N
  refine ⟨k, hkN, Or.inr (Or.inr ⟨?_, hisf⟩)⟩
  exact productionLadder_eq_objectiveStep_of_unblocked (cycleStepN k s) hfire hblock

/-! ## Transience decomposition — splitting the fairness obligation

`CombatObjectiveFairlyScheduled` bundles two SEPARATE concerns. We split them so
the planner-behaviour part and the pure-scheduling part can be discharged
independently:

- **`CombatPersistent`** — a PLANNER property: while the trajectory runs, the
  committed objective is a combat one (`objectiveStepFires ∧ objectiveStepIsFight`).
  This is a runtime obligation about goal selection (the perception-driven
  `ReachCharLevel` meta-goal stays active while underleveled); it is opaque to the
  pure `cycleStep` mechanics and so is an honest hypothesis.

- **`BlockersQuietInfinitelyOften`** — a pure SCHEDULING property: infinitely
  often, none of the 14 higher-priority means fires. This is the transience core:
  each blocker's `planFor` action CLEARS its own firing condition (e.g.
  `deleteItem` clears overstock, `depositAll` clears the deposit set, `npcSell`
  clears the sellable set, `completeTask` clears the task, the bootstrap fights
  retire on unlock), and in the model nothing re-arms it. Honest disclosure: that
  "nothing re-arms it" leans on the model abstracting away the perception refresh
  (which, in the real bot, IS what re-arms guards) — so this is an in-model
  transience; binding it to the refreshing bot is the O5.4 faithfulness question. -/
def CombatPersistent (s : State) : Prop :=
  ∀ k, fires .objectiveStep (cycleStepN k s) = true
        ∧ (cycleStepN k s).objectiveStepIsFight = true

/-- Pure scheduling: the higher-priority means are all quiet infinitely often. -/
def BlockersQuietInfinitelyOften (s : State) : Prop :=
  ∀ N, ∃ k ≥ N, ∀ b ∈ objectiveStepBlockers, fires b (cycleStepN k s) = false

/-- **Transience reduction.** A persistently-combat objective that is unblocked
    infinitely often IS fairly scheduled. Splits `CombatObjectiveFairlyScheduled`
    into the planner obligation (`CombatPersistent`) and the scheduling obligation
    (`BlockersQuietInfinitelyOften`). -/
theorem combat_scheduled_of_persistent_and_quiet (s : State)
    (hcp : CombatPersistent s) (hq : BlockersQuietInfinitelyOften s) :
    CombatObjectiveFairlyScheduled s := by
  intro N
  obtain ⟨k, hkN, hquiet⟩ := hq N
  exact ⟨k, hkN, (hcp k).1, (hcp k).2, hquiet⟩

/-- **End-to-end level-50 reachability from the fairness obligation.** Composes
    the fairness reduction with `ai_reaches_level_fifty_config_positive`: from
    spawn config-positivity (`taskExchangeMinCoins`, `nextExpansionCost` > 0 — both
    `cycleStepN`-invariant) PLUS a fairly-scheduled combat objective, the planner
    reaches level 50. No `hfightFires` hand-wave: the fight-fairness is the single
    explicit, satisfiable runtime hypothesis `CombatObjectiveFairlyScheduled`.

    This is the honest capstone: every other GlobalInvariants component is now
    discharged (hnowait unconditional; hex/hbe config-invariant), leaving exactly
    this combat-scheduling fairness — the genuine "the planner keeps fighting"
    obligation, named as a Lean Prop. -/
theorem ai_reaches_level_fifty_from_fair_combat (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (hfair : CombatObjectiveFairlyScheduled s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  Formal.Liveness.ReducedReachability.ai_reaches_level_fifty_config_positive
    s htec hnec (hfightFires_of_combat_scheduled s hfair)

/-- **End-to-end from the split obligations.** Spawn config-positivity + a
    persistently-combat objective + blockers quiet infinitely often ⇒ level 50.
    This is the cleanest honest capstone: the two remaining obligations are
    `CombatPersistent` (planner keeps a combat goal — runtime) and
    `BlockersQuietInfinitelyOften` (pure in-model scheduling transience). -/
theorem ai_reaches_level_fifty_from_persistent_combat (s : State)
    (htec : s.taskExchangeMinCoins > 0) (hnec : s.nextExpansionCost > 0)
    (hcp : CombatPersistent s) (hq : BlockersQuietInfinitelyOften s) :
    ∃ k, (cycleStepN k s).level ≥ 50 :=
  ai_reaches_level_fifty_from_fair_combat s htec hnec
    (combat_scheduled_of_persistent_and_quiet s hcp hq)

end Formal.Liveness.FightFairness
