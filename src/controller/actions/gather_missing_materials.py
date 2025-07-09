"""
Gather Missing Materials Action

This action handles material gathering when materials are determined to be insufficient.
It coordinates the process of finding, moving to, and gathering the required materials.
"""

from typing import Dict, List, Optional, Tuple

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.recipe_utils import get_recipe_from_context, get_recipe_materials
from src.game.globals import MaterialStatus


class GatherMissingMaterialsAction(ActionBase):
    """
    Action to gather materials when they are determined to be insufficient.
    
    This action:
    1. Takes missing materials from action context
    2. Finds where to gather the first missing material
    3. Moves to the location and gathers materials
    4. Updates material status when sufficient materials are gathered
    """
    
    # GOAP parameters
    conditions = {
        'materials': {
            'status': MaterialStatus.INSUFFICIENT,
            'availability_checked': True
        },
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'materials': {
            'status': [MaterialStatus.GATHERING, MaterialStatus.SUFFICIENT],  # Can be either gathering or sufficient
            'gathering_initiated': True
        },
        'resource_availability': {
            'resources': True,
            'resource_known': True
        },
        'location_context': {
            'target_known': True,
            'needs_movement': True
        }
    }
    
    weight = 2.0
    
    def __init__(self):
        """Initialize the gather missing materials action."""
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute material gathering for missing materials with proper continuation logic.
        
        This action implements stateful continuation:
        1. First execution: Find resource location and request move subgoal
        2. Continuation: Check if at target location and proceed to gather
        
        Args:
            client: API client for character data
            context: ActionContext containing missing materials
            
        Returns:
            Action result with gathering status
        """
        self._context = context
        
        character_name = context.get(StateParameters.CHARACTER_NAME)
        
        # Check for missing materials in context first, then calculate from recipe if needed
        missing_materials_raw = context.get(StateParameters.MISSING_MATERIALS, {})
        
        # Handle both dict and list formats for missing_materials
        if isinstance(missing_materials_raw, list):
            # Convert list format ['item1', 'item2'] to dict format {'item1': 1, 'item2': 1}
            missing_materials = {item: 1 for item in missing_materials_raw}
        elif isinstance(missing_materials_raw, dict):
            missing_materials = missing_materials_raw
        else:
            missing_materials = {}
        
        if not missing_materials:
            # No missing materials in context, calculate from recipe
            try:
                target_recipe = get_recipe_from_context(context)
                if target_recipe:
                    recipe_materials = get_recipe_materials(target_recipe)
                    if recipe_materials:
                        # Check current inventory against recipe requirements
                        current_inventory = context.get_character_inventory()
                        
                        for material_code, required_quantity in recipe_materials.items():
                            current_quantity = current_inventory.get(material_code, 0)
                            if current_quantity < required_quantity:
                                missing_materials[material_code] = required_quantity - current_quantity
            except ValueError:
                # Recipe not available, check if missing_materials was provided directly
                pass
        
        if not missing_materials:
            return self.create_error_result("No materials required for recipe")
        
        if not missing_materials:
            # We have all materials needed
            state_changes = {
                'materials': {
                    'status': MaterialStatus.SUFFICIENT,
                    'gathered': True
                }
            }
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message="All required materials gathered"
            )
            
        self.logger.info(f"🔨 Need to gather materials: {missing_materials}")
        
        try:
            # Get the first missing material and quantity needed
            target_material = list(missing_materials.keys())[0]
            quantity_needed = missing_materials[target_material]
                
            # Check if we're continuing from a previous execution (resource coordinates already found)
            target_x = context.get(StateParameters.TARGET_X)
            target_y = context.get(StateParameters.TARGET_Y)
            stored_material = context.get(StateParameters.TARGET_MATERIAL)
            
            # Step 1: Check if we're at the target location and can proceed to gathering
            if (target_x is not None and target_y is not None and 
                stored_material == target_material):
                
                # Get current character location to check if we're at target
                from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
                char_response = get_character_api(character_name, client=client)
                
                if not char_response.data:
                    return self.create_error_result("Could not get character data")
                    
                current_x = char_response.data.x
                current_y = char_response.data.y
                
                # If we're at the target location, proceed with gathering
                if current_x == target_x and current_y == target_y:
                    self.logger.info(f"📍 At target location ({target_x}, {target_y}), proceeding to gather {target_material}")
                    
                    # Request gather_resource subgoal to perform the actual gathering
                    result = self.create_success_result(f"At target location, requesting gather operation for {target_material}")
                    
                    result.request_subgoal(
                        goal_name="gather_resource",
                        parameters={
                            "target_resource": target_material,
                            "quantity_needed": quantity_needed
                        }
                    )
                    
                    self.logger.info(f"🎯 Requesting gather_resource subgoal for {target_material}")
                    return result
            
            # Step 2: Need to find resource location first
            self.logger.info(f"🎯 Need to find location for {target_material}")
            
            # Store the target material in context for the find_resources subgoal
            context.set_result(StateParameters.TARGET_MATERIAL, target_material)
            context.set_result(StateParameters.QUANTITY_NEEDED, quantity_needed)
            
            # Request find_resources subgoal to locate the material
            result = self.create_success_result(f"Need to find location for {target_material}")
            
            result.request_subgoal(
                goal_name="find_resources", 
                parameters={
                    "resource_types": [target_material]
                }
            )
            
            self.logger.info(f"🎯 Requesting find_resources subgoal for {target_material}")
            return result
            
        except Exception as e:
            return self.create_error_result(f"Material gathering failed: {str(e)}")
            
    def __repr__(self):
        return "GatherMissingMaterialsAction()"