"""Python mirror of `Formal.Liveness.ProductionLadder.productionLadder`.

Walks the 23-element `allInLadderOrder` (GUARD_ORDER ++ COLLECT_REWARD_ORDER
++ [OBJECTIVE_STEP] ++ DISCRETIONARY_ORDER) and returns the FIRST means
whose production `_fires` predicate returns True; None if none fire.

IMPORTANT: this mirror does NOT re-implement `_fires`. It imports the
REAL production functions from `tiers/guards.py` and `tiers/means.py`
and dispatches into them. Any divergence from the Lean walk-order is
also a divergence from production semantics.

The "objective step" tier is NOT a `_fires` predicate in production —
the StrategyArbiter constructs an objective StepGoal candidate and tries
to plan it. For the differential we model it as an OPAQUE Bool callback
the test supplies; the diff test passes `False` because no objective is
in scope for synthetic states (the diff is about means firing under
ladder fallthrough).
"""
from collections.abc import Callable
from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.guards import (
    GUARD_ORDER,
    GuardKind,
    SelectionContext,
)
from artifactsmmo_cli.ai.tiers.guards import _fires as _guard_fires
from artifactsmmo_cli.ai.tiers.means import (
    COLLECT_REWARD_ORDER,
    DISCRETIONARY_ORDER,
    MeansKind,
)
from artifactsmmo_cli.ai.tiers.means import _fires as _means_fires
from artifactsmmo_cli.ai.world_state import WorldState


class LadderMeans(Enum):
    """Unified 24-entry enum mirroring `Formal.Liveness.MeansKind.MeansKind`."""

    HP_CRITICAL = "hp_critical"
    REST_FOR_COMBAT = "rest_for_combat"
    BANK_UNLOCK = "bank_unlock"
    REACH_UNLOCK_LEVEL = "reach_unlock_level"
    DISCARD_CRITICAL = "discard_critical"
    CRAFT_RELIEF = "craft_relief"
    RECYCLE_RELIEF = "recycle_relief"
    SELL_RELIEF = "sell_relief"
    DEPOSIT_FULL = "deposit_full"
    DISCARD_HIGH = "discard_high"
    GEAR_REVIEW = "gear_review"
    CLAIM_PENDING = "claim_pending"
    COMPLETE_TASK = "complete_task"
    SELL_PRESSURED = "sell_pressured"
    LOW_YIELD_CANCEL = "low_yield_cancel"
    TASK_CANCEL = "task_cancel"
    OBJECTIVE_STEP = "objective_step"
    PURSUE_TASK = "pursue_task"
    ACCEPT_TASK = "accept_task"
    TASK_EXCHANGE = "task_exchange"
    MAINTAIN_CONSUMABLES = "maintain_consumables"
    SELL_IDLE = "sell_idle"
    RECYCLE_SURPLUS = "recycle_surplus"
    DRAIN_BANK_JUNK = "drain_bank_junk"
    BANK_EXPAND = "bank_expand"
    WAIT = "wait"


ALL_IN_LADDER_ORDER: tuple[LadderMeans, ...] = (
    LadderMeans.HP_CRITICAL,
    LadderMeans.REST_FOR_COMBAT,
    LadderMeans.BANK_UNLOCK,
    LadderMeans.REACH_UNLOCK_LEVEL,
    LadderMeans.DISCARD_CRITICAL,
    LadderMeans.CRAFT_RELIEF,
    LadderMeans.RECYCLE_RELIEF,
    LadderMeans.SELL_RELIEF,
    LadderMeans.DEPOSIT_FULL,
    LadderMeans.DISCARD_HIGH,
    LadderMeans.GEAR_REVIEW,
    LadderMeans.CLAIM_PENDING,
    LadderMeans.COMPLETE_TASK,
    LadderMeans.SELL_PRESSURED,
    LadderMeans.LOW_YIELD_CANCEL,
    LadderMeans.TASK_CANCEL,
    LadderMeans.OBJECTIVE_STEP,
    LadderMeans.PURSUE_TASK,
    LadderMeans.ACCEPT_TASK,
    LadderMeans.TASK_EXCHANGE,
    LadderMeans.MAINTAIN_CONSUMABLES,
    LadderMeans.SELL_IDLE,
    LadderMeans.RECYCLE_SURPLUS,
    LadderMeans.DRAIN_BANK_JUNK,
    LadderMeans.BANK_EXPAND,
    LadderMeans.WAIT,
)


_GUARD_MAP: dict[LadderMeans, GuardKind] = {
    LadderMeans.HP_CRITICAL: GuardKind.HP_CRITICAL,
    LadderMeans.REST_FOR_COMBAT: GuardKind.REST_FOR_COMBAT,
    LadderMeans.BANK_UNLOCK: GuardKind.BANK_UNLOCK,
    LadderMeans.REACH_UNLOCK_LEVEL: GuardKind.REACH_UNLOCK_LEVEL,
    LadderMeans.DISCARD_CRITICAL: GuardKind.DISCARD_CRITICAL,
    LadderMeans.CRAFT_RELIEF: GuardKind.CRAFT_RELIEF,
    LadderMeans.RECYCLE_RELIEF: GuardKind.RECYCLE_RELIEF,
    LadderMeans.SELL_RELIEF: GuardKind.SELL_RELIEF,
    LadderMeans.DEPOSIT_FULL: GuardKind.DEPOSIT_FULL,
    LadderMeans.DISCARD_HIGH: GuardKind.DISCARD_HIGH,
    LadderMeans.GEAR_REVIEW: GuardKind.GEAR_REVIEW,
}

