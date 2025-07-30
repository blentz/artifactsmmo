"""
Action Factory Abstract Base Class

This module defines the ActionFactory abstract base class for generating
parameterized action instances in the GOAP system.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..state.game_state import GameState
from ..state.character_game_state import CharacterGameState
from .base_action import BaseAction


class ActionFactory(ABC):
    """Abstract factory for generating parameterized action instances"""

    @abstractmethod
    def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
        """Generate all possible action instances for current game state.

        Parameters:
            game_data: Complete game data including maps, items, monsters, resources
            current_state: CharacterGameState instance with current character state

        Return values:
            List of BaseAction instances generated for current conditions

        This method generates all valid action instances that can be executed
        in the current game state, enabling dynamic GOAP planning with
        context-aware action availability.
        """
        pass

    @abstractmethod
    def get_action_type(self) -> type[BaseAction]:
        """Return the action class this factory creates.

        Parameters:
            None

        Return values:
            Type object representing the BaseAction subclass this factory produces

        This method identifies the specific action type that this factory
        generates, enabling the registry to organize and categorize actions
        for efficient GOAP planning and execution.
        """
        pass