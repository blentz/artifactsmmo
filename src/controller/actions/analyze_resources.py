""" AnalyzeResourcesAction module """

from typing import Dict, List, Optional, Set
from artifactsmmo_api_client.api.resources.get_resource import sync as get_resource_api
from artifactsmmo_api_client.api.items.get_item import sync as get_item_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from .base import ActionBase


class AnalyzeResourcesAction(ActionBase):
    """ Action to analyze nearby resources for equipment crafting opportunities """

    def __init__(self, character_x: int = 0, character_y: int = 0, character_level: int = 1,
                 analysis_radius: int = 10, equipment_types: Optional[List[str]] = None):
        """
        Initialize the analyze resources action.

        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate  
            character_level: Character's current level for level-appropriate equipment
            analysis_radius: Radius to search for resources
            equipment_types: Types of equipment to prioritize (e.g., ["weapon", "armor"])
        """
        super().__init__()
        self.character_x = character_x
        self.character_y = character_y
        self.character_level = character_level
        self.analysis_radius = analysis_radius
        self.equipment_types = equipment_types or ["weapon", "armor", "utility"]

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Analyze nearby resources for crafting opportunities """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_x=self.character_x,
            character_y=self.character_y,
            character_level=self.character_level,
            analysis_radius=self.analysis_radius
        )
        
        try:
            # Step 1: Find nearby resources
            nearby_resources = self._find_nearby_resources(client)
            
            if not nearby_resources:
                return self.get_error_response("No resources found in analysis radius")
            
            # Step 2: Analyze each resource for crafting potential
            resource_analysis = {}
            for resource_location in nearby_resources:
                analysis = self._analyze_resource_crafting_potential(client, resource_location)
                if analysis:
                    resource_analysis[resource_location['resource_code']] = analysis
            
            # Step 3: Find level-appropriate equipment that can be crafted
            equipment_opportunities = self._find_equipment_crafting_opportunities(client, resource_analysis)
            
            # Step 4: Prioritize opportunities based on character needs
            prioritized_opportunities = self._prioritize_crafting_opportunities(equipment_opportunities)
            
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

    def _find_nearby_resources(self, client) -> List[Dict]:
        """
        Find all resources within the analysis radius.
        
        Returns:
            List of resource location dictionaries
        """
        resources = []
        
        # Search in a grid pattern around the character
        for dx in range(-self.analysis_radius, self.analysis_radius + 1):
            for dy in range(-self.analysis_radius, self.analysis_radius + 1):
                x = self.character_x + dx
                y = self.character_y + dy
                
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

    def _analyze_resource_crafting_potential(self, client, resource_location: Dict) -> Optional[Dict]:
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
            analysis['can_gather'] = analysis['level_required'] <= self.character_level
            
            # Find what this resource can be used to craft
            if hasattr(resource_data, 'drops') and resource_data.drops:
                for drop in resource_data.drops:
                    drop_code = getattr(drop, 'code', '')
                    if drop_code:
                        crafting_uses = self._find_crafting_uses_for_item(client, drop_code)
                        analysis['crafting_uses'].extend(crafting_uses)
            
            return analysis
            
        except Exception as e:
            self.logger.warning(f"Failed to analyze resource {resource_code}: {str(e)}")
            return None

    def _find_crafting_uses_for_item(self, client, item_code: str) -> List[Dict]:
        """
        Find what items can be crafted using the given item as a material.
        Since we can't get all items in one call, we'll use known common equipment items.
        
        Args:
            client: API client
            item_code: Code of the item to check crafting uses for
            
        Returns:
            List of crafting opportunities
        """
        crafting_uses = []
        
        # Common equipment items that might use basic resources
        common_equipment = [
            # Weapons
            'wooden_staff', 'copper_dagger', 'iron_sword', 'steel_sword',
            'copper_axe', 'iron_axe', 'steel_axe',
            # Armor
            'leather_helmet', 'copper_helmet', 'iron_helmet', 'steel_helmet',
            'leather_boots', 'copper_boots', 'iron_boots', 'steel_boots',
            'leather_armor', 'copper_armor', 'iron_armor', 'steel_armor',
            # Rings and accessories
            'copper_ring', 'iron_ring', 'steel_ring',
            'copper_amulet', 'iron_amulet', 'steel_amulet'
        ]
        
        try:
            for equipment_code in common_equipment:
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
                                    level_appropriate = abs(item_level - self.character_level) <= 3
                                    is_equipment = item_type in self.equipment_types
                                    
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

    def _find_equipment_crafting_opportunities(self, client, resource_analysis: Dict) -> List[Dict]:
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
                level_diff = abs(craft_use['item_level'] - self.character_level)
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

    def _prioritize_crafting_opportunities(self, opportunities: List[Dict]) -> List[Dict]:
        """
        Prioritize crafting opportunities based on character needs.
        
        Args:
            opportunities: List of crafting opportunities
            
        Returns:
            Sorted list of prioritized opportunities
        """
        # Sort by feasibility score (higher is better) and level appropriateness
        def priority_key(opp):
            type_priority = {'weapon': 3, 'armor': 2, 'utility': 1}.get(opp['item_type'], 0)
            level_priority = {'good': 3, 'acceptable': 2, 'poor': 1}.get(opp['level_appropriateness'], 0)
            return (type_priority, level_priority, opp['feasibility_score'])
        
        return sorted(opportunities, key=priority_key, reverse=True)

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
        return (f"AnalyzeResourcesAction({self.character_x}, {self.character_y}, "
                f"level={self.character_level}, radius={self.analysis_radius})")