"""
Reset Combat Context Action

This bridge action resets the combat context from 'completed' back to 'idle',
allowing the character to start a new combat cycle.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class ResetCombatContextAction(ActionBase):
    """
    Bridge action to reset combat context after combat completion.
    
    This action transitions the combat_context.status from 'completed' to 'idle',
    enabling the character to start searching for new combat targets.
    """

    # GOAP parameters
    conditions = {
        'combat_context': {
            'status': 'completed',
        },
    }
    reactions = {
        'combat_context': {
            'status': 'idle',
            'target': None,
            'location': None,
        },
    }
    weights = {'combat_context.status': 1.0}

    def __init__(self):
        """Initialize reset combat context action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute the combat context reset.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                combat_context_reset=True,
                previous_status='completed',
                new_status='idle',
                message="Combat context reset to idle state"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to reset combat context: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "ResetCombatContextAction()"
