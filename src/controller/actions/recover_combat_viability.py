"""
Recover Combat Viability Action

This bridge action recovers combat viability after equipment upgrades,
allowing the character to resume combat activities.
"""

from typing import Dict

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class RecoverCombatViabilityAction(ActionBase):
    """
    Bridge action to recover combat viability after equipment improvements.
    
    This action transitions the combat_context.status from 'not_viable' back to 'idle'
    after the character has upgraded their equipment, enabling them to resume combat
    with better chances of success.
    """

    # GOAP parameters
    conditions = {
        'combat_context': {
            'status': 'not_viable',
        },
        'equipment_status': {
            'upgrade_status': 'completed',
        },
    }
    reactions = {
        'combat_context': {
            'status': 'idle',
            'recent_win_rate': 1.0,  # Reset win rate after equipment upgrade
        },
    }
    weight = 2.5

    def __init__(self):
        """Initialize recover combat viability action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute combat viability recovery.
        
        This is a state-only action that updates the combat context
        without making any API calls.
        """
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # Get equipment upgrade information using StateParameters
            upgraded_item = context.get(StateParameters.EQUIPMENT_SELECTED_ITEM, 'unknown')
            
            # Log the recovery
            self.logger.info(
                f"✅ Combat viability recovered after equipment upgrade: {upgraded_item}"
            )
            self.logger.info("⚔️ Ready to resume combat with improved equipment")
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                combat_viability_recovered=True,
                previous_status='not_viable',
                new_status='idle',
                equipment_upgraded=upgraded_item,
                win_rate_reset=True,
                message="Combat viability recovered, ready to resume hunting"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to recover combat viability: {str(e)}")
            return error_response

    def __repr__(self):
        return "RecoverCombatViabilityAction()"
