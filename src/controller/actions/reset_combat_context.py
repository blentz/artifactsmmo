"""
Reset Combat Context Action

This bridge action resets the combat context from 'completed' back to 'idle',
allowing the character to start a new combat cycle.
"""

from typing import Dict

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult


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
    weight = 1.0

    def __init__(self):
        """Initialize reset combat context action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the combat context reset.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                combat_context_reset=True,
                previous_status='completed',
                new_status='idle',
                message="Combat context reset to idle state"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to reset combat context: {str(e)}")
            return error_response

    def __repr__(self):
        return "ResetCombatContextAction()"
