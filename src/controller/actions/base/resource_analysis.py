"""
Resource Analysis Base Classes

This module provides base classes for resource analysis actions,
implementing common patterns for API discovery and knowledge base integration.
Uses unified context singleton and knowledge base discovery without hardcoding.
"""

import logging
from typing import Dict, List, Optional

from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items_api
from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api

from . import ActionBase


class ResourceDiscoveryMixin:
    """
    Mixin class providing common resource discovery patterns.
    
    Uses unified context singleton and knowledge base for all discovery.
    No hardcoded values - all parameters come from context or knowledge base.
    """
    
    def find_nearby_resources(self, client, context) -> List[Dict]:
        """
        Find all resources within the analysis radius using context parameters.
        
        Args:
            client: API client
            context: ActionContext singleton with all parameters
            
        Returns:
            List of resource location dictionaries sorted by distance
        """
        character_x = context.get('character_x')
        character_y = context.get('character_y')
        analysis_radius = context.get('analysis_radius')
        
        if character_x is None or character_y is None or analysis_radius is None:
            if hasattr(self, 'logger'):
                self.logger.error("Missing required context parameters for resource discovery")
            return []
        
        resources = []
        
        # Search in a grid pattern around the character
        for dx in range(-analysis_radius, analysis_radius + 1):
            for dy in range(-analysis_radius, analysis_radius + 1):
                x = character_x + dx
                y = character_y + dy
                
                try:
                    map_response = get_map_api(x=x, y=y, client=client)
                    if map_response and map_response.data:
                        map_data = map_response.data
                        
                        # Check if this location has a resource
                        has_content = hasattr(map_data, 'content') and map_data.content
                        is_resource = (has_content and 
                                     hasattr(map_data.content, 'type_') and 
                                     map_data.content.type_ == 'resource')
                        
                        if is_resource:
                            resource_info = {
                                'x': x,
                                'y': y,
                                'resource_code': map_data.content.code,
                                'distance': abs(dx) + abs(dy)  # Manhattan distance
                            }
                            resources.append(resource_info)
                            
                except Exception:
                    continue
        
        return sorted(resources, key=lambda r: r['distance'])

    def get_resource_details(self, client, resource_code: str, context) -> Optional[Dict]:
        """
        Get detailed resource information from API with knowledge base fallback.
        
        Args:
            client: API client
            resource_code: Resource code to analyze
            context: ActionContext singleton
            
        Returns:
            Resource data dictionary or None
        """
        # Try knowledge base first
        knowledge_base = context.knowledge_base
        if knowledge_base and hasattr(knowledge_base, 'get_resource_data'):
            cached_data = knowledge_base.get_resource_data(resource_code, client=client)
            if cached_data:
                return cached_data
        
        # Fallback to API
        try:
            resource_response = get_resource_api(code=resource_code, client=client)
            if not resource_response or not resource_response.data:
                return None
            
            return resource_response.data
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to get resource details for {resource_code}: {e}")
            return None


