"""
Analyze Crafting Requirements Action

Simple action to analyze crafting requirements for a target item.
Follows architecture principles:
- Single responsibility
- Simple boolean conditions
- Uses subgoal system for complex workflows
"""

import logging
from typing import Dict, List

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class AnalyzeCraftingRequirementsAction(ActionBase):
    """
    Simple action to analyze crafting requirements for a target item.
    
    Follows architecture principles:
    - Single responsibility (analyze one item's requirements)
    - Simple boolean conditions
    - Uses StateParameters for all data
    - Requests subgoals for complex workflows
    """

    # Simple GOAP parameters
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
        """Initialize the crafting requirements analysis action."""
        super().__init__()
        self.logger = logging.getLogger(__name__)

    def execute(self, client, context: ActionContext) -> ActionResult:
        """Analyze crafting requirements for target item."""
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
            # Get crafting data from knowledge base
            items_data = knowledge_base.data.get('items', {})
            item_data = items_data.get(target_item)
            
            if not item_data:
                # Request subgoal to lookup item info
                return self.create_result_with_subgoal(
                    subgoal_name='lookup_item_info',
                    subgoal_parameters={StateParameters.TARGET_ITEM: target_item},
                    preserve_context=True
                )
                
            craft_data = item_data.get('craft_data')
            if not craft_data:
                return self.create_error_result(f"Item {target_item} is not craftable")
            
            # Extract simple requirements
            required_materials = craft_data.get('items', [])
            required_skill = craft_data.get('skill', 'unknown')
            required_skill_level = craft_data.get('level', 1)
            
            # Set results in context for other actions
            context.set_result(StateParameters.REQUIRED_CRAFT_SKILL, required_skill)
            context.set_result(StateParameters.REQUIRED_CRAFT_LEVEL, required_skill_level)
            
            # Simple success result - required_materials available from knowledge base lookup
            return self.create_success_result(
                target_item=target_item,
                required_materials=required_materials,
                required_skill=required_skill,
                required_skill_level=required_skill_level,
                crafting_requirements_known=True
            )
            
        except Exception as e:
            return self.create_error_result(f"Crafting requirements analysis failed: {str(e)}")

    def create_result_with_subgoal(self, subgoal_name: str, subgoal_parameters: Dict, preserve_context: bool = True) -> ActionResult:
        """Create result that requests a subgoal."""
        result = self.create_success_result(
            subgoal_requested=True,
            subgoal_name=subgoal_name
        )
        result.request_subgoal(subgoal_name, subgoal_parameters, preserve_context)
        return result