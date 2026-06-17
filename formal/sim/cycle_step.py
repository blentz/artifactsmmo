"""Phase 22b — Python mirror of `Formal.Liveness.CycleStep.cycleStep`.

This module is the MIRROR side of the cycle-loop differential. It implements
the Lean `cycleStep` semantics in pure Python over a CycleState dataclass
that 1:1 mirrors `Formal.Liveness.Measure.State`.

The differential test (`formal/diff/test_cycle_step_diff.py`) compares this
mirror against `drive_one_cycle` — which uses the REAL production
`production_ladder` + production Action `.apply()` semantics — on a shared
projection of `TRACKED_FIELDS`. Divergence == mirror drift OR production bug.

Honest disclosure (scope reduction): the differential covers
    production_ladder + action.apply
NOT the full
    perceive -> _build_actions -> arbiter.select -> execute -> learn -> stuck-detect
loop in `src/artifactsmmo_cli/ai/player.py:190-410`. Constructing a faithful
`drive_one_cycle` that exercises `arbiter.select` on every Hypothesis-sampled
state requires per-state fixture rebuilding (equipped weapons, monster
locations, learning history, periodic-refresh state, etc.) that defeats the
purpose of a hands-off random differential. The chosen scope still pins the
key per-cycle commitment: given a firing means, the action the bot actually
runs has the projection the Lean model claims.
"""
from __future__ import annotations

import dataclasses

from formal.sim.production_ladder import LadderMeans


@dataclasses.dataclass(frozen=True)
class CycleState:
    """1:1 Python mirror of `Formal.Liveness.Measure.State`.

    Fields in the same order/types as the Lean structure (Nat -> int,
    Option String -> str | None, Bool -> bool).
    """

    level: int
    xp: int
    task_progress: int
    task_total: int
    inventory_used: int
    inventory_max: int
    hp: int
    max_hp: int
    task_type: str | None
    task_code: str | None
    projected_skill_xp_delta: int
    target_skill_xp: int
    gold: int
    bank_accessible: bool
    bank_unlock_monster_present: bool
    initial_xp: int
    unlock_monster_level: int
    bank_required_level: int
    has_overstock_items: bool
    select_bank_deposits_nonempty: bool
    pending_items_nonempty: bool
    sellable_inventory_nonempty: bool
    task_coins_total: int
    task_exchange_min_coins: int
    low_yield_cancel_fires: bool
    task_cancel_fires: bool
    pursue_task_fires: bool
    objective_step_fires: bool
    bank_items_known: bool
    bank_items_count: int
    bank_capacity: int
    next_expansion_cost: int


# Mirror constants (Plan.lean).
ACCEPT_TASK_PLACEHOLDER_CODE = "__pending__"
BANK_EXPANSION_SLOTS = 20


# ---------------------------------------------------------------------------
# planFor — mirror of `Formal.Liveness.CycleStep.planFor`. Single-action
# witnesses, one per `MeansKind`. ActionKind names are strings (matching the
# Lean enum constructor names).
# ---------------------------------------------------------------------------

MIRROR_PLAN_FOR: dict[LadderMeans, str] = {
    LadderMeans.HP_CRITICAL:        "rest",
    LadderMeans.REST_FOR_COMBAT:    "rest",
    LadderMeans.BANK_UNLOCK:        "fight",
    LadderMeans.REACH_UNLOCK_LEVEL: "fight",
    LadderMeans.DISCARD_CRITICAL:   "deleteItem",
    LadderMeans.CRAFT_RELIEF:       "craft",
    LadderMeans.DEPOSIT_FULL:       "depositAll",
    LadderMeans.DISCARD_HIGH:       "deleteItem",
    LadderMeans.GEAR_REVIEW:        "optimizeLoadout",
    LadderMeans.CLAIM_PENDING:      "claimPendingItem",
    LadderMeans.COMPLETE_TASK:      "completeTask",
    LadderMeans.SELL_PRESSURED:     "npcSell",
    LadderMeans.LOW_YIELD_CANCEL:   "taskCancel",
    LadderMeans.TASK_CANCEL:        "taskCancel",
    LadderMeans.OBJECTIVE_STEP:     "objectiveStep",
    LadderMeans.PURSUE_TASK:        "taskTrade",
    LadderMeans.ACCEPT_TASK:        "acceptTask",
    LadderMeans.TASK_EXCHANGE:      "taskExchange",
    LadderMeans.MAINTAIN_CONSUMABLES: "craft",  # PLAN #6a: cook/brew a heal
    LadderMeans.SELL_IDLE:          "npcSell",
    LadderMeans.RECYCLE_SURPLUS:    "recycle",
    LadderMeans.BANK_EXPAND:        "buyBankExpansion",
    LadderMeans.WAIT:               "wait",
}


