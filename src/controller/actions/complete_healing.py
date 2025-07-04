"""
Complete Healing Action

This bridge action marks the healing process as complete after HP has been restored.
It resets the healing state machine for future healing cycles.
"""

from typing import Dict, Any

from src.lib.action_context import ActionContext
from .base import ActionBase, ActionResult


class CompleteHealingAction(ActionBase):
    """
    Bridge action to complete the healing process.
    
    This action transitions the healing state from 'in_progress' to 'complete'
    and resets healing flags after successful healing.
    """
    
    def __init__(self):
        """Initialize complete healing action."""
        super().__init__()
        
    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """
        Mark healing process as complete.
        
        Args:
            client: API client
            context: Action context
            
        Returns:
            Dict with healing completion results
        """
        self._context = context
        
        try:
            # Get current HP to verify healing success
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
            
            # Get healing context
            healing_context = world_state.get('healing_context', {})
            healing_method = healing_context.get('healing_method', 'unknown')
            
            self.logger.info(f"✅ Healing complete using {healing_method}")
            self.logger.info(f"💚 Final HP: {hp_percentage:.1f}%")
            
            # Calculate healing effectiveness (for future analytics)
            starting_hp = context.get('starting_hp', 0)
            hp_gained = hp_percentage - starting_hp if starting_hp else hp_percentage
            
            # This is a state update action - no API call needed
            return self.create_success_result(
                f"Healing complete: {hp_percentage:.1f}% HP (+{hp_gained:.1f}%)",
                healing_complete=True,
                final_hp=hp_percentage,
                hp_gained=hp_gained,
                healing_method=healing_method
            )
            
        except Exception as e:
            return self.create_error_result(f"Failed to complete healing: {e}")
    
    def __repr__(self):
        return "CompleteHealingAction()"