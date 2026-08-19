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
    ++ COLLECT_REWARD_ORDER (from `tiers/means.py`) -- SUPPLY_BANK then
                                                     CURRENCY_TURNIN LAST in this
                                                     group (2026-08-01 ruling
                                                     promoted SUPPLY_BANK above the
                                                     objective step, gated on
                                                     demand; 2026-08-16 fleet-
                                                     currency-turn-in epic added
                                                     CURRENCY_TURNIN directly below
                                                     it, no demand gate)
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
  | gearReview          -- GEAR_REVIEW,        guards.py:77 (lowest-priority
                        --                     guard, still above all means;
                        --                     fires on ctx.gear_review_active)
  | craftPotions        -- CRAFT_POTIONS,      guards.py (LAST guard in
                        --                     GUARD_ORDER; stocks the utility-slot
                        --                     potion baseline before grind;
                        --                     fires on craft_potions_fires)
  -- Collect-reward (COLLECT_REWARD_ORDER, means.py:35)
  | claimPending        -- CLAIM_PENDING,      means.py:69
  | completeTask        -- COMPLETE_TASK,      means.py:72
  | sellPressured       -- SELL_PRESSURED,     means.py:76
  | lowYieldCancel      -- LOW_YIELD_CANCEL,   means.py:79
  | taskCancel          -- TASK_CANCEL,        means.py:82
  | supplyBank          -- SUPPLY_BANK,        means.py (2026-08-01 human ruling):
                        --                     produce a material a SIBLING declared
                        --                     on the demand board and BANK it.
                        --                     PROMOTED out of DISCRETIONARY_ORDER
                        --                     into COLLECT_REWARD_ORDER, so it now
                        --                     outranks `objectiveStep` — below the
                        --                     step it was unreachable, because a
                        --                     character essentially always has one.
                        --                     LAST within the collect group: the
                        --                     other five rungs are one-or-few-action
                        --                     bookings of an already-earned outcome
                        --                     and self-quiet, whereas this one is an
                        --                     open-ended production run. Gated on
                        --                     `supplyDemand >= SUPPLY_DEMAND_MIN`
                        --                     (ProductionLadder) — the gate is what
                        --                     stops a fleet of siblings serving each
                        --                     other instead of levelling. OR'd
                        --                     (2026-08-16, role-driven-supply epic
                        --                     Task 4) with `supplyAsymmetric` --
                        --                     fires at ANY demand when at least one
                        --                     sibling asking for the item is
                        --                     skill-gated out of making it itself.
  | currencyTurnIn      -- CURRENCY_TURNIN,    means.py (2026-08-16, fleet-currency-
                        --                     turn-in epic Task 6): spend/surrender a
                        --                     fleet-wide dual-role holding (worn AND
                        --                     a vendor's payment currency, e.g.
                        --                     `lich_race_medal`). Fires for BOTH the
                        --                     elected buyer (`ctx.turn_in` set) and a
                        --                     losing candidate asked to surrender
                        --                     (`ctx.recall` set); `_resolve_turn_in`
                        --                     sets at most one per cycle, and only for
                        --                     a character that itself qualified.
                        --                     LAST in COLLECT_REWARD_ORDER, directly
                        --                     below `supplyBank`: same "above the
                        --                     objective step" reasoning (a resolved
                        --                     election must not rot behind whatever
                        --                     gear `J` is chasing), placed after
                        --                     supplyBank because both are open-ended
                        --                     collect rungs and this one is the
                        --                     NEWEST addition to the group. Unlike
                        --                     supplyBank there is no demand-size gate
                        --                     — `turn_in_ready_pure` already requires
                        --                     the full vendor price be reachable
                        --                     before `ctx.turn_in` is ever set.
  -- Objective step (StrategyArbiter inserts a single objective StepGoal here)
  | objectiveStep       -- OBJECTIVE_STEP
  -- Discretionary (DISCRETIONARY_ORDER, means.py:42)
  | pursueTask          -- PURSUE_TASK,        means.py:87
  | acceptTask          -- ACCEPT_TASK,        means.py:94
  | taskExchange        -- TASK_EXCHANGE,      means.py:97
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
   .discardCritical, .craftRelief, .recycleRelief, .sellRelief, .depositFull, .discardHigh, .gearReview,
   .craftPotions,
   .claimPending, .completeTask, .sellPressured, .lowYieldCancel, .taskCancel,
   -- 2026-08-19 (S-051): promoted out of the discretionary group. Below
   -- `.objectiveStep` it was unreachable — a character essentially always has a
   -- step — and accepting belongs to a COURSE rather than competing with one.
   -- AFTER both cancel rungs, so a dead draw goes back before a new one is taken.
   .acceptTask,
   .supplyBank,
   .currencyTurnIn,
   .objectiveStep,
   .pursueTask, .taskExchange, .maintainConsumables,
   .sellIdle, .recycleSurplus, .bankExpand, .geBid, .drainBankJunk,
   .wait]

/-- Sanity: 31 rungs (one per constructor). -/
example : allInLadderOrder.length = 31 := by decide

end Formal.Liveness.MeansKind
