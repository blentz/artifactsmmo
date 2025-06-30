""" MoveToWorkshopAction module """

from typing import Dict, Optional, Tuple
from .movement_base import MovementActionBase


class MoveToWorkshopAction(MovementActionBase):
    """ Action to move character to a workshop location """

    # GOAP parameters
    conditions = {"character_alive": True, "can_move": True, "workshops_discovered": True}
    reactions = {"at_workshop": True, "at_target_location": True}
    weights = {"at_workshop": 10}

    def __init__(self, character_name: str, target_x: int = None, target_y: int = None):
        """
        Initialize the move to workshop action.

        Args:
            character_name: Character name
            target_x: Target X coordinate for workshop location (optional, can come from context)
            target_y: Target Y coordinate for workshop location (optional, can come from context)
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
        
        # Otherwise, get from context (e.g., from find_workshops action)
        target_x = kwargs.get('target_x') or kwargs.get('workshop_x')
        target_y = kwargs.get('target_y') or kwargs.get('workshop_y')
        
        return target_x, target_y

    def build_movement_context(self, **kwargs) -> Dict:
        """
        Build workshop-specific movement context.
        
        Args:
            **kwargs: Context parameters
            
        Returns:
            Movement context dictionary
        """
        context = {
            'at_workshop': True
        }
        
        # Include workshop information if available
        if 'workshop_type' in kwargs:
            context['workshop_type'] = kwargs['workshop_type']
        if 'workshop_code' in kwargs:
            context['workshop_code'] = kwargs['workshop_code']
            
        return context

    def __repr__(self):
        return f"MoveToWorkshopAction({self.character_name}, {self.target_x}, {self.target_y})"