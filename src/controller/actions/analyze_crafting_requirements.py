"""
Simple Analyze Crafting Requirements Action

This action follows the architecture principles:
- Simple boolean/string conditions
- Single responsibility 
- Declarative configuration
- Direct property access with StateParameters
"""

import logging
from typing import Dict, List

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class AnalyzeCraftingRequirementsAction(ActionBase):
    """
    Simple action to analyze crafting requirements using declarative configuration.
    
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
        'crafting_requirements_known': True,
        'materials_requirements_determined': True,
    }
    weight = 12

    def __init__(self):
        """Initialize the simple crafting requirements analysis action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Simple crafting requirements analysis using declarative configuration."""
        # Call superclass to set self._context
        super().execute(client, context)
        
        # Get parameters from context using StateParameters
        character_name = context.get(StateParameters.CHARACTER_NAME)
        if not character_name:
            return self.create_error_result("No character name provided")
        
        target_item = context.get(StateParameters.TARGET_ITEM)
        if not target_item:
            return self.create_error_result("No target item specified")
        
        knowledge_base = context.knowledge_base
        if not knowledge_base:
            return self.create_error_result("No knowledge base available")
        
        self._context = context
        
        try:
            # Simple approach: Get crafting requirements for target item
            items = knowledge_base.data.get('items', {})
            item_data = items.get(target_item)
            
            if not item_data:
                return self.create_error_result(f"No data found for item: {target_item}")
                
            craft_data = item_data.get('craft_data')
            if not craft_data:
                return self.create_error_result(f"Item {target_item} is not craftable")
            
            # Extract simple requirements
            required_materials = craft_data.get('items', [])
            required_skill = craft_data.get('skill', 'unknown')
            required_skill_level = craft_data.get('level', 1)
            
            # Simple success result
            result = self.create_success_result(
                target_item=target_item,
                required_materials=required_materials,
                required_skill=required_skill,
                required_skill_level=required_skill_level,
                crafting_requirements_known=True
            )
            
            # Update context with requirements
            context.set_result(StateParameters.MATERIALS_REQUIRED, required_materials)
            context.set_result(StateParameters.REQUIRED_CRAFT_SKILL, required_skill)
            context.set_result(StateParameters.REQUIRED_CRAFT_LEVEL, required_skill_level)
            
            return result
            
        except Exception as e:
            return self.create_error_result(f"Crafting requirements analysis failed: {str(e)}")