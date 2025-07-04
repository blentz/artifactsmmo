""" FindResourcesAction module - Refactored version """

from typing import Dict, List, Optional

from src.lib.action_context import ActionContext

from .search_base import SearchActionBase
from .base import ActionResult


class FindResourcesAction(SearchActionBase):
    """ Action to find the nearest map location with specified resources """

    def __init__(self):
        """
        Initialize the find resources action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> ActionResult:
        """ Find the nearest resource location using unified search algorithm """
        self._context = context
        
        try:
            return self.perform_action(client, context)
        except Exception as e:
            return self.create_error_result(
                f"{self.__class__.__name__} failed: {str(e)}"
            )
    
    def perform_action(self, client, context: ActionContext) -> ActionResult:
        """
        Perform the resource search with knowledge base fallback.
        
        This implementation demonstrates the refactored approach with:
        1. Knowledge base search first
        2. Map state search second
        3. API search as fallback
        """
        # Get parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        search_radius = context.get('search_radius', 5)
        resource_types = context.get('resource_types', [])
        character_level = context.get('character_level')
        skill_type = context.get('skill_type')
        level_range = context.get('level_range', 5)
        
        
        # Extract context
        knowledge_base = context.knowledge_base
        map_state = context.map_state
        
        # Determine target resource codes
        target_codes = self._determine_target_resource_codes(resource_types)
        if not target_codes:
            return self.create_error_result("No target resource types specified")
        
        # Priority 1: Search knowledge base for known resource locations
        if knowledge_base:
            kb_results = self.search_knowledge_base_resources(
                knowledge_base, 
                resource_code=target_codes[0] if len(target_codes) == 1 else None,
                skill_type=skill_type
            )
            
            # Find closest known resource with location
            closest_kb_resource = self._find_closest_kb_resource(kb_results, character_x, character_y)
            if closest_kb_resource:
                return self._format_resource_response(closest_kb_resource, source='knowledge_base', character_x=character_x, character_y=character_y)
        
        # Priority 2: Search map state for cached locations
        if map_state:
            for resource_code in target_codes:
                map_results = self.search_map_state_for_content(
                    map_state,
                    content_type='resource',
                    content_code=resource_code,
                    center=(character_x, character_y),
                    radius=search_radius
                )
                
                if map_results:
                    closest = min(map_results, key=lambda r: self._calculate_distance(*r['location'], character_x, character_y))
                    return self._format_resource_response(closest, source='map_state', character_x=character_x, character_y=character_y)
        
        # Priority 3: Fall back to API search
        resource_filter = self.create_resource_filter(
            resource_types=target_codes,
            skill_type=skill_type,
            character_level=character_level
        )
        
        # Define result processor for API results
        def resource_result_processor(location, content_code, content_data):
            return self._format_resource_response({
                'location': location,
                'code': content_code,
                'data': content_data
            }, source='api_search', character_x=character_x, character_y=character_y)
        
        # Use unified search algorithm
        result = self.unified_search(client, character_x, character_y, search_radius, resource_filter, resource_result_processor, map_state)
        
        return result

    def _determine_target_resource_codes(self, resource_types: List[str]) -> List[str]:
        """Determine which resource codes to search for based on context."""
        # Use explicitly provided resource types
        if resource_types:
            return resource_types
        
        return []  # No resource types provided

    def _find_closest_kb_resource(self, kb_results: List[Dict], character_x: int, character_y: int) -> Optional[Dict]:
        """Find the closest resource from knowledge base results that has location data."""
        valid_results = []
        
        for result in kb_results:
            data = result.get('data', {})
            # Check if this resource has location data stored
            if 'last_seen_location' in data:
                loc = data['last_seen_location']
                if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                    valid_results.append({
                        'location': (loc[0], loc[1]),
                        'code': result['code'],
                        'data': data
                    })
        
        if not valid_results:
            return None
            
        # Return closest
        return min(valid_results, key=lambda r: self._calculate_distance(*r['location'], character_x, character_y))

    def _format_resource_response(self, resource_info: Dict, source: str, character_x: int, character_y: int) -> Dict:
        """Format a resource finding into a standard response."""
        location = resource_info.get('location', (0, 0))
        code = resource_info.get('code', '')
        data = resource_info.get('data', {})
        content = resource_info.get('content', {})
        
        # Extract data from different sources
        if source == 'map_state' and content:
            skill = content.get('skill', 'unknown')
            level = content.get('level', 1)
        else:
            skill = data.get('skill_required', data.get('skill', 'unknown'))
            level = data.get('level_required', data.get('level', 1))
        
        x, y = location
        distance = self._calculate_distance(x, y, character_x, character_y)
        
        return self.create_success_result(
            message=f"Found {code} at {location}",
            location=location,
            distance=distance,
            resource_code=code,
            resource_name=data.get('name', code),
            resource_skill=skill,
            resource_level=level,
            source=source,
            # Include coordinates for action context
            target_x=x,
            target_y=y,
            resource_x=x,
            resource_y=y
        )

    def create_resource_filter(self, resource_types: List[str] = None, 
                              skill_type: str = None, character_level: int = None):
        """
        Create a filter function for resources based on specified criteria.
        
        Args:
            resource_types: List of specific resource codes to match
            skill_type: Skill type to filter by
            character_level: Character level for level-appropriate filtering
            
        Returns:
            Filter function for use with unified search
        """
        def resource_filter(content_data: Dict, x: int, y: int) -> bool:
            # Must be a resource
            content_type = content_data.get('type_', content_data.get('type', ''))
            if content_type != 'resource':
                return False
            
            content_code = content_data.get('code', '')
            
            # Check resource type match
            if resource_types and content_code not in resource_types:
                return False
            
            # Check skill type match
            if skill_type:
                resource_skill = content_data.get('skill', '')
                if resource_skill != skill_type:
                    return False
            
            # Check level requirements
            if character_level is not None:
                resource_level = content_data.get('level', 1)
                if abs(resource_level - character_level) > 5:  # Default level range
                    return False
            
            return True
        
        return resource_filter

    def _calculate_distance(self, x: int, y: int, character_x: int, character_y: int) -> int:
        """Calculate Manhattan distance from character to given coordinates."""
        return abs(x - character_x) + abs(y - character_y)

    def __repr__(self):
        return "FindResourcesAction()"