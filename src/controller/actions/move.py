""" MoveAction module """

from typing import Optional, Tuple

from src.lib.action_context import ActionContext

from .coordinate_mixin import CoordinateStandardizationMixin
from .movement_base import MovementActionBase


class MoveAction(MovementActionBase, CoordinateStandardizationMixin):
    """ Move character action """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
            'character_status': {
                'cooldown_active': False,
                'alive': True,
            },
        }
    reactions = {
            'location_context': {
                'at_target': True,
            },
        }
    weights = {'move': 1.0}

    def __init__(self):
        """
        Initialize move action.
        """
        super().__init__()

    def get_target_coordinates(self, context: 'ActionContext') -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates from action parameters or context using standardized format.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Tuple of (target_x, target_y) coordinates
        """
        # Check for target coordinates from previous actions (find_monsters, etc.)
        target_x = context.get('target_x')
        target_y = context.get('target_y')
        if target_x is not None and target_y is not None:
            return target_x, target_y
        
        # Check for direct x,y coordinates in context
        x = context.get('x')
        y = context.get('y')
        if x is not None and y is not None:
            return x, y
        
        # Check use_target_coordinates flag
        use_target_coordinates = context.get('use_target_coordinates', False)
        if use_target_coordinates:
            # Convert context to dict for get_standardized_coordinates
            context_dict = dict(context) if hasattr(context, '__iter__') else {}
            return self.get_standardized_coordinates(**context_dict)
        
        return None, None

    def __repr__(self):
        return "MoveAction()"
