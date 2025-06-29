""" FindResourcesAction module """

from typing import Dict, List, Optional, Tuple
from .search_base import SearchActionBase


class FindResourcesAction(SearchActionBase):
    """ Action to find the nearest map location with specified resources """

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 5,
                 resource_types: Optional[List[str]] = None, character_level: Optional[int] = None,
                 skill_type: Optional[str] = None, level_range: int = 5):
        """
        Initialize the find resources action.

        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            search_radius: Radius to search for resources
            resource_types: List of resource types/codes to search for. If None, searches for all resources.
            character_level: Character's current skill level for level-appropriate filtering. If None, no level filtering.
            skill_type: Skill type to filter by (mining, woodcutting, fishing)
            level_range: Acceptable level range (+/-) for resource selection (default: 5)
        """
        super().__init__(character_x, character_y, search_radius)
        self.resource_types = resource_types or []
        self.character_level = character_level
        self.skill_type = skill_type
        self.level_range = level_range

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest resource location using unified search algorithm """
        self.log_execution_start(
            character_x=self.character_x,
            character_y=self.character_y, 
            search_radius=self.search_radius,
            resource_types=self.resource_types
        )
        
        try:
            # Extract recipe-focused resource types from context if available
            context_resource_types = kwargs.get('resource_types', [])
            materials_needed = kwargs.get('materials_needed', [])
            
            # Determine target resource codes with focus on recipe requirements
            target_codes = self._determine_target_resource_codes(context_resource_types, materials_needed)
            
            if not target_codes:
                return self.get_error_response("No target resource types specified for focused search")
            
            # Create resource filter using the unified search base
            resource_filter = self.create_resource_filter(
                resource_types=target_codes,
                skill_type=self.skill_type,
                character_level=self.character_level
            )
            
            # Define result processor for resource-specific response format
            def resource_result_processor(location, content_code, content_data):
                x, y = location
                distance = self._calculate_distance(x, y)
                return self.get_success_response(
                    location=location,
                    distance=distance,
                    resource_code=content_code,
                    resource_name=content_code,
                    resource_skill=content_data.get('skill', 'unknown'),
                    resource_level=content_data.get('level', 1),
                    target_codes=target_codes
                )
            
            # Get map_state from context if available for cached access
            map_state = kwargs.get('map_state')
            
            # PRIORITY 1: Search learned map data first (most accurate)
            for resource_code in target_codes:
                map_location = self._search_map_state_for_resource(map_state, resource_code)
                if map_location:
                    x, y = map_location
                    distance = self._calculate_distance(x, y)
                    self.logger.info(f"🗺️ Found {resource_code} in learned map data at ({x}, {y})")
                    
                    return self.get_success_response(
                        location=(x, y),
                        distance=distance,
                        resource_code=resource_code,
                        resource_name=resource_code,  # Use code as name fallback
                        resource_skill='unknown',
                        resource_level=1,
                        target_codes=target_codes,
                        source='learned_map_data'
                    )
            
            # PRIORITY 2: Try knowledge-based search with known locations (no predictions)
            controller = kwargs.get('controller')
            knowledge_result = None
            if controller and hasattr(controller, 'knowledge_base'):
                knowledge_result = self._search_known_resource_locations_only_real(controller.knowledge_base, target_codes)
            
            # If we found resources in knowledge base, use that location
            if knowledge_result and knowledge_result.get('success'):
                self.logger.info(f"🎯 Found {knowledge_result['resource_code']} at known location {knowledge_result['location']} from knowledge base")
                return knowledge_result
            
            # If no known locations and we have a controller, try learning game data first
            if controller and hasattr(controller, 'learn_all_game_data_efficiently'):
                current_resource_count = len(controller.knowledge_base.get_all_known_resource_codes())
                if current_resource_count < 20:  # Threshold for triggering bulk learning
                    self.logger.info(f"🧠 Limited resource knowledge ({current_resource_count} resources), performing bulk learning...")
                    learning_result = controller.learn_all_game_data_efficiently()
                    if learning_result.get('success'):
                        # Try knowledge search again after learning
                        knowledge_result = self._search_known_resource_locations(controller.knowledge_base, target_codes)
                        if knowledge_result and knowledge_result.get('success'):
                            self.logger.info(f"🎯 Found {knowledge_result['resource_code']} after bulk learning at {knowledge_result['location']}")
                            return knowledge_result
            
            # PRIORITY 3: Try knowledge-based predictions as fallback
            if controller and hasattr(controller, 'knowledge_base'):
                prediction_result = self._search_known_resource_locations(controller.knowledge_base, target_codes)
                if prediction_result and prediction_result.get('success'):
                    self.logger.info(f"🔮 Using prediction for {prediction_result['resource_code']} at {prediction_result['location']} from knowledge base")
                    return prediction_result
            
            # Fallback to map scanning if no known locations found
            self.logger.info(f"🔍 No known locations for {target_codes}, scanning map...")
            
            # Use unified search algorithm with map cache
            result = self.unified_search(client, resource_filter, resource_result_processor, map_state)
            
            # If no resources found within current radius, try a modest expansion
            if result and not result.get('success') and self.search_radius < 8:
                # Expand gradually: 5 -> 8 (only 3 more radius, much more reasonable)
                expanded_radius = min(8, self.search_radius + 3)
                self.logger.info(f"🔍 No resources found within radius {self.search_radius}, expanding search to radius {expanded_radius}")
                # Create a new action with modestly expanded radius
                expanded_action = FindResourcesAction(
                    character_x=self.character_x,
                    character_y=self.character_y, 
                    search_radius=expanded_radius,
                    resource_types=target_codes,
                    character_level=self.character_level,
                    skill_type=self.skill_type
                )
                # Try the expanded search
                expanded_result = expanded_action.unified_search(client, resource_filter, resource_result_processor, map_state)
                if expanded_result and expanded_result.get('success'):
                    self.logger.info(f"✅ Found resources with expanded search radius {expanded_radius}")
                    result = expanded_result
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Resource search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response
    
    def _determine_target_resource_codes(self, context_resource_types: List[str], 
                                        materials_needed: List[Dict]) -> List[str]:
        """
        Determine target resource codes with recipe focus and fallback logic.
        
        Args:
            context_resource_types: Resource types from action context
            materials_needed: Materials needed from recipe information
            
        Returns:
            List of target resource codes to search for
        """
        # Priority 1: Use context resource types (passed from recipe workflow)
        if context_resource_types:
            self.logger.info(f"🎯 Focused resource search for recipe materials: {context_resource_types}")
            return context_resource_types
        
        # Priority 2: Extract from materials_needed (recipe information)
        if materials_needed:
            target_codes = []
            for material in materials_needed:
                if isinstance(material, dict) and material.get('is_resource'):
                    # First try to use the resource_source if available (set by lookup_item_info)
                    if material.get('resource_source'):
                        resource_code = material.get('resource_source')
                        target_codes.append(resource_code)
                        self.logger.info(f"🎯 Using resource source mapping: {material.get('code')} -> {resource_code}")
                    else:
                        # Fallback to manual mapping
                        material_code = material.get('code')
                        if material_code:
                            # Map item codes to resource types (copper -> copper_rocks, ash_wood -> ash_tree)
                            resource_mapping = {
                                'copper': 'copper_rocks',
                                'iron_ore': 'iron_rocks', 
                                'coal': 'coal_rocks',
                                'gold_ore': 'gold_rocks',
                                'ash_wood': 'ash_tree',
                                'spruce_wood': 'spruce_tree',
                                'birch_wood': 'birch_tree'
                            }
                            resource_code = resource_mapping.get(material_code, material_code)
                            target_codes.append(resource_code)
                            self.logger.info(f"🎯 Using fallback mapping: {material_code} -> {resource_code}")
                        
            if target_codes:
                self.logger.info(f"🎯 Recipe-focused resource search for materials: {target_codes}")
                return target_codes
            else:
                # Fall back to material codes directly if mapping failed
                target_codes = [m.get('code') for m in materials_needed if isinstance(m, dict) and m.get('code')]
                if target_codes:
                    self.logger.info(f"🎯 Direct material search: {target_codes}")
                    return target_codes
        
        # Priority 3: Use configured resource types
        if self.resource_types:
            return self.resource_types
        
        # Priority 4: Default resource types for generic search
        default_codes = [
            'copper_rocks', 'iron_rocks', 'coal_rocks', 'gold_rocks',  # Mining
            'ash_tree', 'spruce_tree', 'birch_tree',   # Woodcutting  
            'gudgeon_fishing_spot', 'shrimp_fishing_spot'  # Fishing
        ]
        self.logger.info(f"🔍 Generic resource search: {default_codes}")
        return default_codes

    def _search_known_resource_locations_only_real(self, knowledge_base, target_codes: List[str]) -> Optional[Dict]:
        """
        Search for resources in known real locations from the knowledge base (no predictions).
        
        This only returns actual known locations, not API-based predictions.
        
        Args:
            knowledge_base: KnowledgeBase instance with resource data
            target_codes: List of resource codes to search for
            
        Returns:
            Resource location result if found, None otherwise
        """
        try:
            # Check each target resource code
            for resource_code in target_codes:
                # Look up resource in knowledge base
                if resource_code in knowledge_base.data.get('resources', {}):
                    resource_info = knowledge_base.data['resources'][resource_code]
                    
                    # Check if we have REAL location data for this resource (not predictions)
                    best_locations = resource_info.get('best_locations', [])
                    
                    if best_locations:
                        # Use the first (best) known location
                        location = best_locations[0]
                        if isinstance(location, dict):
                            x, y = location.get('x'), location.get('y')
                        elif isinstance(location, (list, tuple)) and len(location) >= 2:
                            x, y = location[0], location[1]
                        else:
                            continue
                            
                        if x is not None and y is not None:
                            distance = self._calculate_distance(x, y)
                            
                            return self.get_success_response(
                                location=(x, y),
                                distance=distance,
                                resource_code=resource_code,
                                resource_name=resource_info.get('name', resource_code),
                                resource_skill=self._get_resource_skill(resource_info),
                                resource_level=self._get_resource_level(resource_info),
                                target_codes=target_codes,
                                source='knowledge_base'
                            )
            
            # No real known locations found for any target resources
            self.logger.debug(f"No real known locations found for resources: {target_codes}")
            return None
            
        except Exception as e:
            self.logger.debug(f"Error searching real known resource locations: {e}")
            return None

    def _search_known_resource_locations(self, knowledge_base, target_codes: List[str]) -> Optional[Dict]:
        """
        Search for resources in known locations from the knowledge base.
        
        This is much more efficient than map scanning since we already know where resources are.
        
        Args:
            knowledge_base: KnowledgeBase instance with resource data
            target_codes: List of resource codes to search for
            
        Returns:
            Resource location result if found, None otherwise
        """
        try:
            # Check each target resource code
            for resource_code in target_codes:
                # Look up resource in knowledge base
                if resource_code in knowledge_base.data.get('resources', {}):
                    resource_info = knowledge_base.data['resources'][resource_code]
                    
                    # Check if we have location data for this resource
                    best_locations = resource_info.get('best_locations', [])
                    
                    if best_locations:
                        # Use the first (best) known location
                        location = best_locations[0]
                        if isinstance(location, dict):
                            x, y = location.get('x'), location.get('y')
                        elif isinstance(location, (list, tuple)) and len(location) >= 2:
                            x, y = location[0], location[1]
                        else:
                            continue
                        
                        if x is not None and y is not None:
                            distance = self._calculate_distance(x, y)
                            self.logger.info(f"📍 Using known location for {resource_code}: ({x}, {y})")
                            
                            return self.get_success_response(
                                location=(x, y),
                                distance=distance,
                                resource_code=resource_code,
                                resource_name=resource_info.get('name', resource_code),
                                resource_skill=self._get_resource_skill(resource_info),
                                resource_level=self._get_resource_level(resource_info),
                                target_codes=target_codes,
                                source='knowledge_base'
                            )
                    
                    # Method 2: Use learned API data to predict locations based on skill and level (fallback)
                    api_data = resource_info.get('api_data', {})
                    if api_data:
                        skill = api_data.get('skill')
                        level = api_data.get('level', 1)
                        
                        # Use API data to find appropriate location
                        predicted_location = self._predict_resource_location_from_api_data(resource_code, skill, level)
                        if predicted_location:
                            x, y = predicted_location
                            distance = self._calculate_distance(x, y)
                            self.logger.info(f"🔮 Using predicted location for {resource_code}: ({x}, {y}) based on API data")
                            
                            return self.get_success_response(
                                location=(x, y),
                                distance=distance,
                                resource_code=resource_code,
                                resource_name=api_data.get('name', resource_code),
                                resource_skill=skill or 'unknown',
                                resource_level=level,
                                target_codes=target_codes,
                                source='knowledge_base_predicted'
                            )
            
            # No known locations found for any target resources
            self.logger.debug(f"No known locations found for resources: {target_codes}")
            return None
            
        except Exception as e:
            self.logger.debug(f"Error searching known resource locations: {e}")
            return None
    
    def _get_resource_skill(self, resource_info: Dict) -> str:
        """Extract skill from resource info, checking both manual and API data."""
        # Check API data first
        api_data = resource_info.get('api_data', {})
        if api_data.get('skill'):
            return api_data['skill']
        
        # Fallback to manual data
        return resource_info.get('skill', 'unknown')
    
    def _get_resource_level(self, resource_info: Dict) -> int:
        """Extract level from resource info, checking both manual and API data."""
        # Check API data first
        api_data = resource_info.get('api_data', {})
        if api_data.get('level'):
            return api_data['level']
        
        # Fallback to manual data
        return resource_info.get('level', 1)
    
    def _search_map_state_for_resource(self, map_state, resource_code: str) -> Optional[Tuple[int, int]]:
        """
        Search the learned map data for a specific resource location.
        
        Args:
            map_state: MapState instance with learned location data
            resource_code: Code of the resource to find
            
        Returns:
            (x, y) coordinates if found, None otherwise
        """
        try:
            # Look through all learned map locations
            if hasattr(map_state, 'data') and map_state.data:
                for location_key, location_data in map_state.data.items():
                    if isinstance(location_data, dict):
                        content = location_data.get('content')
                        if (content and 
                            isinstance(content, dict) and 
                            content.get('type') == 'resource' and 
                            content.get('code') == resource_code):
                            
                            # Found the resource! Extract coordinates
                            x = location_data.get('x')
                            y = location_data.get('y')
                            if x is not None and y is not None:
                                return (x, y)
                                
            return None
            
        except Exception as e:
            self.logger.debug(f"Error searching map state for {resource_code}: {e}")
            return None

    def _predict_resource_location_from_api_data(self, resource_code: str, skill: str, level: int) -> Optional[Tuple[int, int]]:
        """
        Predict resource location based on API data patterns.
        
        This uses heuristics about where different skill/level resources are typically found.
        """
        try:
            # Simple prediction heuristics based on skill type and level
            # These are rough approximations - real locations will be learned through gameplay
            
            if skill == 'mining':
                # Mining resources tend to be in mountainous areas
                if level <= 5:
                    return (5, 5)  # Basic mining area
                elif level <= 15:
                    return (10, 10)  # Intermediate mining
                else:
                    return (15, 15)  # Advanced mining
                    
            elif skill == 'woodcutting':
                # Trees tend to be in forest areas
                if level <= 5:
                    return (-5, 5)  # Basic forest
                elif level <= 15:
                    return (-10, 10)  # Deeper forest
                else:
                    return (-15, 15)  # Ancient forest
                    
            elif skill == 'fishing':
                # Fishing spots tend to be near water
                if level <= 5:
                    return (0, -5)  # Basic fishing spot
                elif level <= 15:
                    return (5, -10)  # Intermediate waters
                else:
                    return (10, -15)  # Deep waters
            
            # Default prediction for unknown skills - try center area
            return (2, 0)
            
        except Exception:
            return None


    def __repr__(self):
        filters = []
        if self.resource_types:
            filters.append(f"types={self.resource_types}")
        if self.skill_type:
            filters.append(f"skill={self.skill_type}")
        if self.character_level is not None:
            filters.append(f"level={self.character_level}")
        
        filter_str = f", {', '.join(filters)}" if filters else ""
        return (f"FindResourcesAction({self.character_x}, {self.character_y}, "
                f"radius={self.search_radius}{filter_str})")