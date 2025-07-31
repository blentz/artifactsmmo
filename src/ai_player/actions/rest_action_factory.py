"""
Rest Action Factory Implementation

This module provides factory for creating RestAction instances with proper
API client injection for HP recovery operations within the GOAP system.
"""

from typing import Any

from ..state.character_game_state import CharacterGameState
from .action_factory import ActionFactory
from .base_action import BaseAction
from .rest_action import RestAction


class RestActionFactory(ActionFactory):
    """Factory for creating RestAction instances with API client injection."""

    def get_action_type(self) -> type[BaseAction]:
        """Get the action type this factory creates.

        Parameters:
            None

        Return values:
            RestAction class type for registry identification
        """
        return RestAction

    def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
        """Create RestAction instance with API client from game_data.

        Parameters:
            game_data: Game data containing API client
            current_state: Current character state (unused for rest action)

        Return values:
            List containing single RestAction instance with injected API client
        """
        # Extract API client from game_data if available
        api_client = getattr(game_data, 'api_client', None) if game_data else None

        return [RestAction(api_client=api_client)]
