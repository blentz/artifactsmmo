""" MoveToResourceAction module """

from typing import Dict, Optional, Tuple

from src.lib.action_context import ActionContext

from .base.movement import MovementActionBase


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
    weight = 10

    def __init__(self):
        """
        Initialize the move to resource action.
        """
        super().__init__()

    def get_target_coordinates(self, context: ActionContext) -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates from unified context properties.
        
        Args:
            context: ActionContext with unified properties
            
        Returns:
            Tuple of (x, y) coordinates
        """
        # Use unified context properties instead of deprecated nested dicts
        target_x = getattr(context, 'target_x', None) or getattr(context, 'resource_x', None)
        target_y = getattr(context, 'target_y', None) or getattr(context, 'resource_y', None)
        
        return target_x, target_y

    def build_movement_context(self, context: ActionContext) -> Dict:
        """
        Build resource-specific movement context.
        
        Args:
            context: ActionContext with unified properties
            
        Returns:
            Movement context dictionary
        """
        movement_context = {
            'at_resource_location': True
        }
        
        # Include resource information if available using unified context properties
        resource_code = getattr(context, 'resource_code', None)
        if resource_code:
            movement_context['resource_code'] = resource_code
            
        resource_name = getattr(context, 'resource_name', None)
        if resource_name:
            movement_context['resource_name'] = resource_name
            
        return movement_context

    def __repr__(self):
        return "MoveToResourceAction()"