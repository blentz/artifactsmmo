"""Means bands: instrumental/opportunistic actions ranked under the objective
step. Collect-reward sits just below guards; discretionary just below the
objective step. Pure predicates over state/game_data/history + SelectionContext.

No Goal-class imports — the driver (StrategyArbiter) maps MeansKind to goals.
"""

from enum import Enum

from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.bank_expansion_timing import (
    TRIGGER_FILL_DEN,
    TRIGGER_FILL_NUM,
    should_expand_bank,
)
from artifactsmmo_cli.ai.consumable_supply import maintain_consumables_fires
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import low_yield_cancel_fires
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
from artifactsmmo_cli.ai.thresholds import PRESSURE_HIGH_FRACTION
from artifactsmmo_cli.ai.tiers.guards import (
    SelectionContext,
    _has_sellable,
    _used_fraction,
)
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

# Semantic name for this module's sell-pressure gate, bound to the SHARED
# single-source constant (thresholds.py pressure ladder). It used to be a
# re-typed literal (0.85) — the drift the thresholds consolidation was built
# to kill; the local name is kept because the ladder's proven mutation
# anchors bind to the usage lines. (BANK_EXPAND's fill gate now lives inside
# the shared should_expand_bank core — no local constant.)
SELL_PRESSURE_FRACTION = PRESSURE_HIGH_FRACTION


class MeansKind(Enum):
    CLAIM_PENDING = "claim_pending"
    COMPLETE_TASK = "complete_task"
    SELL_PRESSURED = "sell_pressured"
    LOW_YIELD_CANCEL = "low_yield_cancel"
    TASK_CANCEL = "task_cancel"
    PURSUE_TASK = "pursue_task"
    ACCEPT_TASK = "accept_task"
    TASK_EXCHANGE = "task_exchange"
    SELL_IDLE = "sell_idle"
    RECYCLE_SURPLUS = "recycle_surplus"
    BANK_EXPAND = "bank_expand"
    WAIT = "wait"
    # Appended LAST so the DecideKey oracle's index dispatch and the diff test's
    # _MEANS_INDEX stay stable — enum identity is independent of the
    # DISCRETIONARY_ORDER priority slot below (PLAN #6a).
    MAINTAIN_CONSUMABLES = "maintain_consumables"
    DRAIN_BANK_JUNK = "drain_bank_junk"  # 2026-06-24: drain over-cap bank junk.


COLLECT_REWARD_ORDER: tuple[MeansKind, ...] = (
    MeansKind.CLAIM_PENDING,
    MeansKind.COMPLETE_TASK,
    MeansKind.SELL_PRESSURED,
    MeansKind.LOW_YIELD_CANCEL,
    MeansKind.TASK_CANCEL,
)
DISCRETIONARY_ORDER: tuple[MeansKind, ...] = (
    MeansKind.PURSUE_TASK,
    MeansKind.ACCEPT_TASK,
    MeansKind.TASK_EXCHANGE,
    MeansKind.MAINTAIN_CONSUMABLES,  # prep heals for combat before idle housekeeping
    MeansKind.SELL_IDLE,
    MeansKind.RECYCLE_SURPLUS,
    MeansKind.BANK_EXPAND,
    # Lowest-value housekeeping (15), just above WAIT: drain over-cap bank junk
    # only when nothing better — incl. a bank-expansion investment — is pending.
    MeansKind.DRAIN_BANK_JUNK,
    MeansKind.WAIT,
)


def _tasks_coin_total(state: WorldState) -> int:
    return state.inventory.get(TASKS_COIN_CODE, 0) + (state.bank_items or {}).get(TASKS_COIN_CODE, 0)


