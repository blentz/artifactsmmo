"""
Gather Missing Materials Action

This action handles material gathering when materials are determined to be insufficient.
It coordinates the process of finding, moving to, and gathering the required materials.
"""

from typing import Dict, List, Optional, Tuple

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext
from src.controller.actions.find_resources import FindResourcesAction
from src.controller.actions.move_to_resource import MoveToResourceAction
from src.controller.actions.gather_resources import GatherResourcesAction


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
            'status': 'insufficient',
            'availability_checked': True
        },
        'character_status': {
            'alive': True,
        },
    }
    
    reactions = {
        'materials': {
            'status': 'gathering',
            'gathering_initiated': True
        },
        'resource_availability': {
            'resources': True
        }
    }
    
    weight = 2.0
    
    def __init__(self):
        """Initialize the gather missing materials action."""
        super().__init__()
        self.find_resources_action = FindResourcesAction()
        self.move_to_resource_action = MoveToResourceAction()
        self.gather_resources_action = GatherResourcesAction()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute material gathering for missing materials.
        
        Args:
            client: API client for character data
            context: ActionContext containing missing materials
            
        Returns:
            Action result with gathering status
        """
        self._context = context
        
        character_name = context.character_name
        missing_materials = context.get('missing_materials', {})
        
        if not missing_materials:
            return self.create_error_result("No missing materials specified")
            
        self.logger.info(f"🔨 Need to gather materials: {missing_materials}")
        
        try:
            # Get the first missing material and quantity needed
            if isinstance(missing_materials, dict):
                # Handle dict format: {'copper_ore': 10}
                target_material = list(missing_materials.keys())[0]
                quantity_needed = missing_materials[target_material]
            else:
                # Handle list format: ['copper_ore']
                target_material = missing_materials[0] if isinstance(missing_materials, list) else str(missing_materials)
                quantity_needed = 1
                
            self.logger.info(f"🎯 Targeting {quantity_needed}x {target_material}")
            
            # Step 1: Find resource location
            context['resource_types'] = [target_material]
            find_result = self.find_resources_action.execute(client, context)
            
            if not find_result.success:
                return self.create_error_result(f"Could not find resource location for {target_material}")
                
            # Get coordinates from find_result data
            target_x = find_result.data.get('target_x')
            target_y = find_result.data.get('target_y')
            
            if target_x is None or target_y is None:
                return self.create_error_result(f"FindResourcesAction did not return valid coordinates for {target_material}. Got target_x={target_x}, target_y={target_y}")
                
            self.logger.info(f"📍 Found {target_material} at ({target_x}, {target_y})")
            
            # Ensure coordinates are set on context for MoveToResourceAction
            context.target_x = target_x
            context.target_y = target_y
            
            # Step 2: Move to resource location
            move_result = self.move_to_resource_action.execute(client, context)
            
            if not move_result.success:
                # Preserve the actual error from the movement action
                actual_error = getattr(move_result, 'error', 'Unknown movement error')
                return self.create_error_result(f"Could not move to resource location ({target_x}, {target_y}): {actual_error}")
                
            self.logger.info(f"✅ Moved to resource location")
            
            # Step 3: Gather resources
            gathered_total = 0
            attempts = 0
            max_attempts = 10  # Limit gathering attempts
            
            while gathered_total < quantity_needed and attempts < max_attempts:
                gather_result = self.gather_resources_action.execute(client, context)
                
                if not gather_result.success:
                    self.logger.warning(f"Gathering attempt {attempts + 1} failed")
                    break
                    
                # Check items obtained
                items_obtained = gather_result.data.get('items_obtained', [])
                for item in items_obtained:
                    if item.get('code') == target_material:
                        gathered_total += item.get('quantity', 0)
                        
                attempts += 1
                self.logger.info(f"🛠️ Gathered {gathered_total}/{quantity_needed} {target_material} (attempt {attempts})")
                
                if gathered_total >= quantity_needed:
                    break
                    
            # Determine if we gathered enough
            gathering_complete = gathered_total >= quantity_needed
            
            state_changes = {
                'materials': {
                    'status': 'gathering' if not gathering_complete else 'checking',
                    'gathering_initiated': True,
                    'last_gathered': target_material
                },
                'location_context': {
                    'at_resource': True,
                    'current_resource': target_material
                },
                'resource_availability': {
                    'resources': True
                }
            }
            
            # Store results in context for other actions
            context.set_result('target_material', target_material)
            context.set_result('materials_gathered', {target_material: gathered_total})
            context.set_result('gathering_complete', gathering_complete)
            context.set_result('quantity_needed', quantity_needed)
            context.set_result('quantity_gathered', gathered_total)
            
            if gathering_complete:
                message = f"Successfully gathered {gathered_total} {target_material}"
            else:
                message = f"Partially gathered {gathered_total}/{quantity_needed} {target_material}"
                
            return self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                message=message,
                target_material=target_material,
                quantity_gathered=gathered_total,
                quantity_needed=quantity_needed,
                gathering_complete=gathering_complete
            )
            
        except Exception as e:
            return self.create_error_result(f"Material gathering failed: {str(e)}")
            
    def __repr__(self):
        return "GatherMissingMaterialsAction()"