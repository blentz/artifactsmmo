"""DiscardOverstockGoal: sell or delete items held beyond their useful cap."""

from artifactsmmo_cli.ai import priorities
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


PRIORITY_WHEN_OVERSTOCKED = priorities.DISCARD_OVERSTOCK_BASE
"""Baseline. Pressure-scaled tiers live in priorities.DISCARD_OVERSTOCK_*."""

HIGH_PRESSURE_FRACTION = 0.85
"""inventory_used/max above this → DISCARD_OVERSTOCK_HIGH_PRESSURE (55).
Preempts gather (50) so bag-near-full triggers a sell/delete cycle before
gather actions start failing on full inventory."""

CRITICAL_PRESSURE_FRACTION = 0.95
"""inventory_used/max above this → DISCARD_OVERSTOCK_CRITICAL (85). Any
further Gather will fail; clear overstock immediately."""


class DiscardOverstockGoal(Goal):
    """Sell (if NPC buys) or delete items held beyond their useful cap."""

    def __init__(self, game_data: GameData) -> None:
        # game_data stashed so is_satisfied (which only receives state per
        # the Goal protocol) can still compute overstock during planning.
        self._gd = game_data

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        return self.priority(state, game_data, history)

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        """Pressure-scaled: baseline when overstock present, escalating as
        the bag fills. Autoregressive sensing — the more inventory pressure,
        the more urgent overstock management becomes relative to gathering."""
        if self.is_satisfied(state):
            return 0.0
        pressure = state.inventory_used / state.inventory_max if state.inventory_max else 0.0
        if pressure >= CRITICAL_PRESSURE_FRACTION:
            return priorities.DISCARD_OVERSTOCK_CRITICAL
        if pressure >= HIGH_PRESSURE_FRACTION:
            return priorities.DISCARD_OVERSTOCK_HIGH_PRESSURE
        return priorities.DISCARD_OVERSTOCK_BASE

    def is_satisfied(self, state: WorldState) -> bool:
        return not overstocked_items(state, self._gd)

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
        excess = overstocked_items(state, game_data)
        if not excess:
            return []
        result: list[Action] = []
        for code, excess_qty in excess.items():
            if excess_qty <= 0:
                continue
            buyers = game_data.npcs_buying_item(code)
            if buyers:
                # npcs_buying_item sorted highest-first
                npc_code, _price = buyers[0]
                npc_loc = game_data.npc_location(npc_code)
                result.append(NpcSellAction(
                    npc_code=npc_code, item_code=code, quantity=excess_qty,
                    npc_location=npc_loc,
                ))
            else:
                result.append(DeleteItemAction(code=code, quantity=excess_qty))
        return result

    def __repr__(self) -> str:
        return "DiscardOverstock"