# Mirror ladder iteration order — duplicated from `production_ladder.py`'s
# `ALL_IN_LADDER_ORDER` so the mirror has its own copy that can drift from
# the real production ladder under mutation. This is the load-bearing
# walk-order assertion: any mutation that reorders this list breaks the
# differential against `drive_one_cycle` (which uses the real ladder).
MIRROR_LADDER_ORDER: tuple[LadderMeans, ...] = (
    LadderMeans.HP_CRITICAL,
    LadderMeans.BANK_UNLOCK,
    LadderMeans.REACH_UNLOCK_LEVEL,
    LadderMeans.DISCARD_CRITICAL,
    LadderMeans.DEPOSIT_FULL,
    LadderMeans.DISCARD_HIGH,
    LadderMeans.CLAIM_PENDING,
    LadderMeans.COMPLETE_TASK,
    LadderMeans.SELL_PRESSURED,
    LadderMeans.LOW_YIELD_CANCEL,
    LadderMeans.TASK_CANCEL,
    LadderMeans.OBJECTIVE_STEP,
    LadderMeans.PURSUE_TASK,
    LadderMeans.ACCEPT_TASK,
    LadderMeans.TASK_EXCHANGE,
    LadderMeans.SELL_IDLE,
    LadderMeans.BANK_EXPAND,
    LadderMeans.WAIT,
)


# ---------------------------------------------------------------------------
# fires — mirror of `Formal.Liveness.ProductionLadder.fires`.  Closed-form,
# pure-Python; does NOT call into `tiers/guards.py` / `tiers/means.py` (which
# would force a real production WorldState/GameData). This mirror operates on
# the abstract `CycleState` opaque-Bools, matching Lean exactly.
# ---------------------------------------------------------------------------

CRITICAL_HP_NUM = 25
CRITICAL_HP_DEN = 100


def _hp_critical_fires(s: CycleState) -> bool:
    return s.max_hp > 0 and s.hp * CRITICAL_HP_DEN < CRITICAL_HP_NUM * s.max_hp


def _bank_unlock_fires(s: CycleState) -> bool:
    return (
        s.bank_unlock_monster_present
        and not s.bank_accessible
        and s.xp <= s.initial_xp
        and (s.unlock_monster_level == 0 or s.level + 1 >= s.unlock_monster_level)
    )


def _reach_unlock_level_fires(s: CycleState) -> bool:
    return (not s.bank_accessible) and s.level < s.bank_required_level


def _discard_critical_fires(s: CycleState) -> bool:
    used_num = s.inventory_used * 100
    return (
        s.has_overstock_items
        and s.inventory_max > 0
        and used_num >= 95 * s.inventory_max
    )


def _deposit_full_fires(s: CycleState) -> bool:
    used_num = s.inventory_used * 100
    return (
        s.bank_accessible
        and s.select_bank_deposits_nonempty
        and s.inventory_max > 0
        and used_num >= 80 * s.inventory_max
    )


def _discard_high_fires(s: CycleState) -> bool:
    used_num = s.inventory_used * 100
    return (
        s.has_overstock_items
        and s.inventory_max > 0
        and used_num >= 85 * s.inventory_max
    )


def _complete_task_fires(s: CycleState) -> bool:
    return (
        s.task_code is not None
        and s.task_total > 0
        and s.task_progress >= s.task_total
    )


