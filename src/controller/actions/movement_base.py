"""
Base class for movement-related actions

This module provides a base class that encapsulates common movement patterns,
reducing duplication across movement actions.
"""

from typing import Dict, Optional, Tuple

from artifactsmmo_api_client.api.my_characters.action_move_my_name_action_move_post import sync as move_character_api
from artifactsmmo_api_client.models.destination_schema import DestinationSchema

from src.lib.action_context import ActionContext

from .base import ActionBase
from .mixins import CharacterDataMixin


class MovementActionBase(ActionBase, CharacterDataMixin):
    """Base class for all movement-related actions."""
    
    # Default GOAP parameters for movement actions
    conditions = {
            'character_status': {
                'alive': True,
            },
        }
    reactions = {"at_location": True}
    weights = {"at_location": 10}
    
    def __init__(self):
        """
        Initialize movement action base.
        """
        super().__init__()
    
    def get_target_coordinates(self, context: 'ActionContext') -> Tuple[Optional[int], Optional[int]]:
        """
        Get target coordinates for movement.
        To be overridden by subclasses for custom coordinate extraction.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Tuple of (x, y) coordinates or (None, None)
        """
        # Default implementation - direct coordinates
        target_x = context.get('target_x')
        target_y = context.get('target_y')
        return target_x, target_y
    
    def execute_movement(self, client, target_x: int, target_y: int, 
                        movement_context: Dict = None) -> Dict:
        """
        Execute the movement to target coordinates.
        
        Args:
            client: API client
            target_x: Target X coordinate
            target_y: Target Y coordinate
            movement_context: Optional context for movement (e.g., what we're moving to)
            
        Returns:
            Response dictionary
        """
        if movement_context is None:
            movement_context = {}
            
        try:
            # Create destination schema
            destination = DestinationSchema(x=target_x, y=target_y)
            
            # Execute movement
            response = move_character_api(
                name=movement_context.get('character_name', 'unknown'),
                client=client,
                body=destination
            )
            
            # Process successful response
            if response and hasattr(response, 'data'):
                response_data = response.data
                cooldown = getattr(response_data, 'cooldown', None)
                
                result = self.get_success_response(
                    moved=True,
                    target_x=target_x,
                    target_y=target_y,
                    current_x=target_x,
                    current_y=target_y,
                    cooldown=cooldown,
                    movement_completed=True,
                    **movement_context
                )
                
                self.logger.info(f"🚶 Moved to ({target_x}, {target_y})")
                return result
            else:
                return self.get_error_response(
                    "Movement failed: No response data",
                    target_x=target_x,
                    target_y=target_y
                )
                
        except Exception as e:
            # Handle "already at destination" as success
            error_str = str(e).lower()
            if "490" in str(e) and ("already at" in error_str or "destination" in error_str):
                self.logger.info(f"✓ Already at destination ({target_x}, {target_y})")
                return self.get_success_response(
                    moved=False,
                    already_at_destination=True,
                    target_x=target_x,
                    target_y=target_y,
                    current_x=target_x,
                    current_y=target_y,
                    movement_completed=True,
                    **movement_context
                )
            
            # Handle other movement errors
            return self.get_error_response(
                f"Movement failed: {str(e)}",
                target_x=target_x,
                target_y=target_y
            )
    
    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute the movement action.
        
        Args:
            client: API client
            context: ActionContext with parameters
            
        Returns:
            Action result dictionary
        """
        # Get character name from context
        character_name = context.character_name
        
        # Get target coordinates
        target_x, target_y = self.get_target_coordinates(context)
        
        if target_x is None or target_y is None:
            error_response = self.get_error_response(
                "No valid coordinates provided",
                provided_x=target_x,
                provided_y=target_y
            )
            self.log_execution_result(error_response)
            return error_response
        
        # Log execution start
        self.log_execution_start(
            character_name=character_name,
            target_x=target_x,
            target_y=target_y
        )
        
        # Build movement context
        movement_context = self.build_movement_context(context)
        movement_context['character_name'] = character_name
        
        # Execute movement
        result = self.execute_movement(client, target_x, target_y, movement_context)
        
        # Log result
        self.log_execution_result(result)
        return result
    
    def build_movement_context(self, context: 'ActionContext') -> Dict:
        """
        Build context information for the movement.
        Can be overridden by subclasses to add specific context.
        
        Args:
            context: ActionContext with parameters
            
        Returns:
            Movement context dictionary
        """
        return {}
    
    def calculate_distance(self, from_x: int, from_y: int, to_x: int, to_y: int) -> int:
        """
        Calculate Manhattan distance between two points.
        
        Args:
            from_x: Starting X coordinate
            from_y: Starting Y coordinate
            to_x: Target X coordinate
            to_y: Target Y coordinate
            
        Returns:
            Manhattan distance
        """
        return abs(to_x - from_x) + abs(to_y - from_y)
    
    def __repr__(self):
        return f"{self.__class__.__name__}()"
