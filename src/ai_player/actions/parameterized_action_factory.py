"""
Parameterized Action Factory

This module defines the ParameterizedActionFactory base class for actions
requiring parameters (locations, targets, etc.).
"""

from abc import abstractmethod
from typing import Any

from ..state.character_game_state import CharacterGameState
from .action_factory import ActionFactory
from .base_action import BaseAction


class ParameterizedActionFactory(ActionFactory):
    """Base factory for actions requiring parameters (locations, targets, etc.)"""

    def __init__(self, action_class: type[BaseAction]):
        self.action_class = action_class

    def get_action_type(self) -> type[BaseAction]:
        return self.action_class

    @abstractmethod
    def generate_parameters(self, game_data: Any, current_state: CharacterGameState) -> list[dict[str, Any]]:
        """Generate all valid parameter combinations for this action type.

        Parameters:
            game_data: Complete game data including maps, items, monsters, resources
            current_state: CharacterGameState instance with current character state

        Return values:
            List of parameter dictionaries for action instance creation

        This method analyzes the current game state and available data to
        generate all valid parameter combinations for creating instances
        of the parameterized action type.
        """
        pass

    def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
        """Create action instances for all valid parameter combinations"""
        instances = []
        for params in self.generate_parameters(game_data, current_state):
            # Extract location_type for special handling
            location_type = params.pop("location_type", None)

            # Create the action instance
            instance = self.action_class(**params)

            # Set location type as a private attribute if provided
            if location_type:
                instance._location_type = location_type

            instances.append(instance)
        return instances