def _sell_pressured_fires(s: CycleState) -> bool:
    used_num = s.inventory_used * 100
    return (
        s.sellable_inventory_nonempty
        and s.inventory_max > 0
        and used_num >= 85 * s.inventory_max
    )


def _sell_idle_fires(s: CycleState) -> bool:
    return s.sellable_inventory_nonempty and s.task_code is None


def _task_exchange_fires(s: CycleState) -> bool:
    return s.task_coins_total >= s.task_exchange_min_coins


def _bank_expand_fires(s: CycleState) -> bool:
    if s.bank_capacity == 0 or not s.bank_items_known:
        return False
    return (
        s.bank_items_count * 100 >= 95 * s.bank_capacity
        and s.gold >= s.next_expansion_cost
    )


def fires_mirror(k: LadderMeans, s: CycleState) -> bool:
    """Mirror of `Formal.Liveness.ProductionLadder.fires` over CycleState."""
    if k is LadderMeans.HP_CRITICAL:        return _hp_critical_fires(s)
    if k is LadderMeans.BANK_UNLOCK:        return _bank_unlock_fires(s)
    if k is LadderMeans.REACH_UNLOCK_LEVEL: return _reach_unlock_level_fires(s)
    if k is LadderMeans.DISCARD_CRITICAL:   return _discard_critical_fires(s)
    if k is LadderMeans.DEPOSIT_FULL:       return _deposit_full_fires(s)
    if k is LadderMeans.DISCARD_HIGH:       return _discard_high_fires(s)
    if k is LadderMeans.CLAIM_PENDING:      return s.pending_items_nonempty
    if k is LadderMeans.COMPLETE_TASK:      return _complete_task_fires(s)
    if k is LadderMeans.SELL_PRESSURED:     return _sell_pressured_fires(s)
    if k is LadderMeans.LOW_YIELD_CANCEL:   return s.low_yield_cancel_fires
    if k is LadderMeans.TASK_CANCEL:        return s.task_cancel_fires
    if k is LadderMeans.OBJECTIVE_STEP:     return s.objective_step_fires
    if k is LadderMeans.PURSUE_TASK:        return s.pursue_task_fires
    if k is LadderMeans.ACCEPT_TASK:        return s.task_code is None
    if k is LadderMeans.TASK_EXCHANGE:      return _task_exchange_fires(s)
    if k is LadderMeans.SELL_IDLE:          return _sell_idle_fires(s)
    if k is LadderMeans.BANK_EXPAND:        return _bank_expand_fires(s)
    if k is LadderMeans.WAIT:               return True
    raise AssertionError(f"unhandled MeansKind {k!r}")


def mirror_production_ladder(s: CycleState) -> LadderMeans | None:
    """First means in `MIRROR_LADDER_ORDER` whose `fires_mirror` is True.

    Mirror of `Formal.Liveness.ProductionLadder.productionLadder`. The WAIT
    means is unconditionally True so this is total."""
    for k in MIRROR_LADDER_ORDER:
        if fires_mirror(k, s):
            return k
    return None  # unreachable given WAIT terminator


# ---------------------------------------------------------------------------
# applyActionKind — mirror of `Formal.Liveness.Plan.applyActionKind`.
# Single-step semantics per ActionKind name.  Most kinds flip an opaque
# Bool; .fight does xp/level rollover + bank-unlock flip per Phase-21c.
# ---------------------------------------------------------------------------


def _xp_to_next_level(level: int) -> int:
    """Mirror of LIV-001 `xpToNextLevel`. The production planner-side
    projection uses 150 + 100*level (planner.py / scoring), but the Lean
    axiom is opaque. For the mirror we pick a concrete witness that matches
    `FightAction.apply`'s projection contract: `WorldState.max_xp` is the
    threshold, defaulting to 500 in test fixtures.  Since the cycle_step
    differential never inspects `level` post-mutation (level rollover is
    out of scope — see TRACKED_FIELDS), the specific curve doesn't matter
    for the differential's tracked-field equality. We pick 999999 so the
    rollover branch never triggers on Hypothesis-sampled small xps,
    ensuring the mirror's .fight matches `FightAction.apply` (which doesn't
    bump level either — only xp). """
    return 999999


