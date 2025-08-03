"""
Movement Action Implementation

This module implements the movement action for the GOAP system, serving as the
primary action for character positioning and pathfinding within the game world.

The MovementAction demonstrates proper BaseAction implementation using GameState
enum for type safety and integration with the API client for actual execution.
"""

from typing import Any, Optional

from ..state.action_result import ActionResult, GameState
from .base_action import BaseAction


class MovementAction(BaseAction):
    """Movement action implementation using GameState enum for type safety.

    This action moves the character to specific coordinates and serves as
    a template for other action implementations in the modular system.
    """

    def __init__(self, target_x: int, target_y: int, location_type: str = None):
        """Initialize MovementAction with target coordinates and content type.

        Parameters:
            target_x: X coordinate of the target destination
            target_y: Y coordinate of the target destination
            location_type: Type of content at destination ('monster', 'resource', etc.)

        Return values:
            None (constructor)

        This constructor creates a movement action instance for the specified
        target coordinates with optional location content information for
        proper state flag management after movement.
        """
        self.target_x = target_x
        self.target_y = target_y
        self._location_type = location_type

    @property
    def name(self) -> str:
        """Unique movement action identifier"""
        return f"move_to_{self.target_x}_{self.target_y}"

    @property
    def cost(self) -> int:
        """GOAP cost for movement action.

        Parameters:
            None (property)

        Return values:
            Integer cost value for GOAP planning

        Movement actions have a standard cost since the GOAP planner
        will evaluate different paths based on the overall plan cost.
        Specific distance optimization is handled by the action factory
        generating appropriate nearby targets.
        """
        return 1

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
        return {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_MOVE: True
        }

    def can_execute(self, current_state: dict[GameState, Any]) -> bool:
        """Override can_execute to include location check.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether movement action can be executed

        This method adds location-specific validation to ensure the character
        is not already at the target location, preventing unnecessary API calls
        and HTTP 490 "CHARACTER_ALREADY_MAP" errors.
        """
        # First check basic preconditions from parent class
        if not super().can_execute(current_state):
            return False

        # Check if character is not already at target location
        current_x = current_state.get(GameState.CURRENT_X, 0)
        current_y = current_state.get(GameState.CURRENT_Y, 0)

        # Only allow movement if we're not already at the target
        is_not_at_target = (current_x != self.target_x or current_y != self.target_y)

        return is_not_at_target

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
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_REST: False,
            GameState.CAN_USE_ITEM: False,
            GameState.CAN_BANK: False,
        }

        # Set location-specific flags based on target coordinates
        # These will be dynamically set by MovementActionFactory based on map content
        if hasattr(self, '_location_type'):
            if self._location_type == 'monster':
                effects[GameState.AT_MONSTER_LOCATION] = True
                effects[GameState.AT_SAFE_LOCATION] = False
                effects[GameState.XP_SOURCE_AVAILABLE] = True
                effects[GameState.ENEMY_NEARBY] = True
            elif self._location_type == 'resource':
                effects[GameState.AT_RESOURCE_LOCATION] = True
                effects[GameState.XP_SOURCE_AVAILABLE] = True
            elif self._location_type == 'workshop':
                effects[GameState.XP_SOURCE_AVAILABLE] = True

        return effects

    async def _execute_api_call(
        self,
        character_name: str,
        current_state: dict[GameState, Any],
        api_client: 'APIClientWrapper',
        cooldown_manager: Optional['CooldownManager']
    ) -> ActionResult:
        """Execute movement via API client.

        Parameters:
            character_name: Name of the character to move
            current_state: Dictionary with GameState enum keys and current values
            api_client: API client for making the movement call
            cooldown_manager: Optional cooldown manager for tracking cooldowns

        Return values:
            ActionResult with actual movement result from API

        This method makes the actual API call to move the character and handles
        the response, updating cooldowns and returning the real state changes.
        """
        # Make the actual API call
        movement_result = await api_client.move_character(character_name, self.target_x, self.target_y)

        if movement_result.success:
            # Update cooldown if manager provided
            if cooldown_manager and movement_result.cooldown:
                cooldown_manager.update_cooldown(character_name, movement_result.cooldown)

            # Build state changes based on successful movement
            state_changes = {
                GameState.CURRENT_X: self.target_x,
                GameState.CURRENT_Y: self.target_y,
                GameState.COOLDOWN_READY: False,
                GameState.CAN_FIGHT: False,
                GameState.CAN_GATHER: False,
                GameState.CAN_CRAFT: False,
                GameState.CAN_TRADE: False,
                GameState.CAN_MOVE: False,
                GameState.CAN_REST: False,
                GameState.CAN_USE_ITEM: False,
                GameState.CAN_BANK: False,
            }

            # Set location-specific flags if available
            if hasattr(self, '_location_type'):
                if self._location_type == 'monster':
                    state_changes[GameState.AT_MONSTER_LOCATION] = True
                    state_changes[GameState.AT_SAFE_LOCATION] = False
                    state_changes[GameState.XP_SOURCE_AVAILABLE] = True
                elif self._location_type == 'resource':
                    state_changes[GameState.AT_RESOURCE_LOCATION] = True
                    state_changes[GameState.XP_SOURCE_AVAILABLE] = True
                elif self._location_type == 'workshop':
                    state_changes[GameState.XP_SOURCE_AVAILABLE] = True

            return ActionResult(
                success=True,
                message=f"Successfully moved to ({self.target_x}, {self.target_y})",
                state_changes=state_changes,
                cooldown_seconds=movement_result.cooldown.total_seconds if movement_result.cooldown else 0
            )
        else:
            # Movement failed
            return ActionResult(
                success=False,
                message=f"Failed to move: {movement_result.message}",
                state_changes={},
                cooldown_seconds=0
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
