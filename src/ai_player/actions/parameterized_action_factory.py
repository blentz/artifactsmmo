"""
Parameterized Action Factory

This module defines the ParameterizedActionFactory base class for actions
requiring parameters (locations, targets, etc.).
"""

from abc import abstractmethod
from typing import Any

from ..state.game_state import GameState
from .action_factory import ActionFactory
from .base_action import BaseAction


class ParameterizedActionFactory(ActionFactory):
    """Base factory for actions requiring parameters (locations, targets, etc.)"""

    def __init__(self, action_class: type[BaseAction]):
        self.action_class = action_class

    def get_action_type(self) -> type[BaseAction]:
        return self.action_class

    @abstractmethod
    def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
        """Generate all valid parameter combinations for this action type.

        Parameters:
            game_data: Complete game data including maps, items, monsters, resources
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of parameter dictionaries for action instance creation

        This method analyzes the current game state and available data to
        generate all valid parameter combinations for creating instances
        of the parameterized action type.
        """
        pass

    def create_instances(self, game_data: Any, current_state: dict[GameState, Any]) -> list[BaseAction]:
        """Create action instances for all valid parameter combinations"""
        instances = []
        for params in self.generate_parameters(game_data, current_state):
            instances.append(self.action_class(**params))
        return instances