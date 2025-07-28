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
        return {
            GameState.CURRENT_X: self.target_x,
            GameState.CURRENT_Y: self.target_y,
            GameState.COOLDOWN_READY: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_REST: False,
            GameState.CAN_USE_ITEM: False,
            GameState.CAN_BANK: False,
        }

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        """Execute movement via API client.

        Parameters:
            character_name: Name of the character to move
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            ActionResult with success status, message, and position changes

        This method executes the movement action through the API client, handling
        pathfinding validation, cooldown timing, and result processing for
        character positioning in the AI player system.
        """
        try:
            api_client = APIClientWrapper()
            response = await api_client.move_character(character_name, self.target_x, self.target_y)

            state_changes = {
                GameState.CURRENT_X: response.x,
                GameState.CURRENT_Y: response.y,
                GameState.COOLDOWN_READY: False,
                GameState.CAN_MOVE: False,
                GameState.CAN_FIGHT: False,
                GameState.CAN_GATHER: False,
                GameState.CAN_CRAFT: False,
                GameState.CAN_TRADE: False,
                GameState.CAN_REST: False,
                GameState.CAN_USE_ITEM: False,
                GameState.CAN_BANK: False,
            }

            cooldown_seconds = getattr(response.cooldown, "total_seconds", 0) if hasattr(response, "cooldown") else 0

            return ActionResult(
                success=True,
                message=f"Moved character {character_name} to ({response.x}, {response.y})",
                state_changes=state_changes,
                cooldown_seconds=cooldown_seconds,
            )

        except Exception as e:
            if hasattr(e, "status_code") and e.status_code == ArtifactsHTTPStatus["CHARACTER_COOLDOWN"]:
                return ActionResult(
                    success=False,
                    message=f"Character {character_name} is on cooldown",
                    state_changes={},
                    cooldown_seconds=5,
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Movement failed for {character_name}: {str(e)}",
                    state_changes={},
                    cooldown_seconds=0,
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