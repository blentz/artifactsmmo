/-
  Formal.Liveness.LadderEval

  Oracle-evaluable surface for the production liveness ladder.

  `Formal.Liveness.ProductionLadder.fires` / `productionLadder` were made
  COMPUTABLE (commit 62832e3). This module provides a single COMPUTABLE
  neutral `State` literal (`inertLadderState`) onto which the Oracle entry
  `runLadder` (`Oracle.lean`) splices the firing-relevant fields read from a
  flat JSON arg layout, so the O5.4 SELECT-side differential (Brick 3) can
  compare `fires`/`productionLadder` against production's
  `_guard_fires`/`_means_fires`.

  `inertLadderState` provides the FULL field list of
  `Formal.Liveness.Measure.State` (the authoritative field roster the compiler
  enforces; `GameDataFixture.fixtureFreshState` is a convenient shape
  reference) — written inline (we do NOT import GameDataFixture, which is huge)
  — with NEUTRAL inert values: level 1, hp/maxHp 100, inventoryMax 30,
  every Bool false, every Nat 0, every Option none, every List [],
  `taskLifecyclePhase := .none`, `taskType := none`, `taskCode := none`. It is
  a plain `def` (NOT noncomputable) so the oracle can evaluate it.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.ProductionLadder

set_option linter.dupNamespace false

namespace Formal.Liveness.LadderEval

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.TaskLifecyclePhase

/-- A COMPUTABLE `State` literal with neutral inert values for every field.
    Field list mirrors `GameDataFixture.fixtureFreshState` exactly; values are
    the neutral defaults (level 1, hp/maxHp 100, inventoryMax 30, all Bool
    false, all Nat 0, all Option none, all List [], phase `.none`). The Oracle
    `runLadder` entry produces `{ inertLadderState with <args> }` and evaluates
    `fires`/`productionLadder` on it. -/
def inertLadderState : State where
  level := 1
  xp := 0
  taskProgress := 0
  taskTotal := 0
  inventoryUsed := 0
  inventoryMax := 30
  hp := 100
  maxHp := 100
  taskType := none
  taskCode := none
  trackedSkillLevel := 0
  targetSkillLevel := 0
  gold := 0
  bankAccessible := false
  bankUnlockMonsterPresent := false
  initialXp := 0
  unlockMonsterLevel := 0
  bankRequiredLevel := 0
  hasOverstockItems := false
  selectBankDepositsNonempty := false
  pendingItemsNonempty := false
  sellableInventoryNonempty := false
  recyclableSurplusNonempty := false
  bankJunkNonempty := false
  geBidCandidateNonempty := false
  geCancelTargetsNonempty := false
  taskCoinsTotal := 0
  taskExchangeMinCoins := 0
  lowYieldCancelFires := false
  taskCancelFires := false
  pursueTaskFires := false
  objectiveStepFires := false
  objectiveStepIsFight := false
  craftReliefFires := false
  restForCombatReady := false
  gearReviewFires := false
  maintainConsumablesFires := false
  supplyTargetPresent := false
  bankItemsKnown := false
  bankItemsCount := 0
  bankCapacity := 0
  nextExpansionCost := 0
  taskLifecyclePhase := .none
  actionsAttempted := 0
  craftableSlots := 0
  taskFeasibleProjected := false
  taskPool := []
  taskCodesSeen := []
  inventoryItems := []
  gatherTarget := none
  equipment := []
  equipTarget := none
  unequipTarget := none
  posX := 0
  posY := 0
  moveTarget := none
  skillXpDelta := []
  gatherSkill := none
  craftSkill := none
  skillLevels := []
  bankItemsCatalog := []
  bankGold := 0
  pendingItemCodes := []
  npcStock := []
  eventSpawns := []

/-- Non-vacuity witness for the SUPPLY_BANK rung (2026-08-01): its firing
    predicate is satisfiable — the inert state with a supply target present
    fires it. (Whether the rung can be SELECTED is a separate, weaker question
    in this model: `acceptTask`/`pursueTask`/`completeTask` are phase-based
    OVER-approximations that fire in every `taskLifecyclePhase`, so every
    discretionary rung below them — `sellIdle`, `geBid`, `wait`, and now
    `supplyBank` — is selection-unreachable here. That is a pre-existing
    property of the phase abstraction disclosed in `ProductionLadder.lean`,
    not a property of production.) -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with supplyTargetPresent := true } = true := rfl

/-- …and it is genuinely gated: the inert state does NOT fire it. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires inertLadderState = false := rfl

/-- Stable name for each `MeansKind`, matching its Lean constructor (camelCase).
    The Oracle emits one Bool field per kind under this name, plus a
    `"selected"` field carrying this name for `productionLadder`'s result. -/
def meansKindName : MeansKind → String
  | .hpCritical          => "hpCritical"
  | .restForCombat       => "restForCombat"
  | .bankUnlock          => "bankUnlock"
  | .reachUnlockLevel    => "reachUnlockLevel"
  | .geCancel            => "geCancel"
  | .discardCritical     => "discardCritical"
  | .craftRelief         => "craftRelief"
  | .recycleRelief       => "recycleRelief"
  | .sellRelief          => "sellRelief"
  | .depositFull         => "depositFull"
  | .discardHigh         => "discardHigh"
  | .gearReview          => "gearReview"
  | .craftPotions        => "craftPotions"
  | .claimPending        => "claimPending"
  | .completeTask        => "completeTask"
  | .sellPressured       => "sellPressured"
  | .lowYieldCancel      => "lowYieldCancel"
  | .taskCancel          => "taskCancel"
  | .objectiveStep       => "objectiveStep"
  | .pursueTask          => "pursueTask"
  | .acceptTask          => "acceptTask"
  | .taskExchange        => "taskExchange"
  | .maintainConsumables => "maintainConsumables"
  | .supplyBank          => "supplyBank"
  | .sellIdle            => "sellIdle"
  | .recycleSurplus      => "recycleSurplus"
  | .drainBankJunk       => "drainBankJunk"
  | .geBid               => "geBid"
  | .bankExpand          => "bankExpand"
  | .wait                => "wait"

end Formal.Liveness.LadderEval
