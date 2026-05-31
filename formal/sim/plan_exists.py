"""Python mirror of `Formal.Liveness.PlanExists`.

For every in-scope `LadderMeans`, return the single-step witness
plan (a list of ActionKind names, mirroring the Lean refine
witnesses in `formal/Formal/Liveness/PlanExists.lean`).

Honest disclosure (matches Lean):
  * `OBJECTIVE_STEP` is the synthetic ActionKind placeholder
    (Phase 21d-1). The witness is itself synthetic; production
    decomposes the sub-goal into ordinary Actions. Not in scope
    for the operational differential.
  * `WAIT` is the unsatisfiable last-resort. Its witness is `wait`,
    but the post-state still fires the predicate. The Lean lemma is
    the weaker "a plan exists that preserves the state" — production
    short-circuits to `[WaitAction()]` in StrategyArbiter._plans.
  * `BANK_UNLOCK`, `REACH_UNLOCK_LEVEL`, `PURSUE_TASK` all collapse
    to a single witness ActionKind in the Lean model (taskTrade
    collapses a multi-call delivery into one apply; fight is
    extended to flip bank-unlock readiness and roll xp/level).
"""
from formal.sim.production_ladder import LadderMeans

# ActionKind name -> production Action class. The single-step witnesses
# below name the ActionKind that the Lean PlanExists proof picks for
# each MeansKind. The operational differential checks that the real
# production planner returns a plan containing AT LEAST one action of
# the same type (the synthetic .objectiveStep tier is excluded).
WITNESS: dict[LadderMeans, list[str]] = {
    LadderMeans.HP_CRITICAL: ["rest"],
    LadderMeans.BANK_UNLOCK: ["fight"],
    LadderMeans.REACH_UNLOCK_LEVEL: ["fight"],
    LadderMeans.DISCARD_CRITICAL: ["deleteItem"],
    LadderMeans.DEPOSIT_FULL: ["depositAll"],
    LadderMeans.DISCARD_HIGH: ["deleteItem"],
    LadderMeans.CLAIM_PENDING: ["claimPendingItem"],
    LadderMeans.COMPLETE_TASK: ["completeTask"],
    LadderMeans.SELL_PRESSURED: ["npcSell"],
    LadderMeans.LOW_YIELD_CANCEL: ["taskCancel"],
    LadderMeans.TASK_CANCEL: ["taskCancel"],
    # OBJECTIVE_STEP: synthetic — skipped in the operational differential.
    LadderMeans.PURSUE_TASK: ["taskTrade"],
    LadderMeans.ACCEPT_TASK: ["acceptTask"],
    LadderMeans.TASK_EXCHANGE: ["taskExchange"],
    LadderMeans.SELL_IDLE: ["npcSell"],
    LadderMeans.BANK_EXPAND: ["buyBankExpansion"],
    LadderMeans.WAIT: ["wait"],
}


__all__ = ["WITNESS"]
