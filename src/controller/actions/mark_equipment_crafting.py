"""
Mark Equipment Crafting Action

This bridge action marks the transition from equipment analysis to crafting
after a recipe has been selected.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class MarkEquipmentCraftingAction(ActionBase):
    """
    Bridge action to mark equipment as being crafted.
    
    This action transitions the equipment_status.upgrade_status from 'analyzing' to 'crafting'
    after a recipe has been selected and crafting is about to begin.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': 'analyzing',
            'selected_item': '!null',
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': 'crafting',
        },
    }
    weights = {'equipment_status.upgrade_status': 1.5}

    def __init__(self):
        """Initialize mark equipment crafting action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute marking equipment as crafting.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Get selected item information
            equipment_status = context.get('equipment_status', {})
            selected_item = equipment_status.get('selected_item', 'unknown')
            target_slot = equipment_status.get('target_slot', 'unknown')
            
            # Log the transition
            self.logger.info(
                f"🔨 Starting to craft {selected_item} for {target_slot} slot"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                equipment_crafting_marked=True,
                previous_status='analyzing',
                new_status='crafting',
                selected_item=selected_item,
                target_slot=target_slot,
                message=f"Equipment crafting initiated for {selected_item}"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to mark equipment crafting: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "MarkEquipmentCraftingAction()"
