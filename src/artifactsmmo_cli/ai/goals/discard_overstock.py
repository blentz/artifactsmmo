"""DiscardOverstockGoal: sell or delete items held beyond their useful cap."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.inventory_caps import overstocked_items
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


PRIORITY_WHEN_OVERSTOCKED = 40.0
"""Above FarmItems(35) so the loop offloads overstock before continuing
tactical pursuits, but below survival/blocker goals."""


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
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_OVERSTOCKED

    def is_satisfied(self, state: WorldState) -> bool:
        return not overstocked_items(state, self._gd)

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory_overstock_cleared": True}

    def relevant_actions(
        self, actions: list[Action], state: WorldState, game_data: GameData,
    ) -> list[Action]:
        """Only Sell/Delete for items currently overstocked. Prefer Sell when
        a buyer exists; Delete is the fallback."""
        excess = overstocked_items(state, game_data)
        if not excess:
            return []
        result: list[Action] = []
        for action in actions:
            if isinstance(action, NpcSellAction):
                if action.item_code in excess and game_data.npcs_buying_item(action.item_code):
                    result.append(action)
            elif isinstance(action, DeleteItemAction):
                if action.code in excess:
                    # Only allow delete when no NPC buys this item — sell
                    # is always strictly better (gold > zero).
                    if not game_data.npcs_buying_item(action.code):
                        result.append(action)
        return result

    def __repr__(self) -> str:
        return "DiscardOverstock"
