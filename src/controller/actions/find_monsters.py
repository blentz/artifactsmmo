""" FindMonstersAction module """

import math
from typing import Dict, List, Optional, Tuple
from artifactsmmo_api_client.api.monsters.get_all_monster import sync as get_all_monsters_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api
from .base import ActionBase


class FindMonstersAction(ActionBase):
    """ Action to find the nearest map location with specified monsters """
    
    # GOAP parameters - can be overridden by configuration
    conditions = {
        'need_combat': True,
        'monsters_available': False,
        'character_alive': True
    }
    reactions = {
        'monsters_available': True,
        'monster_present': True,
        'at_target_location': True
    }
    weights = {'find_monsters': 2.0}  # Medium-high priority for exploration

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 10,
                 monster_types: Optional[List[str]] = None, character_level: Optional[int] = None,
                 level_range: int = 2):
        """
        Initialize the find monsters action.

        Args:
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            search_radius: Radius to search for monsters
            monster_types: List of monster types to search for. If None, searches for all monsters.
            character_level: Character's current level for level-appropriate filtering. If None, no level filtering.
            level_range: Acceptable level range (+/-) for monster selection (default: 2)
        """
        super().__init__()
        self.character_x = character_x
        self.character_y = character_y
        self.search_radius = search_radius
        self.monster_types = monster_types or []
        self.character_level = character_level
        self.level_range = level_range

    def execute(self, client, **kwargs) -> Optional[Dict]:
        """ Find the nearest monster location """
        if not self.validate_execution_context(client):
            return self.get_error_response("No API client provided")
            
        self.log_execution_start(
            character_x=self.character_x, 
            character_y=self.character_y, 
            search_radius=self.search_radius,
            monster_types=self.monster_types
        )
        
        try:
            # First, get all monsters to find target monsters
            monsters_response = get_all_monsters_api(client=client, size=100)

            if not monsters_response or monsters_response.data is None:
                error_response = self.get_error_response("No monsters data available from API")
                self.log_execution_result(error_response)
                return error_response

            # Find target monsters with level filtering
            target_codes = []
            target_monsters = {}  # Store monster data for level checking
        
            for monster in monsters_response.data:
                # Check type filter if specified
                type_match = True
                if self.monster_types:
                    name_match = any(monster_type.lower() in monster.name.lower()
                                    for monster_type in self.monster_types)
                    code_match = any(monster_type.lower() in monster.code.lower()
                                    for monster_type in self.monster_types)
                    type_match = name_match or code_match
                
                # Check level filter if specified
                level_match = True
                if self.character_level is not None:
                    monster_level = getattr(monster, 'level', 1)
                    level_diff = abs(monster_level - self.character_level)
                    level_match = level_diff <= self.level_range
                
                if type_match and level_match:
                    target_codes.append(monster.code)
                    target_monsters[monster.code] = monster

            if not target_codes:
                error_response = self.get_error_response("No suitable monsters found matching criteria")
                self.log_execution_result(error_response)
                return error_response

            # Search around the character's position for target monsters
            nearest_monster_location = None
            min_distance = float('inf')
            found_monster_code = None

            # Search in expanding circles around the character
            for radius in range(1, self.search_radius + 1):
                locations_found = self._search_radius_for_monsters(client, target_codes, radius)

                if locations_found:
                    # Find the closest one
                    for location, monster_code in locations_found:
                        x, y = location
                        distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                        if distance < min_distance:
                            min_distance = distance
                            nearest_monster_location = (x, y)
                            found_monster_code = monster_code

                    # If we found monsters at this radius, return the nearest one
                    if nearest_monster_location:
                        break

            if nearest_monster_location:
                success_response = self.get_success_response(
                    location=nearest_monster_location,
                    distance=min_distance,
                    monster_code=found_monster_code,
                    target_codes=target_codes
                )
                self.log_execution_result(success_response)
                return success_response

            error_response = self.get_error_response(f"No monsters found within radius {self.search_radius}")
            self.log_execution_result(error_response)
            return error_response
            
        except Exception as e:
            error_response = self.get_error_response(f"Monster search failed: {str(e)}")
            self.log_execution_result(error_response)
            return error_response

    def _search_radius_for_monsters(self, client, target_codes: List[str],
                                   radius: int) -> List[Tuple[Tuple[int, int], str]]:
        """ Search for target monsters at a specific radius around the character """
        monster_locations = []

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

                        # Check if this location has a target monster
                        has_content = hasattr(map_data, 'content') and map_data.content
                        is_monster = (has_content and
                                     hasattr(map_data.content, 'type_') and
                                     map_data.content.type_ == 'monster')
                        has_target_code = (is_monster and
                                          hasattr(map_data.content, 'code') and
                                          map_data.content.code in target_codes)

                        if has_target_code:
                            monster_locations.append(((x, y), map_data.content.code))

                except Exception:
                    # Continue searching even if one location fails
                    continue

        return monster_locations

    def __repr__(self):
        monster_filter = f", types={self.monster_types}" if self.monster_types else ""
        return (f"FindMonstersAction({self.character_x}, {self.character_y}, "
                f"radius={self.search_radius}{monster_filter})")
