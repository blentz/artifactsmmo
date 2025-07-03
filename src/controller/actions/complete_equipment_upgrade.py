"""
Complete Equipment Upgrade Action

This bridge action completes the equipment upgrade process after the item has been equipped.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class CompleteEquipmentUpgradeAction(ActionBase):
    """
    Bridge action to complete equipment upgrade process.
    
    This action transitions the equipment_status.upgrade_status from 'crafting' to 'completed'
    after the item has been successfully equipped.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': 'crafting',
            'equipped': True,
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': 'completed',
        },
    }
    weights = {'equipment_status.upgrade_status': 2.0}

    def __init__(self):
        """Initialize complete equipment upgrade action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute equipment upgrade completion.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Get equipped item information
            equipment_status = context.get('equipment_status', {})
            selected_item = equipment_status.get('selected_item', 'unknown')
            target_slot = equipment_status.get('target_slot', 'unknown')
            
            # Log the completion
            self.logger.info(
                f"🎉 Equipment upgrade complete: {selected_item} equipped in {target_slot} slot"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                equipment_upgrade_completed=True,
                previous_status='ready',
                new_status='completed',
                equipped_item=selected_item,
                target_slot=target_slot,
                message=f"Equipment upgrade completed with {selected_item}"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to complete equipment upgrade: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "CompleteEquipmentUpgradeAction()"
