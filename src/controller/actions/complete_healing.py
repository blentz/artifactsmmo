"""
Simple Complete Healing Action

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


class CompleteHealingAction(ActionBase):
    """
    Simple action to complete the healing process.
    
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
            'healing_status': 'healing_initiated'
        }
    }
    
    reactions = {
        'healing_context': {
            'healing_status': 'healing_completed',
            'healing_needed': False
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the simple healing completion action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Simple healing completion using StateParameters.
        
        Args:
            client: API client
            context: ActionContext containing character state
            
        Returns:
            Action result with healing completion
        """
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get HP values from StateParameters
        current_hp = context.get(StateParameters.CHARACTER_HP, 100)
        max_hp = context.get(StateParameters.CHARACTER_MAX_HP, 100)
        
        # Calculate HP percentage for logging
        hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 100
        
        self.logger.info(f"✅ Healing process completed")
        self.logger.info(f"💚 Final HP: {current_hp}/{max_hp} ({hp_percentage:.1f}%)")
        
        # Update context with results using StateParameters
        context.set_result(StateParameters.HEALING_STATUS, 'healing_completed')
        context.set_result(StateParameters.HEALING_NEEDED, False)
        
        return self.create_success_result(
            message="Healing process completed successfully",
            healing_completed=True,
            final_hp=current_hp,
            final_hp_percentage=hp_percentage
        )