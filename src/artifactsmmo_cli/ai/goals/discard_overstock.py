"""DiscardOverstockGoal: sell or delete items held beyond their useful cap."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.ge_fill import GeFillBuyOrderAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.liquidation_venue import Venue, liquidation_venue
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
    """Sell (if NPC buys) or delete items held beyond their useful cap."""

    def __init__(self, game_data: GameData,
                 profile: dict[str, int] | None = None) -> None:
        # game_data stashed so is_satisfied (which only receives state per
        # the Goal protocol) can still compute overstock during planning.
        self._gd = game_data
        # The active goal's soft inventory profile — never discard a profile
        # item below its target (spec 2026-06-07).
        self._profile = profile or {}

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
        return not overstocked_items(state, self._gd, profile=self._profile)

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
        """Construct one BATCH Sell or Delete per overstocked item.

        Bypasses the pre-built quantity=1 actions in `actions` and emits a
        single-cycle batch action per item so one cycle clears one item's
        overstock entirely. Sell wins over Delete when any NPC buys —
        gold > zero. Sell picks the highest-paying NPC.
        """
        excess = overstocked_items(state, game_data, profile=self._profile)
        if not excess:
            return []
        result: list[Action] = []
        for code, excess_qty in excess.items():
            buyers = game_data.npcs_buying_item(code)
            npc_loc: tuple[int, int] | None = None
            npc_code: str | None = None
            if buyers:
                # npcs_buying_item sorted highest-first
                npc_code, _price = buyers[0]
                npc_loc = game_data.npc_location(npc_code)
            # Immediate-fill GE liquidation: when a standing GE buy order pays
            # strictly more than the best NPC sell-back AND can absorb the whole
            # excess in one fill, offer a GeFillBuyOrder. liquidation_venue → GE
            # (gated by choose_venue, proved in formal/Formal/LiquidationVenue.lean)
            # is the decision; the least-cost / higher-proceeds planner then picks
            # GE vs NPC. We only fill an EXISTING order — never post a new one.
            ge_loc = game_data.grand_exchange_location()
            order = game_data.ge_best_buy_order(code)
            ge_action_available = False
            if ge_loc is not None and order is not None and \
                    liquidation_venue(code, excess_qty, state, game_data) is Venue.GE:
                order_id, price, _order_qty = order
                result.append(GeFillBuyOrderAction(
                    order_id=order_id, item_code=code, price=price,
                    quantity=excess_qty, ge_location=ge_loc,
                ))
                ge_action_available = True

            sell_action: NpcSellAction | None = None
            if npc_code is not None and npc_loc is not None:
                sell_action = NpcSellAction(
                    npc_code=npc_code, item_code=code, quantity=excess_qty,
                    npc_location=npc_loc,
                )
                result.append(sell_action)
            # Delete fallback: emit a Delete whenever there is no fillable GE order
            # AND no EXECUTABLE sell — i.e. no sell action at all, OR the sell
            # action is not currently applicable. The latter is the dormant
            # event-merchant case (trace 2026-06-24): sap's only buyer is the
            # `timber_merchant` event NPC — it HAS a location (so the old
            # `npc_loc is None` guard left Delete unoffered) but its spawn window
            # is closed, so NpcSellAction.is_applicable is False. With neither sell
            # nor delete executable the overstock never clears → the bag-full
            # Withdraw↔Deposit livelock. Delete frees the slot for a worthless-NOW
            # item; when the event later spawns, the sell (gold) is preferred.
            if not ge_action_available and (
                sell_action is None
                or not sell_action.is_applicable(state, game_data)
            ):
                result.append(DeleteItemAction(code=code, quantity=excess_qty))
        return result

    def __repr__(self) -> str:
        return "DiscardOverstock"
