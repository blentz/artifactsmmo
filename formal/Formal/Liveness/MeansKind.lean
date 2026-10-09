/-
  Formal.Liveness.MeansKind

  Production-granularity `MeansKind` enum mirroring the StrategyArbiter's
  ladder. The ladder is the concatenation

    GUARD_ORDER (from `tiers/guards.py`)          -- REST_FOR_COMBAT after
                                                     HP_CRITICAL; CRAFT_RELIEF
                                                     between DISCARD_CRITICAL and
                                                     DEPOSIT_FULL; GEAR_REVIEW
                                                     then CRAFT_POTIONS last
                                                     (lowest-priority guards)
    ++ COLLECT_REWARD_ORDER (from `tiers/means.py`) -- SUPPLY_BANK and
                                                     CURRENCY_TURNIN left it in
                                                     Phase 5-2c-iv (the fleet
                                                     objective's step)
    ++ [OBJECTIVE_STEP]
    ++ DISCRETIONARY_ORDER (from `tiers/means.py`) -- incl MAINTAIN_CONSUMABLES
                                                     and WAIT

  `allInLadderOrder` below is the authoritative enumeration; its length is
  checked by the `example` at the bottom of this file rather than restated
  as a prose count here (a prose count has already drifted once).

  Phase 20e-v2 step 2: a `wait` last-resort means is appended to
  DISCRETIONARY_ORDER, mirroring `MeansKind.WAIT` in
  `src/artifactsmmo_cli/ai/tiers/means.py:32`. Its firing predicate is
  unconditionally `true`, so `productionLadder` is unconditionally
  non-`none` — see `Formal/Liveness/NoDeadlockV2.lean`.

  This is the production-faithful enumeration that replaces the retracted
  Phase-20a/b coarse 8-region `FiringGoal` aggregation. The corresponding
  `_fires` predicates live in `ProductionLadder.lean`.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/

namespace Formal.Liveness.MeansKind

/-- Production MeansKind enum. Mirrors:
    - `src/artifactsmmo_cli/ai/tiers/guards.py::GuardKind`
    - `src/artifactsmmo_cli/ai/tiers/means.py::MeansKind`, split into
      COLLECT_REWARD_ORDER and DISCRETIONARY_ORDER
    - OBJECTIVE_STEP — separate single tier (the objective StepGoal).

    Constructor order matches production's preordered candidate list:
      GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [OBJECTIVE_STEP] ++ DISCRETIONARY_ORDER.
    (This inductive is NOT index-dispatched by the oracle — that is
    `Formal.DecideKey.MeansKind` — so constructors sit in LADDER order here.) -/
inductive MeansKind where
  -- Guards (GUARD_ORDER, guards.py:68)
  | hpCritical          -- HP_CRITICAL,        guards.py:69
  | restForCombat       -- REST_FOR_COMBAT,    guards.py:70 (preempts the
                        --                     next Fight when current hp is
                        --                     insufficient to win but max-hp
                        --                     is — same RestoreHP witness as
                        --                     hpCritical, distinct tier)
  | bankUnlock          -- BANK_UNLOCK,        guards.py:71
  | reachUnlockLevel    -- REACH_UNLOCK_LEVEL, guards.py:72
  | geCancel            -- GE_CANCEL,          guards.py (2026-07-24): on-need +
                        --                     TTL cancellation of posted GE orders.
                        --                     Sits BELOW the two FIGHT gates and
                        --                     ABOVE the bag/bank-management cluster.
                        --                     Fire-and-lose, like recycleRelief: a
                        --                     cancel removes the order from the
                        --                     cancel-target set next cycle.
  | discardCritical     -- DISCARD_CRITICAL,   guards.py:73
  | craftRelief         -- CRAFT_RELIEF,       guards.py:74 (circuit breaker
                        --                     between DISCARD_CRITICAL and
                        --                     DEPOSIT_FULL; fires when inv
                        --                     >= 0.70 AND a goal item is
                        --                     craftable from inventory)
  | recycleRelief       -- RECYCLE_RELIEF,     guards.py (bank-full: recover
                        --                     materials before sell/discard;
                        --                     fires when bank full AND
                        --                     recyclable surplus nonempty)
  | sellRelief          -- SELL_RELIEF, guards.py (bank-full: sell surplus
                        --                     before deposit/discard; fires
                        --                     when bank full AND sellable
                        --                     inventory nonempty)
  | depositFull         -- DEPOSIT_FULL,       guards.py:75
  | discardHigh         -- DISCARD_HIGH,       guards.py:76
  | craftPotions        -- CRAFT_POTIONS,      guards.py (LAST guard in
                        --                     GUARD_ORDER; stocks the utility-slot
                        --                     potion baseline before grind;
                        --                     fires on craft_potions_fires)
  -- Collect-reward (COLLECT_REWARD_ORDER, means.py:35)
  | claimPending        -- CLAIM_PENDING,      means.py:69
  | sellPressured       -- SELL_PRESSURED,     means.py:76
  -- (completeTask retired: Phase 5-2c-iii-c-2 #6)
  -- (lowYieldCancel retired: Phase 5-2c-iii-c-2)
  -- (taskCancel retired: Phase 5-2c-iii-c-2 #5)
  -- (supplyBank and currencyTurnIn retired: Phase 5-2c-iv — fleet work is the
  --  fleet objective, `ReachFleetOutcome`; their firing predicates are
  --  disjuncts of `objectiveStepFires`)
  -- Objective step (StrategyArbiter inserts a single objective StepGoal here)
  | objectiveStep       -- OBJECTIVE_STEP
  -- Discretionary (DISCRETIONARY_ORDER, means.py:42)
  -- (pursueTask retired: Phase 5-2c-iii-c-2 #4)
  -- (acceptTask retired: Phase 5-2c-iii-c-2 #3)
  -- (taskExchange retired: Phase 5-2c-iii-c-2 #2)
  | maintainConsumables -- MAINTAIN_CONSUMABLES, means.py (PLAN #6a): cook/brew
                        --                     heals when combat-active + under-stocked
  | sellIdle            -- SELL_IDLE,          means.py:100
  | recycleSurplus      -- RECYCLE_SURPLUS,    means.py (2026-06-14)
  | drainBankJunk       -- DRAIN_BANK_JUNK,    means.py (2026-06-24): withdraw
                        --                     over-cap bank junk so DiscardOverstock
                        --                     can shed it (fire-and-lose, like recycle)
  | bankExpand          -- BANK_EXPAND,        means.py:103
  | geBid               -- GE_BID,             means.py (2026-07-24): post a GE buy
                        --                     order for a slow-to-craft objective
                        --                     material so it fills async (fire-and-
                        --                     lose, like recycle/drainBankJunk: the
                        --                     posted order suppresses it next cycle)
  -- Last-resort fallback (Phase 20e-v2 step 1, means.py:32, means.py:115)
  | wait                -- WAIT,               always fires
  deriving DecidableEq, Repr

/-- Full ladder in production preorder. `wait` is unconditionally last:
    `productionLadder` falls through to it whenever no other means fires,
    so the ladder is unconditionally total (see `NoDeadlockV2.lean`). -/
def allInLadderOrder : List MeansKind :=
  [.hpCritical, .restForCombat, .bankUnlock, .reachUnlockLevel,
   .geCancel,
   .discardCritical, .craftRelief, .recycleRelief, .sellRelief, .depositFull, .discardHigh,
   .craftPotions,
   -- 2026-10-05 (Phase 5-2b): SELL_PRESSURED is an INTERRUPT — the bag at the
   -- pressure threshold is a precondition of continuing — so it closes the
   -- interrupt prefix, ahead of the collect rungs.
   .sellPressured,
   .claimPending,
   -- 2026-10-05 (Phase 5-2c-ii): BANK_EXPAND is an INTERRUPT — it keeps the
   -- deposit sink open — so it closes the interrupt prefix. (It was the last
   -- collect rung from its 2026-09-13 promotion out of the discretionary group,
   -- where it fired against a 50/50 bank and was selected zero times.)
   .bankExpand,
   .objectiveStep,
   .maintainConsumables,
   .sellIdle, .recycleSurplus, .geBid, .drainBankJunk,
   .wait]

/-- Sanity: 22 rungs (one per constructor). GEAR_REVIEW was retired in Phase
    4-3b: its one arm never fired in recorded history. LOW_YIELD_CANCEL,
    TASK_EXCHANGE, ACCEPT_TASK, PURSUE_TASK, TASK_CANCEL and COMPLETE_TASK
    were retired in Phase 5-2c-iii-c-2: the task objective's step owns the
    cancels, the exchange, the accept, the items-task pursuit and the
    turn-in of a met task. SUPPLY_BANK and CURRENCY_TURNIN were retired in
    Phase 5-2c-iv: fleet work is the fleet objective's step. -/
example : allInLadderOrder.length = 22 := by decide

end Formal.Liveness.MeansKind
