"""
Execute Crafting Plan Action

This action executes a crafting plan by crafting the selected item,
handling unequipping of materials if needed.
"""

from typing import Dict, List, Optional

# API client imports
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult
from .craft_item import CraftItemAction
from .unequip_item import UnequipItemAction
from .mixins.subgoal_mixins import WorkflowSubgoalMixin


class ExecuteCraftingPlanAction(ActionBase, WorkflowSubgoalMixin):
    """
    Action to execute a crafting plan for a selected item.
    
    This action:
    1. Checks if we're at the correct workshop
    2. Unequips any materials that are currently equipped
    3. Crafts the item
    """
    
    # GOAP parameters
    conditions = {
            'character_status': {
                'alive': True,
                'safe': True,
            },
            'materials_sufficient': True,
        }
    reactions = {
        "has_equipment": True,
        "inventory_updated": True,
    }
    weight = 10
    
    def __init__(self):
        """
        Initialize the execute crafting plan action.
        """
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> ActionResult:
        """
        Execute the crafting plan using proper subgoal patterns.
        
        Workflow:
        1. Initial: Validate item and find workshop location  
        2. At workshop: Unequip materials and craft item
        """
        self._context = context
        
        # Get parameters from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        workflow_step = self.get_workflow_step(context, 'initial')
        
        try:
            # Get knowledge base from context
            knowledge_base = context.knowledge_base
            if not knowledge_base:
                return self.create_error_result("No knowledge base available")
            
            # Get target recipe/item for crafting
            target_recipe = context.get(StateParameters.TARGET_RECIPE)
            target_item = context.get(StateParameters.TARGET_ITEM)
            
            # Determine target item from recipe or direct item specification
            if target_recipe:
                target_item = target_recipe
            elif not target_item:
                target_item = self._determine_target_item(context)
                
            if not target_item:
                return self.create_error_result("No target item specified for crafting")
            
            context.set_result('target_item', target_item)
            
            if workflow_step == 'initial':
                return self._handle_initial_step(client, context, target_item, knowledge_base)
            elif workflow_step == 'at_workshop':
                return self._handle_at_workshop_step(client, context, target_item, knowledge_base)
            else:
                return self.create_error_result(f"Unknown workflow step: {workflow_step}")
                
        except Exception as e:
            return self.create_error_result(f"Crafting execution failed: {str(e)}")
    
    def _handle_initial_step(self, client, context: ActionContext, target_item: str, knowledge_base) -> ActionResult:
        """Handle initial step: validate item and request workshop navigation."""
        # Get item data to find workshop type
        item_data = knowledge_base.get_item_data(target_item, client=client)
        if not item_data:
            return self.create_error_result(f"Could not find item data for {target_item}")
        
        craft_data = item_data.get('craft_data', {})
        if not craft_data:
            return self.create_error_result(f"Item {target_item} is not craftable")
        
        workshop_type = craft_data.get('skill', 'unknown')
        
        # Store craft data for later use
        context.set_result('workshop_type', workshop_type)
        context.set_result('craft_data', craft_data)
        
        # Check if already at correct workshop
        if self._is_at_correct_workshop(client, context.get(StateParameters.CHARACTER_NAME), workshop_type):
            self.set_workflow_step(context, 'at_workshop')
            return self._handle_at_workshop_step(client, context, target_item, knowledge_base)
        
        # Request workshop navigation subgoal
        return self.request_workflow_subgoal(
            context,
            goal_name="move_to_location",  # Will be handled by find_workshop + move chain
            parameters={
                "workshop_type": workshop_type,
                "item_code": target_item
            },
            next_step="at_workshop",
            preserve_keys=['target_item', 'workshop_type', 'craft_data']
        )
    
    def _handle_at_workshop_step(self, client, context: ActionContext, target_item: str, knowledge_base) -> ActionResult:
        """Handle at workshop step: unequip materials and craft item."""
        craft_data = context.get('craft_data', {})
        workshop_type = context.get('workshop_type', 'unknown')
        
        # Verify we're still at the correct workshop
        if not self._is_at_correct_workshop(client, context.get(StateParameters.CHARACTER_NAME), workshop_type):
            # Workshop verification failed - restart workflow
            self.set_workflow_step(context, 'initial')
            return self._handle_initial_step(client, context, target_item, knowledge_base)
        
        # Unequip any materials that are currently equipped
        unequip_results = self._unequip_required_materials(
            client, target_item, craft_data, knowledge_base, context.get(StateParameters.CHARACTER_NAME), context
        )
        
        # Update context for crafting
        context.set_result(StateParameters.ITEM_CODE, target_item)
        context.set_result(StateParameters.QUANTITY, 1)
        
        # Craft the item
        craft_action = CraftItemAction()
        craft_result = craft_action.execute(client, context)
        
        if not craft_result or not craft_result.success:
            error_msg = craft_result.error if craft_result else 'No response'
            return self.create_error_result(f"Failed to craft {target_item}: {error_msg}")
        
        return self.create_success_result(
            message=f"Successfully crafted {target_item}",
            target_item=target_item,
            craft_result=craft_result.data if craft_result else {},
            unequipped_items=unequip_results,
            workshop_type=workshop_type
        )
    
    def _determine_target_item(self, action_context: ActionContext) -> Optional[str]:
        """Determine target item from context or parameters"""
        return action_context.get(StateParameters.TARGET_ITEM)
    
    def _is_at_correct_workshop(self, client, character_name: str, workshop_type: str) -> bool:
        """Check if character is at the correct workshop type."""
        try:
            char_response = get_character_api(name=character_name, client=client)
            if not char_response or not char_response.data:
                return False
            
            char_data = char_response.data
            current_x = char_data.x
            current_y = char_data.y
            
            # Check if we're at a workshop
            map_response = get_map_api(x=current_x, y=current_y, client=client)
            if map_response and map_response.data:
                map_data = map_response.data
                if hasattr(map_data, 'content') and map_data.content:
                    if hasattr(map_data.content, 'type_') and map_data.content.type_ == 'workshop':
                        current_workshop = getattr(map_data.content, 'code', '')
                        return current_workshop == workshop_type
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Workshop verification failed: {e}")
            return False
    
    def _unequip_required_materials(self, client, target_item: str, craft_data: Dict,
                                   knowledge_base, character_name: str, context: ActionContext) -> List[Dict]:
        """Unequip any materials that are needed for crafting"""
        unequip_results = []
        
        # Get required materials
        required_materials = craft_data.get('items', [])
        if not required_materials:
            return unequip_results
        
        # Get character's equipped items
        try:
            char_response = get_character_api(name=character_name, client=client)
            if not char_response or not char_response.data:
                return unequip_results
            
            char_data = char_response.data
            
            # Check each equipment slot
            for attr_name in dir(char_data):
                if attr_name.endswith('_slot') and not attr_name.startswith('_'):
                    equipped_item = getattr(char_data, attr_name, '')
                    if equipped_item:
                        # Check if this item is needed for crafting
                        for material in required_materials:
                            material_code = material.get('code', '')
                            if material_code == equipped_item:
                                # Need to unequip this item
                                self.logger.info(f"Unequipping {equipped_item} from {attr_name} for crafting")
                                
                                unequip_action = UnequipItemAction()
                                
                                unequip_context = ActionContext()
                                unequip_context.set(StateParameters.CHARACTER_NAME, character_name)
                                unequip_context.knowledge_base = context.knowledge_base
                                unequip_context.set_parameter('slot', attr_name.replace('_slot', ''))  # Remove _slot suffix
                                
                                unequip_result = unequip_action.execute(client, unequip_context)
                                unequip_results.append({
                                    'item': equipped_item,
                                    'slot': attr_name,
                                    'success': unequip_result.get('success', False) if unequip_result else False
                                })
                                
                                if not unequip_result or not unequip_result.get('success'):
                                    self.logger.warning(f"Failed to unequip {equipped_item} from {attr_name}")
                                
                                break  # Found this material, move to next slot
            
        except Exception as e:
            self.logger.warning(f"Error checking equipped items: {e}")
        
        return unequip_results
    
    def __repr__(self):
        return "ExecuteCraftingPlanAction()"