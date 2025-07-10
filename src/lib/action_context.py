"""
Unified Action Context System - Zero Backward Compatibility

Pure StateParameters-based implementation with no legacy support.
Single execution path for all state access.

Design Principles:
- Single Responsibility: Action context management only
- KISS: Simple StateParameters-only access
- DRY: No duplicate state storage
- Zero backward compatibility: Clean slate
"""

import logging
from typing import Any, Dict, Optional
from src.lib.unified_state_context import get_unified_context
from src.lib.state_parameters import StateParameters


class ActionContext:
    """
    Pure StateParameters-based action context.
    
    Zero backward compatibility - uses only StateParameters registry
    for all state access and validation.
    """
    
    def __init__(self):
        """Initialize with unified state singleton."""
        self._state = get_unified_context()
        self._logger = logging.getLogger(__name__)
    
    def get(self, param: str, default: Any = None) -> Any:
        """Get parameter using StateParameters registry."""
        return self._state.get(param, default)
    
    def set(self, param: str, value: Any) -> None:
        """Set parameter using StateParameters registry."""
        self._state.set(param, value)
        
        # Automatically set related flags - HAS_TARGET_ITEM removed, use knowledge_base.has_target_item() instead
    
    def update(self, updates: Dict[str, Any]) -> None:
        """Update multiple parameters using StateParameters registry."""
        # Use individual set() calls to trigger automatic flag setting
        for param, value in updates.items():
            self.set(param, value)
    
    def set_result(self, param: str, value: Any) -> None:
        """Set result using StateParameters registry only."""
        self.set(param, value)
    
    @classmethod
    def from_controller(cls, controller, action_data: Dict[str, Any] = None) -> 'ActionContext':
        """
        Create ActionContext using the ONE unified context.
        
        Args:
            controller: AI controller instance
            action_data: Action-specific data (ignored - no params support)
            
        Returns:
            ActionContext instance using the singleton unified context
        """
        # There is only ONE context - no synchronization needed
        context = cls()
        
        # Map character data to StateParameters if available
        # Only set character data if the parameters don't already have values
        if hasattr(controller, 'character_state') and controller.character_state:
            char_state = controller.character_state
            
            if hasattr(char_state, 'data'):
                char_data = char_state.data
                
                # Update the ONE context with character data (only if not already set)
                if context.get(StateParameters.CHARACTER_X) == 0:  # Default value
                    context.set(StateParameters.CHARACTER_X, char_data.get('x', 0))
                if context.get(StateParameters.CHARACTER_Y) == 0:  # Default value
                    context.set(StateParameters.CHARACTER_Y, char_data.get('y', 0))
                if context.get(StateParameters.CHARACTER_LEVEL) == 1:  # Default value
                    context.set(StateParameters.CHARACTER_LEVEL, char_data.get('level', 1))
                if context.get(StateParameters.CHARACTER_HP) == 0:  # Default value
                    context.set(StateParameters.CHARACTER_HP, char_data.get('hp', 0))
                if context.get(StateParameters.CHARACTER_MAX_HP) == 0:  # Default value
                    context.set(StateParameters.CHARACTER_MAX_HP, char_data.get('max_hp', 0))
                
                # Only set alive status if HP is provided
                if char_data.get('hp', 0) > 0:
                    context.set(StateParameters.CHARACTER_ALIVE, True)
                
                # Equipment data removed - APIs are authoritative for current equipment state
                # Use character API calls directly instead of duplicating in state parameters
        
        # Set dependencies from controller
        if hasattr(controller, 'knowledge_base'):
            context.knowledge_base = controller.knowledge_base
        if hasattr(controller, 'map_state'):
            context.map_state = controller.map_state
        
        return context
    
    def get_character_inventory(self) -> Dict[str, int]:
        """Get inventory using character data - no caching."""
        # This method will be eliminated when inventory moves to StateParameters
        return {}
    
    # get_equipped_item_in_slot removed - APIs are authoritative for current equipment state
    # Use character API calls directly instead of state parameters