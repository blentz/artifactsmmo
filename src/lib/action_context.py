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
        Create ActionContext using the unified context singleton.
        
        Following docs/ARCHITECTURE.md: No state synchronization needed since
        UnifiedStateContext is the single source of truth.
        
        Args:
            controller: AI controller instance
            action_data: Action-specific data (ignored - singleton pattern)
            
        Returns:
            ActionContext instance using the singleton unified context
        """
        # Pure singleton pattern - no data copying or synchronization
        context = cls()
        
        # Set dependencies from controller - knowledge_base is single source of truth for map operations
        if hasattr(controller, 'knowledge_base'):
            context.knowledge_base = controller.knowledge_base
        
        # Store controller reference for post-execution updates
        context.controller = controller
        
        return context
    
    def get_character_inventory(self) -> Dict[str, int]:
        """Get inventory using character data - no caching."""
        # This method will be eliminated when inventory moves to StateParameters
        return {}
    
    # get_equipped_item_in_slot removed - APIs are authoritative for current equipment state
    # Use character API calls directly instead of state parameters