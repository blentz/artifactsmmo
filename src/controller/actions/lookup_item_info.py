""" LookupItemInfoAction module """

from typing import Dict, List, Optional
from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
# Note: get_all_items API endpoint not available in current client
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api
# Note: get_all_resources API endpoint not available in current client
from .base import ActionBase


class LookupItemInfoAction(ActionBase):
    """ Action to lookup item information, recipes, and crafting requirements """

    def __init__(self, item_code: Optional[str] = None, search_term: Optional[str] = None, 
                 item_type: Optional[str] = None, max_level: Optional[int] = None,
                 character_level: Optional[int] = None, **kwargs):
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
        self.character_level = character_level
        self.kwargs = kwargs

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
        knowledge_base = self.kwargs.get('knowledge_base')
        action_config = self.kwargs.get('action_config', {})
        
        # Get character level or use default
        char_level = self.character_level or 1
        
        # Get level range from configuration
        level_range = action_config.get('equipment_level_range', 2)
        min_level = max(1, char_level - level_range)
        max_level = char_level + level_range
        
        # Get suitable items from knowledge base
        suitable_items = self._get_suitable_items_from_knowledge_base(
            knowledge_base, min_level, max_level, self.item_type
        )
        
        if not suitable_items:
            # If no items in knowledge base, try API search
            suitable_items = self._search_suitable_items_from_api(
                client, min_level, max_level, self.item_type
            )
        
        # Try to find the first available item that can be crafted
        for item_code in suitable_items:
            try:
                item_info = self._lookup_specific_item(client, item_code)
                if item_info.get('success') and item_info.get('craftable'):
                    # Check if craft level requirement is met
                    craft_level = item_info.get('craft_level', 0)
                    if craft_level > char_level + level_range:
                        continue
                    
                    # Return detailed crafting information
                    materials_info = self.lookup_crafting_materials(client, item_code)
                    
                    # Check for multi-step crafting requirements
                    crafting_chain = self._analyze_crafting_chain(client, item_code, materials_info.get('materials', []))
                    
                    # Combine item info with materials for a complete recipe
                    result = {
                        'success': True,
                        'recipe_found': True,
                        'item_code': item_code,
                        'item_name': item_info.get('name', ''),
                        'item_type': item_info.get('type', ''),
                        'item_level': item_info.get('level', 0),
                        'craft_skill': item_info.get('craft_skill', ''),
                        'craft_level': item_info.get('craft_level', 0),
                        'materials_needed': materials_info.get('materials', []),
                        'crafting_chain': crafting_chain,
                        'suitability_score': self._calculate_suitability_score(item_info, char_level)
                    }
                    
                    self.logger.info(f"📋 Recipe found: {item_code} - {item_info.get('name', '')} (level {item_info.get('level', 0)})")
                    return result
                    
            except Exception as e:
                self.logger.debug(f"Could not lookup {item_code}: {e}")
                continue
        
        # If no craftable items found, return a response with suggestions
        return {
            'success': False,
            'error': f'No suitable equipment recipes found for level {char_level} (range: {min_level}-{max_level})',
            'suggestion': f'Try adjusting level range or gathering more materials',
            'searched_levels': {'min': min_level, 'max': max_level}
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
        
        # Add the final target item with its actual craft skill
        # Get the craft skill from the original item lookup
        target_item_info = self._lookup_specific_item(client, target_item)
        craft_skill = target_item_info.get('craft_skill', 'unknown') if target_item_info.get('success') else 'unknown'
        
        crafting_chain.append({
            'step_type': 'craft_final',
            'item_code': target_item,
            'craft_skill': craft_skill,
            'materials': [m.get('code', '') for m in materials]
        })
        
        return crafting_chain

    def _generate_possible_resource_names(self, material_code: str) -> List[str]:
        """Generate possible resource names that might drop a given material."""
        possible_names = []
        knowledge_base = self.kwargs.get('knowledge_base')
        
        # First check knowledge base for known resources that drop this material
        if knowledge_base and hasattr(knowledge_base, 'data'):
            resources = knowledge_base.data.get('resources', {})
            for resource_code, resource_info in resources.items():
                # Check API data for drops
                api_data = resource_info.get('api_data', {})
                drops = api_data.get('drops', [])
                
                for drop in drops:
                    if isinstance(drop, dict) and drop.get('code') == material_code:
                        possible_names.append(resource_code)
                        self.logger.debug(f"Found {resource_code} drops {material_code} in knowledge base")
        
        # If no knowledge base hits, use pattern-based discovery
        # Extract base material name (remove _ore suffix if present)
        base_name = material_code.replace('_ore', '')
        
        # Common resource type suffixes based on skill types
        mining_suffixes = ['_rocks', '_vein', '_deposit', '_mine']
        woodcutting_suffixes = ['_tree', '_forest', '_grove']
        fishing_suffixes = ['_fishing_spot', '_pond', '_waters']
        
        # Determine likely skill type from material name
        if 'wood' in material_code:
            for suffix in woodcutting_suffixes:
                possible_names.append(f"{base_name}{suffix}")
        elif any(metal in material_code for metal in ['copper', 'iron', 'gold', 'silver']):
            for suffix in mining_suffixes:
                possible_names.append(f"{base_name}{suffix}")
        elif any(fish in material_code for fish in ['gudgeon', 'shrimp', 'trout', 'bass']):
            for suffix in fishing_suffixes:
                possible_names.append(f"{base_name}{suffix}")
        else:
            # Generic patterns for unknown material types
            possible_names.extend([
                f"{material_code}_source",
                f"{material_code}_spot", 
                f"{material_code}_location",
                material_code  # Sometimes the resource has the same name
            ])
        
        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in possible_names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)
        
        return unique_names

    def _get_suitable_items_from_knowledge_base(self, knowledge_base, min_level: int, 
                                                max_level: int, item_type: Optional[str]) -> List[str]:
        """Get suitable items from knowledge base based on level range and type."""
        suitable_items = []
        
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return suitable_items
        
        items = knowledge_base.data.get('items', {})
        for item_code, item_info in items.items():
            # Check item type if specified
            if item_type and item_info.get('type') != item_type:
                continue
            
            # Check level range
            item_level = item_info.get('level', 1)
            if min_level <= item_level <= max_level:
                # Check if item is craftable
                if item_info.get('craft_data'):
                    suitable_items.append(item_code)
        
        # Sort by level for better progression
        suitable_items.sort(key=lambda code: items.get(code, {}).get('level', 1))
        
        self.logger.info(f"Found {len(suitable_items)} suitable items in knowledge base for levels {min_level}-{max_level}")
        return suitable_items
    
    def _search_suitable_items_from_api(self, client, min_level: int, 
                                       max_level: int, item_type: Optional[str]) -> List[str]:
        """Search for suitable items using API based on level range."""
        suitable_items = []
        
        # Since we don't have get_all_items, we need to use knowledge base or config
        action_config = self.kwargs.get('action_config', {})
        
        # Get item codes to check from configuration
        items_to_check = action_config.get('craftable_items', [])
        
        if not items_to_check:
            # If no config, we can't search without knowledge base
            self.logger.warning("No items to check from config or knowledge base")
            return suitable_items
        
        # Check each item
        for item_code in items_to_check:
            try:
                item_info = self._lookup_specific_item(client, item_code)
                if item_info.get('success'):
                    item_level = item_info.get('level', 1)
                    if min_level <= item_level <= max_level:
                        if item_type is None or item_info.get('type') == item_type:
                            if item_info.get('craftable'):
                                suitable_items.append(item_code)
            except Exception as e:
                self.logger.debug(f"Could not check {item_code}: {e}")
        
        self.logger.info(f"Found {len(suitable_items)} suitable items from API for levels {min_level}-{max_level}")
        return suitable_items
    
    def _calculate_suitability_score(self, item_info: Dict, character_level: int) -> float:
        """Calculate how suitable an item is for the character's level."""
        item_level = item_info.get('level', 1)
        craft_level = item_info.get('craft_level', 1)
        
        # Score based on how close the item level is to character level
        level_diff = abs(item_level - character_level)
        level_score = max(0, 10 - level_diff)
        
        # Bonus for items at or slightly above character level
        if item_level == character_level:
            level_score += 5
        elif item_level == character_level + 1:
            level_score += 3
        
        # Penalty if craft level is too high
        craft_diff = max(0, craft_level - character_level)
        craft_penalty = craft_diff * 2
        
        # Final score
        score = max(0, level_score - craft_penalty)
        
        return score

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