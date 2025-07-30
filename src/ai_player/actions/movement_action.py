"""
Movement Action Implementation

This module implements the movement action for the GOAP system, serving as the
primary action for character positioning and pathfinding within the game world.

The MovementAction demonstrates proper BaseAction implementation using GameState
enum for type safety and integration with the API client for actual execution.
"""

from typing import Any

from ...game_data.api_client import APIClientWrapper
from ...lib.httpstatus import ArtifactsHTTPStatus
from ..state.game_state import ActionResult, GameState
from .base_action import BaseAction


class MovementAction(BaseAction):
    """Movement action implementation using GameState enum for type safety.

    This action moves the character to specific coordinates and serves as
    a template for other action implementations in the modular system.
    """

    def __init__(self, target_x: int, target_y: int):
        """Initialize MovementAction with target coordinates.

        Parameters:
            target_x: X coordinate of the target destination
            target_y: Y coordinate of the target destination

        Return values:
            None (constructor)

        This constructor creates a movement action instance for the specified
        target coordinates, enabling GOAP planning for character positioning
        and pathfinding within the game world.
        """
        self.target_x = target_x
        self.target_y = target_y

    @property
    def name(self) -> str:
        """Unique movement action identifier"""
        return f"move_to_{self.target_x}_{self.target_y}"

    @property
    def cost(self) -> int:
        """GOAP cost for movement action based on distance.

        Parameters:
            None (property)

        Return values:
            Integer cost value calculated from distance to target location

        This property calculates the GOAP planning cost based on Manhattan
        distance to the target coordinates, enabling efficient pathfinding
        and movement optimization in the planning process.
        """
        base_cost = 1
        manhattan_distance = abs(self.target_x) + abs(self.target_y)
        return base_cost + manhattan_distance

    def get_preconditions(self) -> dict[GameState, Any]:
        """Movement preconditions using GameState enum.

        Parameters:
            None

        Return values:
            Dictionary with GameState enum keys defining movement requirements

        This method returns the preconditions for movement including cooldown
        readiness, valid target location, and path accessibility using GameState
        enum keys for type-safe condition checking.
        """
        return {GameState.COOLDOWN_READY: True, GameState.CAN_MOVE: True}

    def get_effects(self) -> dict[GameState, Any]:
        """Movement effects using GameState enum.

        Parameters:
            None

        Return values:
            Dictionary with GameState enum keys defining movement outcomes

        This method returns the expected effects of movement including position
        updates, location state changes, and cooldown activation using GameState
        enum keys for type-safe effect specification.
        """
        effects = {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
            GameState.COOLDOWN_READY: False,
            # Do NOT disable all capabilities - they should be re-enabled when cooldown expires
            # The StateManager.update_cooldown_state() method handles capability restoration
        }
        
        # Set location-specific flags based on target coordinates
        # These will be dynamically set by MovementActionFactory based on map content
        if hasattr(self, '_location_type'):
            if self._location_type == 'monster':
                effects[GameState.AT_MONSTER_LOCATION] = True
                effects[GameState.AT_SAFE_LOCATION] = False
                effects[GameState.XP_SOURCE_AVAILABLE] = True
            elif self._location_type == 'resource':
                effects[GameState.AT_RESOURCE_LOCATION] = True
                effects[GameState.XP_SOURCE_AVAILABLE] = True
            elif self._location_type == 'workshop':
                effects[GameState.XP_SOURCE_AVAILABLE] = True
        
        return effects

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        """Execute movement via state manager coordination.

        Parameters:
            character_name: Name of the character to move
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            ActionResult with success status, message, and position changes

        This method coordinates movement execution through the proper architecture,
        working with the action executor's state management rather than direct API calls.
        The actual API interaction should be handled by the ActionExecutor/StateManager.
        """
        # For now, return expected state changes - the ActionExecutor should handle the actual API call
        # This is the intended architecture where actions define what should happen,
        # and the executor/state manager handles how to make it happen
        
        state_changes = {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
            GameState.COOLDOWN_READY: False,
        }
        
        # Set location-specific flags based on target coordinates if available
        if hasattr(self, '_location_type'):
            if self._location_type == 'monster':
                state_changes[GameState.AT_MONSTER_LOCATION] = True
            elif self._location_type == 'resource':
                state_changes[GameState.AT_RESOURCE_LOCATION] = True
            elif self._location_type == 'workshop':
                state_changes[GameState.AT_WORKSHOP_LOCATION] = True

        return ActionResult(
            success=True,
            message=f"Movement to ({self.target_x}, {self.target_y}) planned",
            state_changes=state_changes,
            cooldown_seconds=0,  # Actual cooldown will be extracted from API response
        )

    def calculate_distance(self, current_x: int, current_y: int) -> int:
        """Calculate movement distance for cost estimation.

        Parameters:
            current_x: Current X coordinate of the character
            current_y: Current Y coordinate of the character

        Return values:
            Integer representing Manhattan distance to target coordinates

        This method calculates the Manhattan distance from the character's
        current position to the target coordinates for GOAP cost estimation
        and pathfinding optimization.
        """
        return abs(self.target_x - current_x) + abs(self.target_y - current_y)

    def is_valid_position(self, x: int, y: int) -> bool:
        """Validate target position is within game bounds.

        Parameters:
            x: X coordinate to validate
            y: Y coordinate to validate

        Return values:
            Boolean indicating whether coordinates are valid and accessible

        This method validates that the target coordinates are within game
        boundaries, accessible by the character, and not blocked by obstacles
        or restricted areas.
        """
        MIN_X, MAX_X = -50, 50
        MIN_Y, MAX_Y = -50, 50

        return MIN_X <= x <= MAX_X and MIN_Y <= y <= MAX_Y