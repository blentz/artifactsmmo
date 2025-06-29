""" LookupItemInfoAction module """

from typing import Dict, List, Optional
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
# Note: get_all_items API endpoint not available in current client
from artifactsmmo_api_client.api.resources.get_resource import sync as get_resource_api
# Note: get_all_resources API endpoint not available in current client
from .base import ActionBase


class LookupItemInfoAction(ActionBase):
    """ Action to lookup item information, recipes, and crafting requirements """

    def __init__(self, item_code: Optional[str] = None, search_term: Optional[str] = None, 
                 item_type: Optional[str] = None, max_level: Optional[int] = None):
        """
        Initialize the lookup item info action.

        Args:
            item_code: Specific item code to lookup
            search_term: Search term to find items by name/description
            item_type: Filter by item type (weapon, armor, etc.)
            max_level: Maximum level requirement for items
        """
        super().__init__()
        self.item_code = item_code
        self.search_term = search_term
        self.item_type = item_type
        self.max_level = max_level

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Lookup item information and crafting requirements """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(item_code=self.item_code, search_term=self.search_term)
        
        try:
            if self.item_code:
                # Lookup specific item
                result = self._lookup_specific_item(client, self.item_code)
            else:
                # For equipment goals, determine appropriate items to craft
                result = self._determine_equipment_to_craft(client)
            
            self.log_execution_result(result)
            return result
                
        except Exception as e:
            error_response = self.get_error_response(f'Item lookup failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def _lookup_specific_item(self, client, item_code: str) -> Dict:
        """ Lookup details for a specific item """
        item_response = get_item_api(code=item_code, client=client)
        
        if not item_response or not item_response.data:
            return {
                'success': False,
                'error': f'Item {item_code} not found'
            }
        
        item_data = item_response.data
        result = {
            'success': True,
            'item_code': item_code,
            'name': getattr(item_data, 'name', ''),
            'description': getattr(item_data, 'description', ''),
            'type': getattr(item_data, 'type', ''),
            'subtype': getattr(item_data, 'subtype', ''),
            'level': getattr(item_data, 'level', 0),
            'tradeable': getattr(item_data, 'tradeable', False)
        }
        
        # Add crafting information if available
        if hasattr(item_data, 'craft') and item_data.craft:
            craft_info = item_data.craft
            result['craftable'] = True
            result['craft_skill'] = getattr(craft_info, 'skill', '')
            result['craft_level'] = getattr(craft_info, 'level', 0)
            result['craft_items'] = []
            
            if hasattr(craft_info, 'items') and craft_info.items:
                for craft_item in craft_info.items:
                    result['craft_items'].append({
                        'code': getattr(craft_item, 'code', ''),
                        'quantity': getattr(craft_item, 'quantity', 0)
                    })
        else:
            result['craftable'] = False
        
        # Add equipment stats if applicable
        if hasattr(item_data, 'effects') and item_data.effects:
            result['effects'] = []
            for effect in item_data.effects:
                result['effects'].append({
                    'name': getattr(effect, 'name', ''),
                    'value': getattr(effect, 'value', 0)
                })
        
        return result

    def _determine_equipment_to_craft(self, client) -> Dict:
        """ Determine appropriate equipment to craft based on character level and needs """
        # For now, focus on basic equipment suitable for level 1-3 characters
        # This should be enhanced to use character state information
        
        # Common beginner equipment to try
        beginner_items = [
            # Weapons
            'copper_dagger',    # Level 1 weapon
            'iron_sword',       # Level 5 weapon
            # Armor
            'copper_armor',     # Level 1 armor
            'iron_armor',       # Level 5 armor
            # Tools
            'copper_axe',       # For woodcutting
            'copper_pickaxe'    # For mining
        ]
        
        # Try to find the first available item that can be crafted
        for item_code in beginner_items:
            try:
                item_info = self._lookup_specific_item(client, item_code)
                if item_info.get('success') and item_info.get('craftable'):
                    # Return detailed crafting information
                    materials_info = self.lookup_crafting_materials(client, item_code)
                    
                    # Check for multi-step crafting requirements (e.g., copper_dagger needs copper, which needs copper_ore)
                    crafting_chain = self._analyze_crafting_chain(client, item_code, materials_info.get('materials', []))
                    
                    # Combine item info with materials for a complete recipe
                    result = {
                        'success': True,
                        'recipe_found': True,
                        'item_code': item_code,
                        'item_name': item_info.get('name', ''),
                        'item_type': item_info.get('type', ''),
                        'craft_skill': item_info.get('craft_skill', ''),
                        'craft_level': item_info.get('craft_level', 0),
                        'materials_needed': materials_info.get('materials', []),
                        'crafting_chain': crafting_chain
                    }
                    
                    self.logger.info(f"📋 Recipe found: {item_code} - {item_info.get('name', '')}")
                    return result
                    
            except Exception as e:
                self.logger.debug(f"Could not lookup {item_code}: {e}")
                continue
        
        # If no craftable items found, return a default response
        return {
            'success': False,
            'error': 'No suitable equipment recipes found for current character level',
            'suggestion': 'Try hunting for equipment drops or level up first'
        }

    def _search_items(self, client) -> Dict:
        """ Search for items matching the specified criteria """
        # Note: get_all_items API is not available, so we can't search items
        # This method would need the get_all_items endpoint to be implemented
        return {
            'success': False,
            'error': 'Item search not available - get_all_items API endpoint missing',
            'suggestion': 'Use specific item lookup instead'
        }

    def lookup_crafting_materials(self, client, item_code: str) -> Dict:
        """ Get detailed information about materials needed to craft an item """
        item_info = self._lookup_specific_item(client, item_code)
        
        if not item_info['success'] or not item_info.get('craftable'):
            return {
                'success': False,
                'error': f'Item {item_code} is not craftable or not found'
            }
        
        materials_info = []
        
        for craft_item in item_info.get('craft_items', []):
            material_code = craft_item['code']
            quantity_needed = craft_item['quantity']
            
            # Get detailed info about this material
            material_response = get_item_api(code=material_code, client=client)
            if material_response and material_response.data:
                material_data = material_response.data
                material_info = {
                    'code': material_code,
                    'name': getattr(material_data, 'name', ''),
                    'type': getattr(material_data, 'type', ''),
                    'quantity_needed': quantity_needed,
                    'obtainable_from': []
                }
                
                # Find resources that drop this material by trying common naming patterns
                possible_resource_names = self._generate_possible_resource_names(material_code)
                
                material_info['is_resource'] = False
                material_info['resource_sources'] = []
                
                for resource_name in possible_resource_names:
                    try:
                        resource_response = get_resource_api(code=resource_name, client=client)
                        if resource_response and resource_response.data:
                            resource_data = resource_response.data
                            
                            # Debug: Log what the resource actually contains
                            drops = getattr(resource_data, 'drops', [])
                            drop_codes = [getattr(drop, 'code', '') for drop in drops]
                            self.logger.info(f"🔍 Resource {resource_name} drops: {drop_codes}")
                            
                            # Check if this resource drops the material we need
                            # Also check for ore versions (copper -> copper_ore)
                            target_materials = [material_code]
                            if not material_code.endswith('_ore'):
                                target_materials.append(f"{material_code}_ore")
                            
                            for drop in drops:
                                drop_code = getattr(drop, 'code', '')
                                if drop_code in target_materials:
                                    material_info['is_resource'] = True
                                    material_info['resource_sources'].append(resource_name)
                                    material_info['skill_required'] = getattr(resource_data, 'skill', '')
                                    material_info['level_required'] = getattr(resource_data, 'level', 0)
                                    # Store the actual drop (e.g., copper_ore) for gathering
                                    material_info['actual_drop'] = drop_code
                                    self.logger.info(f"✅ Found resource {resource_name} drops {drop_code} (needed: {material_code})")
                                    break
                    except Exception as e:
                        self.logger.debug(f"Resource {resource_name} not found: {e}")
                        continue
                
                # If we found resources, use the first one as primary source
                if material_info['resource_sources']:
                    material_info['resource_source'] = material_info['resource_sources'][0]
                
                materials_info.append(material_info)
        
        return {
            'success': True,
            'item_code': item_code,
            'item_name': item_info.get('name', ''),
            'craft_skill': item_info.get('craft_skill', ''),
            'craft_level': item_info.get('craft_level', 0),
            'materials': materials_info
        }

    def _analyze_crafting_chain(self, client, target_item: str, materials: List[Dict]) -> List[Dict]:
        """
        Analyze if any materials need to be crafted first, creating a crafting chain.
        
        Returns a list of items that need to be crafted in order, starting with base materials.
        """
        crafting_chain = []
        
        for material in materials:
            material_code = material.get('code', '')
            
            # Check if this material itself needs to be crafted
            try:
                material_info = self._lookup_specific_item(client, material_code)
                if material_info.get('success') and material_info.get('craftable'):
                    # This material can be crafted - add it to the chain
                    craft_step = {
                        'step_type': 'craft_intermediate',
                        'item_code': material_code,
                        'item_name': material_info.get('name', ''),
                        'craft_skill': material_info.get('craft_skill', ''),
                        'craft_level': material_info.get('craft_level', 0),
                        'quantity_needed': material.get('quantity_needed', 1),
                        'materials': material_info.get('craft_items', [])
                    }
                    crafting_chain.append(craft_step)
                    self.logger.info(f"🔗 Crafting chain: {material_code} needs to be crafted first")
            except Exception as e:
                self.logger.debug(f"Could not analyze crafting chain for {material_code}: {e}")
        
        # Add the final target item
        crafting_chain.append({
            'step_type': 'craft_final',
            'item_code': target_item,
            'craft_skill': 'weaponcrafting',  # Assuming weapons for now
            'materials': [m.get('code', '') for m in materials]
        })
        
        return crafting_chain

    def _generate_possible_resource_names(self, material_code: str) -> List[str]:
        """Generate possible resource names that might drop a given material."""
        possible_names = []
        
        # Common naming patterns for materials -> resources
        material_patterns = {
            'copper': ['copper_rocks', 'copper_ore', 'copper_mine', 'copper_deposit', 'copper_vein'],
            'iron_ore': ['iron_rocks', 'iron_ore', 'iron_mine', 'iron_deposit', 'iron_vein'],
            'coal': ['coal_rocks', 'coal_ore', 'coal_mine', 'coal_deposit', 'coal_vein'],
            'gold_ore': ['gold_rocks', 'gold_ore', 'gold_mine', 'gold_deposit', 'gold_vein'],
            'ash_wood': ['ash_tree', 'ash_wood', 'ash_forest'],
            'spruce_wood': ['spruce_tree', 'spruce_wood', 'spruce_forest'],
            'birch_wood': ['birch_tree', 'birch_wood', 'birch_forest'],
            'gudgeon': ['gudgeon_fishing_spot', 'gudgeon_pond'],
            'shrimp': ['shrimp_fishing_spot', 'shrimp_pond']
        }
        
        if material_code in material_patterns:
            possible_names.extend(material_patterns[material_code])
        
        # Also try some generic patterns
        possible_names.extend([
            f"{material_code}_source",
            f"{material_code}_spot", 
            f"{material_code}_location",
            material_code  # Sometimes the resource has the same name as the material
        ])
        
        return possible_names

    def __repr__(self):
        if self.item_code:
            return f"LookupItemInfoAction({self.item_code})"
        else:
            filters = []
            if self.search_term:
                filters.append(f"search='{self.search_term}'")
            if self.item_type:
                filters.append(f"type='{self.item_type}'")
            if self.max_level is not None:
                filters.append(f"max_level={self.max_level}")
            return f"LookupItemInfoAction({', '.join(filters)})"