""" MoveAction module """

from typing import Optional, Tuple

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .mixins.coordinate_mixin import CoordinateStandardizationMixin
from .base.movement import MovementActionBase


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
    weight = 1.0

    def __init__(self):
        """
        Initialize move action.
        """
        super().__init__()

    def get_target_coordinates(self, context: 'ActionContext') -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates from context using unified StateParameters approach.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Tuple of (target_x, target_y) coordinates
        """
        # Use unified StateParameters approach - no fallbacks or backward compatibility
        target_x = context.get(StateParameters.TARGET_X)
        target_y = context.get(StateParameters.TARGET_Y)
        
        return target_x, target_y

    def __repr__(self):
        return "MoveAction()"
