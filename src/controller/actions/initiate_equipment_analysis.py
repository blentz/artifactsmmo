"""
Initiate Equipment Analysis Action

This bridge action initiates the equipment upgrade process by transitioning
the equipment status from 'none' to 'analyzing'.
"""

from typing import Dict, Optional

from src.lib.action_context import ActionContext

from .base import ActionBase


class InitiateEquipmentAnalysisAction(ActionBase):
    """
    Bridge action to start equipment upgrade analysis.
    
    This action transitions the equipment_status.upgrade_status from 'none' to 'analyzing',
    signaling the start of the equipment upgrade process.
    """

    # GOAP parameters
    conditions = {
        'equipment_status': {
            'upgrade_status': 'none',
        },
        'character_status': {
            'alive': True,
        },
    }
    reactions = {
        'equipment_status': {
            'upgrade_status': 'analyzing',
        },
    }
    weights = {'equipment_status.upgrade_status': 1.5}

    def __init__(self):
        """Initialize initiate equipment analysis action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> Optional[Dict]:
        """
        Execute equipment analysis initiation.
        
        This is a state-only action that updates the equipment status
        without making any API calls.
        """
        character_name = context.character_name
        if not character_name:
            return self.get_error_response("No character name provided")
            
        self.log_execution_start(character_name=character_name)
        
        try:
            # Get current character level for context
            character_status = context.get('character_status', {})
            character_level = character_status.get('level', 1)
            
            # Log the initiation
            self.logger.info(
                f"🔍 Initiating equipment analysis for level {character_level} character"
            )
            
            # This is a bridge action - it only updates state, no API calls needed
            result = self.get_success_response(
                equipment_analysis_initiated=True,
                previous_status='none',
                new_status='analyzing',
                character_level=character_level,
                message="Equipment upgrade analysis initiated"
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Failed to initiate equipment analysis: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def __repr__(self):
        return "InitiateEquipmentAnalysisAction()"
