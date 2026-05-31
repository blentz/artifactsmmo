/-
  Formal.Liveness.MeansKind

  Production-granularity `MeansKind` enum mirroring the StrategyArbiter's
  ladder. There are 17 means in total, ordered:

    GUARD_ORDER (6, from `tiers/guards.py:49`)
    ++ COLLECT_REWARD_ORDER (5, from `tiers/means.py:34`)
    ++ [OBJECTIVE_STEP] (1)
    ++ DISCRETIONARY_ORDER (5, from `tiers/means.py:41`)

  This is the production-faithful enumeration that replaces the retracted
  Phase-20a/b coarse 8-region `FiringGoal` aggregation. The corresponding
  `_fires` predicates live in `ProductionLadder.lean`.

  Liveness namespace — Mathlib axioms allowed; see
  `formal/Formal/Liveness/README.md`.
-/

namespace Formal.Liveness.MeansKind

/-- Production MeansKind enum. Mirrors:
    - `src/artifactsmmo_cli/ai/tiers/guards.py::GuardKind` (6 constructors)
    - `src/artifactsmmo_cli/ai/tiers/means.py::MeansKind` (10 constructors,
      split into COLLECT_REWARD_ORDER (5), DISCRETIONARY_ORDER (5))
    - OBJECTIVE_STEP — separate single tier (the objective StepGoal).

    Order matches production's preordered candidate list:
      GUARD_ORDER ++ COLLECT_REWARD_ORDER ++ [OBJECTIVE_STEP] ++ DISCRETIONARY_ORDER.

    Total 17 constructors. -/
inductive MeansKind where
  -- Guards (GUARD_ORDER, guards.py:49)
  | hpCritical          -- HP_CRITICAL,        guards.py:67
  | bankUnlock          -- BANK_UNLOCK,        guards.py:69
  | reachUnlockLevel    -- REACH_UNLOCK_LEVEL, guards.py:77
  | discardCritical     -- DISCARD_CRITICAL,   guards.py:81
  | depositFull         -- DEPOSIT_FULL,       guards.py:83
  | discardHigh         -- DISCARD_HIGH,       guards.py:86
  -- Collect-reward (COLLECT_REWARD_ORDER, means.py:34)
  | claimPending        -- CLAIM_PENDING,      means.py:67
  | completeTask        -- COMPLETE_TASK,      means.py:70
  | sellPressured       -- SELL_PRESSURED,     means.py:74
  | lowYieldCancel      -- LOW_YIELD_CANCEL,   means.py:77
  | taskCancel          -- TASK_CANCEL,        means.py:80
  -- Objective step (StrategyArbiter inserts a single objective StepGoal here)
  | objectiveStep       -- OBJECTIVE_STEP
  -- Discretionary (DISCRETIONARY_ORDER, means.py:41)
  | pursueTask          -- PURSUE_TASK,        means.py:85
  | acceptTask          -- ACCEPT_TASK,        means.py:92
  | taskExchange        -- TASK_EXCHANGE,      means.py:95
  | sellIdle            -- SELL_IDLE,          means.py:98
  | bankExpand          -- BANK_EXPAND,        means.py:101
  deriving DecidableEq, Repr

/-- Full ladder in production preorder. -/
def allInLadderOrder : List MeansKind :=
  [.hpCritical, .bankUnlock, .reachUnlockLevel, .discardCritical, .depositFull, .discardHigh,
   .claimPending, .completeTask, .sellPressured, .lowYieldCancel, .taskCancel,
   .objectiveStep,
   .pursueTask, .acceptTask, .taskExchange, .sellIdle, .bankExpand]

/-- Sanity: 17 constructors. -/
example : allInLadderOrder.length = 17 := by decide

end Formal.Liveness.MeansKind
