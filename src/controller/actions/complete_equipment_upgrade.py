"""
Complete Equipment Upgrade Action

This bridge action completes the equipment upgrade process after the item has been equipped.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

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
            'status': 'sufficient'
        },
        'character_status': {
            'alive': True
        }
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': 'completed',
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
        character_name = context.character_name
        if not character_name:
            return self.create_error_result("No character name provided")
        
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
            return self.create_success_result(
                message=f"Equipment upgrade completed with {selected_item}",
                equipment_upgrade_completed=True,
                previous_status='ready',
                new_status='completed',
                equipped_item=selected_item,
                target_slot=target_slot
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to complete equipment upgrade: {str(e)}")

    def __repr__(self):
        return "CompleteEquipmentUpgradeAction()"
