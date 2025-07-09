"""
Mark Equipment Ready Action

This bridge action marks equipment as ready for equipping after successful crafting.
"""

from typing import Dict

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import EquipmentStatus

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
            'upgrade_status': EquipmentStatus.CRAFTING,
            'item_crafted': True,
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': EquipmentStatus.READY,
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
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # Get crafted item information
            selected_item = context.get(StateParameters.EQUIPMENT_SELECTED_ITEM, 'unknown')
            target_slot = context.get(StateParameters.EQUIPMENT_TARGET_SLOT, 'unknown')
            
            # Log the readiness
            self.logger.info(
                f"✅ {selected_item} crafted successfully and ready for equipping"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                equipment_ready_marked=True,
                previous_status=EquipmentStatus.CRAFTING,
                new_status=EquipmentStatus.READY,
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