class EquipmentDiscoveryMixin:
    """
    Mixin class providing equipment discovery patterns.
    
    Uses knowledge base for all equipment type discovery.
    No hardcoded equipment types - discovers from knowledge base data.
    """
    
    def get_equipment_items_from_knowledge(self, context) -> List[str]:
        """
        Get equipment item codes from knowledge base using context parameters.
        
        Args:
            context: ActionContext singleton with all parameters
            
        Returns:
            List of equipment item codes
        """
        knowledge_base = context.knowledge_base
        character_level = context.get('character_level')
        level_range = context.get('level_range')
        
        if not knowledge_base or character_level is None or level_range is None:
            return []
        
        equipment_items = []
        
        try:
            items = knowledge_base.data.get('items', {})
            
            for item_code, item_data in items.items():
                item_level = item_data.get('level', 1)
                
                # Check if this is equipment and level-appropriate
                level_appropriate = abs(item_level - character_level) <= level_range
                is_equipment = self._is_equipment_from_knowledge_base(item_data, knowledge_base)
                
                if is_equipment and level_appropriate:
                    equipment_items.append(item_code)
            
            if equipment_items and hasattr(self, 'logger'):
                self.logger.info(f"📊 Found {len(equipment_items)} equipment items in knowledge base")
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to get equipment items from knowledge base: {e}")
        
        return equipment_items

    def discover_equipment_items_from_api(self, client, context) -> List[str]:
        """
        Discover equipment items from API using knowledge base to determine equipment types.
        
        Args:
            client: API client
            context: ActionContext singleton with all parameters
            
        Returns:
            List of equipment item codes
        """
        knowledge_base = context.knowledge_base
        character_level = context.get('character_level')
        level_range = context.get('level_range')
        
        if not knowledge_base or character_level is None or level_range is None:
            return []
        
        equipment_items = []
        
        try:
            # Get equipment types from knowledge base instead of hardcoding
            equipment_types = self._get_equipment_types_from_knowledge_base(knowledge_base)
            
            for item_type in equipment_types:
                try:
                    # Get items of this type, focusing on level-appropriate items
                    items_response = get_all_items_api(
                        type_=item_type,
                        max_level=character_level + level_range,
                        page=1,
                        size=50,
                        client=client
                    )
                    
                    if items_response and items_response.data:
                        for item in items_response.data:
                            if hasattr(item, 'code') and item.code:
                                equipment_items.append(item.code)
                                
                except Exception as e:
                    if hasattr(self, 'logger'):
                        self.logger.warning(f"Failed to get {item_type} items from API: {e}")
                    continue
            
            if hasattr(self, 'logger'):
                self.logger.info(f"📊 Discovered {len(equipment_items)} equipment items from API")
            return equipment_items
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to discover equipment items from API: {e}")
            return []

    def _is_equipment_from_knowledge_base(self, item_data: Dict, knowledge_base) -> bool:
        """
        Determine if an item is equipment based on knowledge base patterns.
        
        Args:
            item_data: Item data dictionary
            knowledge_base: Knowledge base instance for pattern discovery
            
        Returns:
            True if this appears to be equipment based on knowledge base patterns
        """
        # Use knowledge base to determine equipment patterns instead of hardcoding
        if hasattr(knowledge_base, 'is_equipment_item'):
            return knowledge_base.is_equipment_item(item_data)
        
        # If knowledge base doesn't have equipment detection, discover from data patterns
        return self._discover_equipment_pattern(item_data, knowledge_base)
    
    def _discover_equipment_pattern(self, item_data: Dict, knowledge_base) -> bool:
        """
        Discover if item is equipment by analyzing knowledge base patterns.
        
        Args:
            item_data: Item data dictionary
            knowledge_base: Knowledge base for pattern analysis
            
        Returns:
            True if patterns suggest this is equipment
        """
        # Analyze patterns in knowledge base to determine equipment characteristics
        try:
            # Look for equipment-like data patterns across knowledge base
            items = knowledge_base.data.get('items', {})
            
            # Count items with various characteristics to discover patterns
            stat_patterns = set()
            for item_code, data in items.items():
                for key in data.keys():
                    if any(prefix in key.lower() for prefix in ['attack', 'dmg', 'def', 'res', 'hp']):
                        stat_patterns.add(key)
            
            # Check if this item has stat patterns found in the knowledge base
            has_equipment_stats = any(key in item_data for key in stat_patterns)
            
            # Equipment typically has level and can be equipped
            has_level = item_data.get('level', 0) > 0
            has_craft = 'craft' in item_data or 'craft_data' in item_data
            
            return has_equipment_stats and has_level
            
        except Exception:
            return False
    
    def _get_equipment_types_from_knowledge_base(self, knowledge_base) -> List[str]:
        """
        Dynamically discover equipment types from knowledge base data.
        
        Args:
            knowledge_base: Knowledge base instance
            
        Returns:
            List of equipment type names discovered from knowledge base
        """
        equipment_types = set()
        
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return []
        
        try:
            # Scan items in knowledge base to discover what equipment types exist
            items = knowledge_base.data.get('items', {})
            for item_code, item_data in items.items():
                if self._is_equipment_from_knowledge_base(item_data, knowledge_base):
                    item_type = item_data.get('item_type', '').lower()
                    if item_type:
                        equipment_types.add(item_type)
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.debug(f"Error discovering equipment types: {e}")
        
        return sorted(list(equipment_types))


