"""
Reset Equipment Upgrade Action

This bridge action resets the equipment upgrade process, allowing for a new upgrade cycle.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class ResetEquipmentUpgradeAction(ActionBase):
    """
    Bridge action to reset equipment upgrade process.
    
    This action transitions the equipment_status.upgrade_status from 'completed' back to 'none',
    clearing the selected item and target slot to enable a new upgrade cycle.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': 'completed',
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': 'needs_analysis',
            'selected_item': None,
            'target_slot': None,
        },
    }
    weights = {'equipment_status.upgrade_status': 1.0}

    def __init__(self):
        """Initialize reset equipment upgrade action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute equipment upgrade reset.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Get previous upgrade information for logging
            equipment_status = context.get('equipment_status', {})
            previous_item = equipment_status.get('selected_item', 'unknown')
            
            # Log the reset
            self.logger.info(
                f"🔄 Resetting equipment upgrade status (previous: {previous_item})"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                equipment_upgrade_reset=True,
                previous_status='completed',
                new_status='none',
                previous_item=previous_item,
                message="Equipment upgrade status reset, ready for new upgrade"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to reset equipment upgrade: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "ResetEquipmentUpgradeAction()"
