"""Means bands: instrumental/opportunistic actions ranked under the objective
step. Collect-reward sits just below guards; discretionary just below the
objective step. Pure predicates over state/game_data/history + SelectionContext.

No Goal-class imports — the driver (StrategyArbiter) maps MeansKind to goals.
"""

from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import low_yield_cancel_fires
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import PIVOT, PURSUE, task_decision
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

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
    BANK_EXPAND = "bank_expand"


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
    MeansKind.SELL_IDLE,
    MeansKind.BANK_EXPAND,
)


def _used_fraction(state: WorldState) -> float:
    return state.inventory_used / state.inventory_max if state.inventory_max > 0 else 0.0


def _has_sellable(state: WorldState, game_data: GameData) -> bool:
    return any(
        qty > 0 and game_data.npcs_buying_item(code)
        for code, qty in state.inventory.items()
    )


def _tasks_coin_total(state: WorldState) -> int:
    return state.inventory.get("tasks_coin", 0) + (state.bank_items or {}).get("tasks_coin", 0)


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
        return not state.task_code

    if kind is MeansKind.TASK_EXCHANGE:
        return _tasks_coin_total(state) >= ctx.task_exchange_min_coins

    if kind is MeansKind.SELL_IDLE:
        return _used_fraction(state) < SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)

    if kind is MeansKind.BANK_EXPAND:
        if not ctx.bank_accessible:
            return False
        if state.bank_items is None:
            return False
        if game_data._bank_capacity == 0:
            return False
        fill = len(state.bank_items) / game_data._bank_capacity
        if fill < BANK_EXPAND_FILL:
            return False
        return state.gold >= game_data._next_expansion_cost

    return False  # pragma: no cover — exhaustive over MeansKind enum


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
