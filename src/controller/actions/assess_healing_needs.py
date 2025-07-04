"""
Assess Healing Needs Action

This bridge action evaluates the character's current HP and determines
if healing is needed. It sets appropriate state flags for the healing flow.
"""

from typing import Dict, Any

from src.lib.action_context import ActionContext
from .base import ActionBase, ActionResult


class AssessHealingNeedsAction(ActionBase):
    """
    Bridge action to assess if character needs healing.
    
    This action evaluates the current HP percentage and sets state flags
    to indicate whether healing is needed. This allows GOAP to plan
    appropriate healing actions.
    """
    
    def __init__(self):
        """Initialize assess healing needs action."""
        super().__init__()
        self.healing_threshold = 100  # Default: need healing if HP < 100%
        
    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """
        Assess if character needs healing based on current HP.
        
        Args:
            client: API client
            context: Action context with character state
            
        Returns:
            Dict with healing assessment results
        """
        self._context = context
        
        try:
            # Get current HP from world state
            world_state_obj = context.get('world_state')
            if world_state_obj and hasattr(world_state_obj, 'data'):
                # Production case: WorldState object with .data attribute
                world_state = world_state_obj.data
            elif isinstance(world_state_obj, dict):
                # Test case: world_state is already a dictionary
                world_state = world_state_obj
            else:
                world_state = {}
            character_status = world_state.get('character_status', {})
            hp_percentage = character_status.get('hp_percentage', 100)
            
            # Check if healing is needed
            healing_needed = hp_percentage < self.healing_threshold
            
            if healing_needed:
                self.logger.info(f"💔 Healing needed: HP at {hp_percentage:.1f}%")
            else:
                self.logger.debug(f"💚 No healing needed: HP at {hp_percentage:.1f}%")
            
            # This is a state update action - no API call needed
            return self.create_success_result(
                f"Healing assessment: {'needed' if healing_needed else 'not needed'} (HP: {hp_percentage:.1f}%)",
                healing_needed=healing_needed,
                current_hp_percentage=hp_percentage,
                healing_threshold=self.healing_threshold
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to assess healing needs: {e}")
    
    def __repr__(self):
        return f"AssessHealingNeedsAction(threshold={self.healing_threshold})"