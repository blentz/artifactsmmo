""" AnalyzeResourcesAction module """

from typing import Dict, List, Optional

from artifactsmmo_api_client.api.items.get_item_items_code_get import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api
from artifactsmmo_api_client.api.resources.get_resource_resources_code_get import sync as get_resource_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class AnalyzeResourcesAction(ActionBase):
    """ Action to analyze nearby resources for equipment crafting opportunities """

    # GOAP parameters
    conditions = {"character_alive": True}
    reactions = {
        "resource_analysis_complete": True,
        "nearby_resources_known": True,
        "crafting_opportunities_identified": True,
        "resource_locations_known": True
    }
    weights = {"resource_analysis_complete": 6}

    def __init__(self):
        """
        Initialize the analyze resources action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Analyze nearby resources for crafting opportunities """
        # Call superclass to set self._context
        super().execute(client, context)
        
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get parameters from context
        character_x = context.get('character_x', 0)
        character_y = context.get('character_y', 0)
        character_level = context.get('character_level', 1)
        analysis_radius = context.get('analysis_radius', 10)
        equipment_types = context.get('equipment_types', ["weapon", "armor", "utility"])
        
        self.log_execution_start(
            character_x=character_x,
            character_y=character_y,
            character_level=character_level,
            analysis_radius=analysis_radius
        )
        
        try:
            # Step 1: Find nearby resources
            nearby_resources = self._find_nearby_resources(client, character_x, character_y, analysis_radius)
            
            if not nearby_resources:
                return self.get_error_response("No resources found in analysis radius")
            
            # Step 2: Analyze each resource for crafting potential
            resource_analysis = {}
            # Get knowledge base and config data from context
            knowledge_base = context.knowledge_base
            config_data = context.get('config_data')
            
            for resource_location in nearby_resources:
                analysis = self._analyze_resource_crafting_potential(
                    client, resource_location, knowledge_base, character_level, equipment_types
                )
                if analysis:
                    resource_analysis[resource_location['resource_code']] = analysis
            
            # Step 3: Find level-appropriate equipment that can be crafted
            equipment_opportunities = self._find_equipment_crafting_opportunities(
                client, resource_analysis, character_level, equipment_types
            )
            
            # Step 4: Prioritize opportunities based on character needs using YAML configuration
            prioritized_opportunities = self._prioritize_crafting_opportunities(equipment_opportunities, config_data)
            
            result = self.get_success_response(
                nearby_resources_count=len(nearby_resources),
                analyzed_resources=list(resource_analysis.keys()),
                equipment_opportunities=equipment_opportunities,
                prioritized_opportunities=prioritized_opportunities,
                recommended_action=self._recommend_next_action(prioritized_opportunities)
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f'Resource analysis failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def _find_nearby_resources(self, client, character_x: int, character_y: int, analysis_radius: int) -> List[Dict]:
        """
        Find all resources within the analysis radius.
        
        Returns:
            List of resource location dictionaries
        """
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

    def _analyze_resource_crafting_potential(self, client, resource_location: Dict, knowledge_base, character_level: int, equipment_types: List[str]) -> Optional[Dict]:
        """
        Analyze a specific resource for its crafting potential.
        
        Args:
            client: API client
            resource_location: Resource location info
            
        Returns:
            Analysis results or None if resource isn't useful
        """
        resource_code = resource_location['resource_code']
        
        try:
            # Get detailed resource information
            resource_response = get_resource_api(code=resource_code, client=client)
            if not resource_response or not resource_response.data:
                return None
            
            resource_data = resource_response.data
            
            analysis = {
                'resource_code': resource_code,
                'resource_name': getattr(resource_data, 'name', ''),
                'skill_required': getattr(resource_data, 'skill', 'unknown'),
                'level_required': getattr(resource_data, 'level', 1),
                'location': (resource_location['x'], resource_location['y']),
                'distance': resource_location['distance'],
                'crafting_uses': []
            }
            
            # Check if character can gather this resource
            analysis['can_gather'] = analysis['level_required'] <= character_level
            
            # Find what this resource can be used to craft
            if hasattr(resource_data, 'drops') and resource_data.drops:
                for drop in resource_data.drops:
                    drop_code = getattr(drop, 'code', '')
                    if drop_code:
                        # Pass knowledge base through to enable API fallback pattern
                        crafting_uses = self._find_crafting_uses_for_item(client, drop_code, knowledge_base, character_level, equipment_types)
                        analysis['crafting_uses'].extend(crafting_uses)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze resource {resource_code}: {str(e)}")
            return None

    def _find_crafting_uses_for_item(self, client, item_code: str, knowledge_base, character_level: int, equipment_types: List[str]) -> List[Dict]:
        """
        Find what items can be crafted using the given item as a material.
        Uses knowledge base first, then API discovery as fallback.
        
        Args:
            client: API client
            item_code: Code of the item to check crafting uses for
            knowledge_base: Knowledge base instance (optional)
            
        Returns:
            List of crafting opportunities
        """
        crafting_uses = []
        
        # Try to get equipment items from knowledge base first
        equipment_items = self._get_equipment_items_from_knowledge(knowledge_base, character_level, equipment_types)
        
        # If no knowledge base data, fall back to API discovery
        if not equipment_items:
            equipment_items = self._discover_equipment_items_from_api(client, character_level, equipment_types)
        
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
                                    level_appropriate = abs(item_level - character_level) <= 3
                                    is_equipment = item_type in equipment_types
                                    
                                    if level_appropriate and is_equipment:
                                        craft_info = {
                                            'item_code': item.code,
                                            'item_name': getattr(item, 'name', ''),
                                            'item_type': item_type,
                                            'item_level': item_level,
                                            'material_quantity_needed': getattr(material, 'quantity', 1),
                                            'all_materials_needed': self._extract_all_materials(craft_data),
                                            'workshop_required': getattr(craft_data, 'skill', 'unknown')
                                        }
                                        crafting_uses.append(craft_info)
                                        
                except Exception:
                    # Continue checking other items if one fails
                    continue
            
        except Exception as e:
            self.logger.warning(f"Failed to find crafting uses for {item_code}: {str(e)}")
        
        return crafting_uses

    def _extract_all_materials(self, craft_data) -> List[Dict]:
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

    def _get_equipment_items_from_knowledge(self, knowledge_base, character_level: int, equipment_types: List[str]) -> List[str]:
        """
        Get equipment item codes from knowledge base if available.
        
        Args:
            knowledge_base: Knowledge base instance
            
        Returns:
            List of equipment item codes
        """
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return []
        
        equipment_items = []
        
        try:
            items = knowledge_base.data.get('items', {})
            
            for item_code, item_data in items.items():
                item_type = item_data.get('item_type', '').lower()
                item_level = item_data.get('level', 1)
                
                # Check if this is equipment and level-appropriate
                equipment_type_names = ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots', 'ring', 'amulet']
                level_appropriate = abs(item_level - character_level) <= 5
                
                if item_type in equipment_type_names and level_appropriate:
                    equipment_items.append(item_code)
            
            if equipment_items:
                self.logger.info(f"📊 Found {len(equipment_items)} equipment items in knowledge base")
            
        except Exception as e:
            self.logger.warning(f"Failed to get equipment items from knowledge base: {str(e)}")
        
        return equipment_items

    def _discover_equipment_items_from_api(self, client, character_level: int, equipment_types: List[str]) -> List[str]:
        """
        Discover equipment items from API by fetching items with equipment types.
        Uses API pagination to get level-appropriate equipment.
        
        Args:
            client: API client
            
        Returns:
            List of equipment item codes
        """
        equipment_items = []
        
        try:
            from artifactsmmo_api_client.api.items.get_all_items_items_get import sync as get_all_items_api
            
            # Get equipment items by type
            equipment_type_names = ['weapon', 'helmet', 'body_armor', 'leg_armor', 'boots', 'ring', 'amulet']
            
            for item_type in equipment_type_names:
                try:
                    # Get items of this type, focusing on level-appropriate items
                    items_response = get_all_items_api(
                        type_=item_type,
                        max_level=character_level + 5,  # Include slightly higher level items
                        page=1,
                        size=50,
                        client=client
                    )
                    
                    if items_response and items_response.data:
                        for item in items_response.data:
                            if hasattr(item, 'code') and item.code:
                                equipment_items.append(item.code)
                                
                except Exception as e:
                    self.logger.warning(f"Failed to get {item_type} items from API: {str(e)}")
                    continue
            
            self.logger.info(f"📊 Discovered {len(equipment_items)} equipment items from API")
            return equipment_items
            
        except Exception as e:
            self.logger.warning(f"Failed to discover equipment items from API: {str(e)}")
            # No fallback - force reliance on API data only
            return []

    def _find_equipment_crafting_opportunities(self, client, resource_analysis: Dict, character_level: int, equipment_types: List[str]) -> List[Dict]:
        """
        Find equipment that can be crafted from analyzed resources.
        
        Args:
            client: API client
            resource_analysis: Analysis results for all resources
            
        Returns:
            List of equipment crafting opportunities
        """
        opportunities = []
        
        for resource_code, analysis in resource_analysis.items():
            if not analysis['can_gather']:
                continue
            
            for craft_use in analysis['crafting_uses']:
                # Calculate feasibility score
                level_diff = abs(craft_use['item_level'] - character_level)
                distance_factor = 1.0 / (1.0 + analysis['distance'])
                level_factor = 1.0 / (1.0 + level_diff)
                
                opportunity = {
                    'item_code': craft_use['item_code'],
                    'item_name': craft_use['item_name'],
                    'item_type': craft_use['item_type'],
                    'item_level': craft_use['item_level'],
                    'resource_location': analysis['location'],
                    'resource_code': resource_code,
                    'resource_name': analysis['resource_name'],
                    'distance_to_resource': analysis['distance'],
                    'materials_needed': craft_use['all_materials_needed'],
                    'workshop_skill': craft_use['workshop_required'],
                    'feasibility_score': distance_factor * level_factor,
                    'level_appropriateness': 'good' if level_diff <= 1 else 'acceptable' if level_diff <= 3 else 'poor'
                }
                opportunities.append(opportunity)
        
        return opportunities

    def _prioritize_crafting_opportunities(self, opportunities: List[Dict], config_data=None) -> List[Dict]:
        """
        Prioritize crafting opportunities based on character needs.
        
        Args:
            opportunities: List of crafting opportunities
            config_data: Configuration data to get priorities from
            
        Returns:
            Sorted list of prioritized opportunities
        """
        # Sort by feasibility score (higher is better) and level appropriateness
        def priority_key(opp):
            # Use YAML-configured priority values rather than hardcoded values
            type_priority = self._get_equipment_type_priority(opp['item_type'], config_data)
            level_priority = self._get_level_appropriateness_priority(opp['level_appropriateness'], config_data)
            return (type_priority, level_priority, opp['feasibility_score'])
        
        return sorted(opportunities, key=priority_key, reverse=True)

    def _get_equipment_type_priority(self, item_type: str, config_data=None) -> int:
        """
        Get priority for equipment type based on YAML configuration.
        
        Args:
            item_type: Type of equipment (weapon, armor, etc.)
            config_data: Configuration data instance to read priorities from
            
        Returns:
            Priority value (higher = more important)
        """
        # Try to get priorities from action configuration
        if config_data and hasattr(config_data, 'data'):
            resource_analysis_config = config_data.data.get('resource_analysis_priorities', {})
            priorities_config = resource_analysis_config.get('equipment_type_priorities', {})
            if priorities_config and item_type in priorities_config:
                return priorities_config[item_type]
        
        # Fallback to minimal default priorities (should not be needed with proper YAML config)
        fallback_priorities = {
            'weapon': 3,      # Weapons generally high priority
            'body_armor': 2,  # Armor for protection
            'helmet': 2,      # Head protection
            'leg_armor': 2,   # Leg protection  
            'boots': 2,       # Foot protection
            'ring': 1,        # Accessories
            'amulet': 1,      # Accessories
            'utility': 1      # Utility items
        }
        
        priority = fallback_priorities.get(item_type, 0)
        if priority == 0:
            self.logger.warning(f"⚠️ No priority found for equipment type: {item_type} - check action_configurations.yaml")
        
        return priority

    def _get_level_appropriateness_priority(self, level_appropriateness: str, config_data=None) -> int:
        """
        Get priority for level appropriateness based on YAML configuration.
        
        Args:
            level_appropriateness: Level appropriateness rating
            config_data: Configuration data instance to read priorities from
            
        Returns:
            Priority value (higher = more appropriate)
        """
        # Try to get priorities from action configuration
        if config_data and hasattr(config_data, 'data'):
            resource_analysis_config = config_data.data.get('resource_analysis_priorities', {})
            priorities_config = resource_analysis_config.get('level_appropriateness_priorities', {})
            if priorities_config and level_appropriateness in priorities_config:
                return priorities_config[level_appropriateness]
        
        # Fallback to minimal default priorities (should not be needed with proper YAML config)
        fallback_priorities = {
            'good': 3,        # Level-appropriate equipment
            'acceptable': 2,   # Slightly off level but usable
            'poor': 1         # Too far from character level
        }
        
        priority = fallback_priorities.get(level_appropriateness, 0)
        if priority == 0:
            self.logger.warning(f"⚠️ No priority found for level appropriateness: {level_appropriateness} - check action_configurations.yaml")
        
        return priority

    def _recommend_next_action(self, prioritized_opportunities: List[Dict]) -> Dict:
        """
        Recommend the next action based on crafting analysis.
        
        Args:
            prioritized_opportunities: Prioritized list of opportunities
            
        Returns:
            Action recommendation
        """
        if not prioritized_opportunities:
            return {
                'action': 'continue_hunting',
                'reason': 'No viable equipment crafting opportunities found',
                'priority': 'low'
            }
        
        best_opportunity = prioritized_opportunities[0]
        
        return {
            'action': 'gather_for_crafting',
            'reason': f'Craft {best_opportunity["item_name"]} (level {best_opportunity["item_level"]}) to improve equipment',
            'priority': 'high',
            'target_item': best_opportunity['item_code'],
            'target_resource': best_opportunity['resource_code'],
            'resource_location': best_opportunity['resource_location'],
            'materials_needed': best_opportunity['materials_needed'],
            'workshop_skill': best_opportunity['workshop_skill']
        }

    def __repr__(self):
        return "AnalyzeResourcesAction()"