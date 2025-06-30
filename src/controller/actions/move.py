""" MoveAction module """

from typing import Dict, Optional, Tuple
from .movement_base import MovementActionBase
from .coordinate_mixin import CoordinateStandardizationMixin


class MoveAction(MovementActionBase, CoordinateStandardizationMixin):
    """ Move character action """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
        'can_move': True,
        'character_alive': True
    }
    reactions = {
        'at_target_location': True
    }
    weights = {'move': 1.0}

    def __init__(self, character_name, x=None, y=None, use_target_coordinates=False):
        """
        Initialize move action.
        
        Args:
            character_name: Character name
            x: Target X coordinate (optional)
            y: Target Y coordinate (optional)
            use_target_coordinates: Whether to use coordinates from action context
        """
        super().__init__(character_name)
        self.x = x
        self.y = y
        self.use_target_coordinates = use_target_coordinates

    def get_target_coordinates(self, **kwargs) -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates from action parameters or context using standardized format.
        
        Args:
            **kwargs: Context parameters
            
        Returns:
            Tuple of (target_x, target_y) coordinates
        """
        # If specific coordinates provided, use them
        if self.x is not None and self.y is not None:
            return self.x, self.y
        
        # If use_target_coordinates flag is set, get from action context using standardized logic
        if self.use_target_coordinates:
            return self.get_standardized_coordinates(**kwargs)
        
        return None, None

    def __repr__(self):
        return f"MoveAction({self.character_name}, {self.x}, {self.y})"