"""
Mark Equipment Crafting Action

This bridge action marks the transition from equipment analysis to crafting
after a recipe has been selected.
"""

from typing import Dict

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.game.globals import EquipmentStatus

from .base import ActionBase, ActionResult


class MarkEquipmentCraftingAction(ActionBase):
    """
    Bridge action to mark equipment as being crafted.
    
    This action transitions the equipment_status.upgrade_status from 'ready' to 'crafting'
    after a recipe has been selected and crafting is about to begin.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': EquipmentStatus.READY,
            'has_selected_item': True,
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': EquipmentStatus.CRAFTING,
        },
    }
    weight = 1.5

    def __init__(self):
        """Initialize mark equipment crafting action."""
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute marking equipment as crafting.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
            
        self._context = context
        
        try:
            # Get selected item information
            selected_item = context.get(StateParameters.EQUIPMENT_SELECTED_ITEM, 'unknown')
            target_slot = context.get(StateParameters.EQUIPMENT_TARGET_SLOT, 'unknown')
            
            # Log the transition
            self.logger.info(
                f"🔨 Starting to craft {selected_item} for {target_slot} slot"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.create_success_result(
                equipment_crafting_marked=True,
                previous_status='analyzing',
                new_status='crafting',
                selected_item=selected_item,
                target_slot=target_slot,
                message=f"Equipment crafting initiated for {selected_item}"
            )
            
            return result
            
        except Exception as e:
            error_response = self.create_error_result(f"Failed to mark equipment crafting: {str(e)}")
            return error_response

    def __repr__(self):
        return "MarkEquipmentCraftingAction()"
