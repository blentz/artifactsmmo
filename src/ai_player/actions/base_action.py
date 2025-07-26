"""
Base Action Class for GOAP System

This module defines the abstract base class that all GOAP actions must implement.
It enforces strict GameState enum usage for all state references and provides
a standardized interface for action execution.

The BaseAction class ensures consistency across all action implementations
and integrates seamlessly with the GOAP planning system while maintaining
type safety through the GameState enum.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from ..state.game_state import GameState, ActionResult


class BaseAction(ABC):
    """Abstract base class for all GOAP actions.
    
    All actions must implement this interface and use GameState enum
    for all state references to ensure type safety and consistency.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique action identifier for GOAP system"""
        pass
    
    @property
    @abstractmethod
    def cost(self) -> int:
        """GOAP planning cost for this action"""
        pass
    
    @abstractmethod
    def get_preconditions(self) -> Dict[GameState, Any]:
        """Required state conditions using GameState enum keys"""
        pass
    
    @abstractmethod
    def get_effects(self) -> Dict[GameState, Any]:
        """State changes after execution using GameState enum keys"""
        pass
    
    @abstractmethod
    async def execute(self, character_name: str, current_state: Dict[GameState, Any]) -> ActionResult:
        """Execute action via API and return result with state changes"""
        pass
    
    def can_execute(self, current_state: Dict[GameState, Any]) -> bool:
        """Check if action preconditions are met in current state.
        
        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            
        Return values:
            Boolean indicating whether all preconditions are satisfied
            
        This method validates that the current game state satisfies all the
        preconditions required for this action to be executed, enabling the
        GOAP planner to determine action feasibility.
        """
        pass
    
    def validate_preconditions(self) -> bool:
        """Validate that all preconditions use valid GameState enum keys.
        
        Parameters:
            None (operates on self)
            
        Return values:
            Boolean indicating whether all precondition keys are valid GameState enums
            
        This method verifies that the action's preconditions dictionary only uses
        valid GameState enum keys, ensuring type safety and preventing runtime
        errors in the GOAP planning system.
        """
        pass
    
    def validate_effects(self) -> bool:
        """Validate that all effects use valid GameState enum keys.
        
        Parameters:
            None (operates on self)
            
        Return values:
            Boolean indicating whether all effect keys are valid GameState enums
            
        This method verifies that the action's effects dictionary only uses
        valid GameState enum keys, ensuring type safety and enabling proper
        state updates after action execution in the GOAP system.
        """
        pass