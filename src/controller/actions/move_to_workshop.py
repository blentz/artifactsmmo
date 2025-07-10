""" MoveToWorkshopAction module """

from typing import Dict, Optional, Tuple

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base.movement import MovementActionBase


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
        # Use standardized TARGET_X/Y parameters - workshop locations should set these
        target_x = context.get(StateParameters.TARGET_X)
        target_y = context.get(StateParameters.TARGET_Y)
        
        # If no target coordinates, workshop discovery should have set them
        if target_x is None or target_y is None:
            workshop_code = context.get(StateParameters.WORKSHOP_CODE)
            if workshop_code and context.knowledge_base:
                workshop_locations = context.knowledge_base.get_workshop_locations()
                workshop_info = workshop_locations.get(workshop_code, {})
                target_x = workshop_info.get('x')
                target_y = workshop_info.get('y')
        
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