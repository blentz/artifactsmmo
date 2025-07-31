"""
Movement Action Factory

This module implements the MovementActionFactory for generating movement actions
to all valid locations in the game world.
"""

from typing import Any

from ..state.game_state import GameState
from ..state.character_game_state import CharacterGameState
from .movement_action import MovementAction
from .parameterized_action_factory import ParameterizedActionFactory


class MovementActionFactory(ParameterizedActionFactory):
    """Factory for generating movement actions to all valid locations"""

    def __init__(self) -> None:
        super().__init__(MovementAction)

    def generate_parameters(self, game_data: Any, current_state: CharacterGameState) -> list[dict[str, Any]]:
        """Generate simple nearby movement actions.

        Parameters:
            game_data: Complete game data including map information and locations
            current_state: CharacterGameState instance with current character state

        Return values:
            List of parameter dictionaries for creating movement action instances

        This method generates simple movement actions for nearby locations within
        a small radius, keeping the action space manageable while ensuring the
        character can move to adjacent positions for exploration.
        """
        current_x = getattr(current_state, 'x', 0)
        current_y = getattr(current_state, 'y', 0)

        # Generate only nearby locations in a 3-tile radius
        nearby_locations = self.get_nearby_locations(current_x, current_y, radius=3)
        
        # Filter out invalid coordinates based on known map data
        filtered_locations = self.filter_valid_positions(nearby_locations, game_data)

        # Enhance locations with content information to enable proper GOAP planning
        # This allows the planner to understand that moving to monster/resource locations
        # will enable combat/gathering actions, without making MovementAction map-aware
        enhanced_locations = self.enhance_locations_with_content(filtered_locations, game_data)

        return enhanced_locations

    def get_nearby_locations(self, current_x: int, current_y: int, radius: int = 5) -> list[dict[str, Any]]:
        """Get locations within movement radius for efficiency.

        Parameters:
            current_x: Current X coordinate of the character
            current_y: Current Y coordinate of the character
            radius: Maximum distance to consider for nearby locations

        Return values:
            List of parameter dictionaries for nearby movement actions

        This method identifies locations within the specified radius of the
        character's current position for efficient local movement planning
        and exploration strategies.
        """
        nearby_locations = []

        for x in range(current_x - radius, current_x + radius + 1):
            for y in range(current_y - radius, current_y + radius + 1):
                distance = abs(x - current_x) + abs(y - current_y)
                if distance <= radius and distance > 0:
                    nearby_locations.append({"target_x": x, "target_y": y})

        return nearby_locations

    def get_strategic_locations(self, game_data: Any) -> list[dict[str, Any]]:
        """Get important locations (banks, NPCs, resource spots, monsters).

        Parameters:
            game_data: Complete game data including location information

        Return values:
            List of parameter dictionaries for strategic location movements

        This method identifies key strategic locations such as banks, NPCs,
        resource gathering spots, and monster areas for long-term movement
        planning and goal-oriented navigation.
        """
        strategic_locations: list[dict[str, Any]] = []

        if game_data is None:
            return strategic_locations

        # Extract locations with content from map data
        if hasattr(game_data, "maps") and game_data.maps:
            for map_data in game_data.maps:
                x = map_data.x
                y = map_data.y
                content = map_data.content
                
                location_params = {"target_x": x, "target_y": y}
                
                # Add location type information for specialized movement actions
                if content:
                    location_params["location_type"] = content.type
                    strategic_locations.append(location_params)

        return strategic_locations

    def filter_valid_positions(self, positions: list[dict[str, Any]], game_data: Any) -> list[dict[str, Any]]:
        """Filter out invalid positions (obstacles, out of bounds).

        Parameters:
            positions: List of position dictionaries to validate
            game_data: Complete game data including map boundaries and obstacles

        Return values:
            List of validated position dictionaries with invalid positions removed

        This method validates position accessibility by checking game boundaries,
        obstacle locations, and movement restrictions to ensure only reachable
        positions are included in movement planning.
        """
        valid_positions = []
        
        # If no game data, return empty list to avoid generating invalid actions
        if not game_data or not hasattr(game_data, 'maps'):
            return valid_positions
        
        # Create set of valid coordinates from cached map data
        valid_coords = {(m.x, m.y) for m in game_data.maps if hasattr(m, 'x') and hasattr(m, 'y')}
        
        for position in positions:
            x = position.get("target_x")
            y = position.get("target_y")

            if x is not None and y is not None:
                # Only include positions that exist in the cached map data
                if (x, y) in valid_coords:
                    valid_positions.append(position)

        return valid_positions

    def enhance_locations_with_content(self, locations: list[dict[str, Any]], game_data: Any) -> list[dict[str, Any]]:
        """Enhance location parameters with content type information from game data.

        Parameters:
            locations: List of location dictionaries to enhance
            game_data: Complete game data including map information

        Return values:
            List of enhanced location dictionaries with location_type information

        This method looks up each location in the game data to determine if it
        contains monsters, resources, workshops, etc. and adds location_type
        information for proper movement action effect calculation.
        """
        enhanced_locations = []
        
        if not game_data or not hasattr(game_data, 'maps'):
            return locations
        
        # Create a lookup map for efficient content checking
        content_map = {}
        for map_data in game_data.maps:
            if map_data.content:
                content_map[(map_data.x, map_data.y)] = map_data.content.type
        
        # Enhance each location with content type if available
        for location in locations:
            x = location["target_x"]
            y = location["target_y"]
            enhanced_location = location.copy()
            
            if (x, y) in content_map:
                enhanced_location["location_type"] = content_map[(x, y)]
            
            enhanced_locations.append(enhanced_location)
        
        return enhanced_locations