"""
Complete Equipment Upgrade Action

This bridge action completes the equipment upgrade process after the item has been equipped.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import MaterialStatus, EquipmentStatus

from .base import ActionBase, ActionResult


class CompleteEquipmentUpgradeAction(ActionBase):
    """
    Bridge action to complete equipment upgrade process.
    
    This action transitions the equipment_status.upgrade_status from 'crafting' to 'completed'
    after the item has been successfully equipped.
    """

    # GOAP parameters - must match default_actions.yaml
    conditions = {
        'skill_requirements': {
            'verified': True,
            'sufficient': True
        },
        'materials': {
            'status': MaterialStatus.SUFFICIENT
        },
        'character_status': {
            'alive': True
        }
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': EquipmentStatus.COMPLETED,
        },
    }
    weight = 3.0

    def __init__(self):
        """Initialize complete equipment upgrade action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """
        Execute equipment upgrade completion.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        self._context = context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
        
        try:
            # Get equipped item information using StateParameters
            selected_item = context.get(StateParameters.TARGET_ITEM, 'unknown')
            target_slot = context.get(StateParameters.TARGET_SLOT, 'unknown')
            
            # Log the completion
            self.logger.info(
                f"🎉 Equipment upgrade complete: {selected_item} equipped in {target_slot} slot"
            )
            
            # Update ActionContext directly with completion status
            context.set(StateParameters.EQUIPMENT_UPGRADE_STATUS, 'completed')
            
            # This is a bridge action - it only updates state, no API calls needed
            return self.create_result_with_state_changes(
                success=True,
                state_changes={
                    'equipment_status': {
                        'upgrade_status': 'completed',
                        'equipped_item': selected_item,
                        'target_slot': target_slot
                    }
                },
                message=f"Equipment upgrade completed with {selected_item}",
                equipped_item=selected_item,
                target_slot=target_slot
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to complete equipment upgrade: {str(e)}")

    def __repr__(self):
        return "CompleteEquipmentUpgradeAction()"
