"""DiscardOverstockGoal: sell, recycle, bank, or delete the copies the keep authority
licenses, for items the space-pressure gate reports as overstock."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.discard_surplus import discardable_surplus
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.shed_actions import shed_actions
from artifactsmmo_cli.ai.thresholds import (
    PRESSURE_CRITICAL_FRACTION,
    PRESSURE_HIGH_FRACTION,
)
from artifactsmmo_cli.ai.world_state import WorldState

# Value constants (inlined from retired priorities.py).
# Baseline: below GATHER_MATERIALS (50) — overstock is non-urgent during normal chains.
_DISCARD_OVERSTOCK_BASE = 40.0
# High-pressure tier (inventory > 85%): above GATHER_MATERIALS so we preempt gather.
_DISCARD_OVERSTOCK_HIGH_PRESSURE = 55.0
# Critical tier (inventory > 95%): above DEPOSIT_FULL (80), below COMPLETE_TASK (90).
_DISCARD_OVERSTOCK_CRITICAL = 85.0

PRIORITY_WHEN_OVERSTOCKED = _DISCARD_OVERSTOCK_BASE
"""Baseline. Pressure-scaled tiers use _DISCARD_OVERSTOCK_* module constants."""

HIGH_PRESSURE_FRACTION = PRESSURE_HIGH_FRACTION
"""inventory_used/max above this → _DISCARD_OVERSTOCK_HIGH_PRESSURE (55).
Preempts gather (50) so bag-near-full triggers a sell/delete cycle before
gather actions start failing on full inventory. The 0.85 value is the shared
pressure-ladder HIGH rung (single source: ai/thresholds.py)."""

CRITICAL_PRESSURE_FRACTION = PRESSURE_CRITICAL_FRACTION
"""inventory_used/max above this → _DISCARD_OVERSTOCK_CRITICAL (85). Any
further Gather will fail; clear overstock immediately. The 0.95 value is the
shared pressure-ladder CRITICAL rung (single source: ai/thresholds.py)."""


class DiscardOverstockGoal(Goal):
    """Sell (if an NPC buys), else recycle/bank/delete the copies the keep authority
    licenses, for the items the space-pressure gate reports as overstock.

    WHAT MAY BE SHED IS THE KEEP AUTHORITY'S ANSWER, not this goal's
    (item-protection-authority epic, Task 9): `ai/discard_surplus.discardable_surplus`
    licenses `min(bankable, destroyable)` copies, so the equipped copy, the active
    profile's gear demand, the recipe demand, the task's own item, the currency, the
    heal stock and — through the in-bag half of the `min` — the last WORKING tool /
    COMBAT weapon all survive the DELETE. The goal used to take a `profile` code-set
    closure (`guards.active_profile`, rooted on the `target_gear | target_tools`
    blanket) merged with the `useful_quantity_cap` heuristic; both are gone.
    """

    def __init__(self, game_data: GameData, ctx: SelectionContext,
                 bank_accessible: bool = False) -> None:
        # game_data stashed so is_satisfied (which only receives state per
        # the Goal protocol) can still compute the surplus during planning.
        self._gd = game_data
        # The per-cycle SelectionContext the keep authority reads (gear_keep,
        # step_profile). It REPLACES the `profile` code-set closure.
        self._ctx = ctx
        # Threaded from SelectionContext at the strategy_driver build site
        # (not a WorldState field): gates the disposal-route DEPOSIT arm.
        self._bank_accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        """Pressure-scaled, space-driven (spec 2026-06-07): overstock only
        EXISTS at/above the high watermark (DISCARD_WATERMARK == 0.85), so a
        non-satisfied DiscardOverstock is already under genuine space pressure.
        The value escalates again at the critical fraction. Below the watermark
        there is no overstock and the goal is satisfied (value 0) — the bag's
        free slots are not a dump trigger."""
        if self.is_satisfied(state):
            return 0.0
        pressure = state.inventory_used / state.inventory_max if state.inventory_max else 0.0
        if pressure >= CRITICAL_PRESSURE_FRACTION:
            return _DISCARD_OVERSTOCK_CRITICAL
        # Overstock implies pressure >= DISCARD_WATERMARK == HIGH_PRESSURE_FRACTION.
        return _DISCARD_OVERSTOCK_HIGH_PRESSURE

    def is_satisfied(self, state: WorldState) -> bool:
        return not discardable_surplus(state, self._gd, self._ctx)

    @property
    def max_depth(self) -> int:
        """Plan needs one Delete/Sell per overstocked item to fully satisfy.
        Default 15 cuts off when many items are overstocked → plan_len=0 →
        the goal silently loses to a lower-priority alternative."""
        return 64

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory_overstock_cleared": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """Construct one BATCH Sell / Recycle / Deposit / Delete per shed-eligible item.

        Bypasses the pre-built quantity=1 actions in `actions` and emits a
        single-cycle batch action per item so one cycle clears one item's
        licensed surplus entirely. Sell wins when any NPC buys — gold > zero; Sell
        picks the highest-paying NPC. With no executable sale the item is
        routed by the proved `disposal_route`: recycle > deposit > delete.
        """
        excess = discardable_surplus(state, game_data, self._ctx)
        if not excess:
            return []
        result: list[Action] = []
        for code, excess_qty in excess.items():
            result.extend(shed_actions(code, excess_qty, state, game_data, self._ctx,
                                       self._bank_accessible))
        return result

    def __repr__(self) -> str:
        return "DiscardOverstock"
