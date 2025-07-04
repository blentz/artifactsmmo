""" MoveToWorkshopAction module """

from typing import Dict, Optional, Tuple

from src.lib.action_context import ActionContext

from .movement_base import MovementActionBase


class MoveToWorkshopAction(MovementActionBase):
    """ Action to move character to a workshop location """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'cooldown_active': False,
            },
            'workshops_discovered': True,
        }
    reactions = {
            'at_workshop': True,
            'location_context': {
                'at_target': True,
            },
        }
    weight = 10

    def __init__(self):
        """
        Initialize the move to workshop action.
        """
        super().__init__()

    def get_target_coordinates(self, context: ActionContext) -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates from action parameters or context.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Tuple of (x, y) coordinates
        """
        # Get from context (e.g., from find_workshops action)
        target_x = context.get('target_x') or context.get('workshop_x')
        target_y = context.get('target_y') or context.get('workshop_y')
        
        return target_x, target_y

    def build_movement_context(self, context: ActionContext) -> Dict:
        """
        Build workshop-specific movement context.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Movement context dictionary
        """
        movement_context = {
            'at_workshop': True
        }
        
        # Include workshop information if available
        workshop_type = context.get('workshop_type')
        if workshop_type:
            movement_context['workshop_type'] = workshop_type
            
        workshop_code = context.get('workshop_code')
        if workshop_code:
            movement_context['workshop_code'] = workshop_code
            
        return movement_context

    def __repr__(self):
        return "MoveToWorkshopAction()"