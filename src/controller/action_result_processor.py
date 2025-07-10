"""
Action Result Processor

Specialized manager for processing action execution results.
Follows architecture principle: specialized managers handle specific concerns.
"""

import logging
from typing import Any, Dict, Tuple

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.unified_state_context import get_unified_context
from .action_executor import ActionResult


class ActionResultProcessor:
    """
    Specialized manager for processing action execution results.
    
    Handles all business logic for extracting data from action results,
    updating goal progress, and managing state transitions.
    
    Single Responsibility: Action result processing only.
    """
    
    def __init__(self):
        """Initialize the action result processor."""
        self.logger = logging.getLogger(__name__)
        self.unified_context = get_unified_context()
    
    def process_result(self, result: ActionResult, action_name: str, context: ActionContext) -> Dict[str, Any]:
        """
        Process action execution result and extract relevant data.
        
        Args:
            result: ActionResult from action execution
            action_name: Name of the executed action
            context: ActionContext used for execution
            
        Returns:
            Dictionary of processed result data
        """
        try:
            if not result or not result.data:
                return {}
            
            # Route to specific processors based on result data characteristics
            if self._has_location_data(result):
                return self._process_location_result(result, action_name)
            elif self._has_recipe_data(result):
                return self._process_recipe_result(result)
            elif self._has_weapon_selection_data(result):
                return self._process_weapon_selection_result(result)
            elif self._has_combat_data(result):
                return self._process_combat_result(result)
            else:
                return self._process_generic_result(result)
                
        except Exception as e:
            self.logger.error(f"Failed to process result for {action_name}: {e}")
            return {}
    
    def _has_location_data(self, result: ActionResult) -> bool:
        """Check if result contains location data."""
        return (hasattr(result.data, 'get') and 
                result.data.get('target_x') is not None and 
                result.data.get('target_y') is not None)
    
    def _has_recipe_data(self, result: ActionResult) -> bool:
        """Check if result contains recipe data."""
        return (hasattr(result.data, 'get') and 
                result.data.get('success') and 
                result.data.get('recipe_found'))
    
    def _has_weapon_selection_data(self, result: ActionResult) -> bool:
        """Check if result contains weapon selection data."""
        return (hasattr(result.data, 'get') and 
                result.data.get('success') and 
                result.data.get('item_code') and 
                result.data.get('selected_weapon'))
    
    def _has_combat_data(self, result: ActionResult) -> bool:
        """Check if result contains combat data."""
        return (hasattr(result.data, 'get') and 
                result.data.get('success') and 
                result.data.get('monster_defeated'))
    
    def _process_location_result(self, result: ActionResult, action_name: str) -> Dict[str, Any]:
        """Process location-finding action results."""
        try:
            if not hasattr(result.data, 'get'):
                return {}
            
            target_x = result.data.get('target_x')
            target_y = result.data.get('target_y')
            
            if target_x is not None and target_y is not None:
                result_data = {
                    'target_x': target_x,
                    'target_y': target_y
                }
                
                self.logger.info(f"Found location from {action_name}: ({target_x}, {target_y})")
                
                return result_data
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to process location result: {e}")
            return {}
    
    def _process_recipe_result(self, result: ActionResult) -> Dict[str, Any]:
        """Process recipe lookup action results."""
        try:
            if not hasattr(result.data, 'get') or not result.data.get('success'):
                return {}
            
            if not result.data.get('recipe_found'):
                return {}
            
            materials_needed = result.data.get('materials_needed', [])
            resource_types = []
            
            for material in materials_needed:
                if material.get('is_resource'):
                    resource_code = material.get('resource_source', material.get('code'))
                    resource_types.append(resource_code)
            
            # Check for crafting chain requirements
            crafting_chain = result.data.get('crafting_chain', [])
            smelting_required = False
            smelt_data = {}
            
            if crafting_chain:
                intermediate_steps = [step for step in crafting_chain if step.get('step_type') == 'craft_intermediate']
                if intermediate_steps:
                    first_step = intermediate_steps[0]
                    smelt_data = {
                        'smelt_item_code': first_step.get('item_code'),
                        'smelt_item_name': first_step.get('item_name'),
                        'smelt_skill': first_step.get('craft_skill')
                    }
                    smelting_required = True
            
            result_data = {
                'recipe_item_code': result.data.get('item_code'),
                'recipe_item_name': result.data.get('item_name'),
                'resource_types': resource_types,
                'craft_skill': result.data.get('craft_skill'),
                'materials_needed': materials_needed,
                'crafting_chain': crafting_chain,
                'smelting_required': smelting_required,
                **smelt_data
            }
            
            self.logger.info(f"📋 Recipe selected: {result.data.get('item_name')} - needs {resource_types}")
            if smelting_required:
                self.logger.info(f"🔥 Smelting required: {smelt_data.get('smelt_item_code')}")
            
            return result_data
            
        except Exception as e:
            self.logger.error(f"Failed to process recipe result: {e}")
            return {}
    
    def _process_weapon_selection_result(self, result: ActionResult) -> Dict[str, Any]:
        """Process weapon recipe evaluation results."""
        try:
            if not hasattr(result.data, 'get') or not result.data.get('success'):
                return {}
            
            if not result.data.get('item_code'):
                return {}
            
            result_data = {
                'item_code': result.data.get('item_code'),
                'selected_weapon': result.data.get('selected_weapon'),
                'weapon_name': result.data.get('weapon_name'),
                'workshop_type': result.data.get('workshop_type')
            }
            
            self.logger.info(f"🗡️ Weapon selected: {result.data.get('weapon_name')} (code: {result.data.get('item_code')})")
            return result_data
            
        except Exception as e:
            self.logger.error(f"Failed to process weapon selection result: {e}")
            return {}
    
    def _process_combat_result(self, result: ActionResult) -> Dict[str, Any]:
        """Process combat action results and update goal progress."""
        try:
            if not hasattr(result.data, 'get') or not result.data.get('success'):
                return {}
            
            if result.data.get('monster_defeated'):
                # Update goal progress in unified context
                current_monsters = self.unified_context.get(StateParameters.GOAL_MONSTERS_HUNTED, 0)
                new_count = current_monsters + 1
                self.unified_context.set(StateParameters.GOAL_MONSTERS_HUNTED, new_count)
                
                self.logger.info(f"⚔️ Monster defeated! Total monsters hunted: {new_count}")
                
                return {'monsters_hunted': new_count, 'monster_defeated': True}
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Failed to process combat result: {e}")
            return {}
    
    def _process_generic_result(self, result: ActionResult) -> Dict[str, Any]:
        """Process generic action results."""
        try:
            # Default behavior: no result processing needed
            # Actions that need result processing should match specific data characteristics
            # This avoids hardcoding action names or data field mappings
            return {}
                
        except Exception as e:
            self.logger.error(f"Failed to process generic result: {e}")
            return {}