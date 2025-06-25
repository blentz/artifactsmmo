""" FindResourcesAction module """

import math
from typing import Dict, List, Optional, Tuple
# Note: get_all_resources API endpoint not available in current client
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from .base import ActionBase


class FindResourcesAction(ActionBase):
    """ Action to find the nearest map location with specified resources """

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 10,
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
        super().__init__()
        self.character_x = character_x
        self.character_y = character_y
        self.search_radius = search_radius
        self.resource_types = resource_types or []
        self.character_level = character_level
        self.skill_type = skill_type
        self.level_range = level_range

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest resource location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_x=self.character_x,
            character_y=self.character_y, 
            search_radius=self.search_radius,
            resource_types=self.resource_types
        )
        
        try:
            # Note: Without get_all_resources, we'll search for common resource types manually
            if self.resource_types:
                target_codes = self.resource_types
            else:
                # Common resource codes if no specific types requested
                target_codes = [
                    'copper', 'iron_ore', 'coal', 'gold_ore',  # Mining
                    'ash_wood', 'spruce_wood', 'birch_wood',   # Woodcutting  
                    'gudgeon', 'shrimp', 'trout'               # Fishing
                ]

            # Search around the character's position for target resources
            nearest_resource_location = None
            min_distance = float('inf')
            found_resource_code = None

            # Search in expanding circles around the character
            for radius in range(1, self.search_radius + 1):
                locations_found = self._search_radius_for_resources(client, target_codes, radius)

                if locations_found:
                    # Find the closest one
                    for location, resource_code in locations_found:
                        x, y = location
                        distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_resource_location = (x, y)
                            found_resource_code = resource_code

                    # If we found resources at this radius, return the nearest one
                    if nearest_resource_location:
                        break

            if nearest_resource_location:
                success_response = self.get_success_response(
                    location=nearest_resource_location,
                    distance=min_distance,
                    resource_code=found_resource_code,
                    resource_name=found_resource_code,  # Use code as name since we don't have details
                    resource_skill='unknown',
                    resource_level=1,
                    target_codes=target_codes
                )
                self.log_execution_result(success_response)
                return success_response

            error_response = self.get_error_response(f"No resources found within radius {self.search_radius}")
            self.log_execution_result(error_response)
            return error_response
            
        except Exception as e:
            error_response = self.get_error_response(f"Resource search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _search_radius_for_resources(self, client, target_codes: List[str],
                                    radius: int) -> List[Tuple[Tuple[int, int], str]]:
        """ Search for target resources at a specific radius around the character """
        resource_locations = []

        # Generate coordinates at the given radius
        y_range = range(self.character_y - radius, self.character_y + radius + 1)
        x_range = range(self.character_x - radius, self.character_x + radius + 1)

        for y in y_range:
            for x in x_range:
                # Skip if this is not at the current radius (for optimization)
                distance_check = (abs(x - self.character_x) != radius and
                                 abs(y - self.character_y) != radius)
                if distance_check:
                    continue

                try:
                    map_response = get_map_api(x=x, y=y, client=client)
                    if map_response and map_response.data:
                        map_data = map_response.data

                        # Check if this location has a target resource
                        has_content = hasattr(map_data, 'content') and map_data.content
                        is_resource = (has_content and
                                      hasattr(map_data.content, 'type_') and
                                      map_data.content.type_ == 'resource')
                        has_target_code = (is_resource and
                                          hasattr(map_data.content, 'code') and
                                          map_data.content.code in target_codes)

                        if has_target_code:
                            resource_locations.append(((x, y), map_data.content.code))

                except Exception:
                    # Continue searching even if one location fails
                    continue

        return resource_locations

    def find_workshops(self, client, workshop_type: Optional[str] = None) -> Optional[Dict]:
        """ Find the nearest workshop location """
        nearest_workshop_location = None
        min_distance = float('inf')
        found_workshop_code = None

        # Search in expanding circles around the character
        for radius in range(1, self.search_radius + 1):
            workshop_locations = self._search_radius_for_workshops(client, radius, workshop_type)

            if workshop_locations:
                # Find the closest one
                for location, workshop_code in workshop_locations:
                    x, y = location
                    distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_workshop_location = (x, y)
                        found_workshop_code = workshop_code

                if nearest_workshop_location:
                    break

        if nearest_workshop_location:
            return {
                'location': nearest_workshop_location,
                'distance': min_distance,
                'workshop_code': found_workshop_code,
                'workshop_type': workshop_type
            }

        return None

    def _search_radius_for_workshops(self, client, radius: int, 
                                    workshop_type: Optional[str] = None) -> List[Tuple[Tuple[int, int], str]]:
        """ Search for workshops at a specific radius around the character """
        workshop_locations = []

        # Generate coordinates at the given radius
        y_range = range(self.character_y - radius, self.character_y + radius + 1)
        x_range = range(self.character_x - radius, self.character_x + radius + 1)

        for y in y_range:
            for x in x_range:
                # Skip if this is not at the current radius (for optimization)
                distance_check = (abs(x - self.character_x) != radius and
                                 abs(y - self.character_y) != radius)
                if distance_check:
                    continue

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
                            workshop_code = getattr(map_data.content, 'code', '')
                            
                            # Filter by workshop type if specified
                            if workshop_type is None or workshop_type.lower() in workshop_code.lower():
                                workshop_locations.append(((x, y), workshop_code))

                except Exception:
                    # Continue searching even if one location fails
                    continue

        return workshop_locations

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