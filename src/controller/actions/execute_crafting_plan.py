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

from .base import ActionBase
from .craft_item import CraftItemAction
from .find_correct_workshop import FindCorrectWorkshopAction
from .move import MoveAction
from .unequip_item import UnequipItemAction


class ExecuteCraftingPlanAction(ActionBase):
    """
    Action to execute a crafting plan for a selected item.
    
    This action:
    1. Checks if we're at the correct workshop
    2. Unequips any materials that are currently equipped
    3. Crafts the item
    """
    
    # GOAP parameters
    conditions = {
        "character_alive": True,
        "character_safe": True,
        "craft_plan_available": True,
        "materials_sufficient": True
    }
    reactions = {
        "has_equipment": True,
        "inventory_updated": True,
        "craft_plan_available": False  # Consumed the plan
    }
    weights = {"has_equipment": 10}
    
    def __init__(self):
        """
        Initialize the execute crafting plan action.
        """
        super().__init__()
        
    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """Execute the crafting plan"""
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get parameters from context
        character_name = context.character_name
        target_item = context.get('target_item')
            
        self.log_execution_start(
            character_name=character_name,
            target_item=target_item
        )
        
        try:
            # Get knowledge base from context
            knowledge_base = context.knowledge_base
            
            if not knowledge_base:
                return self.get_error_response("No knowledge base available")
            
            # Determine target item
            if not target_item:
                target_item = self._determine_target_item(context)
            if not target_item:
                return self.get_error_response("No target item specified for crafting")
            
            # Get item data to find workshop type
            item_data = knowledge_base.get_item_data(target_item, client=client)
            if not item_data:
                return self.get_error_response(f"Could not find item data for {target_item}")
            
            craft_data = item_data.get('craft_data', {})
            if not craft_data:
                return self.get_error_response(f"Item {target_item} is not craftable")
            
            workshop_type = craft_data.get('skill', 'unknown')
            
            # Check if we need to move to workshop
            move_result = self._ensure_at_workshop(client, workshop_type, target_item, character_name, context)
            if not move_result.get('success'):
                return move_result
            
            # Check for equipped materials that need to be unequipped
            unequip_results = self._unequip_required_materials(
                client, target_item, craft_data, knowledge_base, character_name, context
            )
            
            # Create craft context
            craft_context = ActionContext()
            craft_context.update(context)
            craft_context['item_code'] = target_item
            craft_context['quantity'] = 1
            
            # Craft the item
            craft_action = CraftItemAction()
            craft_result = craft_action.execute(client, craft_context)
            
            if not craft_result or not craft_result.get('success'):
                error_msg = craft_result.get('error', 'Unknown error') if craft_result else 'No response'
                return self.get_error_response(f"Failed to craft {target_item}: {error_msg}")
            
            result = self.get_success_response(
                target_item=target_item,
                craft_result=craft_result,
                unequipped_items=unequip_results,
                workshop_type=workshop_type
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Crafting execution failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response
    
    def _determine_target_item(self, action_context: Dict) -> Optional[str]:
        """Determine target item from context or parameters"""
        if 'selected_weapon' in action_context:
            return action_context['selected_weapon']
        if 'item_code' in action_context:
            return action_context['item_code']
        if 'target_item' in action_context:
            return action_context['target_item']
        return None
    
    def _ensure_at_workshop(self, client, workshop_type: str, item_code: str, character_name: str, context: ActionContext) -> Dict:
        """Ensure we're at the correct workshop"""
        # Get current location
        try:
            char_response = get_character_api(name=character_name, client=client)
            if not char_response or not char_response.data:
                return self.get_error_response("Could not get character location")
            
            char_data = char_response.data
            current_x = char_data.x
            current_y = char_data.y
            
            # Check if we're already at a workshop
            map_response = get_map_api(x=current_x, y=current_y, client=client)
            if map_response and map_response.data:
                map_data = map_response.data
                if hasattr(map_data, 'content') and map_data.content:
                    if hasattr(map_data.content, 'type_') and map_data.content.type_ == 'workshop':
                        current_workshop = getattr(map_data.content, 'code', '')
                        if current_workshop == workshop_type:
                            # Already at correct workshop
                            return self.get_success_response(at_workshop=True)
            
            # Need to find and move to workshop
            find_action = FindCorrectWorkshopAction()
            
            find_context = ActionContext(
                character_name=character_name,
                workshop_type=workshop_type,
                item_code=item_code,
                knowledge_base=context.knowledge_base,
                map_state=context.map_state
            )
            
            find_result = find_action.execute(client, find_context)
            if not find_result or not find_result.get('success'):
                return self.get_error_response(f"Could not find {workshop_type} workshop")
            
            # Move to workshop
            target_x = find_result.get('workshop_x')
            target_y = find_result.get('workshop_y')
            
            if target_x is not None and target_y is not None:
                move_action = MoveAction()
                
                move_context = ActionContext(
                    character_name=character_name,
                    action_data={'x': target_x, 'y': target_y},
                    knowledge_base=context.knowledge_base,
                    map_state=context.map_state
                )
                
                move_result = move_action.execute(client, move_context)
                if not move_result or not move_result.get('success'):
                    return self.get_error_response(f"Could not move to workshop at ({target_x}, {target_y})")
            
            return self.get_success_response(at_workshop=True, moved_to_workshop=True)
            
        except Exception as e:
            return self.get_error_response(f"Workshop check failed: {str(e)}")
    
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
                                
                                unequip_context = ActionContext(
                                    character_name=character_name,
                                    slot=attr_name.replace('_slot', ''),  # Remove _slot suffix
                                    knowledge_base=context.knowledge_base
                                )
                                
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