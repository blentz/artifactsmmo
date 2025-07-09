"""
Simple Initiate Healing Action

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


class InitiateHealingAction(ActionBase):
    """
    Simple action to initiate the healing process.
    
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
        'healing_context': {
            'healing_needed': True
        }
    }
    
    reactions = {
        'healing_context': {
            'healing_status': 'healing_initiated'
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the simple healing initiation action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Simple healing initiation using StateParameters.
        
        Args:
            client: API client
            context: ActionContext containing character state
            
        Returns:
            Action result with healing initiation
        """
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get HP values from StateParameters
        current_hp = context.get(StateParameters.CHARACTER_HP, 100)
        max_hp = context.get(StateParameters.CHARACTER_MAX_HP, 100)
        
        # Simple healing method selection - only rest available for now
        healing_method = 'rest'
        
        # Calculate HP percentage for logging
        hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 100
        
        self.logger.info(f"🏥 Initiating healing process using method: {healing_method}")
        self.logger.info(f"💊 Current HP: {current_hp}/{max_hp} ({hp_percentage:.1f}%)")
        
        # Update context with results using StateParameters
        context.set_result(StateParameters.HEALING_STATUS, 'healing_initiated')
        context.set_result(StateParameters.HEALING_METHOD, healing_method)
        
        return self.create_success_result(
            message=f"Healing initiated using method: {healing_method}",
            healing_initiated=True,
            healing_method=healing_method,
            starting_hp=current_hp,
            starting_hp_percentage=hp_percentage
        )