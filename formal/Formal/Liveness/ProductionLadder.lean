/-
  Formal.Liveness.ProductionLadder

  Production-granularity model of the StrategyArbiter's `select_pure` ladder
  walk over `Formal.Liveness.MeansKind.allInLadderOrder` — GUARD_ORDER ++
  COLLECT_REWARD_ORDER ++ [OBJECTIVE_STEP] ++ DISCRETIONARY_ORDER, i.e. every
  `MeansKind` constructor exactly once, in production's candidate preorder.
  (A literal element count used to be restated here; it drifted, so the walk is
  now described by the list it actually iterates.) Mirrors `_fires` predicates
  from:

    - `src/artifactsmmo_cli/ai/tiers/guards.py:65-88` (`_fires`)
    - `src/artifactsmmo_cli/ai/tiers/means.py:65-113` (`_fires`)

  `productionLadder s` returns `some k` where `k` is the FIRST `MeansKind`
  in `allInLadderOrder` (GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [.objectiveStep]
  ++ DISCRETIONARY_ORDER) whose `fires` predicate holds on `s`; `none` if no
  means fires.

  ## Honest disclosure

  Five `_fires` predicates depend on goal-internal or out-of-model logic the
  Lean model does not reproduce literally:
    - `objectiveStep`  (the StrategyArbiter's objective candidate)
    - `supplyBank`     (`ctx.supply_target`/`ctx.asymmetric_demand`, computed
                       from the cross-character coordination DB — outside this
                       single-character model. Carried as the opaque Nat
                       `supplyDemand` plus the opaque Bool `supplyAsymmetric`
                       rather than a single Bool, because since 2026-08-01 the
                       rung is gated on that demand clearing
                       `SUPPLY_DEMAND_MIN` OR (since 2026-08-16) the requested
                       item being asymmetric — not merely on a target existing)
    - `currencyTurnIn` (`ctx.turn_in`/`ctx.recall`, computed from the fleet
                       coordination DB and the per-cycle election in
                       `GamePlayer._resolve_turn_in` — outside this
                       single-character model. Carried as the opaque Bool
                       `currencyTurnInActive`; no threshold, since
                       `turn_in_ready_pure` already gates `ctx.turn_in` itself)
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

/-- Phase 23d-5 / Perimeter-hardening (post-Phase-24): graduated from
    AXIOM to DEF. Production's `low_yield_cancel_fires`
    (src/.../learning/projections.py:384) short-circuits to False when
    `sample_count == 0`. So the empirical threshold is exactly 1 —
    after the first sample the boundary check can trigger. Hard-coded
    literal mirrors production. -/
def lowYieldSampleThreshold : Nat := 1

/-- LIV-003b positivity — THEOREM (was axiom). Trivial by `decide`. -/
theorem lowYieldSampleThreshold_pos : lowYieldSampleThreshold > 0 := by decide

/-! ## Numeric thresholds (mirror production constants) -/

/-- `CRITICAL_HP_FRACTION = 0.75` (thresholds.py). Raised from 0.25; every proof
using this mirror is an "HP-full ⇒ critical guard does not fire" lemma
(`¬ (CRITICAL_HP_DEN * maxHp < CRITICAL_HP_NUM * maxHp)`), which closes for any
`NUM < DEN`, so 75 < 100 keeps them all valid. -/
def CRITICAL_HP_NUM : Nat := 75
def CRITICAL_HP_DEN : Nat := 100

/-- `DEPOSIT_FULL_FRACTION = 0.90` (guards.py; raised from 0.80 per spec
2026-06-07 so it stays STRICTLY ABOVE the deposit ramp start 0.85 — the
`fires(DEPOSIT_FULL) ⇒ depositInventoryValue > 0` invariant in
Formal.Liveness.MeansFiring requires DEPOSIT_FULL_FRACTION > depositRampStart). -/
def DEPOSIT_FULL_NUM : Nat := 90
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

/-- HP-percent strict-less, in Nat: `hp/maxHp < 75/100` with the
    Python-semantics convention `maxHp == 0 ⇒ hp_percent = 1.0` (NOT
    critical). Equivalent to `100 * hp < 75 * maxHp ∧ maxHp > 0`. -/
def hpCriticalFires (s : State) : Bool :=
  decide (s.maxHp > 0) && decide (CRITICAL_HP_DEN * s.hp < CRITICAL_HP_NUM * s.maxHp)

/-- REST_FOR_COMBAT guard. Mirrors `guards.py:89-108`:
      if ctx.combat_monster is None: return False
      if state.hp >= state.max_hp: return False
      if predict_win(state, …): return False
      return predict_win(state @ max_hp, …)
    Clauses (a)/(c)/(d) — combat target present, not winnable at current hp,
    winnable at max hp — are folded into the opaque `restForCombatReady`
    Bool. Clause (b) — `state.hp < state.max_hp` (Rest is actionable) — is
    checked numerically here so the cycle-step progress proof can derive
    `hp ≠ maxHp` for the `.rest` witness. -/
def restForCombatFires (s : State) : Bool :=
  s.restForCombatReady && decide (s.hp < s.maxHp)

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

/-- The bank can physically accept a deposit: accessible, item-count known,
    and used strictly below capacity. Mirrors `ai/bank_room.bank_has_room`.
    `bankItemsKnown=false` (bank unvisited) and `bankCapacity=0` both read as
    NO room. -/
def bankHasRoom (s : State) : Bool :=
  s.bankAccessible && s.bankItemsKnown && decide (s.bankItemsCount < s.bankCapacity)

/-- DISCARD_CRITICAL guard. Mirrors `guards.py` DISCARD_CRITICAL branch:
      ¬bank_has_room AND overstocked AND used/max ≥ 0.95
    Nat form: `100 * inventoryUsed ≥ 95 * inventoryMax`, treating
    `inventoryMax == 0` as ratio 0 (NOT firing).
    2026-06-24: dropped the `!(bankHasRoom s)` gate — genuine overstock (above
    the need/value cap; the active profile protects what the goal needs) is shed
    regardless of bank room (don't hoard junk). DISCARD_CRITICAL outranks
    DEPOSIT_FULL in the ladder, so it now preempts the deposit when overstocked
    at the critical watermark. -/
def discardCriticalFires (s : State) : Bool :=
  s.hasOverstockItems
  && decide (s.inventoryMax > 0)
  && decide (DISCARD_CRITICAL_DEN * s.inventoryUsed
              ≥ DISCARD_CRITICAL_NUM * s.inventoryMax)

/-- DEPOSIT_FULL guard. Mirrors `guards.py` DEPOSIT_FULL branch:
      bank_accessible ∧ bank_has_room ∧ used/max ≥ 0.90 ∧ select_bank_deposits(...) nonempty
    Task 2: added `bankHasRoom s` conjunct so the guard is gated on the bank
    having a free slot (bank not full). -/
def depositFullFires (s : State) : Bool :=
  s.bankAccessible
  && bankHasRoom s
  && decide (s.inventoryMax > 0)
  && decide (DEPOSIT_FULL_DEN * s.inventoryUsed
              ≥ DEPOSIT_FULL_NUM * s.inventoryMax)
  && s.selectBankDepositsNonempty

/-- DISCARD_HIGH guard. Mirrors `guards.py` DISCARD_HIGH branch:
      ¬bank_has_room AND overstocked AND used/max ≥ 0.85
    2026-06-24: dropped the `!(bankHasRoom s)` gate (see discardCriticalFires).
    DISCARD_HIGH is BELOW DEPOSIT_FULL in the ladder, so the deposit buffer fires
    first and DISCARD_HIGH sheds the residual junk overstock. -/
def discardHighFires (s : State) : Bool :=
  s.hasOverstockItems
  && decide (s.inventoryMax > 0)
  && decide (DISCARD_HIGH_DEN * s.inventoryUsed
              ≥ DISCARD_HIGH_NUM * s.inventoryMax)

/-- GEAR_REVIEW guard. Mirrors `guards.py:137-138`:
      return ctx.gear_review_active
    Opaque Bool — the Lean state carries production's `ctx.gear_review_active`
    latch; a diff harness asserts agreement. -/
def gearReviewFires (s : State) : Bool := s.gearReviewFires

/-- CRAFT_POTIONS guard. Mirrors `guards.py::_fires(GuardKind.CRAFT_POTIONS, …)`:
      return craft_potions_fires(state, game_data)
    Opaque Bool — the Lean state carries production's answer; a diff harness
    asserts agreement. Cleared by the `.craft` apply (CraftPotions goal). -/
def craftPotionsFires (s : State) : Bool := s.craftPotionsFires

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

/-- LOW_YIELD_CANCEL. Phase 23d-5 — substantive sample-count gate.
    Production: `low_yield_fires_pure` (low_yield_boundary.py:60) requires
    `farm_samples ≥ LOW_YIELD_SAMPLE_THRESHOLD` (production = 1) before
    firing. The Lean model gates on `actionsAttempted ≥
    lowYieldSampleThreshold`, where `actionsAttempted` is the per-task
    counter bumped by progress-attempting applies (Phase 23d-4) and
    `lowYieldSampleThreshold` is the opaque positive `Nat` declared above.
    Restricted to in-progress phase (the only phase where farm samples
    accrue against an active task). -/
def lowYieldCancelFires (s : State) : Bool :=
  decide (s.taskLifecyclePhase = .inProgress)
  && decide (s.actionsAttempted ≥ lowYieldSampleThreshold)

/-- TASK_CANCEL. Phase 23c-3b: faithful phase-based predicate.
    Production: `means.py:80-83` requires a task exists (accepted or
    in-progress) AND `task_decision == PIVOT`. The PIVOT decision is
    opaque; phase ∈ {accepted, inProgress} is the gating necessary
    condition. Lifecycle-phase mutual exclusion with `acceptTask`
    (which requires `.none`) is preserved by construction. -/
def taskCancelFires (s : State) : Bool :=
  (decide (s.taskLifecyclePhase = .accepted)
   || decide (s.taskLifecyclePhase = .inProgress))
  && !s.taskFeasibleProjected
  -- Item 1d: refined to gate on `taskFeasibleProjected`. Mirrors
  -- production task_decision == PIVOT semantics.

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
  decide (s.taskLifecyclePhase = .none) && s.drawOwed

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

/-- RECYCLE_SURPLUS. Mirrors `means.py::_fires(RECYCLE_SURPLUS, …)`:
      used/max < 0.85 ∧ recyclable_surplus nonempty -/
def recycleSurplusFires (s : State) : Bool :=
  (decide (s.inventoryMax = 0)
   || decide (SELL_PRESSURE_DEN * s.inventoryUsed
               < SELL_PRESSURE_NUM * s.inventoryMax))
  && s.recyclableSurplusNonempty

/-- DRAIN_BANK_JUNK. Mirrors `means.py::_fires(DRAIN_BANK_JUNK, …)`:
      used/max < 0.85 ∧ bank_drain_excess nonempty -/
def drainBankJunkFires (s : State) : Bool :=
  (decide (s.inventoryMax = 0)
   || decide (SELL_PRESSURE_DEN * s.inventoryUsed
               < SELL_PRESSURE_NUM * s.inventoryMax))
  && s.bankJunkNonempty

/-- GE_BID. Mirrors `means.py::_fires(GE_BID, …)`: `bool(ge_bid_candidates(...))`.
    NO pressure gate — the Python guard fires purely on the candidate set being
    nonempty (the opaque `geBidCandidateNonempty` signal). -/
def geBidFires (s : State) : Bool :=
  s.geBidCandidateNonempty

/-- MAINTAIN_CONSUMABLES (PLAN #6a). Mirrors `means.py::_fires(MAINTAIN_CONSUMABLES, …)`:
    combat-active ∧ heal-stock < floor ∧ a better heal is craftable. Opaque
    State-carried Bool (see `Measure.State.maintainConsumablesFires`). -/
def maintainConsumablesFires (s : State) : Bool := s.maintainConsumablesFires

/-- SUPPLY_BANK demand gate (2026-08-01 human ruling). Mirrors
    `means.py::SUPPLY_DEMAND_MIN`. The rung was promoted out of
    DISCRETIONARY_ORDER into COLLECT_REWARD_ORDER, i.e. ABOVE `objectiveStep`;
    this threshold is what keeps that promotion from letting a fleet of siblings
    serve each other's every request instead of levelling. Derived from data,
    not chosen: every non-null `supply_target` in the 44 recorded
    `play-trace-*.jsonl` runs carried demand exactly 10, and over all 321
    craftable roots in `formal/sim/game_data_snapshot.json` no root's LARGEST
    base-material closure demand lands on 8 or 9 — an empty band, so any
    threshold in 8..10 partitions the roots identically (53 below, 268 at or
    above). See the constant's comment block in `tiers/means.py` for the full
    distribution and for what the gate buys and gives up. -/
def SUPPLY_DEMAND_MIN : Nat := 10

/-- The threshold is POSITIVE. Load-bearing, not cosmetic: it is what makes
    modelling "supply target present ∧ demand ≥ threshold" by the single Nat
    `supplyDemand` faithful — `supplyDemand = 0` (no target) is quiet exactly
    because the threshold exceeds 0. See `State.supplyDemand`. -/
theorem SUPPLY_DEMAND_MIN_pos : SUPPLY_DEMAND_MIN > 0 := by decide

/-- SUPPLY_BANK (2026-08-01, asymmetry arm added 2026-08-16 role-driven-supply
    epic Task 4). Mirrors `means.py::_fires(SUPPLY_BANK, …)` =
    `ctx.supply_target is not None and (ctx.supply_target[2] >=
    SUPPLY_DEMAND_MIN or ctx.supply_target[0] in ctx.asymmetric_demand)`: fires
    when some unexpired sibling demand is servable by this character's role AND
    EITHER that demand is substantial enough to justify pausing this
    character's own objective step for a production run, OR the requested item
    is asymmetric — at least one sibling that asked for it is skill-gated out
    of producing it itself, the case that makes holding a role worth anything
    regardless of request size. The demand and the asymmetry flag are both
    opaque `State` fields because they are computed from the coordination DB,
    which this model does not reproduce — the same honest-disclosure treatment
    `objectiveStep` gets.

    The asymmetry arm carries an extra `s.supplyDemand > 0` conjunct that
    `_fires`'s Python `target[0] in ctx.asymmetric_demand` does not: NOT a
    behavioural deviation — production's own data never yields a target with
    demand 0 (`supplyDemand`'s doc comment on `State`; the guarantee is
    enforced on the WRITE side, `coordination_store.py::publish_demand`'s
    `if quantity > 0` guard on its sole `MaterialDemand` insert — NOT inside
    `_pick_supply_target`, which merely reads back rows that guard already
    filtered), so `ctx.asymmetric_demand` membership only ever coincides with
    `target[2] ≥ 1` in every REAL state, the same way `SUPPLY_DEMAND_MIN_pos`
    already makes the bulk arm's `supplyDemand > 0` derivation sound. Unlike
    that Nat-valued field, `supplyAsymmetric` is a free `Bool` with no
    structural link back to `supplyDemand`, so the Lean model — which must
    stay total over EVERY `State`, not just production-reachable ones —
    can otherwise construct a "junk" state (`supplyAsymmetric := true`,
    `supplyDemand := 0`) production never emits. Without the conjunct that
    junk state would fire the rung while `.gather`'s saturating
    `supplyDemand - 1` apply (`Plan.lean`) makes zero progress, falsifying
    `BlockerDescent.descends_supplyBank`'s hypothesis-free descent over ALL
    states. The conjunct closes that Lean-only gap without touching any
    observable behaviour on a real trace. -/
def supplyBankFires (s : State) : Bool :=
  decide (s.supplyDemand ≥ SUPPLY_DEMAND_MIN) ||
    (s.supplyAsymmetric && decide (s.supplyDemand > 0))

/-- CURRENCY_TURNIN (2026-08-16, fleet-currency-turn-in epic Task 6). Mirrors
    `means.py::_fires(CURRENCY_TURNIN, …)` = `ctx.turn_in is not None or
    ctx.recall is not None`: fires for BOTH sides of a resolved fleet election
    — the elected buyer or a losing candidate asked to surrender. No demand
    threshold (unlike `supplyBankFires`): `turn_in_ready_pure` already requires
    the full vendor price be reachable before `ctx.turn_in` is ever set. The
    flag is an opaque `State` field because it is computed from the
    coordination DB / election logic this model does not reproduce — the same
    honest-disclosure treatment `objectiveStep`/`supplyBank` get. -/
def currencyTurnInFires (s : State) : Bool := s.currencyTurnInActive

/-- WAIT. Mirrors `means.py:115-119`: the last-resort fallback fires
    unconditionally. Position-last in `allInLadderOrder` ensures every
    other means is tried first. -/
def waitFires (_s : State) : Bool := true

/-- BANK_EXPAND. Mirrors `means.py::_fires(BANK_EXPAND, …)`, which since
    2026-07-06 delegates to the proven `should_expand_bank` core:
      bank_accessible
      ∧ bank_items is not None
      ∧ game_data._bank_capacity ≠ 0
      ∧ used * FILL_DEN ≥ capacity * FILL_NUM   (exact 95/100 cross-multiply)
      ∧ gold ≥ next_expansion_cost + goldReserve  (the reserve SAFETY gate:
        the purchase never drains gold below the progression reserve;
        `goldReserve` mirrors `reserve_floor(state, game_data, None)`). -/
def bankExpandFires (s : State) : Bool :=
  s.bankAccessible
  && s.bankItemsKnown
  && decide (s.bankCapacity > 0)
  && decide (BANK_EXPAND_FILL_DEN * s.bankItemsCount
              ≥ BANK_EXPAND_FILL_NUM * s.bankCapacity)
  && decide (s.gold ≥ s.nextExpansionCost + s.goldReserve)

/-- CRAFT_RELIEF. Mirrors `tiers/guards.py::_fires(CRAFT_RELIEF, …)`:
    fires when inv pressure crosses `CRAFT_RELIEF_FRACTION` (0.70) AND a
    goal item is craftable from current inventory. Opaque Bool — the
    Lean state carries production's answer (see `Measure.State`); a diff
    harness asserts agreement with `craft_relief_candidates`. -/
def craftReliefFires (s : State) : Bool := s.craftReliefFires

/-- GE_CANCEL. Mirrors `tiers/guards.py::_fires(GE_CANCEL, …)`: fires iff
    `cancel_selection.cancel_targets(...)` is nonempty. NO pressure gate — the
    guard's Python `_fires` is exactly `bool(cancel_targets(...))`, mirroring the
    fire-and-lose shape of `geBidFires`. -/
def geCancelFires (s : State) : Bool := s.geCancelTargetsNonempty

/-- RECYCLE_RELIEF. Mirrors `tiers/guards.py::_fires(RECYCLE_RELIEF, …)`:
    bank full (not bankHasRoom) AND recyclable surplus nonempty. -/
def recycleReliefFires (s : State) : Bool :=
  !(bankHasRoom s) && s.recyclableSurplusNonempty

/-- SELL_RELIEF. Mirrors `tiers/guards.py::_fires(SELL_RELIEF, …)`:
    bank full (not bankHasRoom) AND sellable inventory nonempty. -/
def sellReliefFires (s : State) : Bool :=
  !(bankHasRoom s) && s.sellableInventoryNonempty

/-- Dispatch: per-MeansKind firing predicate. Computable — every branch reads
    State fields / decides concrete predicates (`lowYieldSampleThreshold` is the
    concrete `def := 1`, not an axiom), so the ladder is oracle-evaluable for the
    O5.4 SELECT-side differential. -/
def fires (k : MeansKind) (s : State) : Bool :=
  match k with
  | .hpCritical       => hpCriticalFires s
  | .restForCombat    => restForCombatFires s
  | .bankUnlock       => bankUnlockFires s
  | .reachUnlockLevel => reachUnlockLevelFires s
  | .geCancel         => geCancelFires s
  | .discardCritical  => discardCriticalFires s
  | .craftRelief      => craftReliefFires s
  | .recycleRelief    => recycleReliefFires s
  | .sellRelief       => sellReliefFires s
  | .depositFull      => depositFullFires s
  | .discardHigh      => discardHighFires s
  | .gearReview       => gearReviewFires s
  | .craftPotions     => craftPotionsFires s
  | .claimPending     => claimPendingFires s
  | .completeTask     => completeTaskFires s
  | .sellPressured    => sellPressuredFires s
  | .lowYieldCancel   => lowYieldCancelFires s
  | .taskCancel       => taskCancelFires s
  | .objectiveStep    => objectiveStepFires s
  | .pursueTask       => pursueTaskFires s
  | .acceptTask       => acceptTaskFires s
  | .taskExchange     => taskExchangeFires s
  | .maintainConsumables => maintainConsumablesFires s
  | .supplyBank       => supplyBankFires s
  | .currencyTurnIn   => currencyTurnInFires s
  | .sellIdle         => sellIdleFires s
  | .recycleSurplus   => recycleSurplusFires s
  | .drainBankJunk    => drainBankJunkFires s
  | .geBid            => geBidFires s
  | .bankExpand       => bankExpandFires s
  | .wait             => waitFires s

/-! ## Ladder walk -/

/-- `productionLadder s` = first `MeansKind` in `allInLadderOrder` whose
    `fires` predicate holds on `s`; `none` if none fire. Computable (see
    `fires`) — the oracle evaluates this directly for the O5.4 differential. -/
def productionLadder (s : State) : Option MeansKind :=
  allInLadderOrder.findSome? (fun k => if fires k s then some k else none)

end Formal.Liveness.ProductionLadder
