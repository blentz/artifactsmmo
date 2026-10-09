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
  objectiveStepFires := false
  objectiveStepIsFight := false
  craftReliefFires := false
  restForCombatReady := false
  maintainConsumablesFires := false
  supplyDemand := 0
  supplyAsymmetric := false
  currencyTurnInActive := false
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

/-- Non-vacuity witness for the SUPPLY_BANK predicate (2026-08-01; the fleet
    objective's supply arm since Phase 5-2c-iv): its firing
    predicate is satisfiable — the inert state carrying an at-threshold sibling
    demand fires it. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with
        supplyDemand := Formal.Liveness.ProductionLadder.SUPPLY_DEMAND_MIN }
      = true := rfl

/-- …and it is genuinely gated: the inert state (no target at all) does NOT
    fire it. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires inertLadderState = false := rfl

/-- …and the gate is a THRESHOLD, not a mere presence test: a supply target
    carrying demand one unit BELOW `SUPPLY_DEMAND_MIN` leaves the rung quiet.
    This is the Lean read-back of the human ruling's load-bearing clause —
    without it the promotion above `objectiveStep` would let siblings serve each
    other's every trivial request instead of levelling. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with
        supplyDemand := Formal.Liveness.ProductionLadder.SUPPLY_DEMAND_MIN - 1 }
      = false := rfl

/-- …and a demand well ABOVE the threshold fires it (the bulk requests — 24, 50,
    80, 120 units — that dominate the recipe graph). -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with supplyDemand := 80 } = true := rfl

/-- Non-vacuity witness for the ASYMMETRY arm (2026-08-16, role-driven-supply
    epic Task 4): its firing predicate is satisfiable at the SMALLEST possible
    demand — `supplyDemand = 1`, the live case, since every published request
    is quantity 1 and the bulk gate (`SUPPLY_DEMAND_MIN = 10`) had therefore
    never fired before this arm existed. `supplyAsymmetric := true` fires the
    rung on its own, with no help from the demand size. Same shape as
    `currencyTurnInFires`'s witness above — an opaque Bool this model cannot
    reconstruct, but state-carried as a real, reachable observation. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with supplyDemand := 1, supplyAsymmetric := true }
      = true := rfl

/-- …and it is genuinely gated: at that SAME `supplyDemand = 1` — one below the
    threshold, so the bulk arm is quiet — `supplyAsymmetric := false` leaves
    the rung quiet too. This pins the asymmetry arm's SENSITIVITY: drop the
    `|| (s.supplyAsymmetric && …)` disjunct entirely and the witness ABOVE
    (`supplyAsymmetric := true`) disagrees (`false ≠ true`) — this one alone
    is insensitive to that deletion, since `supplyAsymmetric := false` already
    makes the disjunct's left conjunct `false` either way. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with supplyDemand := 1, supplyAsymmetric := false }
      = false := rfl

/-- …and the `&& s.supplyDemand > 0` conjunct on the asymmetry arm (added over
    the brief's literal `|| s.supplyAsymmetric` — see `supplyBankFires`'s doc
    comment) is EXCLUDED at the point of definition, not merely load-bearing
    in `CycleStep.cycleStep_progress_or_waits`'s fleet-supply branch: at
    `inertLadderState`'s default `supplyDemand := 0`, `supplyAsymmetric :=
    true` alone does NOT fire the rung. Delete the conjunct and this witness
    flips to `true`, disagreeing — the pair with the `supplyDemand := 1`
    witness above pins the conjunct in both directions right here. -/
example :
    Formal.Liveness.ProductionLadder.supplyBankFires
      { inertLadderState with supplyAsymmetric := true } = false := rfl

/-- Phase 5-2c-iv: the supply demand is the FLEET OBJECTIVE's, not a rung's —
    with every guard and interrupt quiet, no task held and the opaque objective
    Bool unarmed, an at-threshold supply demand fires (and selects) the
    objective step. (2026-08-01 to Phase 5-2c-iv it selected the SUPPLY_BANK
    rung above the step.) -/
example :
    Formal.Liveness.ProductionLadder.productionLadder
      { inertLadderState with
        supplyDemand := Formal.Liveness.ProductionLadder.SUPPLY_DEMAND_MIN }
      = some MeansKind.objectiveStep := rfl

/-- …and the gate still decides: one unit below the threshold the same state
    leaves the objective step quiet. -/
example :
    Formal.Liveness.ProductionLadder.objectiveStepFires
      { inertLadderState with
        supplyDemand := Formal.Liveness.ProductionLadder.SUPPLY_DEMAND_MIN - 1 }
      = false := rfl

/-- …and guards still outrank supply, at any demand: an hp-critical state with a
    huge sibling demand rests rather than produces. -/
example :
    Formal.Liveness.ProductionLadder.productionLadder
      { inertLadderState with supplyDemand := 120, hp := 1, maxHp := 100 }
      = some MeansKind.hpCritical := rfl

/-- Non-vacuity witness for the CURRENCY_TURNIN predicate (2026-08-16, fleet-
    currency-turn-in epic Task 6): its firing predicate is SATISFIABLE — the
    inert state with `currencyTurnInActive := true` fires it. This is the same
    shape as `supplyBankFires`'s witness above: `ctx.turn_in`/`ctx.recall` are
    both `None` (hence `currencyTurnInActive = false`) on EVERY single-character
    run, but `GamePlayer._resolve_turn_in` sets one of them the cycle a `play
    --all` fleet's pooled holdings cross a vendor's price — a real, reachable
    state, not a hypothesis nothing can satisfy. -/
example :
    Formal.Liveness.ProductionLadder.currencyTurnInFires
      { inertLadderState with currencyTurnInActive := true } = true := rfl

/-- …and it is genuinely gated: the inert state (no election result at all)
    does NOT fire it — the same "inert without `--all`" shape `supplyBank` has. -/
example :
    Formal.Liveness.ProductionLadder.currencyTurnInFires inertLadderState = false := rfl

/-- Phase 5-2c-iv: a resolved election is the fleet objective's too — with
    every guard and interrupt quiet, no task held and the opaque objective Bool
    unarmed, it fires (and selects) the objective step. -/
example :
    Formal.Liveness.ProductionLadder.productionLadder
      { inertLadderState with currencyTurnInActive := true }
      = some MeansKind.objectiveStep := rfl

/-- …and guards still outrank it, at any resolved election: an hp-critical
    state with a live turn-in rests rather than transacting. -/
example :
    Formal.Liveness.ProductionLadder.productionLadder
      { inertLadderState with currencyTurnInActive := true, hp := 1, maxHp := 100 }
      = some MeansKind.hpCritical := rfl

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
  | .craftPotions        => "craftPotions"
  | .claimPending        => "claimPending"
  | .sellPressured       => "sellPressured"
  | .objectiveStep       => "objectiveStep"
  | .maintainConsumables => "maintainConsumables"
  | .sellIdle            => "sellIdle"
  | .recycleSurplus      => "recycleSurplus"
  | .drainBankJunk       => "drainBankJunk"
  | .geBid               => "geBid"
  | .bankExpand          => "bankExpand"
  | .wait                => "wait"

end Formal.Liveness.LadderEval
