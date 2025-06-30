""" MoveToResourceAction module """

from typing import Dict, Optional, Tuple
from .movement_base import MovementActionBase


class MoveToResourceAction(MovementActionBase):
    """ Action to move character to a resource location """

    # GOAP parameters
    conditions = {"character_alive": True, "can_move": True, "resource_location_known": True}
    reactions = {"at_resource_location": True, "at_target_location": True}
    weights = {"at_resource_location": 10}

    def __init__(self, character_name: str, target_x: int = None, target_y: int = None):
        """
        Initialize the move to resource action.

        Args:
            character_name: Character name
            target_x: Target X coordinate for resource location (optional, can come from context)
            target_y: Target Y coordinate for resource location (optional, can come from context)
        """
        super().__init__(character_name)
        self.target_x = target_x
        self.target_y = target_y

    def get_target_coordinates(self, **kwargs) -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates from action parameters or context.
        
        Args:
            **kwargs: Context parameters
            
        Returns:
            Tuple of (x, y) coordinates
        """
        # If specific coordinates provided during initialization, use them
        if self.target_x is not None and self.target_y is not None:
            return self.target_x, self.target_y
        
        # Otherwise, get from context (e.g., from find_resources action)
        target_x = kwargs.get('target_x') or kwargs.get('resource_x')
        target_y = kwargs.get('target_y') or kwargs.get('resource_y')
        
        return target_x, target_y

    def build_movement_context(self, **kwargs) -> Dict:
        """
        Build resource-specific movement context.
        
        Args:
            **kwargs: Context parameters
            
        Returns:
            Movement context dictionary
        """
        context = {
            'at_resource_location': True
        }
        
        # Include resource information if available
        if 'resource_code' in kwargs:
            context['resource_code'] = kwargs['resource_code']
        if 'resource_name' in kwargs:
            context['resource_name'] = kwargs['resource_name']
            
        return context

    def __repr__(self):
        return f"MoveToResourceAction({self.character_name}, {self.target_x}, {self.target_y})"