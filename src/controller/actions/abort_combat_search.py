"""
Abort Combat Search Action

This bridge action aborts an unsuccessful combat search by transitioning
the combat context from 'searching' back to 'idle'.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


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
    weight = 1.5

    def __init__(self):
        """Initialize abort combat search action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the combat search abort.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        self._context = context
        
        character_name = context.get(StateParameters.CHARACTER_NAME, "")
        if not character_name:
            return self.create_error_result("No character name provided")
        
        try:
            # Log the reason for aborting
            self.logger.info("🚫 Aborting combat search - no monsters available in area")
            
            # Create state changes to mark combat as idle
            state_changes = {
                'combat_context': {
                    'status': 'idle',
                    'target': None,
                    'location': None,
                }
            }
            
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message="Combat search aborted, returning to idle state",
                combat_search_aborted=True,
                previous_status='searching',
                new_status='idle',
                reason="No monsters available"
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to abort combat search: {str(e)}")

    def __repr__(self):
        return "AbortCombatSearchAction()"