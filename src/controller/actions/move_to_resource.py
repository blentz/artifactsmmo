""" MoveToResourceAction module """

from typing import Dict, Optional, Tuple

from src.lib.action_context import ActionContext

from .movement_base import MovementActionBase


class MoveToResourceAction(MovementActionBase):
    """ Action to move character to a resource location """

    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'cooldown_active': False,
            },
            'resource_location_known': True,
        }
    reactions = {
            'at_resource_location': True,
            'location_context': {
                'at_target': True,
            },
        }
    weights = {"at_resource_location": 10}

    def __init__(self):
        """
        Initialize the move to resource action.
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
        # Get from context (e.g., from find_resources action)
        target_x = context.get('target_x') or context.get('resource_x')
        target_y = context.get('target_y') or context.get('resource_y')
        
        return target_x, target_y

    def build_movement_context(self, context: ActionContext) -> Dict:
        """
        Build resource-specific movement context.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Movement context dictionary
        """
        movement_context = {
            'at_resource_location': True
        }
        
        # Include resource information if available
        resource_code = context.get('resource_code')
        if resource_code:
            movement_context['resource_code'] = resource_code
            
        resource_name = context.get('resource_name')
        if resource_name:
            movement_context['resource_name'] = resource_name
            
        return movement_context

    def __repr__(self):
        return "MoveToResourceAction()"