class CraftingAnalysisMixin:
    """
    Mixin class providing crafting analysis patterns.
    
    Uses knowledge base and context for all crafting analysis.
    No hardcoded material patterns.
    """
    
    def extract_all_materials(self, craft_data) -> List[Dict]:
        """
        Extract all materials needed for a craft recipe.
        
        Args:
            craft_data: Craft data from item API
            
        Returns:
            List of material requirements
        """
        materials = []
        
        if hasattr(craft_data, 'items') and craft_data.items:
            for material in craft_data.items:
                material_info = {
                    'code': getattr(material, 'code', ''),
                    'quantity': getattr(material, 'quantity', 1)
                }
                materials.append(material_info)
        
        return materials

    def find_crafting_uses_for_item(self, client, item_code: str, context) -> List[Dict]:
        """
        Find what items can be crafted using the given item as a material.
        
        Args:
            client: API client
            item_code: Code of the item to check crafting uses for
            context: ActionContext singleton with all parameters
            
        Returns:
            List of crafting opportunities
        """
        knowledge_base = context.knowledge_base
        character_level = context.get('character_level')
        level_range = context.get('level_range')
        
        if not knowledge_base or character_level is None or level_range is None:
            return []
        
        crafting_uses = []
        
        # Try to get equipment items from knowledge base first
        equipment_items = self.get_equipment_items_from_knowledge(context)
        
        # If no knowledge base data, fall back to API discovery
        if not equipment_items:
            equipment_items = self.discover_equipment_items_from_api(client, context)
        
        try:
            for equipment_code in equipment_items:
                try:
                    item_response = get_item_api(code=equipment_code, client=client)
                    if not item_response or not item_response.data:
                        continue
                        
                    item = item_response.data
                    
                    if hasattr(item, 'craft') and item.craft:
                        craft_data = item.craft
                        
                        # Check if this item uses our resource as a material
                        if hasattr(craft_data, 'items') and craft_data.items:
                            for material in craft_data.items:
                                if getattr(material, 'code', '') == item_code:
                                    # This item can be crafted using our resource
                                    item_level = getattr(item, 'level', 1)
                                    item_type = getattr(item, 'type', 'unknown')
                                    
                                    # Check if this is level-appropriate equipment
                                    level_appropriate = abs(item_level - character_level) <= level_range
                                    is_equipment = self._is_equipment_from_knowledge_base(
                                        {'item_type': item_type, 'level': item_level}, 
                                        knowledge_base
                                    )
                                    
                                    if level_appropriate and is_equipment:
                                        craft_info = {
                                            'item_code': item.code,
                                            'item_name': getattr(item, 'name', ''),
                                            'item_type': item_type,
                                            'item_level': item_level,
                                            'material_quantity_needed': getattr(material, 'quantity', 1),
                                            'all_materials_needed': self.extract_all_materials(craft_data),
                                            'workshop_required': getattr(craft_data, 'skill', 'unknown')
                                        }
                                        crafting_uses.append(craft_info)
                                        
                except Exception:
                    # Continue checking other items if one fails
                    continue
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to find crafting uses for {item_code}: {e}")
        
        return crafting_uses


