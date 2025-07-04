"""
Mark Equipment Ready Action

This bridge action marks equipment as ready for equipping after successful crafting.
"""

from typing import Dict

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult


class MarkEquipmentReadyAction(ActionBase):
    """
    Bridge action to mark equipment as ready after crafting.
    
    This action transitions the equipment_status.upgrade_status from 'crafting' to 'ready'
    after the item has been successfully crafted and is ready to be equipped.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': 'crafting',
            'item_crafted': True,
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': 'ready',
        },
    }
    weight = 1.5

    def __init__(self):
        """Initialize mark equipment ready action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute marking equipment as ready.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # Get crafted item information
            equipment_status = context.get('equipment_status', {})
            selected_item = equipment_status.get('selected_item', 'unknown')
            target_slot = equipment_status.get('target_slot', 'unknown')
            
            # Log the readiness
            self.logger.info(
                f"✅ {selected_item} crafted successfully and ready for equipping"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                equipment_ready_marked=True,
                previous_status='crafting',
                new_status='ready',
                selected_item=selected_item,
                target_slot=target_slot,
                message=f"{selected_item} is ready to be equipped"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to mark equipment ready: {str(e)}")
            return error_response

    def __repr__(self):
        return "MarkEquipmentReadyAction()"
