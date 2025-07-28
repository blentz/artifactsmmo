"""
Movement Action Factory

This module implements the MovementActionFactory for generating movement actions
to all valid locations in the game world.
"""

from typing import Any

from ..state.game_state import GameState
from .movement_action import MovementAction
from .parameterized_action_factory import ParameterizedActionFactory


class MovementActionFactory(ParameterizedActionFactory):
    """Factory for generating movement actions to all valid locations"""

    def __init__(self) -> None:
        super().__init__(MovementAction)

    def generate_parameters(self, game_data: Any, current_state: dict[GameState, Any]) -> list[dict[str, Any]]:
        """Generate movement actions for all accessible map locations.

        Parameters:
            game_data: Complete game data including map information and locations
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            List of parameter dictionaries for creating movement action instances

        This method analyzes available map data to generate parameters for
        movement actions to all strategic locations including NPCs, resources,
        monsters, and key game areas.
        """
        parameters = []

        current_x = current_state.get(GameState.CURRENT_X, 0)
        current_y = current_state.get(GameState.CURRENT_Y, 0)

        nearby_locations = self.get_nearby_locations(current_x, current_y, radius=10)
        strategic_locations = self.get_strategic_locations(game_data)

        all_locations = nearby_locations + strategic_locations
        valid_locations = self.filter_valid_positions(all_locations, game_data)

        for location in valid_locations:
            if location["target_x"] != current_x or location["target_y"] != current_y:
                parameters.append(location)

        return parameters

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

        if hasattr(game_data, "maps") and game_data.maps:
            for map_data in game_data.maps:
                if hasattr(map_data, "x") and hasattr(map_data, "y"):
                    strategic_locations.append({"target_x": map_data.x, "target_y": map_data.y})

        if hasattr(game_data, "resources") and game_data.resources:
            for resource in game_data.resources:
                if hasattr(resource, "x") and hasattr(resource, "y"):
                    strategic_locations.append({"target_x": resource.x, "target_y": resource.y})

        if hasattr(game_data, "monsters") and game_data.monsters:
            for monster in game_data.monsters:
                if hasattr(monster, "x") and hasattr(monster, "y"):
                    strategic_locations.append({"target_x": monster.x, "target_y": monster.y})

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
        movement_action = MovementAction(0, 0)

        for position in positions:
            x = position.get("target_x")
            y = position.get("target_y")

            if x is not None and y is not None:
                if movement_action.is_valid_position(x, y):
                    valid_positions.append(position)

        return valid_positions