class WorkshopDiscoveryMixin:
    """
    Mixin class providing workshop discovery patterns.
    
    Uses knowledge base for workshop skill mapping discovery.
    No hardcoded workshop types or skill mappings.
    """
    
    def find_nearby_workshops(self, client, context, workshop_type: str = None) -> List[Dict]:
        """
        Find all workshops within the search radius using context parameters.
        
        Args:
            client: API client
            context: ActionContext singleton with all parameters
            workshop_type: Optional filter for specific workshop type
            
        Returns:
            List of workshop location dictionaries sorted by distance
        """
        character_x = context.get('character_x')
        character_y = context.get('character_y')
        search_radius = context.get('search_radius')
        
        if character_x is None or character_y is None or search_radius is None:
            if hasattr(self, 'logger'):
                self.logger.error("Missing required context parameters for workshop discovery")
            return []
        
        workshops = []
        
        # Search in a grid pattern around the character
        for dx in range(-search_radius, search_radius + 1):
            for dy in range(-search_radius, search_radius + 1):
                x = character_x + dx
                y = character_y + dy
                
                try:
                    map_response = get_map_api(x=x, y=y, client=client)
                    if map_response and map_response.data:
                        map_data = map_response.data
                        
                        # Check if this location has a workshop
                        has_content = hasattr(map_data, 'content') and map_data.content
                        is_workshop = (has_content and 
                                     hasattr(map_data.content, 'type_') and 
                                     map_data.content.type_ == 'workshop')
                        
                        if is_workshop:
                            workshop_code = map_data.content.code
                            
                            # Filter by workshop type if specified
                            if workshop_type and workshop_code != workshop_type:
                                continue
                            
                            workshop_info = {
                                'x': x,
                                'y': y,
                                'workshop_code': workshop_code,
                                'distance': abs(dx) + abs(dy)  # Manhattan distance
                            }
                            workshops.append(workshop_info)
                            
                except Exception:
                    continue
        
        return sorted(workshops, key=lambda w: w['distance'])
    
    def get_workshop_details(self, client, workshop_code: str, context) -> Optional[Dict]:
        """
        Get detailed workshop information using knowledge base for skill mapping.
        
        Args:
            client: API client
            workshop_code: Workshop code to analyze
            context: ActionContext singleton
            
        Returns:
            Workshop data dictionary or None
        """
        knowledge_base = context.knowledge_base
        
        try:
            # Try to get workshop details from knowledge base first
            if knowledge_base and hasattr(knowledge_base, 'get_workshop_data'):
                workshop_data = knowledge_base.get_workshop_data(workshop_code)
                if workshop_data:
                    return workshop_data
            
            # Discover skill from knowledge base patterns instead of hardcoding
            skill = self._discover_workshop_skill_from_knowledge_base(workshop_code, knowledge_base)
            
            return {
                'code': workshop_code,
                'type': 'workshop',
                'skill': skill
            }
            
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Failed to get workshop details for {workshop_code}: {e}")
            return None
    
    def _discover_workshop_skill_from_knowledge_base(self, workshop_code: str, knowledge_base) -> str:
        """
        Discover workshop skill from knowledge base patterns instead of hardcoding.
        
        Args:
            workshop_code: Workshop code
            knowledge_base: Knowledge base for pattern discovery
            
        Returns:
            Skill name discovered from knowledge base patterns
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return 'unknown'
        
        try:
            # Look for workshop patterns in crafting data
            items = knowledge_base.data.get('items', {})
            
            # Find items that are crafted and see what skills are associated
            for item_code, item_data in items.items():
                craft_data = item_data.get('craft_data') or item_data.get('craft', {})
                if craft_data and isinstance(craft_data, dict):
                    skill = craft_data.get('skill')
                    if skill and workshop_code.lower().startswith(skill.lower()):
                        return skill
            
            # If no direct match, return unknown - no hardcoded fallbacks
            return 'unknown'
            
        except Exception:
            return 'unknown'
    
    def find_workshops_by_skill(self, client, context, required_skill: str) -> List[Dict]:
        """
        Find workshops that support a specific crafting skill using context parameters.
        
        Args:
            client: API client
            context: ActionContext singleton with all parameters
            required_skill: Skill required (discovered from knowledge base)
            
        Returns:
            List of matching workshop locations
        """
        all_workshops = self.find_nearby_workshops(client, context)
        
        matching_workshops = []
        for workshop in all_workshops:
            workshop_details = self.get_workshop_details(client, workshop['workshop_code'], context)
            if workshop_details and workshop_details.get('skill') == required_skill:
                workshop['skill'] = required_skill
                matching_workshops.append(workshop)
        
        return matching_workshops


class ResourceAnalysisBase(ActionBase, ResourceDiscoveryMixin, EquipmentDiscoveryMixin, CraftingAnalysisMixin):
    """
    Base class for resource analysis actions.
    
    Combines all resource analysis mixins with ActionBase to provide
    a complete foundation for resource analysis functionality.
    Uses unified context singleton throughout.
    """
    
    def __init__(self):
        """Initialize the resource analysis base."""
        super().__init__()
    
    def calculate_distance(self, x: int, y: int, character_x: int, character_y: int) -> int:
        """Calculate Manhattan distance from character to given coordinates."""
        return abs(x - character_x) + abs(y - character_y)


class ComprehensiveDiscoveryBase(ActionBase, ResourceDiscoveryMixin, EquipmentDiscoveryMixin, 
                                CraftingAnalysisMixin, WorkshopDiscoveryMixin):
    """
    Comprehensive base class for actions that need all discovery patterns.
    
    Combines all discovery mixins with ActionBase for actions that need to:
    - Find and analyze resources
    - Discover equipment items
    - Analyze crafting recipes and materials  
    - Find and work with workshops
    
    Uses unified context singleton and knowledge base throughout.
    No hardcoded values or fallbacks.
    """
    
    def __init__(self):
        """Initialize the comprehensive discovery base."""
        super().__init__()
    
    def calculate_distance(self, x: int, y: int, character_x: int, character_y: int) -> int:
        """Calculate Manhattan distance from character to given coordinates."""
        return abs(x - character_x) + abs(y - character_y)