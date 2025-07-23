"""
Base classes for action functionality.

This module provides base classes that define the core interfaces and functionality
for different types of actions.
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.unified_state_context import UnifiedStateContext


@dataclass
class ActionResult:
    """Standardized action result with guaranteed fields."""
    success: bool
    message: str = ""
    data: Dict[str, Any] = None
    error: Optional[str] = None
    action_name: str = ""
    state_changes: Dict[str, Any] = None
    subgoal_request: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize empty dicts if None."""
        if self.data is None:
            self.data = {}
        if self.state_changes is None:
            self.state_changes = {}
    
    def request_subgoal(self, goal_name: str, parameters: Dict[str, Any] = None, 
                       preserve_context: list = None) -> None:
        """
        Request a subgoal to be executed before continuing current goal.
        
        This method enables recursive workflow execution where actions can delegate
        subtasks to the GOAP system and continue execution after completion.
        
        EXECUTION FLOW:
        1. Action calls request_subgoal() to delegate work
        2. GOAP system executes subgoal recursively  
        3. After subgoal completion, original action is re-executed
        4. Action should check stored context to determine continuation logic
        
        CONTINUATION PATTERN:
        Actions should implement continuation logic by checking stored context:
        
        ```python
        def execute(self, client, context):
            # Check for continuation from previous execution
            if context.get('target_x') is not None:
                # Continuation logic - subgoal completed
                return self._continue_after_subgoal(client, context)
            
            # Initial execution - request subgoal
            result = self.create_success_result("Starting workflow")
            result.request_subgoal(
                goal_name="move_to_location",
                parameters={"target_x": 10, "target_y": 5},
                preserve_context=["target_resource", "workflow_step"]
            )
            return result
        ```
        
        Args:
            goal_name: Name of the subgoal to execute (must match goal template)
            parameters: Parameters to pass to the subgoal planning
            preserve_context: List of context keys to preserve across subgoal execution
                            Always include keys needed for continuation logic
        """
        self.subgoal_request = {
            "goal_name": goal_name,
            "parameters": parameters or {},
            "preserve_context": preserve_context or []
        }


