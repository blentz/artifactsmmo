"""
Mark Combat Not Viable Action

This bridge action marks combat as not viable when the recent win rate
is too low, triggering the need for equipment upgrades.
"""

from typing import Dict

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import CombatStatus

from .base import ActionBase, ActionResult


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
            'status': CombatStatus.NOT_VIABLE,
        },
    }
    weight = 2.0

    def __init__(self):
        """Initialize mark combat not viable action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute marking combat as not viable.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # Get current win rate from context
            recent_win_rate = context.get(StateParameters.COMBAT_RECENT_WIN_RATE, 0.0)
            
            # Log the decision
            self.logger.warning(
                f"⚠️ Combat not viable: Recent win rate {recent_win_rate:.1%} "
                f"is below threshold (20%)"
            )
            self.logger.info("🛡️ Recommending equipment upgrades before continuing combat")
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                combat_viability_marked=True,
                previous_status=context.get(StateParameters.COMBAT_STATUS, 'unknown'),
                new_status='not_viable',
                recent_win_rate=recent_win_rate,
                recommendation="Upgrade equipment before continuing combat",
                message=f"Combat marked as not viable (win rate: {recent_win_rate:.1%})"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to mark combat not viable: {str(e)}")
            return error_response

    def __repr__(self):
        return "MarkCombatNotViableAction()"
