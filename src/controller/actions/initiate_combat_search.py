"""
InitiateCombatSearchAction - Bridge action to transition combat context from idle to searching.

This action serves as a bridge in the GOAP planning system to allow characters to transition
from idle combat state to actively searching for monsters.
"""

import logging
from typing import Dict

from src.lib.action_context import ActionContext

from .base import ActionBase


class InitiateCombatSearchAction(ActionBase):
    """
    Bridge action that transitions combat context from 'idle' to 'searching'.
    
    This enables the GOAP planner to create plans that include monster hunting
    by providing the necessary state transition.
    """
    
    # GOAP parameters - consolidated state format
    conditions = {
        'combat_context': {
            'status': 'idle'
        },
        'character_status': {
            'alive': True,
            'cooldown_active': False
        }
    }
    
    reactions = {
        'combat_context': {
            'status': 'searching'
        }
    }
    
    weights = {'initiate_combat_search': 2.0}
    weight = 2
    g = 1  # GOAP cost
    
    def __init__(self):
        """Initialize the initiate combat search action."""
        self.logger = logging.getLogger(__name__)
    
    def execute(self, client, context: ActionContext) -> Dict:
        """
        Execute the combat search initiation.
        
        This is a logical state transition that doesn't require API calls.
        It simply marks the character's combat context as ready to search for monsters.
        
        Args:
            client: API client (not used for this action)
            context: Action execution context
            
        Returns:
            Success response with updated combat context
        """
        try:
            self.logger.info("🔍 Initiating combat search - transitioning from idle to searching")
            
            # This is a pure state transition action
            # The actual monster search will be handled by find_monsters action
            
            return {
                'success': True,
                'action': 'InitiateCombatSearchAction',
                'combat_context': {
                    'status': 'searching',
                    'target': None,
                    'location': None
                },
                'message': 'Combat search initiated - ready to find monsters'
            }
            
        except Exception as e:
            self.logger.error(f"Failed to initiate combat search: {e}")
            return {
                'success': False,
                'action': 'InitiateCombatSearchAction',
                'error': f"Failed to initiate combat search: {str(e)}"
            }
    
    def __repr__(self):
        return "InitiateCombatSearchAction()"