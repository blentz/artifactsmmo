/-
  Formal.Liveness.MeansKind

  Production-granularity `MeansKind` enum mirroring the StrategyArbiter's
  ladder. There are 23 means in total, ordered:

    GUARD_ORDER (10, from `tiers/guards.py:68`)  -- REST_FOR_COMBAT after
                                                   HP_CRITICAL; CRAFT_RELIEF
                                                   between DISCARD_CRITICAL and
                                                   DEPOSIT_FULL; GEAR_REVIEW
                                                   last (lowest-priority guard)
    ++ COLLECT_REWARD_ORDER (5, from `tiers/means.py:35`)
    ++ [OBJECTIVE_STEP] (1)
    ++ DISCRETIONARY_ORDER (7, from `tiers/means.py:42`)  -- incl MAINTAIN_CONSUMABLES + WAIT

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
    - `src/artifactsmmo_cli/ai/tiers/guards.py::GuardKind` (9 constructors)
    - `src/artifactsmmo_cli/ai/tiers/means.py::MeansKind` (11 constructors,
      split into COLLECT_REWARD_ORDER (5), DISCRETIONARY_ORDER (6))
    - OBJECTIVE_STEP — separate single tier (the objective StepGoal).

    Order matches production's preordered candidate list:
      GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [OBJECTIVE_STEP] ++ DISCRETIONARY_ORDER.

    Total 23 constructors. -/
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
  -- Collect-reward (COLLECT_REWARD_ORDER, means.py:35)
  | claimPending        -- CLAIM_PENDING,      means.py:69
  | completeTask        -- COMPLETE_TASK,      means.py:72
  | sellPressured       -- SELL_PRESSURED,     means.py:76
  | lowYieldCancel      -- LOW_YIELD_CANCEL,   means.py:79
  | taskCancel          -- TASK_CANCEL,        means.py:82
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
  -- Last-resort fallback (Phase 20e-v2 step 1, means.py:32, means.py:115)
  | wait                -- WAIT,               always fires
  deriving DecidableEq, Repr

/-- Full ladder in production preorder. `wait` is unconditionally last:
    `productionLadder` falls through to it whenever no other means fires,
    so the ladder is unconditionally total (see `NoDeadlockV2.lean`). -/
def allInLadderOrder : List MeansKind :=
  [.hpCritical, .restForCombat, .bankUnlock, .reachUnlockLevel,
   .discardCritical, .craftRelief, .recycleRelief, .sellRelief, .depositFull, .discardHigh, .gearReview,
   .claimPending, .completeTask, .sellPressured, .lowYieldCancel, .taskCancel,
   .objectiveStep,
   .pursueTask, .acceptTask, .taskExchange, .maintainConsumables,
   .sellIdle, .recycleSurplus, .drainBankJunk, .bankExpand,
   .wait]

/-- Sanity: 26 constructors. -/
example : allInLadderOrder.length = 26 := by decide

end Formal.Liveness.MeansKind