_MEANS_MAP: dict[LadderMeans, MeansKind] = {
    LadderMeans.CLAIM_PENDING: MeansKind.CLAIM_PENDING,
    LadderMeans.COMPLETE_TASK: MeansKind.COMPLETE_TASK,
    LadderMeans.SELL_PRESSURED: MeansKind.SELL_PRESSURED,
    LadderMeans.LOW_YIELD_CANCEL: MeansKind.LOW_YIELD_CANCEL,
    LadderMeans.TASK_CANCEL: MeansKind.TASK_CANCEL,
    LadderMeans.PURSUE_TASK: MeansKind.PURSUE_TASK,
    LadderMeans.ACCEPT_TASK: MeansKind.ACCEPT_TASK,
    LadderMeans.TASK_EXCHANGE: MeansKind.TASK_EXCHANGE,
    LadderMeans.MAINTAIN_CONSUMABLES: MeansKind.MAINTAIN_CONSUMABLES,
    LadderMeans.SELL_IDLE: MeansKind.SELL_IDLE,
    LadderMeans.RECYCLE_SURPLUS: MeansKind.RECYCLE_SURPLUS,
    LadderMeans.DRAIN_BANK_JUNK: MeansKind.DRAIN_BANK_JUNK,
    LadderMeans.BANK_EXPAND: MeansKind.BANK_EXPAND,
    LadderMeans.WAIT: MeansKind.WAIT,
}

# Sanity: GUARD_ORDER and COLLECT/DISCRETIONARY ORDER align with the
# Lean ladder.  Any reordering on the production side breaks this.
assert tuple(g for g in GUARD_ORDER) == (
    GuardKind.HP_CRITICAL,
    GuardKind.REST_FOR_COMBAT,
    GuardKind.BANK_UNLOCK,
    GuardKind.REACH_UNLOCK_LEVEL,
    GuardKind.DISCARD_CRITICAL,
    GuardKind.CRAFT_RELIEF,
    GuardKind.RECYCLE_RELIEF,
    GuardKind.SELL_RELIEF,
    GuardKind.DEPOSIT_FULL,
    GuardKind.DISCARD_HIGH,
    GuardKind.GEAR_REVIEW,
), "GUARD_ORDER drift — Lean MeansKind.allInLadderOrder is stale"

assert COLLECT_REWARD_ORDER == (
    MeansKind.CLAIM_PENDING,
    MeansKind.COMPLETE_TASK,
    MeansKind.SELL_PRESSURED,
    MeansKind.LOW_YIELD_CANCEL,
    MeansKind.TASK_CANCEL,
), "COLLECT_REWARD_ORDER drift — Lean MeansKind.allInLadderOrder is stale"

assert DISCRETIONARY_ORDER == (
    MeansKind.PURSUE_TASK,
    MeansKind.ACCEPT_TASK,
    MeansKind.TASK_EXCHANGE,
    MeansKind.MAINTAIN_CONSUMABLES,
    MeansKind.SELL_IDLE,
    MeansKind.RECYCLE_SURPLUS,
    MeansKind.DRAIN_BANK_JUNK,
    MeansKind.BANK_EXPAND,
    MeansKind.WAIT,
), "DISCRETIONARY_ORDER drift — Lean MeansKind.allInLadderOrder is stale"


def fires(
    k: LadderMeans,
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    ctx: SelectionContext,
    objective_step_fires: bool,
) -> bool:
    """Dispatch into the production `_fires` for the corresponding tier.

    `objective_step_fires` is the opaque Bool flag for the objective tier —
    in production the StrategyArbiter tries to plan an objective StepGoal;
    the differential test supplies its observation here.
    """
    if k is LadderMeans.OBJECTIVE_STEP:
        return objective_step_fires
    if k in _GUARD_MAP:
        return _guard_fires(_GUARD_MAP[k], state, game_data, history, ctx)
    return _means_fires(_MEANS_MAP[k], state, game_data, history, ctx)


def production_ladder(
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    ctx: SelectionContext,
    objective_step_fires: bool = False,
) -> LadderMeans | None:
    """First means in `ALL_IN_LADDER_ORDER` whose production `_fires` returns
    True; None if none fire. Mirrors
    `Formal.Liveness.ProductionLadder.productionLadder`."""
    for k in ALL_IN_LADDER_ORDER:
        if fires(k, state, game_data, history, ctx, objective_step_fires):
            return k
    return None


__all__ = [
    "ALL_IN_LADDER_ORDER",
    "LadderMeans",
    "fires",
    "production_ladder",
]


# Convenience: callable factory used by the diff test for any-other-fires
# enumeration without re-typing the long enum names.
def all_other_fires(
    skip: LadderMeans,
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    ctx: SelectionContext,
    objective_step_fires: bool,
) -> list[LadderMeans]:
    """Every means that fires excluding `skip`. Used to attribute deadlock
    witnesses: if PursueTask doesn't fire and the list is also empty, that
    is a real production deadlock state."""
    out: list[LadderMeans] = []
    for k in ALL_IN_LADDER_ORDER:
        if k is skip:
            continue
        if fires(k, state, game_data, history, ctx, objective_step_fires):
            out.append(k)
    return out


# Reference for static typing / linting only.
_FiresFn = Callable[
    [LadderMeans, WorldState, GameData, LearningStore | None, SelectionContext, bool],
    bool,
]
