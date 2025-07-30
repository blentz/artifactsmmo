"""
Gathering Action Factory Implementation

This module provides factory for creating GatheringAction instances with proper
resource targeting and API client injection for gathering operations within the GOAP system.
"""

from typing import Any

from ..state.game_state import GameState
from ..state.character_game_state import CharacterGameState
from .action_factory import ActionFactory
from .base_action import BaseAction
from .gathering_action import GatheringAction


class GatheringActionFactory(ActionFactory):
    """Factory for creating GatheringAction instances with resource targeting."""

    def get_action_type(self) -> type[BaseAction]:
        """Get the action type this factory creates.
        
        Parameters:
            None
            
        Return values:
            GatheringAction class type for registry identification
        """
        return GatheringAction

    def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
        """Create GatheringAction instances for available resources.
        
        Parameters:
            game_data: Game data containing resources and API client
            current_state: Current character state for resource filtering
            
        Return values:
            List of GatheringAction instances for available resources
        """
        actions = []
        
        # Extract API client from game_data if available
        api_client = getattr(game_data, 'api_client', None) if game_data else None
        
        # Create generic gathering action
        actions.append(GatheringAction(api_client=api_client))
        
        # Create specific resource gathering actions if resources are available
        if hasattr(game_data, 'resources') and game_data.resources:
            for resource in game_data.resources:
                if hasattr(resource, 'code'):
                    actions.append(GatheringAction(resource_type=resource.code, api_client=api_client))
        
        return actions