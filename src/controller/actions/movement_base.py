"""
Base class for movement-related actions

This module provides a base class that encapsulates common movement patterns,
reducing duplication across movement actions.
"""

from typing import Dict, Optional, Tuple

from artifactsmmo_api_client.api.my_characters.action_move_my_name_action_move_post import sync as move_character_api
from artifactsmmo_api_client.models.destination_schema import DestinationSchema

from src.lib.action_context import ActionContext

from .base import ActionBase, ActionResult
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
    weight = 10
    
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
        # Default implementation - use unified context properties
        target_x = getattr(context, 'target_x', None)
        target_y = getattr(context, 'target_y', None)
        return target_x, target_y
    
    def execute_movement(self, client, target_x: int, target_y: int, 
                        movement_context: Dict = None) -> ActionResult:
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
            
            # Get character name for movement API
            api_character_name = movement_context.get('character_name', 'unknown')
            
            # Debug logging for character name
            self.logger.info(f"🚶 Moving character '{api_character_name}' to ({target_x}, {target_y})")
            
            # Execute movement
            response = move_character_api(
                name=api_character_name,
                client=client,
                body=destination
            )
            
            # Process successful response
            if response and hasattr(response, 'data'):
                response_data = response.data
                cooldown = getattr(response_data, 'cooldown', None)
                
                # Validate actual character position from API response
                actual_x, actual_y = None, None
                if hasattr(response_data, 'character'):
                    character_data = response_data.character
                    if hasattr(character_data, 'x') and hasattr(character_data, 'y'):
                        actual_x = character_data.x
                        actual_y = character_data.y
                
                # Check if character actually moved to target position
                if actual_x == target_x and actual_y == target_y:
                    result = self.create_success_result(
                        message=f"Moved to ({target_x}, {target_y})",
                        moved=True,
                        target_x=target_x,
                        target_y=target_y,
                        current_x=actual_x,
                        current_y=actual_y,
                        cooldown=cooldown,
                        movement_completed=True,
                        **movement_context
                    )
                    
                    self.logger.info(f"🚶 Moved to ({target_x}, {target_y})")
                    return result
                else:
                    # Character is not at expected location - movement failed
                    self.logger.warning(f"❌ Move failed: Character at ({actual_x}, {actual_y}) instead of target ({target_x}, {target_y})")
                    return self.create_error_result(
                        f"Movement validation failed: Character at ({actual_x}, {actual_y}) instead of target ({target_x}, {target_y})",
                        target_x=target_x,
                        target_y=target_y,
                        actual_x=actual_x,
                        actual_y=actual_y,
                        movement_failed=True
                    )
            else:
                return self.create_error_result(
                    "Movement failed: No response data",
                    target_x=target_x,
                    target_y=target_y
                )
                
        except Exception as e:
            # Handle "already at destination" as success
            error_str = str(e).lower()
            if "490" in str(e) and ("already at" in error_str or "destination" in error_str):
                self.logger.info(f"✓ Already at destination ({target_x}, {target_y})")
                return self.create_success_result(
                    message=f"Already at destination ({target_x}, {target_y})",
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
            return self.create_error_result(
                f"Movement failed: {str(e)}",
                target_x=target_x,
                target_y=target_y
            )
    
    def execute(self, client, context: 'ActionContext') -> ActionResult:
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
        
        # Debug logging for character name issue
        if not character_name:
            self.logger.error(f"❌ No character name found in context. Available attributes: {list(dir(context))}")
            return self.create_error_result("No character name provided in context")
        
        # Get target coordinates
        target_x, target_y = self.get_target_coordinates(context)
        
        if target_x is None or target_y is None:
            return self.create_error_result(
                "No valid coordinates provided",
                provided_x=target_x,
                provided_y=target_y
            )
        
        self._context = context
        
        # Build movement context
        movement_context = self.build_movement_context(context)
        movement_context['character_name'] = character_name
        
        # Execute movement
        result = self.execute_movement(client, target_x, target_y, movement_context)
        
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
