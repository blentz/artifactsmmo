"""Survival goals: HP restoration and inventory management."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState

MIN_FREE_SLOTS = 5


class RestoreHPGoal(Goal):
    """Restore HP to full. Urgency spikes when HP is low."""

    def value(self, state: WorldState, game_data: GameData) -> float:
        return (1.0 - state.hp_percent) * 100.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.hp >= state.max_hp

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        return {"hp": state.max_hp}

    def __repr__(self) -> str:
        return "RestoreHP"


class DepositInventoryGoal(Goal):
    """Deposit inventory to bank when it's nearly full."""

    def value(self, state: WorldState, game_data: GameData) -> float:
        if state.inventory_max == 0:
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        return used_fraction * 80.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.inventory_free >= MIN_FREE_SLOTS

    def desired_state(self, state: WorldState, game_data: GameData) -> dict:
        return {"inventory_free": MIN_FREE_SLOTS}

    def __repr__(self) -> str:
        return "DepositInventory"
