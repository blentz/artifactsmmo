/-
  Formal.Liveness.MeansKind

  Production-granularity `MeansKind` enum mirroring the StrategyArbiter's
  ladder. There are 18 means in total, ordered:

    GUARD_ORDER (6, from `tiers/guards.py:49`)
    ++ COLLECT_REWARD_ORDER (5, from `tiers/means.py:35`)
    ++ [OBJECTIVE_STEP] (1)
    ++ DISCRETIONARY_ORDER (6, from `tiers/means.py:42`)  -- includes WAIT

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
    - `src/artifactsmmo_cli/ai/tiers/guards.py::GuardKind` (6 constructors)
    - `src/artifactsmmo_cli/ai/tiers/means.py::MeansKind` (11 constructors,
      split into COLLECT_REWARD_ORDER (5), DISCRETIONARY_ORDER (6))
    - OBJECTIVE_STEP — separate single tier (the objective StepGoal).

    Order matches production's preordered candidate list:
      GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [OBJECTIVE_STEP] ++ DISCRETIONARY_ORDER.

    Total 18 constructors. -/
inductive MeansKind where
  -- Guards (GUARD_ORDER, guards.py:49)
  | hpCritical          -- HP_CRITICAL,        guards.py:67
  | bankUnlock          -- BANK_UNLOCK,        guards.py:69
  | reachUnlockLevel    -- REACH_UNLOCK_LEVEL, guards.py:77
  | discardCritical     -- DISCARD_CRITICAL,   guards.py:81
  | depositFull         -- DEPOSIT_FULL,       guards.py:83
  | discardHigh         -- DISCARD_HIGH,       guards.py:86
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
  | sellIdle            -- SELL_IDLE,          means.py:100
  | bankExpand          -- BANK_EXPAND,        means.py:103
  -- Last-resort fallback (Phase 20e-v2 step 1, means.py:32, means.py:115)
  | wait                -- WAIT,               always fires
  deriving DecidableEq, Repr

/-- Full ladder in production preorder. `wait` is unconditionally last:
    `productionLadder` falls through to it whenever no other means fires,
    so the ladder is unconditionally total (see `NoDeadlockV2.lean`). -/
def allInLadderOrder : List MeansKind :=
  [.hpCritical, .bankUnlock, .reachUnlockLevel, .discardCritical, .depositFull, .discardHigh,
   .claimPending, .completeTask, .sellPressured, .lowYieldCancel, .taskCancel,
   .objectiveStep,
   .pursueTask, .acceptTask, .taskExchange, .sellIdle, .bankExpand,
   .wait]

/-- Sanity: 18 constructors. -/
example : allInLadderOrder.length = 18 := by decide

end Formal.Liveness.MeansKind
