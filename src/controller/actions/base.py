""" ActionBase module with Abstract Base Class enforcement """

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass

from src.lib.action_context import ActionContext


@dataclass
class ActionResult:
    """Standardized action result with guaranteed fields."""
    success: bool
    message: str = ""
    data: Dict[str, Any] = None
    error: Optional[str] = None
    action_name: str = ""
    state_changes: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize empty dicts if None."""
        if self.data is None:
            self.data = {}
        if self.state_changes is None:
            self.state_changes = {}


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
    
    @abstractmethod
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the action and return standardized result.
        
        ALL SUBCLASSES MUST:
        1. Store context: self._context = context
        2. Return an ActionResult instance
        3. Handle all exceptions and return appropriate error results
        
        Args:
            client: API client for game interactions
            context: ActionContext with execution parameters
            
        Returns:
            ActionResult with success status, data, and state changes
        """
        self._context = context
        self.logger.debug(f"Executing {self.__class__.__name__}")

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

    # Legacy methods removed - all actions must use new ActionResult format

    def __repr__(self):
        """String representation with GOAP metadata."""
        return f"{self.__class__.__name__}(weight={self.weight})"