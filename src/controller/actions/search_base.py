"""
Unified Search Algorithm Base Class

This module provides a unified search algorithm base class that eliminates redundancy
across multiple find_* action classes (find_monsters, find_resources, find_workshops).
All search-related actions can inherit from this class to use consistent search logic.
"""

import math
from typing import Callable, Dict, List, Optional, Set, Tuple

from .base import ActionBase, ActionResult
from .mixins import KnowledgeBaseSearchMixin, MapStateAccessMixin


class SearchActionBase(ActionBase, KnowledgeBaseSearchMixin, MapStateAccessMixin):
    """
    Base class for all search-related actions with unified search algorithm.
    
    Provides:
    - Boundary detection and caching
    - Expanding radius search patterns
    - Consistent error handling
    - Configurable content filtering
    - Distance calculation and optimization
    """
    
    # Shared boundary cache across all search action instances
    _map_boundaries: Dict[str, Set[Tuple[int, int]]] = {
        'north': set(),    # coordinates that returned 404 when going north
        'south': set(),    # coordinates that returned 404 when going south  
        'east': set(),     # coordinates that returned 404 when going east
        'west': set()      # coordinates that returned 404 when going west
    }

    def __init__(self):
        """
        Initialize the search action base.
        """
        super().__init__()

    def unified_search(self, client, character_x: int, character_y: int, search_radius: int,
                      content_filter: Callable[[Dict, int, int], bool],
                      result_processor: Callable[[Tuple[int, int], str, Dict], Dict] = None,
                      map_state = None) -> Optional[Dict]:
        """
        Unified search algorithm that can be customized for different content types.
        
        Args:
            client: API client for making map requests
            character_x: Character's current X coordinate
            character_y: Character's current Y coordinate
            search_radius: Maximum radius to search
            content_filter: Function that takes (content_data, x, y) and returns True if content matches
            result_processor: Optional function to process successful results
            map_state: MapState instance for cached map access (preferred over direct API calls)
            
        Returns:
            Dictionary with search results or None if nothing found
        """
        
        # Search results
        found_locations = []
        
        # Search in expanding circles around the character
        for radius in range(0, search_radius + 1):
            locations_at_radius = self._search_radius_for_content(client, character_x, character_y, radius, content_filter, map_state)
            
            if locations_at_radius:
                found_locations.extend(locations_at_radius)
                # For immediate results, find the closest one at this radius
                closest_location = self._find_closest_location(character_x, character_y, locations_at_radius)
                if closest_location:
                    location, content_code, content_data = closest_location
                    
                    # Process result if processor provided
                    if result_processor:
                        return result_processor(location, content_code, content_data)
                    else:
                        # Default result processing
                        x, y = location
                        distance = self._calculate_distance(character_x, character_y, x, y)
                        return self.create_success_result(
                            location=location,
                            distance=distance,
                            content_code=content_code,
                            content_type=content_data.get('type_', 'unknown')
                        )
        
        # If no locations found, return error
        return self.create_error_result(f"No matching content found within radius {search_radius}")

    def _search_radius_for_content(self, client, character_x: int, character_y: int, radius: int, 
                                  content_filter: Callable[[Dict, int, int], bool],
                                  map_state = None) -> List[Tuple[Tuple[int, int], str, Dict]]:
        """
        Search for content at a specific radius using the provided filter.
        
        Args:
            client: API client for making requests
            radius: Search radius from character position
            content_filter: Function to filter content
            map_state: MapState instance for cached map access
            
        Returns:
            List of (location, content_code, content_data) tuples
        """
        found_content = []
        
        # Generate coordinates at the given radius using efficient boundary traversal
        coordinates = self._generate_radius_coordinates(character_x, character_y, radius)
        
        for x, y in coordinates:
            # Skip if this coordinate is likely outside map boundaries
            if self._is_likely_outside_map(x, y):
                self.logger.debug(f"Skipping ({x}, {y}) - likely outside map boundaries")
                continue
            
            try:
                # Use MapState cache - knowledge base handles all cache freshness decisions
                # Check if we have fresh cached data first
                if map_state.is_cache_fresh(x, y):
                    coord_key = f"{x},{y}"
                    map_data = map_state.data.get(coord_key, {})
                    self.logger.debug(f"✅ Cache hit: location ({x}, {y})")
                else:
                    # Scan the location (which will use cache or fetch from API as needed)
                    try:
                        scan_result = map_state.scan(x, y, cache=True)
                        # Check if scan returned None (boundary hit)
                        if scan_result is None:
                            self._record_boundary_hit(character_x, character_y, x, y)
                            self.logger.debug(f"Map boundary detected at ({x}, {y})")
                            continue
                        coord_key = f"{x},{y}"
                        map_data = map_state.data.get(coord_key, {})
                        self.logger.debug(f"🔄 Cache refresh: location ({x}, {y})")
                    except Exception as scan_error:
                        # Handle scan errors (including 404s that throw exceptions)
                        if "404" in str(scan_error) or "not found" in str(scan_error).lower():
                            self._record_boundary_hit(character_x, character_y, x, y)
                            self.logger.debug(f"Map boundary detected at ({x}, {y}) via exception: {scan_error}")
                        else:
                            self.logger.debug(f"Error scanning ({x}, {y}): {scan_error}")
                        continue
                
                # Extract content from map data
                content = map_data.get('content', None)
                
                if content:
                    # Convert content to dictionary for consistent processing
                    content_dict = self._content_to_dict(content)
                    
                    # Apply the content filter
                    if content_filter(content_dict, x, y):
                        content_code = content_dict.get('code', 'unknown')
                        self.logger.debug(f"✅ Found matching content '{content_code}' at ({x}, {y})")
                        found_content.append(((x, y), content_code, content_dict))
                
            except Exception as e:
                # Log the error for debugging but continue searching
                self.logger.debug(f"Error querying map at ({x}, {y}): {str(e)}")
                continue
        
        return found_content

    def _generate_radius_coordinates(self, character_x: int, character_y: int, radius: int) -> List[Tuple[int, int]]:
        """
        Generate coordinates at a specific radius from character position.
        
        Uses efficient boundary traversal instead of checking every coordinate in a square.
        
        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            radius: Distance from character position
            
        Returns:
            List of (x, y) coordinate tuples
        """
        coordinates = []
        
        if radius == 0:
            return [(character_x, character_y)]
        
        # Generate coordinates on the boundary of the radius
        # Top and bottom edges
        for x in range(character_x - radius, character_x + radius + 1):
            coordinates.append((x, character_y - radius))  # Top edge
            coordinates.append((x, character_y + radius))  # Bottom edge
        
        # Left and right edges (excluding corners already added)
        for y in range(character_y - radius + 1, character_y + radius):
            coordinates.append((character_x - radius, y))  # Left edge
            coordinates.append((character_x + radius, y))  # Right edge
        
        return coordinates

    def _content_to_dict(self, content) -> Dict:
        """
        Convert content object to dictionary for consistent processing.
        
        Args:
            content: Content object from map API response
            
        Returns:
            Dictionary representation of content
        """
        if isinstance(content, dict):
            return content
        elif hasattr(content, 'to_dict'):
            return content.to_dict()
        elif hasattr(content, '__dict__'):
            return content.__dict__
        else:
            # Try to extract common attributes manually
            content_dict = {}
            for attr in ['code', 'type', 'type_', 'name', 'level', 'skill']:
                if hasattr(content, attr):
                    attr_key = 'type_' if attr == 'type' else attr  # Map 'type' to 'type_' for consistency
                    content_dict[attr_key] = getattr(content, attr)
            return content_dict

    def _find_closest_location(self, character_x: int, character_y: int, locations: List[Tuple[Tuple[int, int], str, Dict]]) -> Optional[Tuple[Tuple[int, int], str, Dict]]:
        """
        Find the closest location from a list of found locations.
        
        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            locations: List of (location, content_code, content_data) tuples
            
        Returns:
            Closest location tuple or None
        """
        if not locations:
            return None
        
        min_distance = float('inf')
        closest_location = None
        
        for location_tuple in locations:
            location, content_code, content_data = location_tuple
            x, y = location
            distance = self._calculate_distance(character_x, character_y, x, y)
            
            if distance < min_distance:
                min_distance = distance
                closest_location = location_tuple
        
        return closest_location

    def _calculate_distance(self, from_x: int, from_y: int, to_x: int, to_y: int) -> float:
        """
        Calculate distance between two coordinates.
        
        Args:
            from_x: Starting X coordinate
            from_y: Starting Y coordinate
            to_x: Target X coordinate
            to_y: Target Y coordinate
            
        Returns:
            Euclidean distance
        """
        return math.sqrt((to_x - from_x) ** 2 + (to_y - from_y) ** 2)

    def _is_likely_outside_map(self, x: int, y: int) -> bool:
        """
        Check if coordinates are likely outside the map based on known boundaries.
        
        Args:
            x: X coordinate to check
            y: Y coordinate to check
            
        Returns:
            True if coordinates are likely outside map boundaries
        """
        # Check if we've hit boundaries in any direction that would make this coordinate invalid
        
        # If we know the northern boundary and this y is above it, skip
        for bx, by in self._map_boundaries['north']:
            if x == bx and y > by:
                return True
                
        # If we know the southern boundary and this y is below it, skip  
        for bx, by in self._map_boundaries['south']:
            if x == bx and y < by:
                return True
                
        # If we know the eastern boundary and this x is to the right of it, skip
        for bx, by in self._map_boundaries['east']:
            if y == by and x > bx:
                return True
                
        # If we know the western boundary and this x is to the left of it, skip
        for bx, by in self._map_boundaries['west']:
            if y == by and x < bx:
                return True
        
        return False

    def _record_boundary_hit(self, character_x: int, character_y: int, x: int, y: int) -> None:
        """
        Record that we hit a map boundary at the given coordinates.
        
        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            x: X coordinate where boundary was hit
            y: Y coordinate where boundary was hit
        """
        # Determine which direction this boundary represents relative to character
        if y > character_y:
            self._map_boundaries['north'].add((x, y))
        elif y < character_y:
            self._map_boundaries['south'].add((x, y))
        elif x > character_x:
            self._map_boundaries['east'].add((x, y))
        elif x < character_x:
            self._map_boundaries['west'].add((x, y))
            
        # Log boundary information for debugging
        boundary_info = {
            'north': len(self._map_boundaries['north']),
            'south': len(self._map_boundaries['south']),
            'east': len(self._map_boundaries['east']),
            'west': len(self._map_boundaries['west'])
        }
        self.logger.debug(f"Map boundaries known: {boundary_info}")

    @classmethod
    def clear_boundary_cache(cls) -> None:
        """
        Clear the boundary cache. Useful for testing or when map changes.
        """
        cls._map_boundaries = {
            'north': set(),
            'south': set(),
            'east': set(),
            'west': set()
        }

    @classmethod 
    def get_boundary_stats(cls) -> Dict[str, int]:
        """
        Get statistics about known map boundaries.
        
        Returns:
            Dictionary with counts of known boundaries in each direction
        """
        return {
            'north': len(cls._map_boundaries['north']),
            'south': len(cls._map_boundaries['south']),
            'east': len(cls._map_boundaries['east']),
            'west': len(cls._map_boundaries['west'])
        }

    # Content filter factory methods for common search patterns
    
    @staticmethod
    def create_monster_filter(monster_types: List[str] = None, character_level: int = None, 
                             level_range: int = 2) -> Callable[[Dict, int, int], bool]:
        """
        Create a content filter for finding monsters.
        
        Args:
            monster_types: List of monster codes to search for
            character_level: Character level for level-appropriate filtering
            level_range: Acceptable level range (+/-) for monster selection
            
        Returns:
            Content filter function
        """
        def monster_filter(content_dict: Dict, x: int, y: int) -> bool:
            content_type = content_dict.get('type_', 'unknown')
            content_code = content_dict.get('code', '')
            
            # Check if it's a monster-type content
            if content_type not in ['monster', 'unknown']:
                return False
            
            # Check if it matches specific monster types if provided
            if monster_types and content_code not in monster_types:
                # Also check if the content_code matches monster name patterns
                monster_patterns = ['slime', 'goblin', 'wolf', 'orc', 'cyclops', 'chicken', 'cow', 'pig']
                if not any(pattern in content_code.lower() for pattern in monster_patterns):
                    return False
            
            # Check level appropriateness if character level provided
            if character_level is not None and 'level' in content_dict:
                monster_level = content_dict.get('level', 1)
                # Only fight monsters at or below character level + level_range
                # This ensures safety - no monsters above character capability
                if monster_level > character_level + level_range:
                    return False
            
            return True
        
        return monster_filter

    @staticmethod
    def create_resource_filter(resource_types: List[str] = None, skill_type: str = None,
                              character_level: int = None) -> Callable[[Dict, int, int], bool]:
        """
        Create a content filter for finding resources.
        
        Args:
            resource_types: List of resource codes to search for
            skill_type: Skill type to filter by (mining, woodcutting, fishing)
            character_level: Character level for level-appropriate filtering
            
        Returns:
            Content filter function
        """
        def resource_filter(content_dict: Dict, x: int, y: int) -> bool:
            content_type = content_dict.get('type_', 'unknown')
            content_code = content_dict.get('code', '')
            
            # Check if it's a resource-type content
            resource_patterns = ['_rocks', '_tree', '_fishing_spot', '_field', 'mushmush', 'glowstem']
            is_likely_resource = (content_type in ['resource', 'unknown'] or
                                any(pattern in content_code for pattern in resource_patterns))
            
            if not is_likely_resource:
                return False
            
            # Check if it matches specific resource types if provided
            if resource_types and content_code not in resource_types:
                return False
            
            # Check skill type filtering if provided
            if skill_type:
                skill_patterns = {
                    'mining': ['_rocks', 'copper', 'iron', 'coal', 'gold'],
                    'woodcutting': ['_tree', 'ash', 'spruce', 'birch'],
                    'fishing': ['_fishing_spot', 'gudgeon', 'shrimp', 'salmon']
                }
                patterns = skill_patterns.get(skill_type, [])
                if not any(pattern in content_code for pattern in patterns):
                    return False
            
            # Check level appropriateness if character level provided
            if character_level is not None and 'level' in content_dict:
                resource_level = content_dict.get('level', 1)
                if resource_level > character_level + 2:  # Allow resources up to 2 levels higher
                    return False
            
            return True
        
        return resource_filter

    def create_workshop_filter(self, workshop_type: str = None) -> Callable[[Dict, int, int], bool]:
        """
        Create a content filter for finding workshops.
        
        Args:
            workshop_type: Specific workshop type to search for
            
        Returns:
            Content filter function
        """
        def workshop_filter(content_dict: Dict, x: int, y: int) -> bool:
            content_type = content_dict.get('type', content_dict.get('type_', 'unknown'))
            content_code = content_dict.get('code', '')
            
            # Check if it's a workshop-type content
            workshop_patterns = ['crafting', 'smithy', 'workshop']
            workshop_codes = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy']
            
            is_likely_workshop = (content_type == 'workshop' or
                                any(pattern in content_code for pattern in workshop_patterns) or
                                content_code in workshop_codes)
            
            if not is_likely_workshop:
                return False
            
            # Check if it matches specific workshop type if provided
            if workshop_type and workshop_type.lower() not in content_code.lower():
                return False
            
            return True
        
        return workshop_filter