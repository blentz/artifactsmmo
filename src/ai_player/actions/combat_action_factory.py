"""
Combat Action Factory Implementation

This module provides factory for creating CombatAction instances with proper
monster targeting for combat operations within the GOAP system.
"""

from typing import Any

from ..state.character_game_state import CharacterGameState
from .action_factory import ActionFactory
from .base_action import BaseAction
from .combat_action import CombatAction


class CombatActionFactory(ActionFactory):
    """Factory for creating CombatAction instances with monster targeting."""

    def get_action_type(self) -> type[BaseAction]:
        """Get the action type this factory creates.

        Parameters:
            None

        Return values:
            CombatAction class type for registry identification
        """
        return CombatAction

    def create_instances(self, game_data: Any, current_state: CharacterGameState) -> list[BaseAction]:
        """Create CombatAction instances for available monsters.

        Parameters:
            game_data: Game data containing monsters and API client
            current_state: Current character state for monster filtering

        Return values:
            List of CombatAction instances for available monsters
        """
        actions = []

        # Create generic combat action
        actions.append(CombatAction())

        # Create specific monster combat actions if monsters are available
        if hasattr(game_data, 'monsters') and game_data.monsters:
            for monster in game_data.monsters:
                if hasattr(monster, 'code'):
                    actions.append(CombatAction(target_monster=monster.code))

        return actions
