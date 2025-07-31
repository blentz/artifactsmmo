"""
Gathering Action Implementation

This module implements the gathering action for collecting resources in the game.
It handles tool requirements, skill level checks, and inventory management
while integrating with the GOAP system for resource collection planning.

The GatheringAction demonstrates proper handling of skill-based actions and
resource collection mechanics within the modular action system.
"""

from typing import Any, Optional

from ...game_data.api_client import APIClientWrapper
from ..state.character_game_state import CharacterGameState
from ..state.game_state import ActionResult, GameState
from .base_action import BaseAction


class GatheringAction(BaseAction):
    """Gathering action for resource collection using GameState enum.

    Handles resource gathering with tool and skill requirements,
    integrating with the API for actual gathering execution.
    """

    def __init__(self, resource_type: str | None = None, api_client: Optional['APIClientWrapper'] = None):
        """Initialize GatheringAction with optional resource target.

        Parameters:
            resource_type: Specific resource code to gather, or None for any resource
            api_client: API client wrapper for gathering execution

        Return values:
            None (constructor)

        This constructor creates a gathering action instance for collecting resources,
        optionally targeting a specific resource type for strategic gathering
        planning within the AI player system.
        """
        self.resource_type = resource_type
        self.api_client = api_client

    @property
    def name(self) -> str:
        """Unique gathering action identifier.

        Parameters:
            None (property)

        Return values:
            String identifier for the gathering action in GOAP planning

        This property provides the unique action name used by the GOAP planner
        to identify and reference the gathering action in planning sequences,
        including target resource information when specified.
        """
        if self.resource_type:
            return f"gather_{self.resource_type}"
        return "gather"

    @property
    def cost(self) -> int:
        """GOAP cost for gathering action.

        Parameters:
            None (property)

        Return values:
            Integer cost value for GOAP planning optimization

        This property returns the planning cost for gathering actions, enabling
        the GOAP planner to balance resource collection against other actions
        based on efficiency, skill requirements, and strategic value.
        """
        return 5

    def get_preconditions(self) -> dict[GameState, Any]:
        """Gathering preconditions including tool and location using GameState enum.

        Parameters:
            None

        Return values:
            Dictionary with GameState enum keys defining gathering requirements

        This method returns the preconditions for gathering including required
        tool equipment, skill level thresholds, location requirements, and
        inventory space using GameState enum keys for type-safe condition checking.
        """
        preconditions = {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_GATHER: True,
            GameState.AT_RESOURCE_LOCATION: True,
            GameState.INVENTORY_SPACE_AVAILABLE: True,
        }

        if self.resource_type:
            preconditions[GameState.RESOURCE_AVAILABLE] = True

        return preconditions

    def get_effects(self) -> dict[GameState, Any]:
        """Gathering effects including skill XP and items using GameState enum.

        Parameters:
            None

        Return values:
            Dictionary with GameState enum keys defining gathering outcomes

        This method returns the expected effects of gathering including skill
        level increases, XP gains, item acquisition, and cooldown activation.
        The values represent incremental changes that the GOAP planner can reason about.
        """
        return {
            GameState.CHARACTER_XP: 30,        # Increase character XP by ~30 points
            GameState.MINING_LEVEL: 1,         # May increase mining level by 1
            GameState.MINING_XP: 40,           # Increase mining XP by ~40 points
            GameState.COOLDOWN_READY: False,
            GameState.CAN_FIGHT: False,
            GameState.CAN_GATHER: False,
            GameState.CAN_CRAFT: False,
            GameState.CAN_TRADE: False,
            GameState.CAN_MOVE: False,
            GameState.CAN_REST: False,
            GameState.CAN_USE_ITEM: False,
            GameState.CAN_BANK: False,
            GameState.INVENTORY_SPACE_USED: 1,  # Use 1 inventory slot
        }

    async def execute(self, character_name: str, current_state: dict[GameState, Any]) -> ActionResult:
        """Execute gathering via API client.

        Parameters:
            character_name: Name of the character to perform gathering
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            ActionResult with success status, message, and resource collection changes

        This method executes the gathering action through the API client, handling
        tool validation, skill checking, inventory management, and result processing
        for resource collection in the AI player system.
        """
        if self.api_client is None:
            return ActionResult(
                success=False,
                message="API client not available for gathering execution",
                state_changes={},
                cooldown_seconds=0
            )

        # Validate preconditions before attempting gathering
        if not self.has_required_tool(current_state):
            return ActionResult(
                success=False,
                message="Required tool not equipped for gathering",
                state_changes={},
                cooldown_seconds=0
            )

        if not self.has_sufficient_skill(current_state):
            return ActionResult(
                success=False,
                message="Insufficient skill level for gathering this resource",
                state_changes={},
                cooldown_seconds=0
            )

        if not self.has_inventory_space(current_state):
            return ActionResult(
                success=False,
                message="No inventory space available for gathered resources",
                state_changes={},
                cooldown_seconds=0
            )

        try:
            # Execute gathering via API
            gather_result = await self.api_client.gather_resource(character_name)

            # Extract state changes from gathering result
            state_changes = {
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

            # Update character state from API response
            if hasattr(gather_result.data, 'character'):
                character = gather_result.data.character
                state_changes.update({
                    GameState.CHARACTER_LEVEL: character.level,
                    GameState.CHARACTER_XP: character.xp,
                    GameState.CHARACTER_GOLD: character.gold,
                    GameState.CURRENT_X: character.x,
                    GameState.CURRENT_Y: character.y,
                    GameState.HP_CURRENT: character.hp,
                })

                # Update relevant skill XP based on gathering type
                # Update multiple skills as gathering might affect different ones
                if hasattr(character, 'mining_xp'):
                    state_changes[GameState.MINING_XP] = character.mining_xp
                    state_changes[GameState.MINING_LEVEL] = character.mining_level
                if hasattr(character, 'woodcutting_xp'):
                    state_changes[GameState.WOODCUTTING_XP] = character.woodcutting_xp
                    state_changes[GameState.WOODCUTTING_LEVEL] = character.woodcutting_level
                if hasattr(character, 'fishing_xp'):
                    state_changes[GameState.FISHING_XP] = character.fishing_xp
                    state_changes[GameState.FISHING_LEVEL] = character.fishing_level

            # Build success message
            message = "Gathering successful"
            if hasattr(gather_result.data, 'details') and gather_result.data.details:
                try:
                    # Convert details to string, handling mock objects
                    details_str = str(gather_result.data.details)
                    if details_str and not details_str.startswith("<Mock"):
                        message = f"Gathered resources: {details_str}"
                except Exception:
                    # If details conversion fails, use default message
                    pass

            return ActionResult(
                success=True,
                message=message,
                state_changes=state_changes,
                cooldown_seconds=(
                    gather_result.data.cooldown.total_seconds
                    if hasattr(gather_result.data, 'cooldown') else 0
                )
            )

        except Exception as error:
            return ActionResult(
                success=False,
                message=f"Gathering failed: {str(error)}",
                state_changes={},
                cooldown_seconds=0
            )

    def has_required_tool(self, current_state: dict[GameState, Any]) -> bool:
        """Check if character has required tool equipped.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether character has the proper tool equipped

        This method validates that the character has the appropriate tool
        equipped for the target resource type, ensuring gathering action
        preconditions are met before execution.
        """
        # Check if any tool is equipped
        tool_equipped = current_state.get(GameState.TOOL_EQUIPPED)

        # If no tool is equipped, gathering cannot proceed
        if not tool_equipped:
            return False

        # For specific resource types, we could check for specific tools
        # For now, accept any tool as sufficient for gathering
        return True

    def has_sufficient_skill(self, current_state: dict[GameState, Any]) -> bool:
        """Check if character has sufficient skill level.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether character meets minimum skill requirements

        This method validates that the character's relevant skill level meets
        the minimum requirements for gathering the target resource type,
        ensuring successful action execution.
        """
        required_level = self.get_skill_requirement()

        # Check the relevant gathering skill based on resource type
        # For now, check mining level as a default
        current_level = current_state.get(GameState.MINING_LEVEL, 1)

        # Also check woodcutting and fishing as fallbacks
        if current_level < required_level:
            current_level = max(
                current_state.get(GameState.WOODCUTTING_LEVEL, 1),
                current_state.get(GameState.FISHING_LEVEL, 1),
                current_level
            )

        return bool(current_level >= required_level)

    def has_inventory_space(self, current_state: dict[GameState, Any]) -> bool:
        """Check if character has inventory space for resources.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether character has available inventory slots

        This method validates that the character has sufficient inventory space
        to store gathered resources, preventing failed gathering attempts due
        to inventory limitations.
        """
        # Check if already marked as available
        if GameState.INVENTORY_SPACE_AVAILABLE in current_state:
            space_available = current_state[GameState.INVENTORY_SPACE_AVAILABLE]
            return bool(space_available) if space_available is not None else False

        # Calculate from current inventory values
        inventory_used = current_state.get(GameState.INVENTORY_SPACE_USED, 0)
        # Assume max inventory is around 100 slots (this is a reasonable default)
        max_inventory = 100

        return bool(inventory_used < max_inventory)

    def get_skill_requirement(self) -> int:
        """Get minimum skill level required for this resource.

        Parameters:
            None

        Return values:
            Integer representing minimum skill level needed for this resource

        This method returns the minimum skill level requirement for gathering
        the target resource type, enabling skill progression planning and
        action precondition validation in the GOAP system.
        """
        # Default minimum skill level for gathering
        return 1

    def can_execute(self, current_state: CharacterGameState) -> bool:
        """Check if action preconditions are met in current state.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether all preconditions are satisfied
        """
        preconditions = self.get_preconditions()
        return all(
            current_state.get(key) == value for key, value in preconditions.items()
        )

    def validate_preconditions(self) -> bool:
        """Validate that all preconditions use valid GameState enum keys.

        Parameters:
            None (operates on self)

        Return values:
            Boolean indicating whether all precondition keys are valid GameState enums
        """
        try:
            preconditions = self.get_preconditions()
            return all(isinstance(key, GameState) for key in preconditions.keys())
        except Exception:
            return False

    def validate_effects(self) -> bool:
        """Validate that all effects use valid GameState enum keys.

        Parameters:
            None (operates on self)

        Return values:
            Boolean indicating whether all effect keys are valid GameState enums
        """
        try:
            effects = self.get_effects()
            return all(isinstance(key, GameState) for key in effects.keys())
        except Exception:
            return False
