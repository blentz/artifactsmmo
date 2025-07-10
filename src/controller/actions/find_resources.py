""" FindResourcesAction module """

from typing import Dict, List, Optional, Tuple

from src.lib.action_context import ActionContext

from .base import ActionResult
from .mixins.coordinate_mixin import CoordinateStandardizationMixin
from .base.search import SearchActionBase


class FindResourcesAction(SearchActionBase, CoordinateStandardizationMixin):
    """ Action to find the nearest map location with specified resources """

    def __init__(self):
        """
        Initialize the find resources action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Find the nearest resource location using unified search algorithm """
        # Get parameters from context - no need for defensive coding with singleton
        character_x = context.character_x
        character_y = context.character_y
        search_radius = context.search_radius
        resource_types = context.resource_types
        character_level = context.character_level
        skill_type = context.skill_type
        level_range = context.level_range
        
        # Parameters will be passed directly to helper methods via context
        
        self._context = context
        
        try:
            # Priority: Check for current_gathering_goal from subgoal context
            if context.current_gathering_goal:
                material = context.current_gathering_goal.get('material')
                if material:
                    # Map material to resource code
                    resource_code = context.knowledge_base.get_resource_for_material(material)
                    if resource_code:
                        self.logger.info(f"🎯 Using current_gathering_goal: Looking for {resource_code} to gather {material}")
                        context.resource_types = [resource_code]
                    else:
                        # Try direct material name as fallback
                        self.logger.info(f"🎯 Using current_gathering_goal: Looking for {material} directly")
                        context.resource_types = [material]
            
            # Check for missing_materials (from calculate_material_quantities action)
            if not context.resource_types and (context.missing_materials or context.raw_material_needs):
                material_dict = context.raw_material_needs if context.raw_material_needs else context.missing_materials
                context.resource_types = list(material_dict.keys())
                self.logger.info(f"🎯 Using materials from context: {context.resource_types}")
            
            # Determine target resource codes with focus on recipe requirements
            target_codes = self._determine_target_resource_codes(context)
            
            if not target_codes:
                return self.create_error_result("No target resource types specified for focused search")
            
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
                
                # Set coordinates directly on ActionContext for unified access
                if hasattr(self, '_context') and self._context:
                    self._context.target_x = x
                    self._context.target_y = y
                    self._context.resource_code = content_code
                    self._context.resource_name = content_code
                
                coordinate_data = {
                    'target_x': x,
                    'target_y': y,
                    'distance': distance,
                    'resource_code': content_code,
                    'resource_name': content_code,
                    'resource_skill': content_data.get('skill', 'unknown'),
                    'resource_level': content_data.get('level', 1),
                    'target_codes': target_codes
                }
                
                
                # Nested state changes for GOAP compatibility
                state_changes = {
                    'location_context': {
                        'target': {'x': x, 'y': y},
                        'resource_known': True,
                        'target_x': x,
                        'target_y': y
                    },
                    'resource_availability': {
                        'resources': True
                    }
                }
                
                return self.create_result_with_state_changes(
                    success=True,
                    state_changes=state_changes,
                    **coordinate_data
                )
            
            # Get map_state from context for cached access
            map_state = context.map_state
            
            # PRIORITY 1: Search learned map data first (most accurate)
            for resource_code in target_codes:
                map_location = self._search_map_state_for_resource(map_state, resource_code)
                if map_location:
                    x, y = map_location
                    distance = self._calculate_distance(character_x, character_y, x, y)
                    self.logger.info(f"🗺️ Found {resource_code} in learned map data at ({x}, {y})")
                    
                    # Set coordinates directly on ActionContext for unified access
                    if hasattr(self, '_context') and self._context:
                        self._context.target_x = x
                        self._context.target_y = y
                        self._context.resource_code = resource_code
                        self._context.resource_name = resource_code
                    
                    coordinate_data = {
                        'target_x': x,
                        'target_y': y,
                        'distance': distance,
                        'resource_code': resource_code,
                        'resource_name': resource_code,  # Use code as name fallback
                        'resource_skill': 'unknown',
                        'resource_level': 1,
                        'target_codes': target_codes,
                        'source': 'learned_map_data'
                    }
                    
                    # Set coordinates using ActionContext methods for subsequent actions
                    if hasattr(self, '_context') and self._context:
                        self._context.set_result('target_x', x)
                        self._context.set_result('target_y', y)
                        self._context.set_result('resource_code', resource_code)
                        self._context.set_result('resource_name', resource_code)
                    
                    # Nested state changes for GOAP compatibility
                    state_changes = {
                        'location_context': {
                            'target': {'x': x, 'y': y},
                            'resource_known': True,
                            'target_x': x,
                            'target_y': y
                        },
                        'resource_availability': {
                            'resources': True
                        }
                    }
                    
                    return self._create_resource_result_with_movement_check(x, y, coordinate_data, state_changes)
            
            # PRIORITY 2: Try knowledge-based search with known locations (no predictions)
            controller = context.controller
            knowledge_base = context.knowledge_base
            knowledge_result = None
            if knowledge_base:
                knowledge_result = self._search_known_resource_locations_only_real(knowledge_base, target_codes)
            
            # If we found resources in knowledge base, use that location
            if knowledge_result and knowledge_result.success:
                self.logger.info(f"🎯 Found {knowledge_result.data['resource_code']} at known location {knowledge_result.data['location']} from knowledge base")
                return knowledge_result
            
            # If no known locations and we have a controller, try learning game data first
            if controller and hasattr(controller, 'learn_all_game_data_efficiently'):
                action_config = context.get('action_config', {})
                min_resource_knowledge = action_config.get('min_resource_knowledge_threshold', 20)
                
                current_resource_count = len(knowledge_base.get_all_known_resource_codes())
                if current_resource_count < min_resource_knowledge:
                    self.logger.info(f"🧠 Limited resource knowledge ({current_resource_count} resources), performing bulk learning...")
                    learning_result = controller.learn_all_game_data_efficiently()
                    if learning_result and hasattr(learning_result, 'success') and learning_result.success:
                        # Try knowledge search again after learning
                        knowledge_result = self._search_known_resource_locations(knowledge_base, target_codes)
                        if knowledge_result and knowledge_result.success:
                            self.logger.info(f"🎯 Found {knowledge_result.data['resource_code']} after bulk learning at {knowledge_result.data['location']}")
                            return knowledge_result
            
            # PRIORITY 3: Try knowledge-based predictions as fallback
            if knowledge_base:
                prediction_result = self._search_known_resource_locations(knowledge_base, target_codes)
                if prediction_result and prediction_result.success:
                    self.logger.info(f"🔮 Using prediction for {prediction_result.data['resource_code']} at {prediction_result.data['location']} from knowledge base")
                    return prediction_result
            
            # Fallback to map scanning if no known locations found
            self.logger.info(f"🔍 No known locations for {target_codes}, scanning map...")
            
            # Use unified search algorithm with map cache
            result = self.unified_search(client, character_x, character_y, search_radius, resource_filter, resource_result_processor, map_state)
            
            # If no resources found within current radius, try expansion based on configuration
            action_config = context.get('action_config', {})
            max_search_radius = action_config.get('max_resource_search_radius', 8)
            radius_expansion = action_config.get('resource_search_radius_expansion', 3)
            
            if result and not result.success and search_radius < max_search_radius:
                expanded_radius = min(max_search_radius, search_radius + radius_expansion)
                self.logger.info(f"🔍 No resources found within radius {search_radius}, expanding search to radius {expanded_radius}")
                # Create a new action with modestly expanded radius
                expanded_action = FindResourcesAction()
                # Pass context to the expanded action
                expanded_action._context = context
                # Try the expanded search
                expanded_result = expanded_action.unified_search(client, character_x, character_y, expanded_radius, resource_filter, resource_result_processor, map_state)
                if expanded_result and expanded_result.success:
                    self.logger.info(f"✅ Found resources with expanded search radius {expanded_radius}")
                    result = expanded_result
            
            return result
            
        except Exception as e:
            return self.create_error_result(f"Resource search failed: {str(e)}")
    
    def _determine_target_resource_codes(self, context: ActionContext) -> List[str]:
        """Determine target resource codes with focus on recipe requirements."""
        # Priority 1: Use provided context resource types
        if context.resource_types:
            self.logger.info(f"🎯 Context resource search: {context.resource_types}")
            return context.resource_types
        
        # Priority 2: Get all known resource types from knowledge base
        if context.knowledge_base and context.knowledge_base.data:
            known_resources = list(context.knowledge_base.data.get('resources', {}).keys())
            if known_resources:
                # Filter by skill type if specified
                if context.skill_type:
                    filtered_resources = []
                    for resource_code in known_resources:
                        resource_info = context.knowledge_base.data['resources'][resource_code]
                        resource_skill = self._get_resource_skill(resource_info)
                        if resource_skill == context.skill_type:
                            filtered_resources.append(resource_code)
                    if filtered_resources:
                        self.logger.info(f"🔍 Generic {context.skill_type} resource search: {filtered_resources[:10]}")  # Limit log output
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
                            # Get character position from context
                            char_x = self._context.character_x if hasattr(self, '_context') else 0
                            char_y = self._context.character_y if hasattr(self, '_context') else 0
                            distance = self._calculate_distance(char_x, char_y, x, y)
                            
                            # Set coordinates directly on ActionContext for unified access
                            if hasattr(self, '_context') and self._context:
                                self._context.target_x = x
                                self._context.target_y = y
                                self._context.resource_code = resource_code
                                self._context.resource_name = resource_info.get('name', resource_code)
                            
                            coordinate_data = {
                                'target_x': x,
                                'target_y': y,
                                'distance': distance,
                                'resource_code': resource_code,
                                'resource_name': resource_info.get('name', resource_code),
                                'resource_skill': self._get_resource_skill(resource_info),
                                'resource_level': self._get_resource_level(resource_info),
                                'target_codes': target_codes,
                                'source': 'knowledge_base'
                            }
                            
                            return self._create_resource_result_with_movement_check(x, y, coordinate_data)
            
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
                            # Get character position from context
                            char_x = self._context.character_x if hasattr(self, '_context') else 0
                            char_y = self._context.character_y if hasattr(self, '_context') else 0
                            distance = self._calculate_distance(char_x, char_y, x, y)
                            self.logger.info(f"📍 Using known location for {resource_code}: ({x}, {y})")
                            
                            # Set coordinates directly on ActionContext for unified access
                            if hasattr(self, '_context') and self._context:
                                self._context.target_x = x
                                self._context.target_y = y
                                self._context.resource_code = resource_code
                                self._context.resource_name = resource_info.get('name', resource_code)
                            
                            coordinate_data = {
                                'target_x': x,
                                'target_y': y,
                                'distance': distance,
                                'resource_code': resource_code,
                                'resource_name': resource_info.get('name', resource_code),
                                'resource_skill': self._get_resource_skill(resource_info),
                                'resource_level': self._get_resource_level(resource_info),
                                'target_codes': target_codes,
                                'source': 'knowledge_base'
                            }
                            
                            return self._create_resource_result_with_movement_check(x, y, coordinate_data)
                    
                    # Method 2: Use learned API data to predict locations based on skill and level (fallback)
                    api_data = resource_info.get('api_data', {})
                    if api_data:
                        skill = api_data.get('skill')
                        level = api_data.get('level', 1)
                        
                        # Use API data to find appropriate location
                        predicted_location = self._predict_resource_location_from_api_data(resource_code, skill, level)
                        if predicted_location:
                            x, y = predicted_location
                            # Get character position from context
                            char_x = self._context.character_x if hasattr(self, '_context') else 0
                            char_y = self._context.character_y if hasattr(self, '_context') else 0
                            distance = self._calculate_distance(char_x, char_y, x, y)
                            self.logger.info(f"🔮 Using predicted location for {resource_code}: ({x}, {y}) based on API data")
                            
                            # Set coordinates directly on ActionContext for unified access
                            if hasattr(self, '_context') and self._context:
                                self._context.target_x = x
                                self._context.target_y = y
                                self._context.resource_code = resource_code
                                self._context.resource_name = api_data.get('name', resource_code)
                            
                            coordinate_data = {
                                'target_x': x,
                                'target_y': y,
                                'distance': distance,
                                'resource_code': resource_code,
                                'resource_name': api_data.get('name', resource_code),
                                'resource_skill': skill or 'unknown',
                                'resource_level': level,
                                'target_codes': target_codes,
                                'source': 'knowledge_base_predicted'
                            }
                            
                            return self._create_resource_result_with_movement_check(x, y, coordinate_data)
            
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



    def _create_resource_result_with_movement_check(self, x: int, y: int, coordinate_data: dict, state_changes: dict = None) -> ActionResult:
        """
        Create a resource result and request move_to_location subgoal if needed.
        
        Args:
            x: Target X coordinate
            y: Target Y coordinate  
            coordinate_data: Data to include in result
            state_changes: Optional state changes for GOAP
            
        Returns:
            ActionResult with optional subgoal request
        """
        if state_changes:
            result = self.create_result_with_state_changes(
                success=True,
                state_changes=state_changes,
                **coordinate_data
            )
        else:
            result = self.create_success_result(**coordinate_data)
            
        # Check if character needs to move to resource location
        char_x = getattr(self._context, 'character_x', 0) if hasattr(self, '_context') else 0
        char_y = getattr(self._context, 'character_y', 0) if hasattr(self, '_context') else 0
        
        # Request move_to_location subgoal if character is not at resource location
        if char_x != x or char_y != y:
            self.logger.info(f"🚶 Character at ({char_x}, {char_y}) needs to move to resource at ({x}, {y})")
            result.request_subgoal(
                goal_name="move_to_location",
                parameters={
                    "target_x": x,
                    "target_y": y
                },
                preserve_context=["resource_code", "resource_name", "target_x", "target_y"]
            )
        else:
            self.logger.info(f"✅ Character already at resource location ({x}, {y})")
            
        return result

    def __repr__(self):
        return "FindResourcesAction()"