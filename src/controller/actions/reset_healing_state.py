"""
Reset Healing State Action

This bridge action resets the healing state after completion,
allowing the healing flow to be used again in future cycles.
"""

from typing import Dict, Any

from src.lib.action_context import ActionContext
from src.game.globals import HealingStatus
from .base import ActionBase, ActionResult


class ResetHealingStateAction(ActionBase):
    """
    Bridge action to reset healing state after completion.
    
    This action transitions the healing state from HealingStatus.COMPLETE back to HealingStatus.IDLE,
    making the healing system ready for future use.
    """
    
    def __init__(self):
        """Initialize reset healing state action."""
        super().__init__()
        
    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """
        Reset healing state to HealingStatus.IDLE.
        
        Args:
            client: API client
            context: Action context
            
        Returns:
            Dict with state reset results
        """
        self._context = context
        
        try:
            self.logger.debug(f"🔄 Resetting healing state to {HealingStatus.IDLE}")
            
            # This is a state update action - no API call needed
            return self.create_success_result(
                f"Healing state reset to {HealingStatus.IDLE}",
                healing_state_reset=True
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to reset healing state: {e}")
    
    def __repr__(self):
        return "ResetHealingStateAction()"