"""
Subgoal Mixins for Actions

This module provides reusable mixins for common subgoal patterns in actions.
These mixins implement standardized approaches for requesting and handling
subgoals like movement, material gathering, and workshop navigation.
"""

from typing import List, Optional
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.controller.actions.base import ActionResult


class MovementSubgoalMixin:
    """
    Mixin for actions that need to request movement subgoals.
    
    Provides standardized methods for:
    - Requesting movement to target coordinates
    - Checking if character is at target location
    - Preserving context across subgoal execution
    """
    
    def request_movement_subgoal(self, context: ActionContext, target_x: int, target_y: int, 
                                preserve_keys: Optional[List[str]] = None) -> ActionResult:
        """
        Request movement to target location with proper context preservation.
        
        Args:
            context: ActionContext to store target coordinates
            target_x: X coordinate to move to
            target_y: Y coordinate to move to
            preserve_keys: Additional context keys to preserve across subgoal
            
        Returns:
            ActionResult with subgoal request for movement
        """
        # Store target coordinates in context
        context.set(StateParameters.TARGET_X, target_x)
        context.set(StateParameters.TARGET_Y, target_y)
        
        # Build context preservation list
        preserve_context = preserve_keys or []
        preserve_context.extend([StateParameters.TARGET_X, StateParameters.TARGET_Y])
        
        # Create result with subgoal request
        result = self.create_success_result(f"Requesting movement to ({target_x}, {target_y})")
        result.request_subgoal(
            goal_name="move_to_location",
            parameters={"target_x": target_x, "target_y": target_y},
            preserve_context=preserve_context
        )
        return result
    
    def is_at_target_location(self, client, context: ActionContext) -> bool:
        """
        Check if character is at the stored target location.
        
        Args:
            client: API client for character data
            context: ActionContext containing target coordinates
            
        Returns:
            True if character is at target location, False otherwise
        """
        target_x = context.get(StateParameters.TARGET_X)
        target_y = context.get(StateParameters.TARGET_Y)
        
        if target_x is None or target_y is None:
            return False
            
        # Get current character position
        try:
            char_response = get_character_api(context.get(StateParameters.CHARACTER_NAME), client=client)
            if not char_response.data:
                return False
                
            current_x = char_response.data.x
            current_y = char_response.data.y
            
            return current_x == target_x and current_y == target_y
            
        except Exception:
            return False
    
    def get_stored_target_coordinates(self, context: ActionContext) -> Optional[tuple]:
        """
        Get stored target coordinates from context.
        
        Args:
            context: ActionContext containing coordinates
            
        Returns:
            Tuple of (x, y) coordinates or None if not stored
        """
        target_x = context.get(StateParameters.TARGET_X)
        target_y = context.get(StateParameters.TARGET_Y)
        
        if target_x is not None and target_y is not None:
            return (target_x, target_y)
        return None


class WorkflowSubgoalMixin:
    """
    Mixin for actions that implement multi-step workflows with subgoals.
    
    Provides standardized methods for:
    - Tracking workflow step progression
    - Managing state transitions between steps
    - Preserving workflow context across subgoals
    """
    
    def get_workflow_step(self, context: ActionContext, default_step: str = 'initial') -> str:
        """
        Get current workflow step from context.
        
        Args:
            context: ActionContext containing workflow state
            default_step: Default step if none stored
            
        Returns:
            Current workflow step name
        """
        return context.get(StateParameters.WORKFLOW_STEP, default_step)
    
    def set_workflow_step(self, context: ActionContext, step: str) -> None:
        """
        Set workflow step in context.
        
        Args:
            context: ActionContext to store step
            step: Step name to store
        """
        context.set(StateParameters.WORKFLOW_STEP, step)
    
    def request_workflow_subgoal(self, context: ActionContext, goal_name: str, 
                                parameters: dict, next_step: str,
                                preserve_keys: Optional[List[str]] = None) -> ActionResult:
        """
        Request a subgoal as part of a workflow, setting next step for continuation.
        
        Args:
            context: ActionContext for state management
            goal_name: Name of subgoal to request
            parameters: Parameters for subgoal
            next_step: Workflow step to set for continuation
            preserve_keys: Additional context keys to preserve
            
        Returns:
            ActionResult with subgoal request
        """
        # Set next step for continuation
        self.set_workflow_step(context, next_step)
        
        # Build context preservation list
        preserve_context = preserve_keys or []
        preserve_context.append(StateParameters.WORKFLOW_STEP)
        
        # Create result with subgoal request
        result = self.create_success_result(f"Workflow step: requesting {goal_name}")
        result.request_subgoal(
            goal_name=goal_name,
            parameters=parameters,
            preserve_context=preserve_context
        )
        return result


class MaterialGatheringSubgoalMixin:
    """
    Mixin for actions that need to gather materials through subgoals.
    
    Provides standardized methods for:
    - Requesting material gathering subgoals
    - Tracking gathered materials
    - Managing material requirements
    """
    
    def request_material_gathering_subgoal(self, context: ActionContext, materials: dict,
                                         preserve_keys: Optional[List[str]] = None) -> ActionResult:
        """
        Request material gathering subgoal.
        
        Args:
            context: ActionContext for state management
            materials: Dictionary of materials needed {item: quantity}
            preserve_keys: Additional context keys to preserve
            
        Returns:
            ActionResult with subgoal request for material gathering
        """
        # Store material requirements
        context.set(StateParameters.MATERIALS_MISSING, materials)
        
        # Build context preservation list
        preserve_context = preserve_keys or []
        preserve_context.extend([StateParameters.MATERIALS_MISSING])
        
        # Create result with subgoal request
        result = self.create_success_result(f"Requesting material gathering for {list(materials.keys())}")
        result.request_subgoal(
            goal_name="gather_materials",
            parameters={"missing_materials": materials},
            preserve_context=preserve_context
        )
        return result
    
    def has_required_materials(self, context: ActionContext) -> bool:
        """
        Check if required materials have been gathered.
        
        Args:
            context: ActionContext containing material state
            
        Returns:
            True if materials are marked as gathered, False otherwise
        """
        materials_status = context.get(StateParameters.MATERIALS_STATUS)
        return materials_status in ['gathered', 'sufficient', 'gathered_raw']


class CombinedSubgoalMixin(MovementSubgoalMixin, WorkflowSubgoalMixin, MaterialGatheringSubgoalMixin):
    """
    Combined mixin providing all subgoal handling capabilities.
    
    Use this for complex actions that need movement, workflow management,
    and material gathering subgoals.
    """
    pass