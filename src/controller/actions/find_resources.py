""" FindResourcesAction module """

from typing import Dict, List, Optional, Tuple

from src.lib.action_context import ActionContext

from .coordinate_mixin import CoordinateStandardizationMixin
from .search_base import SearchActionBase


class FindResourcesAction(SearchActionBase, CoordinateStandardizationMixin):
    """ Action to find the nearest map location with specified resources """

    def __init__(self):
        """
        Initialize the find resources action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Find the nearest resource location using unified search algorithm """
        # Get parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        search_radius = context.get('search_radius', 5)
        resource_types = context.get('resource_types', [])
        character_level = context.get('character_level', context.character_level)
        skill_type = context.get('skill_type')
        level_range = context.get('level_range', 5)
        
        # Parameters will be passed directly to helper methods via context
        
        self.log_execution_start(
            character_x=character_x,
            character_y=character_y, 
            search_radius=search_radius,
            resource_types=resource_types
        )
        
        try:
            # Extract recipe-focused resource types from context if available
            context_resource_types = context.get('resource_types', [])
            materials_needed = context.get('materials_needed', [])
            
            # Convert context to kwargs dict for helper methods
            kwargs = dict(context) if hasattr(context, '__iter__') else {}
            # Remove keys that are passed as positional arguments to avoid conflicts
            kwargs.pop('resource_types', None)
            kwargs.pop('skill_type', None)
            
            # Determine target resource codes with focus on recipe requirements
            target_codes = self._determine_target_resource_codes(context_resource_types, materials_needed, resource_types, skill_type, **kwargs)
            
            if not target_codes:
                return self.get_error_response("No target resource types specified for focused search")
            
            # Create resource filter using the unified search base
            resource_filter = self.create_resource_filter(
                resource_types=target_codes,
                skill_type=skill_type,
                character_level=character_level
            )
            
            # Define result processor for resource-specific response format
            def resource_result_processor(location, content_code, content_data):
                x, y = location
                distance = self._calculate_distance(character_x, character_y, x, y)
                
                # Create standardized coordinate response
                coordinate_data = self.create_coordinate_response(
                    x, y,
                    distance=distance,
                    resource_code=content_code,
                    resource_name=content_code,
                    resource_skill=content_data.get('skill', 'unknown'),
                    resource_level=content_data.get('level', 1),
                    target_codes=target_codes
                )
                
                return self.get_success_response(**coordinate_data)
            
            # Get map_state from context if available for cached access
            map_state = context.map_state
            
            # PRIORITY 1: Search learned map data first (most accurate)
            for resource_code in target_codes:
                map_location = self._search_map_state_for_resource(map_state, resource_code)
                if map_location:
                    x, y = map_location
                    distance = self._calculate_distance(character_x, character_y, x, y)
                    self.logger.info(f"🗺️ Found {resource_code} in learned map data at ({x}, {y})")
                    
                    # Create standardized coordinate response
                    coordinate_data = self.create_coordinate_response(
                        x, y,
                        distance=distance,
                        resource_code=resource_code,
                        resource_name=resource_code,  # Use code as name fallback
                        resource_skill='unknown',
                        resource_level=1,
                        target_codes=target_codes,
                        source='learned_map_data'
                    )
                    
                    return self.get_success_response(**coordinate_data)
            
            # PRIORITY 2: Try knowledge-based search with known locations (no predictions)
            controller = context.controller
            knowledge_base = context.knowledge_base
            knowledge_result = None
            if knowledge_base:
                knowledge_result = self._search_known_resource_locations_only_real(knowledge_base, target_codes)
            
            # If we found resources in knowledge base, use that location
            if knowledge_result and knowledge_result.get('success'):
                self.logger.info(f"🎯 Found {knowledge_result['resource_code']} at known location {knowledge_result['location']} from knowledge base")
                return knowledge_result
            
            # If no known locations and we have a controller, try learning game data first
            if controller and hasattr(controller, 'learn_all_game_data_efficiently'):
                action_config = kwargs.get('action_config', {})
                min_resource_knowledge = action_config.get('min_resource_knowledge_threshold', 20)
                
                current_resource_count = len(knowledge_base.get_all_known_resource_codes())
                if current_resource_count < min_resource_knowledge:
                    self.logger.info(f"🧠 Limited resource knowledge ({current_resource_count} resources), performing bulk learning...")
                    learning_result = controller.learn_all_game_data_efficiently()
                    if learning_result.get('success'):
                        # Try knowledge search again after learning
                        knowledge_result = self._search_known_resource_locations(knowledge_base, target_codes)
                        if knowledge_result and knowledge_result.get('success'):
                            self.logger.info(f"🎯 Found {knowledge_result['resource_code']} after bulk learning at {knowledge_result['location']}")
                            return knowledge_result
            
            # PRIORITY 3: Try knowledge-based predictions as fallback
            if knowledge_base:
                prediction_result = self._search_known_resource_locations(knowledge_base, target_codes)
                if prediction_result and prediction_result.get('success'):
                    self.logger.info(f"🔮 Using prediction for {prediction_result['resource_code']} at {prediction_result['location']} from knowledge base")
                    return prediction_result
            
            # Fallback to map scanning if no known locations found
            self.logger.info(f"🔍 No known locations for {target_codes}, scanning map...")
            
            # Use unified search algorithm with map cache
            result = self.unified_search(client, character_x, character_y, search_radius, resource_filter, resource_result_processor, map_state)
            
            # If no resources found within current radius, try expansion based on configuration
            action_config = kwargs.get('action_config', {})
            max_search_radius = action_config.get('max_resource_search_radius', 8)
            radius_expansion = action_config.get('resource_search_radius_expansion', 3)
            
            if result and not result.get('success') and search_radius < max_search_radius:
                expanded_radius = min(max_search_radius, search_radius + radius_expansion)
                self.logger.info(f"🔍 No resources found within radius {search_radius}, expanding search to radius {expanded_radius}")
                # Create a new action with modestly expanded radius
                expanded_action = FindResourcesAction()
                # Set instance variables for the expanded search
                expanded_action.character_x = self.character_x
                expanded_action.character_y = self.character_y
                expanded_action.search_radius = expanded_radius
                expanded_action.resource_types = target_codes
                expanded_action.character_level = character_level
                expanded_action.skill_type = skill_type
                # Try the expanded search
                expanded_result = expanded_action.unified_search(client, character_x, character_y, expanded_radius, resource_filter, resource_result_processor, map_state)
                if expanded_result and expanded_result.get('success'):
                    self.logger.info(f"✅ Found resources with expanded search radius {expanded_radius}")
                    result = expanded_result
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f"Resource search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response
    
    def _determine_target_resource_codes(self, context_resource_types: List[str], materials_needed: List[Dict], resource_types: List[str], skill_type: str, **kwargs) -> List[str]:
        """Determine target resource codes with focus on recipe requirements."""
        # Priority 1: Use provided context resource types
        if context_resource_types:
            self.logger.info(f"🎯 Context resource search: {context_resource_types}")
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
                        # Try to find resource mapping from knowledge base
                        material_code = material.get('code')
                        if material_code:
                            resource_code = self._get_resource_for_material(material_code, **kwargs)
                            if resource_code:
                                target_codes.append(resource_code)
                                self.logger.info(f"🎯 Using knowledge base mapping: {material_code} -> {resource_code}")
                            else:
                                # If no mapping found, use the material code directly
                                target_codes.append(material_code)
                                self.logger.warning(f"⚠️ No resource mapping found for {material_code}, using directly")
                        
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
        if resource_types:
            return resource_types
        
        # Priority 4: Get all known resource types from knowledge base
        knowledge_base = kwargs.get('knowledge_base')
        if knowledge_base and hasattr(knowledge_base, 'data'):
            known_resources = list(knowledge_base.data.get('resources', {}).keys())
            if known_resources:
                # Filter by skill type if specified
                if skill_type:
                    filtered_resources = []
                    for resource_code in known_resources:
                        resource_info = knowledge_base.data['resources'][resource_code]
                        resource_skill = self._get_resource_skill(resource_info)
                        if resource_skill == skill_type:
                            filtered_resources.append(resource_code)
                    if filtered_resources:
                        self.logger.info(f"🔍 Generic {skill_type} resource search: {filtered_resources[:10]}")  # Limit log output
                        return filtered_resources
                else:
                    self.logger.info(f"🔍 Generic resource search from {len(known_resources)} known resources")
                    return known_resources[:20]  # Limit to prevent too broad search
        
        # Last resort: Return empty list to indicate no search targets
        self.logger.warning("⚠️ No resource types available for search")
        return []

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
                            distance = self._calculate_distance(character_x, character_y, x, y)
                            
                            # Create standardized coordinate response
                            coordinate_data = self.create_coordinate_response(
                                x, y,
                                distance=distance,
                                resource_code=resource_code,
                                resource_name=resource_info.get('name', resource_code),
                                resource_skill=self._get_resource_skill(resource_info),
                                resource_level=self._get_resource_level(resource_info),
                                target_codes=target_codes,
                                source='knowledge_base'
                            )
                            
                            return self.get_success_response(**coordinate_data)
            
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
                            distance = self._calculate_distance(character_x, character_y, x, y)
                            self.logger.info(f"📍 Using known location for {resource_code}: ({x}, {y})")
                            
                            # Create standardized coordinate response
                            coordinate_data = self.create_coordinate_response(
                                x, y,
                                distance=distance,
                                resource_code=resource_code,
                                resource_name=resource_info.get('name', resource_code),
                                resource_skill=self._get_resource_skill(resource_info),
                                resource_level=self._get_resource_level(resource_info),
                                target_codes=target_codes,
                                source='knowledge_base'
                            )
                            
                            return self.get_success_response(**coordinate_data)
                    
                    # Method 2: Use learned API data to predict locations based on skill and level (fallback)
                    api_data = resource_info.get('api_data', {})
                    if api_data:
                        skill = api_data.get('skill')
                        level = api_data.get('level', 1)
                        
                        # Use API data to find appropriate location
                        predicted_location = self._predict_resource_location_from_api_data(resource_code, skill, level)
                        if predicted_location:
                            x, y = predicted_location
                            distance = self._calculate_distance(character_x, character_y, x, y)
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
        Predict resource location based on learned patterns from knowledge base.
        """
        try:
            # Get knowledge_base from instance if set during execute
            knowledge_base = getattr(self, '_knowledge_base', None)
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return None
            
            # Look for similar resources in knowledge base to predict location
            resources = knowledge_base.data.get('resources', {})
            similar_locations = []
            
            for known_code, known_info in resources.items():
                # Skip the resource we're looking for
                if known_code == resource_code:
                    continue
                    
                # Check if this is a similar resource (same skill and close level)
                known_skill = self._get_resource_skill(known_info)
                known_level = self._get_resource_level(known_info)
                
                if known_skill == skill and abs(known_level - level) <= 2:
                    # Check if we have real location data
                    best_locations = known_info.get('best_locations', [])
                    if best_locations:
                        location = best_locations[0]
                        if isinstance(location, dict):
                            x, y = location.get('x'), location.get('y')
                        elif isinstance(location, (list, tuple)) and len(location) >= 2:
                            x, y = location[0], location[1]
                        else:
                            continue
                        
                        if x is not None and y is not None:
                            similar_locations.append((x, y, known_level))
            
            if similar_locations:
                # Use the location of the closest level match
                similar_locations.sort(key=lambda loc: abs(loc[2] - level))
                best_match = similar_locations[0]
                self.logger.info(f"🔮 Predicting location for {resource_code} based on similar resources")
                return (best_match[0], best_match[1])
            
            # No similar resources found - cannot predict
            self.logger.debug(f"No similar resources found to predict location for {resource_code}")
            return None
            
        except Exception as e:
            self.logger.debug(f"Error predicting resource location: {e}")
            return None


    def _get_resource_for_material(self, material_code: str, **kwargs) -> Optional[str]:
        """
        Get the resource code that produces a given material.
        
        Args:
            material_code: Code of the material item
            **kwargs: Additional context including knowledge_base
            
        Returns:
            Resource code that produces this material, or None if not found
        """
        knowledge_base = kwargs.get('knowledge_base')
        if not knowledge_base or not hasattr(knowledge_base, 'data'):
            return None
            
        # Check items in knowledge base for resource_source mapping
        items = knowledge_base.data.get('items', {})
        item_info = items.get(material_code, {})
        
        # First check if we have a direct resource_source mapping
        if item_info.get('resource_source'):
            return item_info['resource_source']
        
        # Search through resources to find which one drops this material
        resources = knowledge_base.data.get('resources', {})
        for resource_code, resource_info in resources.items():
            # Check drops from API data
            api_data = resource_info.get('api_data', {})
            drops = api_data.get('drops', [])
            
            for drop in drops:
                if isinstance(drop, dict) and drop.get('code') == material_code:
                    self.logger.debug(f"Found resource {resource_code} drops {material_code}")
                    return resource_code
        
        # No mapping found
        return None

    def __repr__(self):
        return "FindResourcesAction()"