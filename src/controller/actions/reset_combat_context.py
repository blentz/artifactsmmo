"""
Reset Combat Context Action

This bridge action resets the combat context from 'completed' back to 'idle',
allowing the character to start a new combat cycle.
"""

from typing import Dict

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class ResetCombatContextAction(ActionBase):
    """
    Bridge action to reset combat context after combat completion or defeat.
    
    This action transitions the combat_context.status from 'completed' or 'defeated' to 'idle',
    enabling the character to start searching for new combat targets.
    """

    # GOAP parameters
    conditions = {
        'combat_context': {
            'status': ['completed', 'defeated'],
        },
    }
    reactions = {
        'combat_context': {
            'status': 'idle',
            'target': None,
            'location': None,
        },
    }
    weight = 1.0

    def __init__(self):
        """Initialize reset combat context action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the combat context reset after completion or defeat.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # This is a bridge action - it only updates state, no API calls needed
            # Get current status for logging
            current_status = context.get(StateParameters.COMBAT_STATUS, 'unknown')
            
            result = self.create_success_result(
                combat_context_reset=True,
                previous_status=current_status,
                new_status='idle',
                message=f"Combat context reset from {current_status} to idle state"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to reset combat context: {str(e)}")
            return error_response

    def __repr__(self):
        return "ResetCombatContextAction()"
