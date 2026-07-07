-- @concept: core, planner @property: totality
/-
Formal model of the dispatcher-exhaustiveness extracted from
`src/artifactsmmo_cli/ai/tiers/decide_key.py` (the GuardKind/MeansKind
dispatch tables that `strategy_driver.py`'s LIVE `map_guard` / `map_means`
use).

## Dispatcher exhaustiveness

`map_guard` / `map_means` in `strategy_driver.py` dispatch a `GuardKind` /
`MeansKind` to a `Goal`. The Python implementation uses `if/elif/.../raise
ValueError("Unknown ...")` — a fall-through that is supposed to be DEAD code.
We mirror the enums as Lean inductives and write a TOTAL `match` over each.
The Lean compiler enforces exhaustiveness at elaboration: if a new variant
is added without a case here, the elaborator fails (compile-time guarantee
that the fall-through is unreachable). The `_total` theorems below then read
back the totality as a Prop: every variant produces a non-empty repr.

EXACT MATCH: the strings here mirror the production `Goal` `__repr__` outputs
(see `tests/test_ai/test_decide_key.py::TestDispatcherExhaustiveness`
which round-trips through the Python `goal_repr_of_guard/means` tables, which
in turn are pulled from the same Goal repr strings the driver uses).

(Historical note: this module also carried `Key`/`decideCmp`, the sort-key
comparator of the retired flat scalar ranking's `StrategyEngine.decide`.
That comparator was deleted with the flat ranking in progression-tree
Phase 4b; the dispatcher model below binds the LIVE arbiter dispatchers.)

Lean core only — no mathlib. Compile-time exhaustiveness via the inductive
`match`.
-/

namespace Formal.DecideKey

/-! ## Dispatcher inductives + total `repr` maps. -/

/-- Mirror of `src/artifactsmmo_cli/ai/tiers/guards.py::GuardKind`. The trailing
variants (`restForCombat`, `gearReview`, `recycleRelief`) are appended last so
the oracle's index dispatch (and the diff test's `_GUARD_INDEX`) keeps the
existing 0..7 positions stable. -/
inductive GuardKind where
  | hpCritical
  | bankUnlock
  | reachUnlockLevel
  | discardCritical
  | craftRelief
  | depositFull
  | discardHigh
  | restForCombat
  | gearReview
  | recycleRelief
  | sellRelief
  | craftPotions
deriving Repr, DecidableEq

/-- Mirror of `src/artifactsmmo_cli/ai/tiers/means.py::MeansKind`. -/
inductive MeansKind where
  | claimPending
  | completeTask
  | sellPressured
  | lowYieldCancel
  | taskCancel
  | pursueTask
  | acceptTask
  | taskExchange
  | sellIdle
  | recycleSurplus  -- 2026-06-14: proactive recycle of surplus craftable gear
  | bankExpand
  | wait  -- Phase 20e-v2: always-firing sentinel sentinel (production fix
          -- src/.../tiers/means.py:WAIT). Closes the StrategyArbiter
          -- deadlock window when no other means fires.
  | maintainConsumables  -- PLAN #6a: cook/brew heals when combat-active and
                         -- under-stocked. Appended LAST to keep the oracle's
                         -- index dispatch (0..11) stable.
  | drainBankJunk  -- 2026-06-24: withdraw over-cap bank junk. Appended LAST
                   -- (oracle index 13) to keep earlier index dispatch stable.
deriving Repr, DecidableEq

/-- TOTAL `match`: every `GuardKind` variant maps to a non-empty repr string.
The Lean compiler enforces exhaustiveness at elaboration — if a new variant
is added to `GuardKind`, this declaration FAILS TO ELABORATE unless a case is
added. The fall-through is statically unreachable. -/
def goalReprOfGuard : GuardKind → String
  | .hpCritical       => "RestoreHP"
  | .restForCombat    => "RestoreHP"
  | .discardCritical  => "DiscardOverstock"
  | .discardHigh      => "DiscardOverstock"
  | .bankUnlock       => "UnlockBank"
  | .reachUnlockLevel => "ReachUnlockLevel"
  | .craftRelief      => "CraftRelief"
  | .depositFull      => "DepositInventory"
  | .gearReview       => "UpgradeEquipment"
  | .recycleRelief    => "RecycleSurplus"
  | .sellRelief       => "SellInventory"
  | .craftPotions     => "CraftPotions"

/-- TOTAL `match`: every `MeansKind` variant maps to a non-empty repr string. -/
def goalReprOfMeans : MeansKind → String
  | .claimPending    => "ClaimPending"
  | .completeTask    => "CompleteTask"
  | .sellPressured   => "SellInventory"
  | .sellIdle        => "SellInventory"
  | .lowYieldCancel  => "LowYieldCancel"
  | .taskCancel      => "TaskCancel"
  | .pursueTask      => "PursueTask"
  | .acceptTask      => "AcceptTask"
  | .taskExchange    => "TaskExchange"
  | .recycleSurplus  => "RecycleSurplus"
  | .bankExpand      => "ExpandBank"
  | .wait            => "Wait"
  | .maintainConsumables => "MaintainConsumables"
  | .drainBankJunk   => "DrainBankJunk"

/-! ### Exhaustiveness intent theorems (totality witnesses). -/

/-- Every `GuardKind` variant yields a non-empty repr. The proof's `match` is
the SAME exhaustive structure as `goalReprOfGuard` itself: any new variant
forces a new case here too, so the compile-time exhaustiveness check applies
at BOTH sites. (This is the Prop-level read-back of the static exhaustiveness
guarantee.) -/
theorem goalReprOfGuard_nonempty : ∀ k : GuardKind, (goalReprOfGuard k).length > 0 := by
  intro k; cases k <;> decide

/-- Every `MeansKind` variant yields a non-empty repr. -/
theorem goalReprOfMeans_nonempty : ∀ k : MeansKind, (goalReprOfMeans k).length > 0 := by
  intro k; cases k <;> decide

/-! ### Non-vacuity examples. -/

/-- Every guard variant indeed yields a known production repr (witness for
the dispatcher table). -/
example : goalReprOfGuard .hpCritical = "RestoreHP" := rfl
example : goalReprOfGuard .depositFull = "DepositInventory" := rfl

/-- Every means variant likewise. -/
example : goalReprOfMeans .pursueTask = "PursueTask" := rfl
example : goalReprOfMeans .sellIdle = "SellInventory" := rfl

end Formal.DecideKey
