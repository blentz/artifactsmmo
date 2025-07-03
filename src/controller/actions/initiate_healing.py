"""
Initiate Healing Action

This bridge action starts the healing flow when healing is needed.
It transitions the healing state machine and prepares for actual healing actions.
"""

from typing import Dict, Any

from src.lib.action_context import ActionContext
from .base import ActionBase


class InitiateHealingAction(ActionBase):
    """
    Bridge action to initiate the healing process.
    
    This action transitions the healing state from 'needed' to 'in_progress'
    and determines the appropriate healing method based on available options.
    """
    
    def __init__(self):
        """Initialize initiate healing action."""
        super().__init__()
        
    def execute(self, client, context: 'ActionContext') -> Dict[str, Any]:
        """
        Initiate the healing process.
        
        Args:
            client: API client
            context: Action context
            
        Returns:
            Dict with healing initiation results
        """
        try:
            # Get current state
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
            
            # Determine best healing method
            # For now, we only have rest, but this can be extended
            healing_method = self._select_healing_method(world_state, context)
            
            self.logger.info(f"🏥 Initiating healing process using method: {healing_method}")
            self.logger.info(f"💊 Current HP: {hp_percentage:.1f}%")
            
            # This is a state update action - no API call needed
            return self.get_success_response(
                healing_initiated=True,
                healing_method=healing_method,
                starting_hp=hp_percentage
            )
            
        except Exception as e:
            return self.get_error_response(f"Failed to initiate healing: {e}")
    
    def _select_healing_method(self, world_state: Dict[str, Any], 
                              context: 'ActionContext') -> str:
        """
        Select the best available healing method.
        
        Future methods might include:
        - 'potion' if healing potions are in inventory
        - 'spell' if character has healing spells
        - 'food' if food items are available
        
        Args:
            world_state: Current world state
            context: Action context
            
        Returns:
            str: Selected healing method
        """
        # For now, only rest is available
        # Future: Check inventory for potions, check skills for healing spells, etc.
        
        # Example future logic:
        # inventory = world_state.get('materials', {}).get('inventory', {})
        # if 'health_potion' in inventory and inventory['health_potion'] > 0:
        #     return 'potion'
        
        return 'rest'
    
    def __repr__(self):
        return "InitiateHealingAction()"