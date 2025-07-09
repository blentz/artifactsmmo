"""
Simple Assess Healing Needs Action

This action follows the architecture principles:
- Simple boolean conditions
- Uses StateParameters for all data access
- Declarative GOAP configuration
- No backward compatibility code
"""

import logging
from typing import Dict, Any

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class AssessHealingNeedsAction(ActionBase):
    """
    Simple action to assess if character needs healing.
    
    Follows architecture principles:
    - Simple boolean conditions
    - Uses StateParameters for all data
    - No complex business logic
    """
    
    # GOAP parameters - simple boolean conditions
    conditions = {
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'healing_context': {
            'healing_needed': True
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the simple healing assessment action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Simple healing assessment using StateParameters.
        
        Args:
            client: API client
            context: ActionContext containing character state
            
        Returns:
            Action result with healing assessment
        """
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get HP values from StateParameters
        current_hp = context.get(StateParameters.CHARACTER_HP, 100)
        max_hp = context.get(StateParameters.CHARACTER_MAX_HP, 100)
        
        if max_hp == 0:
            return self.create_error_result("Invalid character state: max_hp is 0")
        
        # Calculate HP percentage
        hp_percentage = (current_hp / max_hp) * 100
        
        # Simple healing threshold - needs healing if not at full HP
        healing_needed = current_hp < max_hp
        
        # Log result
        if healing_needed:
            self.logger.info(f"💔 Healing needed: HP at {current_hp}/{max_hp} ({hp_percentage:.1f}%)")
        else:
            self.logger.debug(f"💚 No healing needed: HP at {current_hp}/{max_hp} ({hp_percentage:.1f}%)")
        
        # Update context with results using StateParameters
        context.set_result(StateParameters.HEALING_NEEDED, healing_needed)
        
        return self.create_success_result(
            message=f"Healing assessment: {'needed' if healing_needed else 'not needed'} (HP: {current_hp}/{max_hp})",
            healing_needed=healing_needed,
            current_hp=current_hp,
            max_hp=max_hp,
            hp_percentage=hp_percentage
        )