def _fires(kind: MeansKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext) -> bool:
    if kind is MeansKind.CLAIM_PENDING:
        return bool(state.pending_items)

    if kind is MeansKind.COMPLETE_TASK:
        return (bool(state.task_code) and state.task_total > 0
                and state.task_progress >= state.task_total)

    if kind is MeansKind.SELL_PRESSURED:
        return _used_fraction(state) >= SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)

    if kind is MeansKind.LOW_YIELD_CANCEL:
        return low_yield_cancel_fires(state, game_data, history)

    if kind is MeansKind.TASK_CANCEL:
        if not state.task_code or history is None:
            return False
        return task_decision(state, game_data, history) == PIVOT

    if kind is MeansKind.PURSUE_TASK:
        return (state.task_type == "items"
                and bool(state.task_code) and state.task_total > 0
                and state.task_progress < state.task_total
                and history is not None
                and task_decision(state, game_data, history) == PURSUE)

    if kind is MeansKind.ACCEPT_TASK:
        if state.task_code:
            return False
        # Defer AcceptTask whenever the player has GEAR-CHAIN work to do.
        # An immediate AcceptTask after TaskComplete re-locks the cycle
        # into another items task before UpgradeEquipment can fire,
        # leaving target gear unworn for hundreds of cycles. Two
        # deferral conditions:
        #   (a) target gear is OWNED but UNEQUIPPED → UpgradeEquipment
        #       should win first (one-action equip);
        #   (b) target gear is CRAFTABLE under current skill levels →
        #       the fallback walk should drive the gather/craft chain
        #       rather than accept another task that competes for the
        #       same materials.
        # Both conditions are about the AI's own gear pipeline, not the
        # task economy — accepting a task while gear is in progress
        # creates contention for materials (copper_bar) that the gear
        # chain needs. Trace 2026-06-06 12:28: 2 copper_daggers crafted
        # via CraftRelief never equipped; full armor set never started
        # despite 2300+ gold and crafting skills at level 6+.
        equipped = {c for c in state.equipment.values() if c is not None}
        for code in ctx.target_gear:
            if code in equipped:
                continue
            if state.inventory.get(code, 0) > 0:
                return False  # owned + unequipped → defer for UpgradeEquipment
            stats = game_data.item_stats(code)
            if stats is None or not stats.crafting_skill:
                continue
            if state.skills.get(stats.crafting_skill, 1) >= stats.crafting_level:
                return False  # craftable now → defer for gear chain
        return True

    if kind is MeansKind.TASK_EXCHANGE:
        return _tasks_coin_total(state) >= ctx.task_exchange_min_coins

    if kind is MeansKind.SELL_IDLE:
        return _used_fraction(state) < SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)

    if kind is MeansKind.RECYCLE_SURPLUS:
        # Idle/low-pressure only: recovered materials need room to land (under
        # pressure the deposit/discard guards handle space). Fires when the keep
        # authority (`ai/inventory_keep`) licenses the destruction of surplus
        # craftable gear — copies above BOTH keep_in_bag and keep_owned, so the
        # equipped copy, the profile's demand and the working tool are never it.
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(recyclable_surplus(state, game_data, ctx)))

    if kind is MeansKind.DRAIN_BANK_JUNK:
        # Idle/low-pressure only: the withdraw mints items into the bag, so it
        # needs free slots to land (under pressure the deposit/discard guards
        # handle space). Fires when the keep authority (`ai/inventory_keep`)
        # licenses the destruction of over-cap BANK junk — copies above
        # `keep_owned`, so the last tool, the last weapon and the profile's gear
        # demand are never withdrawn into the discard ladder's mouth.
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(bank_drain_excess(state, game_data, ctx)))

    if kind is MeansKind.MAINTAIN_CONSUMABLES:
        # Only when combat is the active means (a target is selected): keep a
        # heal stockpile for MID-FIGHT drinking. NOT "instead of resting between
        # fights" -- resting between fights is cheap since Rest went dynamic
        # (max(3, ceil(missing%))s, refills to full), so stocking to avoid it
        # never pays. Gated on under-stock + craftable-better-heal (the shared
        # pure predicate). PLAN #6a.
        if ctx.combat_monster is None:
            return False
        return maintain_consumables_fires(state, game_data)

    if kind is MeansKind.BANK_EXPAND:
        if not ctx.bank_accessible:
            return False
        if state.bank_items is None:
            return False
        if game_data.bank_capacity == 0:
            return False
        # SAME proven decision the goal uses (should_expand_bank: exact
        # integer fill cross-multiply + the gold-reserve safety gate). The
        # old guard re-typed a float fill compare and the pre-fix bare
        # `gold >= cost` — the exact SAFETY-HOLE the core closed — so the
        # arbiter admitted candidates ExpandBankGoal.value then scored 0
        # (drift flagged 2026-07-06). A bank expansion is never a reserved
        # gear code, so the player threads reserve_floor(state, gd, None)
        # as ctx.gold_reserve (means.py cannot import progression_reserve —
        # tiers package cycle), mirroring the goal. (The goal also raises `used` by the
        # active-profile floor — history-dependent; the means guard has no
        # history and keeps the plain count, as before.)
        return should_expand_bank(
            len(state.bank_items), game_data.bank_capacity, state.gold,
            game_data.next_expansion_cost, ctx.gold_reserve,
            TRIGGER_FILL_NUM, TRIGGER_FILL_DEN,
        )

    # MeansKind.WAIT: always-firing last-resort. Position-last in
    # DISCRETIONARY_ORDER ensures every other means gets a chance before
    # this candidate is considered by select_pure's positional walk.
    # (Exhaustive over MeansKind — anything else is unreachable.)
    return kind is MeansKind.WAIT


def means_fires(kind: MeansKind, state: WorldState, game_data: GameData,
                history: LearningStore | None, ctx: SelectionContext) -> bool:
    """Whether ONE means kind fires — the single-kind public face of `_fires`.

    `StrategyArbiter.select` needs exactly one predicate BEFORE the rest:
    `PURSUE_TASK`, which decides whether the objective step is task-suppressed and
    therefore whether the step has a protection profile to bind onto the ctx. The
    remaining kinds are evaluated (via `active_means`) AFTER that binding, because
    three of them — SELL_IDLE, RECYCLE_SURPLUS, DRAIN_BANK_JUNK — read the keep
    authority, which reads `ctx.step_profile`. Evaluating them on the unbound ctx
    made the predicate and the goal it maps to disagree (the predicate saw an EMPTY
    step profile, the goal saw the full one), so a means could fire on surplus its
    goal then refused to shed: a zero-length plan candidate.

    PURSUE_TASK itself reads only `state.task_*` and the learning history — no ctx
    field at all — so evaluating it before the binding is exactly the same verdict
    as after, which is what makes the ordering sound."""
    return _fires(kind, state, game_data, history, ctx)


def active_means(
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    ctx: SelectionContext,
) -> tuple[list[MeansKind], list[MeansKind]]:
    """Return (collect_reward, discretionary) — triggered means in declared band order.

    history accepted for parity / used by the cancel predicates (low-yield, pivot).

    CALL ORDER (load-bearing): the caller must bind `ctx.step_profile` BEFORE
    calling this — SELL_IDLE / RECYCLE_SURPLUS / DRAIN_BANK_JUNK read the keep
    authority, which reads that field. See `means_fires`.
    """
    collect = [k for k in COLLECT_REWARD_ORDER if _fires(k, state, game_data, history, ctx)]
    discretionary = [k for k in DISCRETIONARY_ORDER if _fires(k, state, game_data, history, ctx)]
    return collect, discretionary
