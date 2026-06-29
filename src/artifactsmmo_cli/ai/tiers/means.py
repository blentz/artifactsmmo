"""Means bands: instrumental/opportunistic actions ranked under the objective
step. Collect-reward sits just below guards; discretionary just below the
objective step. Pure predicates over state/game_data/history + SelectionContext.

No Goal-class imports — the driver (StrategyArbiter) maps MeansKind to goals.
"""

from enum import Enum

from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.consumable_supply import maintain_consumables_fires
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import low_yield_cancel_fires
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
from artifactsmmo_cli.ai.tiers.guards import (
    SelectionContext,
    _gear_protected,
    _has_sellable,
    protected_gear_codes,
)
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

SELL_PRESSURE_FRACTION = 0.85
BANK_EXPAND_FILL = 0.95


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


def _used_fraction(state: WorldState) -> float:
    return state.inventory_used / state.inventory_max if state.inventory_max > 0 else 0.0



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
        return low_yield_cancel_fires(state, history)

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
        # pressure the deposit/discard guards handle space). Fires when surplus
        # craftable gear (not the committed objective) can be recycled for mats.
        # Gear protection (spec 2026-06-28-gear-loadout-profiles): active-profile
        # gear set + cap when available, else the legacy target_gear fallback.
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(recyclable_surplus(
                    state, game_data, _gear_protected(ctx),
                    gear_keep=ctx.gear_keep or None)))

    if kind is MeansKind.DRAIN_BANK_JUNK:
        # Idle/low-pressure only: the withdraw mints items into the bag, so it
        # needs free slots to land (under pressure the deposit/discard guards
        # handle space). Fires when over-cap bank junk exists that is not the
        # committed objective gear.
        return (_used_fraction(state) < SELL_PRESSURE_FRACTION
                and bool(bank_drain_excess(
                    state, game_data, _gear_protected(ctx),
                    gear_keep=ctx.gear_keep or None)))

    if kind is MeansKind.MAINTAIN_CONSUMABLES:
        # Only when combat is the active means (a target is selected): keep a
        # heal stockpile so the bot cooks/brews instead of resting between
        # fights. Gated on under-stock + craftable-better-heal (the shared
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
        fill = len(state.bank_items) / game_data.bank_capacity
        if fill < BANK_EXPAND_FILL:
            return False
        return state.gold >= game_data.next_expansion_cost

    # MeansKind.WAIT: always-firing last-resort. Position-last in
    # DISCRETIONARY_ORDER ensures every other means gets a chance before
    # this candidate is considered by select_pure's positional walk.
    # (Exhaustive over MeansKind — anything else is unreachable.)
    return kind is MeansKind.WAIT


def active_means(
    state: WorldState,
    game_data: GameData,
    history: LearningStore | None,
    ctx: SelectionContext,
) -> tuple[list[MeansKind], list[MeansKind]]:
    """Return (collect_reward, discretionary) — triggered means in declared band order.

    history accepted for parity / used by the cancel predicates (low-yield, pivot).
    """
    collect = [k for k in COLLECT_REWARD_ORDER if _fires(k, state, game_data, history, ctx)]
    discretionary = [k for k in DISCRETIONARY_ORDER if _fires(k, state, game_data, history, ctx)]
    return collect, discretionary
