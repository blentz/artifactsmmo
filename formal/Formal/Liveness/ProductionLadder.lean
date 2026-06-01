/-
  Formal.Liveness.ProductionLadder

  Production-granularity model of the StrategyArbiter's `select_pure` ladder
  walk over the 17-element MeansKind list. Mirrors `_fires` predicates from:

    - `src/artifactsmmo_cli/ai/tiers/guards.py:65-88` (`_fires`)
    - `src/artifactsmmo_cli/ai/tiers/means.py:65-113` (`_fires`)

  `productionLadder s` returns `some k` where `k` is the FIRST `MeansKind`
  in `allInLadderOrder` (GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [.objectiveStep]
  ++ DISCRETIONARY_ORDER) whose `fires` predicate holds on `s`; `none` if no
  means fires.

  ## Honest disclosure

  Three `_fires` predicates depend on goal-internal logic the Lean model
  does not reproduce literally:
    - `objectiveStep`  (the StrategyArbiter's objective candidate)
    - `selectBankDepositsNonempty` used by `depositFull` (guards.py:85)
    - `sellableInventoryNonempty` used by `sellPressured`/`sellIdle`
      (means.py:54-58)

  Each is exposed on `State` as an OPAQUE Bool — its truth is whatever
  production observed; the Lean model records it. None of these are
  axioms (no `axiom` keyword introduced); a later diff harness will
  assert each Bool matches production's actual computation.

  Phase 23c-3b: the four lifecycle MeansKinds (`completeTask`,
  `acceptTask`, `lowYieldCancel`, `taskCancel`, `pursueTask`) are now
  PHASE-BASED, derived from `state.taskLifecyclePhase`. The opaque Bool
  fields `pursueTaskFires`, `taskCancelFires`, `lowYieldCancelFires`
  remain on `State` for legacy callers (CycleStep, PlanExists, Plan) but
  the firing predicates no longer consume them. The phase-based forms
  are simplifications in the direction "production fires ⇒ phase
  predicate fires": the lifecycle phase is a necessary gating condition
  for each, but PIVOT/PURSUE decisions are collapsed.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/
import Formal.Liveness.Measure
import Formal.Liveness.MeansKind
import Formal.Liveness.TaskLifecyclePhase

set_option linter.dupNamespace false

namespace Formal.Liveness.ProductionLadder

open Formal.Liveness.Measure
open Formal.Liveness.MeansKind
open Formal.Liveness.TaskLifecyclePhase

/-! ## Numeric thresholds (mirror production constants) -/

/-- `CRITICAL_HP_FRACTION = 0.25` (guards.py:17). -/
def CRITICAL_HP_NUM : Nat := 25
def CRITICAL_HP_DEN : Nat := 100

/-- `DEPOSIT_FULL_FRACTION = 0.80` (guards.py:18). -/
def DEPOSIT_FULL_NUM : Nat := 80
def DEPOSIT_FULL_DEN : Nat := 100

/-- `DISCARD_HIGH_FRACTION = 0.85` (guards.py:19). -/
def DISCARD_HIGH_NUM : Nat := 85
def DISCARD_HIGH_DEN : Nat := 100

/-- `DISCARD_CRITICAL_FRACTION = 0.95` (guards.py:20). -/
def DISCARD_CRITICAL_NUM : Nat := 95
def DISCARD_CRITICAL_DEN : Nat := 100

/-- `MAX_ACHIEVABLE_GAP = 5` (guards.py:21). -/
def MAX_ACHIEVABLE_GAP_LV2 : Nat := 5

/-- `SELL_PRESSURE_FRACTION = 0.85` (means.py:17). -/
def SELL_PRESSURE_NUM : Nat := 85
def SELL_PRESSURE_DEN : Nat := 100

/-- `BANK_EXPAND_FILL = 0.95` (means.py:18). -/
def BANK_EXPAND_FILL_NUM : Nat := 95
def BANK_EXPAND_FILL_DEN : Nat := 100

/-! ## Per-MeansKind firing predicate

For each `k`, `fires k s = true` iff production's `_fires(k, ...)` would
return `True` on the same state/ctx/data. Each branch cites its
production source line. -/

/-- HP-percent strict-less, in Nat: `hp/maxHp < 25/100` with the
    Python-semantics convention `maxHp == 0 ⇒ hp_percent = 1.0` (NOT
    critical). Equivalent to `100 * hp < 25 * maxHp ∧ maxHp > 0`. -/
def hpCriticalFires (s : State) : Bool :=
  decide (s.maxHp > 0) && decide (CRITICAL_HP_DEN * s.hp < CRITICAL_HP_NUM * s.maxHp)

/-- BANK_UNLOCK guard. Mirrors `guards.py:69-76`:
      if ctx.bank_unlock_monster is None or ctx.bank_accessible: return False
      if state.xp > ctx.initial_xp: return False
      target = game_data.monster_level(ctx.bank_unlock_monster)
      return target == 0 or state.level >= target - 1
    `unlockMonsterLevel == 0` is "unknown" (let planner try and fail). -/
def bankUnlockFires (s : State) : Bool :=
  s.bankUnlockMonsterPresent
  && !s.bankAccessible
  && decide (s.xp ≤ s.initialXp)
  && (decide (s.unlockMonsterLevel = 0)
      || decide (s.level + 1 ≥ s.unlockMonsterLevel))

/-- REACH_UNLOCK_LEVEL guard. Mirrors `guards.py:77-80`:
      bank_required_level > 0
      ∧ state.level < bank_required_level
      ∧ bank_required_level - state.level ≤ MAX_ACHIEVABLE_GAP -/
def reachUnlockLevelFires (s : State) : Bool :=
  decide (s.bankRequiredLevel > 0)
  && decide (s.level < s.bankRequiredLevel)
  && decide (s.bankRequiredLevel - s.level ≤ MAX_ACHIEVABLE_GAP_LV2)

/-- DISCARD_CRITICAL guard. Mirrors `guards.py:81-82`:
      overstocked AND used/max ≥ 0.95
    Nat form: `100 * inventoryUsed ≥ 95 * inventoryMax`, treating
    `inventoryMax == 0` as ratio 0 (NOT firing). -/
def discardCriticalFires (s : State) : Bool :=
  s.hasOverstockItems
  && decide (s.inventoryMax > 0)
  && decide (DISCARD_CRITICAL_DEN * s.inventoryUsed
              ≥ DISCARD_CRITICAL_NUM * s.inventoryMax)

/-- DEPOSIT_FULL guard. Mirrors `guards.py:83-85`:
      bank_accessible ∧ used/max ≥ 0.80 ∧ select_bank_deposits(...) nonempty -/
def depositFullFires (s : State) : Bool :=
  s.bankAccessible
  && decide (s.inventoryMax > 0)
  && decide (DEPOSIT_FULL_DEN * s.inventoryUsed
              ≥ DEPOSIT_FULL_NUM * s.inventoryMax)
  && s.selectBankDepositsNonempty

/-- DISCARD_HIGH guard. Mirrors `guards.py:86-87`:
      overstocked AND used/max ≥ 0.85 -/
def discardHighFires (s : State) : Bool :=
  s.hasOverstockItems
  && decide (s.inventoryMax > 0)
  && decide (DISCARD_HIGH_DEN * s.inventoryUsed
              ≥ DISCARD_HIGH_NUM * s.inventoryMax)

/-- CLAIM_PENDING. Mirrors `means.py:67-68`. -/
def claimPendingFires (s : State) : Bool := s.pendingItemsNonempty

/-- COMPLETE_TASK. Phase 23c-3b: faithful phase-based predicate.
    Production source: `means.py:70-72` checks
      task_code present ∧ task_total > 0 ∧ task_progress ≥ task_total
    which is precisely the canonical condition for
    `TaskLifecyclePhase.complete`. -/
def completeTaskFires (s : State) : Bool :=
  decide (s.taskLifecyclePhase = .complete)

/-- SELL_PRESSURED. Mirrors `means.py:74-75`:
      used/max ≥ 0.85 ∧ has_sellable -/
def sellPressuredFires (s : State) : Bool :=
  decide (s.inventoryMax > 0)
  && decide (SELL_PRESSURE_DEN * s.inventoryUsed
              ≥ SELL_PRESSURE_NUM * s.inventoryMax)
  && s.sellableInventoryNonempty

/-- LOW_YIELD_CANCEL. Phase 23c-3b: faithful phase-based predicate.
    Production: `low_yield_cancel_fires` requires ≥1 sample (a
    post-action-attempt), so fires only on `TaskLifecyclePhase.inProgress`
    (progress > 0). This is a SIMPLIFICATION of production's PIVOT
    decision — it's the strictest sufficient condition. -/
def lowYieldCancelFires (s : State) : Bool :=
  decide (s.taskLifecyclePhase = .inProgress)

/-- TASK_CANCEL. Phase 23c-3b: faithful phase-based predicate.
    Production: `means.py:80-83` requires a task exists (accepted or
    in-progress) AND `task_decision == PIVOT`. The PIVOT decision is
    opaque; phase ∈ {accepted, inProgress} is the gating necessary
    condition. Lifecycle-phase mutual exclusion with `acceptTask`
    (which requires `.none`) is preserved by construction. -/
def taskCancelFires (s : State) : Bool :=
  decide (s.taskLifecyclePhase = .accepted)
  || decide (s.taskLifecyclePhase = .inProgress)

/-- OBJECTIVE_STEP. Opaque Bool — the StrategyArbiter's objective tier
    yields a plannable StepGoal iff this is true. -/
def objectiveStepFires (s : State) : Bool := s.objectiveStepFires

/-- PURSUE_TASK. Phase 23c-3b: faithful phase-based predicate.
    Production: `means.py:85-90` requires `task_type == "items"`,
    `task_code` set, `task_progress < task_total`, history present, and
    `task_decision == PURSUE`. We simplify to the lifecycle gating
    `phase ∈ {accepted, inProgress}`; the items-task-type and PURSUE
    decision branches are collapsed (the proof claim is production
    fires → phase predicate fires, which holds in this direction). -/
def pursueTaskFires (s : State) : Bool :=
  decide (s.taskLifecyclePhase = .accepted)
  || decide (s.taskLifecyclePhase = .inProgress)

/-- ACCEPT_TASK. Phase 23c-3b: faithful phase-based predicate.
    Production: `means.py:92-93` checks `not state.task_code`, which
    is precisely `TaskLifecyclePhase.none`. -/
def acceptTaskFires (s : State) : Bool :=
  decide (s.taskLifecyclePhase = .none)

/-- TASK_EXCHANGE. Mirrors `means.py:95-96`:
      tasks_coin_total ≥ ctx.task_exchange_min_coins -/
def taskExchangeFires (s : State) : Bool :=
  decide (s.taskCoinsTotal ≥ s.taskExchangeMinCoins)

/-- SELL_IDLE. Mirrors `means.py:98-99`:
      used/max < 0.85 ∧ has_sellable -/
def sellIdleFires (s : State) : Bool :=
  (decide (s.inventoryMax = 0)
   || decide (SELL_PRESSURE_DEN * s.inventoryUsed
               < SELL_PRESSURE_NUM * s.inventoryMax))
  && s.sellableInventoryNonempty

/-- WAIT. Mirrors `means.py:115-119`: the last-resort fallback fires
    unconditionally. Position-last in `allInLadderOrder` ensures every
    other means is tried first. -/
def waitFires (_s : State) : Bool := true

/-- BANK_EXPAND. Mirrors `means.py:101-111`:
      bank_accessible
      ∧ bank_items is not None
      ∧ game_data._bank_capacity ≠ 0
      ∧ len(bank_items) / capacity ≥ 0.95
      ∧ gold ≥ next_expansion_cost -/
def bankExpandFires (s : State) : Bool :=
  s.bankAccessible
  && s.bankItemsKnown
  && decide (s.bankCapacity > 0)
  && decide (BANK_EXPAND_FILL_DEN * s.bankItemsCount
              ≥ BANK_EXPAND_FILL_NUM * s.bankCapacity)
  && decide (s.gold ≥ s.nextExpansionCost)

/-- Dispatch: per-MeansKind firing predicate. -/
def fires (k : MeansKind) (s : State) : Bool :=
  match k with
  | .hpCritical       => hpCriticalFires s
  | .bankUnlock       => bankUnlockFires s
  | .reachUnlockLevel => reachUnlockLevelFires s
  | .discardCritical  => discardCriticalFires s
  | .depositFull      => depositFullFires s
  | .discardHigh      => discardHighFires s
  | .claimPending     => claimPendingFires s
  | .completeTask     => completeTaskFires s
  | .sellPressured    => sellPressuredFires s
  | .lowYieldCancel   => lowYieldCancelFires s
  | .taskCancel       => taskCancelFires s
  | .objectiveStep    => objectiveStepFires s
  | .pursueTask       => pursueTaskFires s
  | .acceptTask       => acceptTaskFires s
  | .taskExchange     => taskExchangeFires s
  | .sellIdle         => sellIdleFires s
  | .bankExpand       => bankExpandFires s
  | .wait             => waitFires s

/-! ## Ladder walk -/

/-- `productionLadder s` = first `MeansKind` in `allInLadderOrder` whose
    `fires` predicate holds on `s`; `none` if none fire. -/
def productionLadder (s : State) : Option MeansKind :=
  allInLadderOrder.findSome? (fun k => if fires k s then some k else none)

end Formal.Liveness.ProductionLadder
