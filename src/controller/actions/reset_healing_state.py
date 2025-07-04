"""
Reset Healing State Action

This bridge action resets the healing state after completion,
allowing the healing flow to be used again in future cycles.
"""

from typing import Dict, Any

from src.lib.action_context import ActionContext
from .base import ActionBase, ActionResult


class ResetHealingStateAction(ActionBase):
    """
    Bridge action to reset healing state after completion.
    
    This action transitions the healing state from 'complete' back to 'idle',
    making the healing system ready for future use.
    """
    
    def __init__(self):
        """Initialize reset healing state action."""
        super().__init__()
        
    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """
        Reset healing state to idle.
        
        Args:
            client: API client
            context: Action context
            
        Returns:
            Dict with state reset results
        """
        self._context = context
        
        try:
            self.logger.debug("🔄 Resetting healing state to idle")
            
            # This is a state update action - no API call needed
            return self.create_success_result(
                "Healing state reset to idle",
                healing_state_reset=True
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to reset healing state: {e}")
    
    def __repr__(self):
        return "ResetHealingStateAction()"