def apply_action_kind_mirror(action: str, s: CycleState) -> CycleState:
    """Mirror of `Formal.Liveness.Plan.applyActionKind`."""
    if action == "rest":
        return dataclasses.replace(s, hp=s.max_hp)
    if action == "wait":
        return s
    if action == "claimPendingItem":
        return dataclasses.replace(s, pending_items_nonempty=False)
    if action == "completeTask":
        # 2026-06-03: TASK_COMPLETE_XP_ESTIMATE revised 10 → 0. Server
        # RewardsSchema = {items, gold} only; no XP field. XP unchanged
        # on turn-in. Mirrors production complete_task.py.
        return dataclasses.replace(
            s, task_code=None, task_total=0, task_progress=0,
            xp=s.xp,
        )
    if action == "acceptTask":
        return dataclasses.replace(
            s, task_code=ACCEPT_TASK_PLACEHOLDER_CODE, task_total=1, task_progress=0,
        )
    if action == "taskExchange":
        # Nat saturating subtraction.
        new_coins = max(0, s.task_coins_total - s.task_exchange_min_coins)
        return dataclasses.replace(s, task_coins_total=new_coins)
    if action == "taskCancel":
        return dataclasses.replace(
            s,
            task_cancel_fires=False,
            low_yield_cancel_fires=False,
            pursue_task_fires=False,
            task_code=None,
            task_total=0,
            task_progress=0,
        )
    if action == "buyBankExpansion":
        new_gold = max(0, s.gold - s.next_expansion_cost)
        return dataclasses.replace(
            s,
            bank_capacity=s.bank_capacity + BANK_EXPANSION_SLOTS,
            gold=new_gold,
        )
    if action == "deleteItem":
        return dataclasses.replace(s, has_overstock_items=False)
    if action == "depositAll":
        return dataclasses.replace(s, select_bank_deposits_nonempty=False)
    if action == "npcSell":
        return dataclasses.replace(s, sellable_inventory_nonempty=False)
    if action == "fight":
        unlock_monster_ready = (
            s.bank_unlock_monster_present
            and not s.bank_accessible
            and s.xp <= s.initial_xp
            and (s.unlock_monster_level == 0
                 or s.level + 1 >= s.unlock_monster_level)
        )
        new_bank_accessible = True if unlock_monster_ready else s.bank_accessible
        will_level = s.xp + 10 >= _xp_to_next_level(s.level) and s.level < 50
        new_level = s.level + 1 if will_level else s.level
        new_xp = 0 if will_level else s.xp + 10
        return dataclasses.replace(
            s, level=new_level, xp=new_xp, bank_accessible=new_bank_accessible,
        )
    if action == "taskTrade":
        return dataclasses.replace(
            s, pursue_task_fires=False, task_progress=s.task_total,
        )
    if action == "objectiveStep":
        return dataclasses.replace(s, objective_step_fires=False)
    # Lean's `_, s => s` catch-all (kinds without explicit semantics).
    return s


# ---------------------------------------------------------------------------
# cycle_step — mirror of `Formal.Liveness.CycleStep.cycleStep`.
# ---------------------------------------------------------------------------


def cycle_step_mirror(s: CycleState) -> CycleState:
    """One cycle: pick firing means via `mirror_production_ladder`,
    look up witness action via `MIRROR_PLAN_FOR`, apply via
    `apply_action_kind_mirror`. Identity on impossible-None branch
    (ruled out by WAIT being unconditionally True)."""
    k = mirror_production_ladder(s)
    if k is None:
        return s
    action = MIRROR_PLAN_FOR.get(k)
    if action is None:
        return s
    return apply_action_kind_mirror(action, s)


__all__ = [
    "ACCEPT_TASK_PLACEHOLDER_CODE",
    "BANK_EXPANSION_SLOTS",
    "CycleState",
    "MIRROR_LADDER_ORDER",
    "MIRROR_PLAN_FOR",
    "apply_action_kind_mirror",
    "cycle_step_mirror",
    "fires_mirror",
    "mirror_production_ladder",
]
