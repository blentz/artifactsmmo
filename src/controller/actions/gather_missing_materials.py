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
        
        # Get the target recipe we're working with
        target_recipe = context.get(StateParameters.TARGET_RECIPE)
        if not target_recipe:
            return self.create_error_result("No target recipe to gather materials for")
            
        self.logger.info(f"🔍 Gathering missing materials for recipe: {target_recipe}")
        
        # Get required materials from knowledge base
        knowledge_base = context.knowledge_base
        material_requirements = knowledge_base.get_material_requirements(target_recipe)
        if not material_requirements:
            return self.create_error_result(f"Could not determine requirements for recipe: {target_recipe}")
        
        # Check current inventory to determine what's missing
        current_inventory = self._get_current_inventory(context)
        missing_materials = {}
        for material, required_qty in material_requirements.items():
            available_qty = current_inventory.get(material, 0)
            if available_qty < required_qty:
                missing_materials[material] = required_qty - available_qty
        
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
                            "resource": target_material,
                            "quantity": quantity_needed
                        },
                        preserve_context=["target_recipe"]
                    )
                    
                    self.logger.info(f"🎯 Requesting gather_resource subgoal for {target_material}")
                    return result
            
            # Step 2: Need to find resource location first
            self.logger.info(f"🎯 Need to find location for {target_material}")
            
            # Context already has TARGET_RECIPE - no additional parameters needed
            
            # Request find_resources subgoal to locate the material
            result = self.create_success_result(f"Need to find location for {target_material}")
            
            result.request_subgoal(
                goal_name="find_resources", 
                parameters={
                    "resource_types": [target_material]
                },
                preserve_context=["target_recipe"]
            )
            
            self.logger.info(f"🎯 Requesting find_resources subgoal for {target_material}")
            return result
            
        except Exception as e:
            return self.create_error_result(f"Material gathering failed: {str(e)}")
    
    def _get_current_inventory(self, context: ActionContext) -> Dict[str, int]:
        """Get current inventory from context."""
        inventory = getattr(context, 'inventory', [])
        
        inventory_dict = {}
        for item in inventory:
            inventory_dict[item.code] = item.quantity
                    
        return inventory_dict
            
    def __repr__(self):
        return "GatherMissingMaterialsAction()"