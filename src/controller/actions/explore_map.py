""" ExploreMapAction module """

import random
from typing import Dict, List, Optional, Tuple

from artifactsmmo_api_client.api.maps.get_map_maps_x_y_get import sync as get_map_api

from src.lib.action_context import ActionContext

from .base import ActionBase


class ExploreMapAction(ActionBase):
    """ Action to explore the map for monsters, resources, and strategic locations """

    def __init__(self):
        """
        Initialize the explore map action.
        """
        super().__init__()

    def execute(self, client, context: ActionContext) -> Optional[Dict]:
        """ Explore the map to find interesting locations """
        if not self.validate_execution_context(client, context):
            return self.get_error_response("No API client provided")
        
        # Get parameters from context
        character_x = context.get('character_x', context.character_x)
        character_y = context.get('character_y', context.character_y)
        exploration_radius = context.get('exploration_radius', 15)
        exploration_strategy = context.get('exploration_strategy', 'spiral')
        target_content_types = context.get('target_content_types', ['monster', 'resource'])
            
        self.log_execution_start(
            character_x=character_x,
            character_y=character_y, 
            radius=exploration_radius,
            strategy=exploration_strategy
        )
        
        try:
            # Generate exploration coordinates based on strategy
            exploration_coords = self._generate_exploration_coordinates(
                character_x, character_y, exploration_radius, exploration_strategy
            )
            
            discovered_locations = {
                "monsters": [],
                "resources": [],
                "workshops": [],
                "other": []
            }
            
            explored_count = 0
            max_explorations = min(50, len(exploration_coords))  # Limit API calls
            
            # Explore each coordinate
            for x, y in exploration_coords[:max_explorations]:
                try:
                    map_response = get_map_api(x=x, y=y, client=client)
                    explored_count += 1
                    
                    if map_response and map_response.data:
                        map_data = map_response.data
                        location_info = self._analyze_location(map_data, x, y, character_x, character_y, target_content_types)
                        
                        if location_info:
                            content_type = location_info.get('content_type', 'other')
                            if content_type == 'monster':
                                discovered_locations["monsters"].append(location_info)
                            elif content_type == 'resource':
                                discovered_locations["resources"].append(location_info)
                            elif content_type == 'workshop':
                                discovered_locations["workshops"].append(location_info)
                            else:
                                discovered_locations["other"].append(location_info)
                
                except Exception as e:
                    self.logger.warning(f"Failed to explore location ({x}, {y}): {str(e)}")
                    continue
            
            # Analyze discoveries and suggest next action
            next_action_suggestion = self._suggest_next_action(discovered_locations, character_x, character_y, exploration_radius)
            
            result = self.get_success_response(
                explored_locations=explored_count,
                discovered_monsters=len(discovered_locations["monsters"]),
                discovered_resources=len(discovered_locations["resources"]),
                discovered_workshops=len(discovered_locations["workshops"]),
                discoveries=discovered_locations,
                next_action_suggestion=next_action_suggestion,
                exploration_strategy_used=exploration_strategy
            )
            
            self.log_execution_result(result)
            return result
            
        except Exception as e:
            error_response = self.get_error_response(f'Map exploration failed: {str(e)}')
            self.log_execution_result(error_response)
            return error_response

    def _generate_exploration_coordinates(self, character_x: int, character_y: int, 
                                        exploration_radius: int, exploration_strategy: str) -> List[Tuple[int, int]]:
        """
        Generate exploration coordinates based on the chosen strategy.
        
        Returns:
            List of (x, y) coordinates to explore
        """
        if exploration_strategy == "spiral":
            return self._generate_spiral_coordinates(character_x, character_y, exploration_radius)
        elif exploration_strategy == "random":
            return self._generate_random_coordinates(character_x, character_y, exploration_radius)
        elif exploration_strategy == "cardinal":
            return self._generate_cardinal_coordinates(character_x, character_y, exploration_radius)
        elif exploration_strategy == "grid":
            return self._generate_grid_coordinates(character_x, character_y, exploration_radius)
        else:
            # Default to spiral
            return self._generate_spiral_coordinates(character_x, character_y, exploration_radius)

    def _generate_spiral_coordinates(self, character_x: int, character_y: int, exploration_radius: int) -> List[Tuple[int, int]]:
        """Generate coordinates in a spiral pattern from character position."""
        coords = []
        for radius in range(1, exploration_radius + 1):
            # Generate coordinates at this radius
            for angle_step in range(0, 360, 45):  # Every 45 degrees
                angle_rad = angle_step * 3.14159 / 180
                x = round(character_x + radius * cos_approximation(angle_rad))
                y = round(character_y + radius * sin_approximation(angle_rad))
                coords.append((x, y))
        return coords

    def _generate_random_coordinates(self, character_x: int, character_y: int, exploration_radius: int) -> List[Tuple[int, int]]:
        """Generate random coordinates within exploration radius."""
        coords = []
        for _ in range(exploration_radius * 2):  # Generate more random points
            # Random offset within exploration radius
            dx = random.randint(-exploration_radius, exploration_radius)
            dy = random.randint(-exploration_radius, exploration_radius)
            coords.append((character_x + dx, character_y + dy))
        return coords

    def _generate_cardinal_coordinates(self, character_x: int, character_y: int, exploration_radius: int) -> List[Tuple[int, int]]:
        """Generate coordinates in cardinal directions (N, S, E, W)."""
        coords = []
        for distance in range(1, exploration_radius + 1):
            # North, South, East, West
            coords.extend([
                (character_x, character_y + distance),
                (character_x, character_y - distance),
                (character_x + distance, character_y),
                (character_x - distance, character_y)
            ])
        return coords

    def _generate_grid_coordinates(self, character_x: int, character_y: int, exploration_radius: int) -> List[Tuple[int, int]]:
        """Generate coordinates in a grid pattern."""
        coords = []
        step_size = max(1, exploration_radius // 5)  # Grid spacing
        for x in range(character_x - exploration_radius, 
                      character_x + exploration_radius + 1, step_size):
            for y in range(character_y - exploration_radius,
                          character_y + exploration_radius + 1, step_size):
                if abs(x - character_x) <= exploration_radius and \
                   abs(y - character_y) <= exploration_radius:
                    coords.append((x, y))
        return coords

    def _analyze_location(self, map_data, x: int, y: int, character_x: int, character_y: int, target_content_types: List[str]) -> Optional[Dict]:
        """
        Analyze a map location and extract useful information.
        
        Args:
            map_data: Map data from API response
            x: X coordinate
            y: Y coordinate
            character_x: Character's X coordinate
            character_y: Character's Y coordinate
            target_content_types: Types of content to analyze
            
        Returns:
            Dictionary with location information or None if not interesting
        """
        if not hasattr(map_data, 'content') or not map_data.content:
            return None
        
        content = map_data.content
        content_type = getattr(content, 'type_', None)
        
        if content_type not in target_content_types:
            return None
        
        location_info = {
            'x': x,
            'y': y,
            'content_type': content_type,
            'code': getattr(content, 'code', ''),
            'distance_from_character': abs(x - character_x) + abs(y - character_y)
        }
        
        # Add type-specific information
        if content_type == 'monster':
            location_info['monster_code'] = getattr(content, 'code', '')
        elif content_type == 'resource':
            location_info['resource_code'] = getattr(content, 'code', '')
        elif content_type == 'workshop':
            location_info['workshop_code'] = getattr(content, 'code', '')
        
        return location_info

    def _suggest_next_action(self, discoveries: Dict, character_x: int, character_y: int, exploration_radius: int) -> Dict:
        """
        Suggest the next best action based on what was discovered.
        
        Args:
            discoveries: Dictionary of discovered locations by type
            
        Returns:
            Dictionary with action suggestion
        """
        suggestion = {
            'action': 'continue_hunting',
            'reason': 'Default hunting strategy',
            'priority': 'low'
        }
        
        # Check for nearby monsters first
        if discoveries["monsters"]:
            closest_monster = min(discoveries["monsters"], 
                                key=lambda m: m['distance_from_character'])
            suggestion = {
                'action': 'move_to_monster',
                'reason': f'Found monster {closest_monster["monster_code"]} at distance {closest_monster["distance_from_character"]}',
                'priority': 'high',
                'target_location': (closest_monster['x'], closest_monster['y']),
                'monster_code': closest_monster['monster_code']
            }
        
        # Check for resources for equipment crafting
        elif discoveries["resources"]:
            closest_resource = min(discoveries["resources"],
                                 key=lambda r: r['distance_from_character'])
            suggestion = {
                'action': 'investigate_resource',
                'reason': f'Found resource {closest_resource["resource_code"]} for potential equipment crafting',
                'priority': 'medium',
                'target_location': (closest_resource['x'], closest_resource['y']),
                'resource_code': closest_resource['resource_code']
            }
        
        # Check for workshops
        elif discoveries["workshops"]:
            closest_workshop = min(discoveries["workshops"],
                                 key=lambda w: w['distance_from_character'])
            suggestion = {
                'action': 'visit_workshop',
                'reason': f'Found workshop {closest_workshop["workshop_code"]} for crafting',
                'priority': 'medium',
                'target_location': (closest_workshop['x'], closest_workshop['y']),
                'workshop_code': closest_workshop['workshop_code']
            }
        
        # If nothing found, suggest moving to a different area
        else:
            suggestion = {
                'action': 'relocate',
                'reason': 'No interesting content found in current area',
                'priority': 'medium',
                'target_location': self._suggest_relocation_target(character_x, character_y, exploration_radius)
            }
        
        return suggestion

    def _suggest_relocation_target(self, character_x: int, character_y: int, exploration_radius: int) -> Tuple[int, int]:
        """Suggest a relocation target when nothing is found in current area."""
        # Move to a random direction with larger distance
        directions = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]
        direction = random.choice(directions)
        distance = exploration_radius * 2  # Move farther away
        
        new_x = character_x + direction[0] * distance
        new_y = character_y + direction[1] * distance
        
        return (new_x, new_y)

    def __repr__(self):
        return "ExploreMapAction()"


def cos_approximation(angle_rad: float) -> float:
    """Simple cosine approximation for angles in radians."""
    # Simple lookup table for common angles
    angle_degrees = int(angle_rad * 180 / 3.14159)
    cos_values = {
        0: 1.0, 45: 0.707, 90: 0.0, 135: -0.707, 
        180: -1.0, 225: -0.707, 270: 0.0, 315: 0.707
    }
    return cos_values.get(angle_degrees % 360, 0.0)


def sin_approximation(angle_rad: float) -> float:
    """Simple sine approximation for angles in radians."""
    # Simple lookup table for common angles  
    angle_degrees = int(angle_rad * 180 / 3.14159)
    sin_values = {
        0: 0.0, 45: 0.707, 90: 1.0, 135: 0.707,
        180: 0.0, 225: -0.707, 270: -1.0, 315: -0.707
    }
    return sin_values.get(angle_degrees % 360, 0.0)