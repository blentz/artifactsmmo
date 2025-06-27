""" FindWorkshopsAction module """

import math
from typing import Dict, List, Optional, Tuple
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from .base import ActionBase


class FindWorkshopsAction(ActionBase):
    """ Action to find the nearest workshop location """

    # GOAP parameters
    conditions = {"character_alive": True, "can_move": True}
    reactions = {"workshops_discovered": True, "at_target_location": False}
    weights = {"workshops_discovered": 15}

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 10,
                 workshop_type: Optional[str] = None):
        """
        Initialize the find workshops action.

        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            search_radius: Radius to search for workshops
            workshop_type: Type of workshop to search for (e.g., 'weaponcrafting', 'gearcrafting')
        """
        super().__init__()
        self.character_x = character_x
        self.character_y = character_y
        self.search_radius = search_radius
        self.workshop_type = workshop_type

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest workshop location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_x=self.character_x,
            character_y=self.character_y, 
            search_radius=self.search_radius,
            workshop_type=self.workshop_type
        )
        
        try:
            # Search around the character's position for workshops
            nearest_workshop_location = None
            min_distance = float('inf')
            found_workshop_code = None

            # Search in expanding circles around the character
            for radius in range(1, self.search_radius + 1):
                workshop_locations = self._search_radius_for_workshops(client, radius)

                if workshop_locations:
                    # Find the closest one
                    for location, workshop_code in workshop_locations:
                        x, y = location
                        distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_workshop_location = (x, y)
                            found_workshop_code = workshop_code

                    # If we found workshops at this radius, return the nearest one
                    if nearest_workshop_location:
                        break

            if nearest_workshop_location:
                success_response = self.get_success_response(
                    location=nearest_workshop_location,
                    distance=min_distance,
                    workshop_code=found_workshop_code,
                    workshop_type=self.workshop_type or 'general'
                )
                self.log_execution_result(success_response)
                return success_response

            error_response = self.get_error_response(f"No workshops found within radius {self.search_radius}")
            self.log_execution_result(error_response)
            return error_response
            
        except Exception as e:
            error_response = self.get_error_response(f"Workshop search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _search_radius_for_workshops(self, client, radius: int) -> List[Tuple[Tuple[int, int], str]]:
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
                            if self.workshop_type is None or self.workshop_type.lower() in workshop_code.lower():
                                workshop_locations.append(((x, y), workshop_code))

                except Exception:
                    # Continue searching even if one location fails
                    continue

        return workshop_locations

    def __repr__(self):
        workshop_filter = f", type={self.workshop_type}" if self.workshop_type else ""
        return (f"FindWorkshopsAction({self.character_x}, {self.character_y}, "
               f"radius={self.search_radius}{workshop_filter})")