class ActionBase(ABC):
    """ 
    Abstract base class for all GOAP actions with enforced state management.
    
    All actions MUST:
    1. Implement execute() method that returns ActionResult
    2. Define GOAP metadata (conditions, reactions, weight)
    3. Use standardized success/error reporting
    """
    
    # GOAP metadata - subclasses MUST define these
    conditions: Dict[str, Any] = {}
    reactions: Dict[str, Any] = {}
    weight: float = 1.0

    def __init__(self):
        """Initialize base action with logging and context."""
        self.logger = logging.getLogger(self.__class__.__name__)
        self._context: Optional[ActionContext] = None
        self._validate_goap_metadata()
    
    def _validate_goap_metadata(self) -> None:
        """Validate that action defines required GOAP metadata."""
        if not hasattr(self.__class__, 'conditions') or not isinstance(self.conditions, dict):
            raise ValueError(f"{self.__class__.__name__} must define 'conditions' as a dict")
            
        if not hasattr(self.__class__, 'reactions') or not isinstance(self.reactions, dict):
            raise ValueError(f"{self.__class__.__name__} must define 'reactions' as a dict")
            
        if not hasattr(self.__class__, 'weight') or not isinstance(self.weight, (int, float)):
            raise ValueError(f"{self.__class__.__name__} must define 'weight' as a number")
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the action with automatic cooldown handling.
        
        This base implementation provides universal cooldown detection and handling.
        Subclasses should call super().execute(client, context) first, then implement
        their specific logic.
        
        COOLDOWN HANDLING:
        - Automatically detects when action should retry after cooldown
        - Requests wait_for_cooldown subgoal when needed
        - Implements retry logic after cooldown expires
        
        SUBCLASS PATTERN:
        ```python
        def execute(self, client, context):
            # Check for cooldown handling first
            cooldown_result = super().execute(client, context)
            if cooldown_result:
                return cooldown_result
            
            # Implement action-specific logic here
            try:
                # Your action logic
                response = api_call(client, ...)
                return self.create_success_result(...)
            except Exception as e:
                # Check if it's a cooldown error
                if self.is_cooldown_error(e):
                    return self.handle_cooldown_error()
                return self.create_error_result(str(e))
        ```
        
        Args:
            client: API client for game interactions
            context: ActionContext with execution parameters
            
        Returns:
            ActionResult if cooldown handling needed, None if action should proceed
        """
        self._context = context
        self.logger.debug(f"Executing {self.__class__.__name__}")
        
        # Check if this is a retry after cooldown completion
        if context and context.get(StateParameters.CHARACTER_COOLDOWN_HANDLED, False):
            self.logger.info(f"🔄 Retrying {self.__class__.__name__} after cooldown completion")
            # Clear the cooldown flag to prevent infinite retry
            context.set(StateParameters.CHARACTER_COOLDOWN_HANDLED, False)
            # Return None to signal subclass should proceed with normal execution
            return None
        
        # Return None to signal subclass should proceed with normal execution
        return None

    def create_success_result(self, message: str = "", **data) -> ActionResult:
        """Create a standardized success result."""
        return ActionResult(
            success=True,
            message=message,
            data=data,
            action_name=self.__class__.__name__
        )
    
    def create_error_result(self, error_message: str, **data) -> ActionResult:
        """Create a standardized error result."""
        return ActionResult(
            success=False,
            error=error_message,
            data=data,
            action_name=self.__class__.__name__
        )
    
    def create_result_with_state_changes(self, success: bool, 
                                       state_changes: Dict[str, Any],
                                       message: str = "",
                                       error: str = None,
                                       **data) -> ActionResult:
        """Create a result with explicit state changes."""
        return ActionResult(
            success=success,
            message=message,
            error=error,
            data=data,
            state_changes=state_changes,
            action_name=self.__class__.__name__
        )
    
    
    def handle_cooldown_error(self) -> ActionResult:
        """
        Handle cooldown error by requesting wait_for_cooldown subgoal.
        
        This method should be called by subclasses when they detect a cooldown error.
        It immediately updates the UnifiedStateContext with cooldown status, then
        requests the wait_for_cooldown subgoal using the recursive subgoal pattern.
        
        Returns:
            ActionResult with subgoal request for cooldown handling
        """
        self.logger.info(f"⏳ {self.__class__.__name__} detected cooldown - requesting wait_for_cooldown subgoal")
        
        # Immediately update UnifiedStateContext with cooldown status
        # This ensures GOAP world state is synchronized before subgoal planning begins
        context = UnifiedStateContext()
        context.update({
            StateParameters.CHARACTER_COOLDOWN_ACTIVE: True
        })
        self.logger.debug("Updated UnifiedStateContext: cooldown_active = True")
        
        # Create result that requests cooldown handling subgoal
        result = self.create_success_result(
            message=f"{self.__class__.__name__} cooldown detected - delegating to wait_for_cooldown subgoal"
        )
        
        # Request wait_for_cooldown subgoal using recursive pattern
        result.request_subgoal(
            goal_name="wait_for_cooldown",
            parameters={},
            preserve_context=["retry_action", "action_context"]
        )
        
        return result
    
    def is_cooldown_error(self, exception: Exception) -> bool:
        """
        Check if an exception indicates a cooldown error.
        
        Args:
            exception: Exception to check
            
        Returns:
            True if the exception indicates CHARACTER_IN_COOLDOWN (status 499)
        """
        error_str = str(exception).lower()
        return "499" in str(exception) or "cooldown" in error_str

    # Legacy methods removed - all actions must use new ActionResult format

    def __repr__(self):
        """String representation with GOAP metadata."""
        return f"{self.__class__.__name__}(weight={self.weight})"


# Import specialized base classes
from .character import CharacterActionBase
from .movement import MovementActionBase
from .search import SearchActionBase
from .resource_analysis import ResourceAnalysisBase

__all__ = [
    'ActionBase',
    'ActionResult',
    'CharacterActionBase',
    'MovementActionBase', 
    'SearchActionBase',
    'ResourceAnalysisBase'
]