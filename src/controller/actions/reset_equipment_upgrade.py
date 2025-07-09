"""
Reset Equipment Upgrade Action

This bridge action resets the equipment upgrade process, allowing for a new upgrade cycle.
"""

from typing import Dict

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import EquipmentStatus

from .base import ActionBase, ActionResult


class ResetEquipmentUpgradeAction(ActionBase):
    """
    Bridge action to reset equipment upgrade process.
    
    This action transitions the equipment_status.upgrade_status from 'completed' back to 'none',
    clearing the selected item and target slot to enable a new upgrade cycle.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': EquipmentStatus.COMPLETED,
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': EquipmentStatus.NEEDS_ANALYSIS,
            'selected_item': None,
            'target_slot': None,
        },
    }
    weight = 1.0

    def __init__(self):
        """Initialize reset equipment upgrade action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute equipment upgrade reset.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # Get previous upgrade information for logging
            equipment_status = context.get(StateParameters.EQUIPMENT_STATUS, {})
            previous_item = equipment_status.get('selected_item', 'unknown')
            
            # Log the reset
            self.logger.info(
                f"🔄 Resetting equipment upgrade status (previous: {previous_item})"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                equipment_upgrade_reset=True,
                previous_status=EquipmentStatus.COMPLETED,
                new_status=EquipmentStatus.NONE,
                previous_item=previous_item,
                message="Equipment upgrade status reset, ready for new upgrade"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to reset equipment upgrade: {str(e)}")
            return error_response

    def __repr__(self):
        return "ResetEquipmentUpgradeAction()"
