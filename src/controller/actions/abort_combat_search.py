"""
Abort Combat Search Action

This bridge action aborts an unsuccessful combat search by transitioning
the combat context from 'searching' back to 'idle'.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class AbortCombatSearchAction(ActionBase):
    """
    Bridge action to abort combat search when no monsters are available.
    
    This action transitions the combat_context.status from 'searching' to 'idle'
    when monster search has been unsuccessful, preventing the character from
    getting stuck in the searching state.
    """

    # GOAP parameters
    conditions = {
        'combat_context': {
            'status': 'searching',
        },
        'resource_availability': {
            'monsters': False,
        },
    }
    reactions = {
        'combat_context': {
            'status': 'idle',
            'target': None,
            'location': None,
        },
    }
    weights = {'combat_context.status': 1.5}

    def __init__(self):
        """Initialize abort combat search action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute the combat search abort.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Log the reason for aborting
            self.logger.info("🚫 Aborting combat search - no monsters available in area")
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                combat_search_aborted=True,
                previous_status='searching',
                new_status='idle',
                reason="No monsters available",
                message="Combat search aborted, returning to idle state"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to abort combat search: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "AbortCombatSearchAction()"