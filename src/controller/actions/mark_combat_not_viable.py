"""
Mark Combat Not Viable Action

This bridge action marks combat as not viable when the recent win rate
is too low, triggering the need for equipment upgrades.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class MarkCombatNotViableAction(ActionBase):
    """
    Bridge action to mark combat as not viable based on poor performance.
    
    This action transitions the combat_context.status to 'not_viable' when
    the recent win rate falls below the viability threshold, signaling that
    the character needs better equipment before continuing combat.
    """

    # GOAP parameters
    conditions = {
        'combat_context': {
            'recent_win_rate': '<0.2',
        },
        'character_status': {
            'alive': True,
        },
    }
    reactions = {
        'combat_context': {
            'status': 'not_viable',
        },
    }
    weights = {'combat_context.status': 2.0}

    def __init__(self):
        """Initialize mark combat not viable action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute marking combat as not viable.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Get current win rate from context
            combat_context = context.get('combat_context', {})
            recent_win_rate = combat_context.get('recent_win_rate', 0.0)
            
            # Log the decision
            self.logger.warning(
                f"⚠️ Combat not viable: Recent win rate {recent_win_rate:.1%} "
                f"is below threshold (20%)"
            )
            self.logger.info("🛡️ Recommending equipment upgrades before continuing combat")
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                combat_viability_marked=True,
                previous_status=combat_context.get('status', 'unknown'),
                new_status='not_viable',
                recent_win_rate=recent_win_rate,
                recommendation="Upgrade equipment before continuing combat",
                message=f"Combat marked as not viable (win rate: {recent_win_rate:.1%})"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to mark combat not viable: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "MarkCombatNotViableAction()"
