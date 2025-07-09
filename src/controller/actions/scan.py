"""
Scan Action

This action scans the surrounding area to discover workshops, resources,
and other points of interest, updating location context for GOAP planning.
"""

from typing import Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character_api
from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api

from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters

from .base import ActionBase, ActionResult


class ScanAction(ActionBase):
    """
    Action to scan surrounding area for workshops and resources.
    
    This action explores the nearby map to discover workshops, resource nodes,
    and other important locations, updating the location context for planning.
    """

    # GOAP parameters - consolidated state format
    conditions = {
        "character_status": {
            "alive": True,
            "cooldown_active": False
        }
    }
    reactions = {
        "location_context": {
            "workshop": "${discovered_workshop}"
        }
    }
    weight = 2

    def __init__(self):
        """Initialize the scan action."""
        super().__init__()

    def execute(self, client, context: 'ActionContext') -> ActionResult:
        """Scan surrounding area for points of interest."""
        self._context = context
        
        # Get parameters from context
        character_name = context.get(StateParameters.CHARACTER_NAME)
        search_radius = context.get(StateParameters.SEARCH_RADIUS, 3)
        
        try:
            # Get current character position
            character_response = get_character_api(name=character_name, client=client)
            if not character_response or not character_response.data:
                return self.create_error_result("Could not get character data")
            
            character_data = character_response.data
            char_x = getattr(character_data, 'x', 0)
            char_y = getattr(character_data, 'y', 0)
            
            # Scan surrounding area
            discoveries = self._scan_surrounding_area(char_x, char_y, search_radius, client, context)
            
            # Process discoveries and update location context
            location_updates = self._process_discoveries(discoveries, char_x, char_y)
            
            # Create result with consolidated state updates
            return self.create_success_result(
                message=f"Scanned {len(discoveries)} locations",
                location_context=location_updates.get('location_context', {}),
                discoveries=discoveries,
                scan_center=(char_x, char_y),
                search_radius=search_radius
            )
            
        except Exception as e:
            return self.create_error_result(f"Scan failed: {str(e)}")

    def _scan_surrounding_area(self, center_x: int, center_y: int, radius: int,
                              client, context: 'ActionContext') -> List[Dict]:
        """Scan the area around the given center point."""
        discoveries = []
        
        try:
            # Scan in a grid pattern around the center
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    scan_x = center_x + dx
                    scan_y = center_y + dy
                    
                    # Skip center point (character's current location)
                    if dx == 0 and dy == 0:
                        continue
                    
                    # Get map information for this location
                    location_info = self._scan_location(scan_x, scan_y, client)
                    if location_info:
                        discoveries.append(location_info)
            
            self.logger.info(f"Scanned {len(discoveries)} locations within radius {radius}")
            return discoveries
            
        except Exception as e:
            self.logger.warning(f"Area scan failed: {e}")
            return []

    def _scan_location(self, x: int, y: int, client) -> Optional[Dict]:
        """Scan a specific location for content."""
        try:
            map_response = get_map_api(x=x, y=y, client=client)
            if not map_response or not map_response.data:
                return None
            
            map_data = map_response.data
            content = getattr(map_data, 'content', None)
            
            if not content:
                return None
            
            # Categorize the content
            content_info = {
                'coordinates': (x, y),
                'content_code': content.get('code', ''),
                'content_type': content.get('type', ''),
                'name': content.get('name', ''),
                'level': content.get('level', 1)
            }
            
            # Determine if this is a workshop, resource, or other POI
            content_info['category'] = self._categorize_content(content_info)
            
            return content_info
            
        except Exception as e:
            self.logger.debug(f"Failed to scan location ({x}, {y}): {e}")
            return None

    def _categorize_content(self, content_info: Dict) -> str:
        """Categorize discovered content."""
        try:
            content_type = content_info.get('content_type', '').lower()
            content_code = content_info.get('content_code', '').lower()
            
            # Workshop detection
            workshop_types = ['workshop', 'bank', 'grand_exchange']
            if content_type in workshop_types:
                return 'workshop'
            
            # Resource detection
            resource_indicators = ['tree', 'rocks', 'ore', 'fish', 'spot']
            if any(indicator in content_code for indicator in resource_indicators):
                return 'resource'
            
            # Monster detection
            if content_type == 'monster':
                return 'monster'
            
            # Default category
            return 'unknown'
            
        except Exception as e:
            self.logger.debug(f"Content categorization failed: {e}")
            return 'unknown'

    def _process_discoveries(self, discoveries: List[Dict], char_x: int, char_y: int) -> Dict:
        """Process discoveries and create location context updates."""
        try:
            location_context = {}
            
            # Categorize discoveries
            workshops = [d for d in discoveries if d.get('category') == 'workshop']
            resources = [d for d in discoveries if d.get('category') == 'resource']
            monsters = [d for d in discoveries if d.get('category') == 'monster']
            
            # Find closest workshop
            if workshops:
                closest_workshop = min(workshops, 
                    key=lambda w: abs(w['coordinates'][0] - char_x) + abs(w['coordinates'][1] - char_y))
                location_context['workshop'] = {
                    'coordinates': closest_workshop['coordinates'],
                    'type': closest_workshop.get('content_code', 'unknown'),
                    'name': closest_workshop.get('name', 'Unknown Workshop'),
                    'distance': abs(closest_workshop['coordinates'][0] - char_x) + abs(closest_workshop['coordinates'][1] - char_y)
                }
            
            # Record resource locations
            if resources:
                location_context['resources'] = []
                for resource in resources:
                    location_context['resources'].append({
                        'coordinates': resource['coordinates'],
                        'type': resource.get('content_code', 'unknown'),
                        'name': resource.get('name', 'Unknown Resource'),
                        'distance': abs(resource['coordinates'][0] - char_x) + abs(resource['coordinates'][1] - char_y)
                    })
            
            # Record monster locations
            if monsters:
                location_context['monsters'] = []
                for monster in monsters:
                    location_context['monsters'].append({
                        'coordinates': monster['coordinates'],
                        'type': monster.get('content_code', 'unknown'),
                        'name': monster.get('name', 'Unknown Monster'),
                        'level': monster.get('level', 1),
                        'distance': abs(monster['coordinates'][0] - char_x) + abs(monster['coordinates'][1] - char_y)
                    })
            
            # Set discovery flags
            location_context['workshops_discovered'] = len(workshops) > 0
            location_context['resources_discovered'] = len(resources) > 0
            location_context['monsters_discovered'] = len(monsters) > 0
            
            return {'location_context': location_context}
            
        except Exception as e:
            self.logger.warning(f"Discovery processing failed: {e}")
            return {'location_context': {}}

    def __repr__(self):
        return "ScanAction()"
