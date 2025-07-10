"""
Simple Analyze Equipment Gaps Action

This action follows the architecture principles:
- Simple boolean/string conditions
- Single responsibility 
- Declarative configuration
- Direct property access with StateParameters
"""

import logging
from typing import Any, Dict, Optional

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters


class AnalyzeEquipmentGapsAction(ActionBase):
    """
    Simple action to analyze equipment gaps using declarative configuration.
    
    Follows architecture principles:
    - Simple boolean conditions
    - Single responsibility
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
        'equipment_status': {
            'gaps_analyzed': True
        }
    }
    
    weight = 1.0
    
    def __init__(self):
        """Initialize the simple equipment gap analysis action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Simple equipment gap analysis using declarative configuration.
        
        Args:
            client: API client
            context: ActionContext containing character state
            
        Returns:
            Action result with simple equipment gap analysis
        """
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context using StateParameters
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
        
        character_level = context.get(StateParameters.CHARACTER_LEVEL, 1)
        
        self._context = context
        
        try:
            # Equipment parameters removed - APIs are authoritative for current equipment state
            # Use character API to get current equipment directly
            from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
            
            char_response = get_character_api(name=character_name, client=client)
            if not char_response or not char_response.data:
                return self.create_error_result("Could not retrieve character data")
                
            char_data = char_response.data
            equipment_slots = ['weapon', 'helmet', 'body_armor', 'shield', 'boots', 'amulet', 'ring1', 'ring2']
            
            # Simple gap analysis - check if equipment slots are empty or low level
            gap_analysis = {}
            for slot in equipment_slots:
                current_item = getattr(char_data, slot, None) or ""
                
                if not current_item:
                    gap_analysis[slot] = {
                        'missing': True,
                        'urgency_score': 100,
                        'reason': 'missing_equipment'
                    }
                else:
                    gap_analysis[slot] = {
                        'missing': False,
                        'urgency_score': 50,
                        'reason': 'has_equipment'
                    }
            
            # Find highest priority gap
            max_urgency = max(gap_analysis.values(), key=lambda x: x['urgency_score'])
            target_slot = next(slot for slot, data in gap_analysis.items() 
                             if data['urgency_score'] == max_urgency['urgency_score'])
            
            # Simple success result
            result = self.create_success_result(
                gap_analysis=gap_analysis,
                target_slot=target_slot,
                gaps_analyzed=True,
                character_level=character_level
            )
            
            # Update context with results
            context.set_result(StateParameters.EQUIPMENT_GAP_ANALYSIS, gap_analysis)
            context.set_result(StateParameters.TARGET_SLOT, target_slot)
            
            return result
            
        except Exception as e:
            return self.create_error_result(f"Equipment gap analysis failed: {str(e)}")