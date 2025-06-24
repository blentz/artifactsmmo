""" FindSlimeAction module """

import math
from typing import Dict, List, Optional, Tuple
from artifactsmmo_api_client.api.monsters.get_all_monster import sync as get_all_monsters_api
from artifactsmmo_api_client.api.maps.get_map_x_y import sync as get_map_api


class FindSlimeAction:
    """ Action to find the nearest map location with a slime monster """
    conditions = {}
    reactions = {}
    weights = {}

    g = None  # goal; involved in plan costs

    def __init__(self, character_x: int = 0, character_y: int = 0, search_radius: int = 10):
        self.character_x = character_x
        self.character_y = character_y
        self.search_radius = search_radius

    def execute(self, client) -> Optional[Dict]:
        """ Find the nearest slime location """
        # First, get all monsters to find slime monsters
        monsters_response = get_all_monsters_api(client=client, size=100)
        
        if not monsters_response or not monsters_response.data:
            return None
            
        # Find slime monsters
        slime_codes = []
        for monster in monsters_response.data:
            if 'slime' in monster.name.lower() or 'slime' in monster.code.lower():
                slime_codes.append(monster.code)
        
        if not slime_codes:
            return None
            
        # Search around the character's position for slimes
        nearest_slime_location = None
        min_distance = float('inf')
        
        # Search in expanding circles around the character
        for radius in range(1, self.search_radius + 1):
            locations_found = self._search_radius_for_slimes(client, slime_codes, radius)
            
            if locations_found:
                # Find the closest one
                for location in locations_found:
                    x, y = location
                    distance = math.sqrt((x - self.character_x) ** 2 + (y - self.character_y) ** 2)
                    if distance < min_distance:
                        min_distance = distance
                        nearest_slime_location = (x, y)
                
                # If we found slimes at this radius, return the nearest one
                if nearest_slime_location:
                    break
        
        if nearest_slime_location:
            return {
                'location': nearest_slime_location,
                'distance': min_distance,
                'slime_codes': slime_codes
            }
        
        return None

    def _search_radius_for_slimes(self, client, slime_codes: List[str], radius: int) -> List[Tuple[int, int]]:
        """ Search for slimes at a specific radius around the character """
        slime_locations = []
        
        # Generate coordinates at the given radius
        y_range = range(self.character_y - radius, self.character_y + radius + 1)
        x_range = range(self.character_x - radius, self.character_x + radius + 1)
        
        for y in y_range:
            for x in x_range:
                # Skip if this is not at the current radius (for optimization)
                if abs(x - self.character_x) != radius and abs(y - self.character_y) != radius:
                    continue
                    
                try:
                    map_response = get_map_api(x=x, y=y, client=client)
                    if map_response and map_response.data:
                        map_data = map_response.data
                        
                        # Check if this location has a monster
                        if (hasattr(map_data, 'content') and 
                            map_data.content and 
                            hasattr(map_data.content, 'type_') and
                            map_data.content.type_ == 'monster' and
                            hasattr(map_data.content, 'code') and
                            map_data.content.code in slime_codes):
                            slime_locations.append((x, y))
                            
                except Exception as e:
                    # Continue searching even if one location fails
                    continue
        
        return slime_locations

    def __repr__(self):
        return f"FindSlimeAction({self.character_x}, {self.character_y}, radius={self.search_radius})"
