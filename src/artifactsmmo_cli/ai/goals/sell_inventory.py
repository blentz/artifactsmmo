"""Sell inventory items to NPCs to clear space when bank is inaccessible."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.survival import MIN_FREE_SLOTS
from artifactsmmo_cli.ai.world_state import WorldState


class SellInventoryGoal(Goal):
    """Recover gold by selling inventory items when the bank is locked."""

    def __init__(self, bank_accessible: bool = True) -> None:
        self._bank_accessible = bank_accessible

    def value(self, state: WorldState, game_data: GameData) -> float:
        if self._bank_accessible or state.inventory_max == 0:
            return 0.0
        # Any sellable item in inventory?
        if not any(game_data.npcs_buying_item(code) for code in state.inventory if state.inventory[code] > 0):
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        return used_fraction * 100.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.inventory_free >= MIN_FREE_SLOTS

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        return {"inventory_free": MIN_FREE_SLOTS}

    def relevant_actions(self, actions: list[Action], state: WorldState, game_data: GameData) -> list[Action]:
        result: list[Action] = []
        for action in actions:
            if isinstance(action, RestAction):
                result.append(action)
            elif isinstance(action, NpcSellAction) and state.inventory.get(action.item_code, 0) > 0:
                result.append(action)
        return result

    def __repr__(self) -> str:
        return "SellInventory"
