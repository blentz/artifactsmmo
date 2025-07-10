"""
Universal Movement Action

This action consolidates move, move_to_resource, and move_to_workshop into a single
configurable movement action. It uses the existing MovementActionBase infrastructure
but adds configuration-driven behavior to eliminate code duplication.
"""

from typing import Dict, Optional, Tuple
from src.lib.action_context import ActionContext
from .base import ActionResult
from .mixins.coordinate_mixin import CoordinateStandardizationMixin
from .base.movement import MovementActionBase


class UniversalMovementAction(MovementActionBase, CoordinateStandardizationMixin):
    """
    Universal movement action that can move to coordinates, resources, or workshops
    based on configuration parameters.
    """
    
    def __init__(self):
        super().__init__()
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute universal movement based on action configuration.
        
        Expected action_config parameters:
        - movement_type: "coordinate" | "resource" | "workshop"
        - target_coordinates: [x, y] for coordinate movement
        - target_resource_key: context key containing resource location
        - target_workshop_key: context key containing workshop location
        """
        if client is None:
            return self.create_error_result("No API client provided")
        
        try:
            # Get action configuration
            action_config = context.get('action_config', {})
            movement_type = action_config.get('movement_type', 'coordinate')
            
            # Get current character position
            character = client.get_character()
            character_x, character_y = character.x, character.y
            
            self._context = context
            
            # Route to appropriate movement method based on type
            if movement_type == 'coordinate':
                return self._move_to_coordinates(client, context, character_x, character_y, action_config)
            elif movement_type == 'resource':
                return self._move_to_resource(client, context, character_x, character_y, action_config)
            elif movement_type == 'workshop':
                return self._move_to_workshop(client, context, character_x, character_y, action_config)
            else:
                return self.create_error_result(f"Unknown movement type: {movement_type}")
                
        except Exception as e:
            return self.create_error_result(f"Universal movement failed: {str(e)}")
    
    def _move_to_coordinates(self, client, context: ActionContext, character_x: int, character_y: int,
                           action_config: Dict) -> ActionResult:
        """Move to specific coordinates."""
        try:
            # Get target coordinates from config or context
            target_coordinates = action_config.get('target_coordinates')
            if not target_coordinates:
                # Try to get from context parameters
                target_x = context.get('target_x') or context.get('x')
                target_y = context.get('target_y') or context.get('y')
                
                if target_x is not None and target_y is not None:
                    target_coordinates = [target_x, target_y]
                else:
                    return self.create_error_result("No target coordinates provided")
            
            target_x, target_y = self.standardize_coordinates(target_coordinates[0], target_coordinates[1])
            
            # Check if already at target
            if character_x == target_x and character_y == target_y:
                return ActionResult(
                    success=True,
                    message=f"Already at target location ({target_x}, {target_y})",
                    action_name="move_coordinates"
                )
            
            # Execute movement
            result = client.move_character(target_x, target_y)
            
            # Check if move was successful
            if hasattr(result, 'data') and hasattr(result.data, 'x'):
                new_x, new_y = result.data.x, result.data.y
                if new_x == target_x and new_y == target_y:
                    context.set_result('character_x', new_x)
                    context.set_result('character_y', new_y)
                    
                    return ActionResult(
                        success=True,
                        message=f"Moved to ({new_x}, {new_y})",
                        data={'x': new_x, 'y': new_y},
                        action_name="move_coordinates"
                    )
                else:
                    return ActionResult(
                        success=False,
                        message=f"Move failed: reached ({new_x}, {new_y}) instead of ({target_x}, {target_y})",
                        action_name="move_coordinates"
                    )
            else:
                return self.create_error_result("Move failed: invalid response from API")
                
        except Exception as e:
            return self.create_error_result(f"Coordinate movement failed: {str(e)}")
    
    def _move_to_resource(self, client, context: ActionContext, character_x: int, character_y: int,
                         action_config: Dict) -> ActionResult:
        """Move to a resource location."""
        try:
            # Get target resource from context
            target_resource_key = action_config.get('target_resource_key', 'target_resource')
            target_resource = context.get(target_resource_key)
            
            if not target_resource:
                return self.create_error_result(f"No target resource found in context key: {target_resource_key}")
            
            # Extract coordinates from resource data
            resource_location = target_resource.get('location')
            if not resource_location:
                return self.create_error_result("Resource location not found in target_resource")
            
            target_x, target_y = self.standardize_coordinates(resource_location[0], resource_location[1])
            
            # Check if already at resource
            if character_x == target_x and character_y == target_y:
                context.set_result('at_resource', True)
                return ActionResult(
                    success=True,
                    message=f"Already at resource location ({target_x}, {target_y})",
                    action_name="move_to_resource"
                )
            
            # Execute movement
            result = client.move_character(target_x, target_y)
            
            # Check if move was successful
            if hasattr(result, 'data') and hasattr(result.data, 'x'):
                new_x, new_y = result.data.x, result.data.y
                if new_x == target_x and new_y == target_y:
                    context.set_result('character_x', new_x)
                    context.set_result('character_y', new_y)
                    context.set_result('at_resource', True)
                    
                    return ActionResult(
                        success=True,
                        message=f"Moved to resource at ({new_x}, {new_y})",
                        data={'x': new_x, 'y': new_y, 'resource': target_resource.get('code')},
                        action_name="move_to_resource"
                    )
                else:
                    return ActionResult(
                        success=False,
                        message=f"Move to resource failed: reached ({new_x}, {new_y}) instead of ({target_x}, {target_y})",
                        action_name="move_to_resource"
                    )
            else:
                return self.create_error_result("Move to resource failed: invalid response from API")
                
        except Exception as e:
            return self.create_error_result(f"Resource movement failed: {str(e)}")
    
    def _move_to_workshop(self, client, context: ActionContext, character_x: int, character_y: int,
                         action_config: Dict) -> ActionResult:
        """Move to a workshop location."""
        try:
            # Get target workshop from context
            target_workshop_key = action_config.get('target_workshop_key', 'target_workshop')
            target_workshop = context.get(target_workshop_key)
            
            if not target_workshop:
                return self.create_error_result(f"No target workshop found in context key: {target_workshop_key}")
            
            # Extract coordinates from workshop data
            workshop_location = target_workshop.get('location')
            if not workshop_location:
                return self.create_error_result("Workshop location not found in target_workshop")
            
            target_x, target_y = self.standardize_coordinates(workshop_location[0], workshop_location[1])
            
            # Check if already at workshop
            if character_x == target_x and character_y == target_y:
                context.set_result('at_workshop', True)
                return ActionResult(
                    success=True,
                    message=f"Already at workshop location ({target_x}, {target_y})",
                    action_name="move_to_workshop"
                )
            
            # Execute movement
            result = client.move_character(target_x, target_y)
            
            # Check if move was successful
            if hasattr(result, 'data') and hasattr(result.data, 'x'):
                new_x, new_y = result.data.x, result.data.y
                if new_x == target_x and new_y == target_y:
                    context.set_result('character_x', new_x)
                    context.set_result('character_y', new_y)
                    context.set_result('at_workshop', True)
                    
                    return ActionResult(
                        success=True,
                        message=f"Moved to workshop at ({new_x}, {new_y})",
                        data={'x': new_x, 'y': new_y, 'workshop': target_workshop.get('code')},
                        action_name="move_to_workshop"
                    )
                else:
                    return ActionResult(
                        success=False,
                        message=f"Move to workshop failed: reached ({new_x}, {new_y}) instead of ({target_x}, {target_y})",
                        action_name="move_to_workshop"
                    )
            else:
                return self.create_error_result("Move to workshop failed: invalid response from API")
                
        except Exception as e:
            return self.create_error_result(f"Workshop movement failed: {str(e)}")
    
    def __repr__(self):
        return "UniversalMovementAction()"