"""
Rest Action Implementation

This module implements the rest action for HP recovery in the game.
It handles HP threshold checking, safe location validation, and recovery
timing while integrating with the GOAP system for survival planning.

The RestAction demonstrates proper handling of character survival mechanics
and emergency recovery within the modular action system.
"""

from typing import Any, Optional

from ...game_data.api_client import APIClientWrapper
from ..state.action_result import ActionResult, GameState
from ..state.character_game_state import CharacterGameState
from .base_action import BaseAction


class RestAction(BaseAction):
    """Rest action for HP recovery using GameState enum.

    Handles character resting with HP threshold and safety requirements,
    integrating with the API for actual rest execution.
    """

    def __init__(self):
        """Initialize RestAction for HP recovery operations.

        Parameters:
            None

        Return values:
            None (constructor)

        This constructor initializes the RestAction with default HP thresholds
        and safety requirements for character survival and recovery operations
        within the AI player system.
        """
        self.hp_threshold = 0.3  # Rest when HP drops below 30%
        self.safe_hp_threshold = 0.5  # Consider safe when above 50%

    @property
    def name(self) -> str:
        """Unique rest action identifier.

        Parameters:
            None (property)

        Return values:
            String identifier for the rest action in GOAP planning

        This property provides the unique action name used by the GOAP planner
        to identify and reference the rest action in planning sequences and
        action execution workflows.
        """
        return "rest"

    @property
    def cost(self) -> int:
        """GOAP cost for rest action.

        Parameters:
            None (property)

        Return values:
            Integer cost value for GOAP planning optimization

        This property returns the planning cost for the rest action, enabling
        the GOAP planner to optimize action sequences by considering the
        relative cost of resting versus other available actions.
        """
        return 5

    def get_preconditions(self) -> dict[GameState, Any]:
        """Rest preconditions including HP threshold using GameState enum.

        Parameters:
            None

        Return values:
            Dictionary with GameState enum keys defining rest requirements

        This method returns the preconditions for resting including low HP
        threshold, safe location requirements, and cooldown readiness using
        GameState enum keys for type-safe condition checking.
        """
        return {
            GameState.COOLDOWN_READY: True,
            GameState.CAN_REST: True,
        }

    def get_effects(self) -> dict[GameState, Any]:
        """Rest effects including HP recovery using GameState enum.

        Parameters:
            None

        Return values:
            Dictionary with GameState enum keys defining rest outcomes

        This method returns the expected effects of resting including HP
        recovery, cooldown activation, and safety state changes using
        GameState enum keys for type-safe effect specification.
        """
        return {
            # Only declare effects we can guarantee - HP amount is determined by API
            GameState.HP_LOW: False,
            GameState.HP_CRITICAL: False,
            GameState.SAFE_TO_FIGHT: True,
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


    def needs_rest(self, current_state: dict[GameState, Any]) -> bool:
        """Check if character HP is below threshold.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether character needs to rest for HP recovery

        This method evaluates the character's current HP against safety
        thresholds to determine if immediate rest is required for survival
        and continued operation in the AI player system.
        """
        # Check if already marked as needing rest
        if GameState.HP_LOW in current_state:
            return bool(current_state[GameState.HP_LOW])

        # Calculate from current HP values
        current_hp = current_state.get(GameState.HP_CURRENT, 0)
        max_hp = current_state.get(GameState.HP_MAX, 1)

        if current_hp <= 0 or max_hp <= 0:
            return True  # Need rest if no HP or invalid data

        # Check if HP is below threshold
        hp_percentage = current_hp / max_hp
        return hp_percentage < self.hp_threshold

    def is_safe_location(self, current_state: dict[GameState, Any]) -> bool:
        """Check if current location is safe for resting.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether current location allows safe resting

        This method evaluates the character's current location for safety
        factors such as absence of monsters and proximity to safe zones,
        ensuring rest can be performed without interruption or danger.
        """
        # Check if location is explicitly marked as safe
        if GameState.AT_SAFE_LOCATION in current_state:
            return bool(current_state[GameState.AT_SAFE_LOCATION])

        # Check for danger indicators
        if current_state.get(GameState.IN_COMBAT, False):
            return False  # Not safe if in combat

        if current_state.get(GameState.ENEMY_NEARBY, False):
            return False  # Not safe if enemies nearby

        # If no danger indicators and no explicit safe location marker,
        # assume safe (conservative approach for rest action)
        return True

    def calculate_rest_time(self, current_state: dict[GameState, Any]) -> int:
        """Calculate estimated rest time for full recovery.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Integer representing estimated seconds for full HP recovery

        This method calculates the expected time required for the character
        to fully recover HP through resting, enabling accurate planning
        and scheduling within the AI player action sequences.
        """
        current_hp = current_state.get(GameState.HP_CURRENT, 0)
        max_hp = current_state.get(GameState.HP_MAX, 1)

        if current_hp <= 0 or max_hp <= 0:
            return 60  # Default rest time if invalid data

        if current_hp >= max_hp:
            return 0  # No rest needed if already at full HP

        # Calculate HP to recover
        hp_to_recover = max_hp - current_hp

        # Estimate based on game mechanics (approximate 1 HP per 6 seconds)
        # This is a reasonable estimate - actual time may vary based on game balance
        base_recovery_rate = 6  # seconds per HP point

        estimated_time = hp_to_recover * base_recovery_rate

        # Cap the maximum rest time to something reasonable (10 minutes)
        return min(estimated_time, 600)

    def get_hp_percentage(self, current_state: dict[GameState, Any]) -> float:
        """Calculate current HP as percentage of max HP.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Float representing current HP as percentage (0.0 to 1.0)

        This method calculates the character's HP percentage for threshold
        evaluation and emergency assessment, enabling precise survival
        monitoring and priority-based rest scheduling in the AI player.
        """
        current_hp = current_state.get(GameState.HP_CURRENT, 0)
        max_hp = current_state.get(GameState.HP_MAX, 1)

        if max_hp <= 0:
            return 0.0  # Return 0% if invalid max HP

        # Calculate percentage and clamp between 0.0 and 1.0
        percentage = current_hp / max_hp
        return max(0.0, min(1.0, percentage))

    async def _execute_api_call(
        self,
        character_name: str,
        current_state: dict[GameState, Any],
        api_client: 'APIClientWrapper',
        cooldown_manager: Optional['CooldownManager']
    ) -> ActionResult:
        """Execute rest via API client.
        
        Parameters:
            character_name: Name of the character to rest
            current_state: Dictionary with GameState enum keys and current values
            api_client: API client for making the rest call
            cooldown_manager: Optional cooldown manager for tracking cooldowns
            
        Return values:
            ActionResult with actual rest result from API
            
        This method makes the actual API call to rest and handles
        the response, updating cooldowns and returning the real state changes.
        """
        # Make the actual API call to rest
        rest_result = await api_client.rest_character(character_name)

        if rest_result:
            # Update cooldown if manager provided and cooldown data exists
            if cooldown_manager and hasattr(rest_result, 'cooldown'):
                cooldown_manager.update_cooldown(character_name, rest_result.cooldown)

            # Build state changes based on successful rest
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
            if hasattr(rest_result, 'character'):
                character = rest_result.character
                # Use comprehensive state extraction
                character_states = self._extract_character_state(character)
                state_changes.update(character_states)

            # Get cooldown duration
            cooldown_seconds = 0
            if hasattr(rest_result, 'cooldown'):
                cooldown_seconds = rest_result.cooldown.total_seconds

            # Build success message
            message = "Rest successful"
            if hasattr(rest_result, 'character'):
                message = f"Rest successful: HP restored to {rest_result.character.hp}/{rest_result.character.max_hp}"

            return ActionResult(
                success=True,
                message=message,
                state_changes=state_changes,
                cooldown_seconds=cooldown_seconds
            )
        else:
            return ActionResult(
                success=False,
                message="Rest failed: No response from API",
                state_changes={},
                cooldown_seconds=0
            )

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
        preconditions = self.get_preconditions()
        return all(isinstance(key, GameState) for key in preconditions.keys())

    def validate_effects(self) -> bool:
        """Validate that all effects use valid GameState enum keys.

        Parameters:
            None (operates on self)

        Return values:
            Boolean indicating whether all effect keys are valid GameState enums
        """
        effects = self.get_effects()
        return all(isinstance(key, GameState) for key in effects.keys())
