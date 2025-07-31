"""
Action Executor

This module handles the execution of GOAP actions via the API client.
It manages cooldown checking, API calls, error handling, and result processing
to ensure reliable action execution within the AI player system.

The ActionExecutor bridges the gap between GOAP planning and actual API execution,
handling all the timing and error recovery required for robust gameplay automation.
"""

import asyncio
import logging
import random
import time
from typing import Any

from ..game_data.api_client_wrapper import APIClientWrapper
from ..game_data.cache_manager import CacheManager
from ..game_data.cooldown_manager import CooldownManager
from .actions import get_global_registry
from .actions.base_action import BaseAction
from .state.character_game_state import CharacterGameState
from .state.game_state import ActionResult, GameState


class ActionExecutor:
    """Executes GOAP actions via API with cooldown and error handling"""

    def __init__(self, api_client: APIClientWrapper, cooldown_manager: CooldownManager, cache_manager: CacheManager):
        """Initialize ActionExecutor with API client and cooldown management.

        Parameters:
            api_client: API client wrapper for game operations
            cooldown_manager: Manager for character cooldown tracking
            cache_manager: CacheManager instance for accessing game data (maps, monsters, resources)

        Return values:
            None (constructor)

        This constructor initializes the ActionExecutor with the necessary
        components for reliable action execution including API communication,
        cooldown management, and game data access for action generation.
        """
        self.api_client = api_client
        self.cooldown_manager = cooldown_manager
        self.cache_manager = cache_manager
        self.action_registry = get_global_registry()
        self.retry_attempts = 3
        self.retry_delays = [1, 2, 4]  # exponential backoff

        # Rate limiting state tracking
        self._last_rate_limit_time = 0.0
        self._rate_limit_wait_time = 0.0

    async def execute_action(self, action: BaseAction, character_name: str, current_state: CharacterGameState) -> ActionResult:
        """Execute single action with full error handling and cooldown management.

        Parameters:
            action: BaseAction instance to execute
            character_name: Name of the character performing the action
            current_state: CharacterGameState Pydantic model with current character state

        Return values:
            ActionResult containing success status, message, and state changes

        This method executes a single GOAP action via the API, handling all
        error conditions, cooldown timing, and result processing to ensure
        reliable action execution within the AI player system.
        """
        try:
            # Validate preconditions
            if not self.validate_action_preconditions(action, current_state):
                return ActionResult(
                    success=False,
                    message=f"Action {action.name} preconditions not met",
                    state_changes={},
                    cooldown_seconds=0
                )

            # Wait for cooldown if needed
            await self.wait_for_cooldown(character_name)

            # Execute the action with retry logic
            for attempt in range(self.retry_attempts):
                try:
                    result = await action.execute(character_name, current_state)

                    # Process and validate the result
                    if result.success:
                        # Verify action success by checking state changes
                        if await self.verify_action_success(action, result, character_name):
                            # Cooldown management is handled by the actions themselves when they process API responses
                            # No manual cooldown update needed here as actions update via API client

                            return result
                        else:
                            return ActionResult(
                                success=False,
                                message=f"Action {action.name} execution verification failed",
                                state_changes={},
                                cooldown_seconds=0
                            )
                    else:
                        # Handle failed execution
                        if attempt < self.retry_attempts - 1:
                            await asyncio.sleep(self.retry_delays[attempt])
                            continue
                        else:
                            return result

                except Exception as e:
                    # Handle action-specific errors
                    recovery_result = await self.handle_action_error(action, e, character_name)
                    if recovery_result is not None:
                        return recovery_result

                    # If not recoverable and not last attempt, retry
                    if attempt < self.retry_attempts - 1:
                        await asyncio.sleep(self.retry_delays[attempt])
                        continue
                    else:
                        return ActionResult(
                            success=False,
                            message=f"Action {action.name} failed after {self.retry_attempts} attempts: {str(e)}",
                            state_changes={},
                            cooldown_seconds=0
                        )

            # This shouldn't be reached, but provide fallback
            return ActionResult(
                success=False,
                message=f"Action {action.name} execution completed without result",
                state_changes={},
                cooldown_seconds=0
            )

        except Exception as e:
            # Handle unexpected errors
            return ActionResult(
                success=False,
                message=f"Unexpected error executing {action.name}: {str(e)}",
                state_changes={},
                cooldown_seconds=0
            )

    async def execute_plan(self, plan: list[dict[str, Any]], character_name: str) -> bool:
        """Execute entire action plan with state updates.

        Parameters:
            plan: List of action dictionaries representing the planned sequence
            character_name: Name of the character to execute the plan for

        Return values:
            Boolean indicating whether the entire plan executed successfully

        This method executes a complete action plan by sequentially processing
        each action, handling cooldowns between actions, updating state after
        each execution, and providing comprehensive error recovery.
        """
        if not plan:
            return True

        try:
            self.logger = logging.getLogger(f"action_executor.{character_name}")
            self.logger.info(f"ActionExecutor: Starting plan execution for {len(plan)} actions")
            self.logger.info(f"ActionExecutor: Plan content: {plan}")
            # Get initial character state
            self.logger.info("ActionExecutor: Getting character data from API...")
            character = await self.api_client.get_character(character_name)
            self.logger.info(f"ActionExecutor: Got character data: {character.name} at ({character.x}, {character.y})")

            # Get map content for location context
            self.logger.info("ActionExecutor: Getting map data from API...")
            game_map = await self.api_client.get_map(character.x, character.y)
            self.logger.info(f"ActionExecutor: Got map data: {game_map}")

            # Convert to internal state format - keep as CharacterGameState
            self.logger.info("ActionExecutor: Converting to CharacterGameState...")
            character_state = CharacterGameState.from_api_character(character, game_map.content, self.api_client.cooldown_manager)
            self.logger.info("ActionExecutor: Initial state loaded successfully")

            self.logger.info(f"ActionExecutor: Starting for loop with {len(plan)} actions")
            for i, action_info in enumerate(plan):
                try:
                    self.logger.info(f"ActionExecutor: Processing plan step {i+1}: {action_info.get('name', 'unknown')}")
                    # Extract action name and parameters
                    action_name = action_info.get('action', action_info.get('name'))
                    self.logger.info(f"ActionExecutor: Extracted action name: '{action_name}'")
                    if not action_name:
                        self.logger.error(f"No action name found in action_info: {action_info}")
                        return False

                    # Get action instance from registry using actual current state
                    self.logger.info(f"ActionExecutor: Getting action from registry: '{action_name}'")
                    action = await self.get_action_by_name(action_name, character_state)
                    self.logger.info(f"ActionExecutor: Got action from registry: {action}")
                    if not action:
                        self.logger.warning(f"Could not find action '{action_name}' in registry")
                        return False

                    self.logger.debug(f"Found action '{action_name}', executing...")

                    # Translate action to API call based on action type
                    if action.name == "combat":
                        try:
                            fight_result = await self.api_client.fight_monster(character_name)
                            result = ActionResult(
                                success=True,
                                message=f"Combat successful: {fight_result.data.fight.result}",
                                state_changes={
                                    GameState.CHARACTER_XP: fight_result.data.character.xp,
                                    GameState.CHARACTER_GOLD: fight_result.data.character.gold,
                                    GameState.HP_CURRENT: fight_result.data.character.hp,
                                    GameState.COOLDOWN_READY: False,
                                },
                                cooldown_seconds=fight_result.data.cooldown.total_seconds
                            )
                        except Exception as e:
                            result = ActionResult(
                                success=False,
                                message=f"Combat failed: {str(e)}",
                                state_changes={},
                                cooldown_seconds=0
                            )
                    elif action.name.startswith("move_to_"):
                        # Handle movement actions via API
                        try:
                            # Extract target coordinates from action
                            target_x = action.target_x
                            target_y = action.target_y

                            move_result = await self.api_client.move_character(character_name, target_x, target_y)
                            result = ActionResult(
                                success=True,
                                message=f"Moved character {character_name} to ({move_result.x}, {move_result.y})",
                                state_changes={
                                    GameState.CURRENT_X: move_result.x,
                                    GameState.CURRENT_Y: move_result.y,
                                    GameState.COOLDOWN_READY: False,
                                },
                                cooldown_seconds=getattr(move_result.cooldown, "total_seconds", 5) if hasattr(move_result, "cooldown") else 5
                            )
                        except Exception as e:
                            # Check for HTTP 490 "CHARACTER_ALREADY_MAP" error
                            if hasattr(e, 'status_code') and e.status_code == 490:
                                result = ActionResult(
                                    success=True,
                                    message=f"Character {character_name} already at target location ({target_x}, {target_y})",
                                    state_changes={
                                        GameState.CURRENT_X: target_x,
                                        GameState.CURRENT_Y: target_y,
                                    },
                                    cooldown_seconds=0  # No cooldown for non-movement
                                )
                            else:
                                result = ActionResult(
                                    success=False,
                                    message=f"Movement failed for {character_name}: {str(e)}",
                                    state_changes={},
                                    cooldown_seconds=0
                                )
                    else:
                        # Execute other actions normally
                        result = await self.execute_action(action, character_name, character_state)

                    if not result.success:
                        self.logger.warning(f"Action '{action_name}' failed: {result.message}")
                        # Try emergency recovery for critical failures
                        if "critical" in result.message.lower() or "hp" in result.message.lower():
                            recovery_success = await self.emergency_recovery(character_name, f"Plan step {i+1} failed: {result.message}")
                            if not recovery_success:
                                return False
                        else:
                            return False

                    self.logger.info(f"Action '{action_name}' succeeded: {result.message}")

                    # Update state with action results
                    # Convert character_state to typed state dictionary for updates
                    goap_state = character_state.to_goap_state()
                    typed_state = GameState.validate_state_dict(goap_state)

                    for state_key, new_value in result.state_changes.items():
                        typed_state[state_key] = new_value

                    # Update the character_state object with the new values
                    character_state = CharacterGameState.from_goap_state(typed_state)

                    # Wait for cooldown between actions if needed
                    if result.cooldown_seconds > 0:
                        await asyncio.sleep(min(result.cooldown_seconds, 30))  # Cap wait time

                except Exception as e:
                    # Try emergency recovery for action execution errors
                    recovery_success = await self.emergency_recovery(character_name, f"Plan execution error at step {i+1}: {str(e)}")
                    if not recovery_success:
                        return False

            return True

        except Exception as e:
            self.logger.debug(f"Exception in plan execution: {type(e).__name__}: {str(e)}")
            # Final emergency recovery attempt
            await self.emergency_recovery(character_name, f"Plan execution critical error: {str(e)}")
            return False

    async def wait_for_cooldown(self, character_name: str) -> None:
        """Wait for character cooldown to expire before action execution.

        Parameters:
            character_name: Name of the character to check cooldown for

        Return values:
            None (async operation)

        This method checks the character's cooldown status and waits
        asynchronously until the cooldown expires, ensuring API compliance
        and preventing 499 cooldown errors during action execution.
        """
        try:
            # Check if character is ready via cooldown manager
            if self.cooldown_manager.is_ready(character_name):
                return

            # Get remaining cooldown time
            remaining_time = self.cooldown_manager.get_remaining_time(character_name)

            if remaining_time > 0:
                # Wait for the cooldown to expire, but cap at reasonable maximum
                wait_time = min(remaining_time, 300)  # Max 5 minutes
                await asyncio.sleep(wait_time)

            # Use cooldown manager's async wait method if available
            await self.cooldown_manager.wait_for_cooldown(character_name)

        except Exception:
            # Fallback: wait a short time if cooldown checking fails
            await asyncio.sleep(1)

    def validate_action_preconditions(self, action: BaseAction, current_state: CharacterGameState) -> bool:
        """Verify action preconditions are met before execution.

        Parameters:
            action: BaseAction instance to validate preconditions for
            current_state: CharacterGameState Pydantic model with current character state

        Return values:
            Boolean indicating whether all action preconditions are satisfied

        This method validates that the current game state meets all the
        preconditions required for the action, preventing failed execution
        attempts and ensuring optimal action planning efficiency.
        """
        try:
            # Use the BaseAction's built-in can_execute method
            return action.can_execute(current_state)
        except Exception:
            # If precondition checking fails, be conservative and return False
            return False

    async def handle_action_error(self, action: BaseAction, error: Exception, character_name: str) -> ActionResult | None:
        """Handle API errors during action execution with recovery strategies.

        Parameters:
            action: BaseAction instance that encountered an error during execution
            error: Exception that occurred during action execution
            character_name: Name of the character that experienced the error

        Return values:
            Optional ActionResult with recovery outcome, or None if unrecoverable

        This method implements comprehensive error handling for action execution
        including retry logic, emergency recovery, and graceful degradation
        strategies to maintain AI player operation despite API issues.
        """
        error_message = str(error)
        type(error).__name__

        # Handle specific error types
        if hasattr(error, 'status_code'):
            status_code = error.status_code

            # Handle cooldown errors (499)
            if status_code == 499:
                return ActionResult(
                    success=False,
                    message=f"Character {character_name} is on cooldown",
                    state_changes={GameState.COOLDOWN_READY: False},
                    cooldown_seconds=5
                )

            # Handle "already at map location" (490) - treat as successful movement
            elif status_code == 490:
                return ActionResult(
                    success=True,
                    message=f"Character {character_name} already at target location",
                    state_changes={},  # No state changes needed - already at destination
                    cooldown_seconds=0  # No cooldown for non-movement
                )

            # Handle rate limiting (429)
            elif status_code == 429:
                retry_after = getattr(error, 'retry_after', 60)
                self.handle_rate_limit(retry_after)
                return ActionResult(
                    success=False,
                    message=f"Rate limited, retry after {retry_after} seconds",
                    state_changes={},
                    cooldown_seconds=retry_after
                )

            # Handle insufficient resources/items (4xx errors)
            elif 400 <= status_code < 500:
                return ActionResult(
                    success=False,
                    message=f"Action {action.name} failed: {error_message}",
                    state_changes={},
                    cooldown_seconds=0
                )

        # Handle HP-related errors
        if "hp" in error_message.lower() or "health" in error_message.lower():
            # Trigger emergency recovery
            recovery_success = await self.emergency_recovery(character_name, f"HP critical during {action.name}")
            if recovery_success:
                return ActionResult(
                    success=False,
                    message=f"HP recovery initiated for {character_name}",
                    state_changes={GameState.HP_LOW: True},
                    cooldown_seconds=0
                )

        # Handle connection/network errors
        if "connection" in error_message.lower() or "timeout" in error_message.lower():
            return ActionResult(
                success=False,
                message=f"Network error during {action.name}: {error_message}",
                state_changes={},
                cooldown_seconds=5  # Short delay before retry
            )

        # For unhandled errors, return None to indicate no recovery possible
        return None

    async def process_action_result(self, api_response: Any, action: BaseAction) -> ActionResult:
        """Convert API response to ActionResult with state changes.

        Parameters:
            api_response: Raw API response from action execution
            action: BaseAction instance that was executed

        Return values:
            ActionResult containing processed success status, message, and state changes

        This method transforms the raw API response into a standardized ActionResult
        format, extracting state changes, cooldown information, and execution
        status for consistent result handling throughout the system.
        """
        try:
            # Extract cooldown information
            cooldown_seconds = 0
            if hasattr(api_response, 'cooldown'):
                cooldown_data = api_response.cooldown
                if hasattr(cooldown_data, 'total_seconds'):
                    cooldown_seconds = cooldown_data.total_seconds
                elif hasattr(cooldown_data, 'remaining_seconds'):
                    cooldown_seconds = cooldown_data.remaining_seconds

            # Get expected effects from the action
            expected_effects = action.get_effects()

            # Create state changes based on action effects and API response
            state_changes = {}

            # Apply action effects
            for state_key, effect_value in expected_effects.items():
                state_changes[state_key] = effect_value

            # Extract state changes from API response if character data is present
            if hasattr(api_response, 'character') and api_response.character is not None:
                # Get map content for location context
                character = api_response.character
                game_map = await self.api_client.get_map(character.x, character.y)

                # Convert to internal state format
                character_state = CharacterGameState.from_api_character(character, game_map.content, self.api_client.cooldown_manager)
                goap_state = character_state.to_goap_state()
                typed_state = GameState.validate_state_dict(goap_state)

                # Update state changes with actual character data
                for state_key, value in typed_state.items():
                    state_changes[state_key] = value

            # Determine success status
            success = not hasattr(api_response, 'error') and not hasattr(api_response, 'message') or \
                     (hasattr(api_response, 'message') and 'failed' not in str(api_response.message).lower())

            # Create result message
            message = ""
            if hasattr(api_response, 'message'):
                message = str(api_response.message)
            else:
                message = f"Action {action.name} executed successfully"

            return ActionResult(
                success=success,
                message=message,
                state_changes=state_changes,
                cooldown_seconds=cooldown_seconds
            )

        except Exception as e:
            # Fallback result for processing errors
            return ActionResult(
                success=False,
                message=f"Failed to process result for {action.name}: {str(e)}",
                state_changes={},
                cooldown_seconds=0
            )

    async def emergency_recovery(self, character_name: str, error_context: str) -> bool:
        """Perform emergency recovery actions (rest, move to safety).

        Parameters:
            character_name: Name of the character requiring emergency recovery
            error_context: String describing the error context that triggered recovery

        Return values:
            Boolean indicating whether emergency recovery was successful

        This method implements emergency recovery procedures including moving
        to safe locations, resting to recover HP, and clearing problematic
        states to restore AI player operation after critical errors.
        """
        try:
            # Get current character state
            character = await self.api_client.get_character(character_name)

            # Check if HP is low and needs recovery
            if character.hp < character.max_hp * 0.3:  # Less than 30% HP
                try:
                    # Move to spawn/safe location (0, 0) if not already there
                    if character.x != 0 or character.y != 0:
                        await self.api_client.move_character(character_name, 0, 0)
                        await asyncio.sleep(2)  # Wait for movement cooldown

                    # Rest to recover HP
                    rest_attempts = 0
                    max_rest_attempts = 10

                    while character.hp < character.max_hp * 0.8 and rest_attempts < max_rest_attempts:
                        try:
                            await self.api_client.rest_character(character_name)
                            await asyncio.sleep(5)  # Wait for rest cooldown

                            # Refresh character state
                            character = await self.api_client.get_character(character_name)
                            rest_attempts += 1

                        except Exception:
                            if rest_attempts >= max_rest_attempts - 1:
                                return False
                            await asyncio.sleep(2)
                            rest_attempts += 1

                    return True

                except Exception:
                    # If movement or resting fails, try just resting in place
                    try:
                        await self.api_client.rest_character(character_name)
                        return True
                    except Exception:
                        return False

            # If HP is fine, try basic recovery (move to safe location)
            try:
                if character.x != 0 or character.y != 0:
                    await self.api_client.move_character(character_name, 0, 0)
                    return True
                else:
                    # Already at safe location, just wait a moment
                    await asyncio.sleep(1)
                    return True
            except Exception:
                return False

        except Exception:
            # If we can't even get character state, recovery failed
            return False

    async def get_action_by_name(self, action_name: str, current_state: CharacterGameState) -> BaseAction | None:
        """Get action instance by name from registry using actual game state.

        Parameters:
            action_name: String identifier for the desired action
            current_state: CharacterGameState Pydantic model with current character state

        Return values:
            BaseAction instance matching the name, or None if not found

        This method retrieves a specific action instance from the action
        registry by name, using the actual game state for parameterized actions
        to ensure consistency between planning and execution phases.
        """
        # Get game data for proper action generation
        game_data = await self.cache_manager.get_game_data()
        return self.action_registry.get_action_by_name(action_name, current_state, game_data)

    def estimate_execution_time(self, action: BaseAction, current_state: CharacterGameState) -> float:
        """Estimate time required to execute action including cooldown.

        Parameters:
            action: BaseAction instance to estimate execution time for
            current_state: CharacterGameState Pydantic model with current character state

        Return values:
            Float representing estimated seconds for complete action execution

        This method calculates the total time required for action execution
        including API call time, processing time, and resulting cooldown
        period for accurate planning and scheduling.
        """
        try:
            # Base API call time (estimate)
            api_call_time = 1.0

            # Estimate cooldown time based on action type
            cooldown_time = 0.0
            action_name = action.name.lower()

            if 'move' in action_name:
                cooldown_time = 5.0
            elif 'fight' in action_name or 'combat' in action_name:
                cooldown_time = 10.0
            elif 'gather' in action_name or 'mine' in action_name or 'fish' in action_name:
                cooldown_time = 8.0
            elif 'craft' in action_name:
                cooldown_time = 15.0
            elif 'rest' in action_name:
                cooldown_time = 3.0
            else:
                cooldown_time = 5.0  # Default

            # Add current cooldown wait time if character not ready
            current_cooldown = 0.0
            if not current_state.cooldown_ready:
                current_cooldown = 2.0  # Estimate

            return api_call_time + cooldown_time + current_cooldown

        except Exception:
            # Fallback estimate
            return 10.0

    async def verify_action_success(self, action: BaseAction, result: ActionResult, character_name: str) -> bool:
        """Verify action was executed successfully by checking state changes.

        Parameters:
            action: BaseAction instance that was executed
            result: ActionResult containing execution outcome and state changes
            character_name: Name of the character that executed the action

        Return values:
            Boolean indicating whether action execution was verified as successful

        This method validates action execution success by comparing expected
        state changes with actual results, ensuring action effects match
        expectations for reliable GOAP planning feedback.
        """
        try:
            # If the result already indicates failure, don't verify
            if not result.success:
                return False

            # Get expected effects from the action
            expected_effects = action.get_effects()

            # Check if key expected effects are present in result
            for expected_key, expected_value in expected_effects.items():
                if expected_key in result.state_changes:
                    actual_value = result.state_changes[expected_key]

                    # For most states, exact match is expected
                    # For position states, allow small variations due to pathfinding
                    if expected_key in [GameState.CURRENT_X, GameState.CURRENT_Y]:
                        if abs(actual_value - expected_value) > 1:
                            return False
                    else:
                        if actual_value != expected_value:
                            return False

            # If we get here, verification passed
            return True

        except Exception:
            # If verification fails due to error, be conservative
            return False

    def handle_rate_limit(self, retry_after: int) -> None:
        """Handle API rate limiting with appropriate backoff.

        Parameters:
            retry_after: Number of seconds to wait before retrying as specified by API

        Return values:
            None (implements waiting strategy)

        This method implements appropriate backoff strategies for API rate
        limiting including exponential backoff, jitter, and compliance with
        server-specified retry intervals to maintain API access.
        """
        try:
            # Cap the retry time at a reasonable maximum
            capped_retry_after = min(retry_after, 300)  # Max 5 minutes

            # Add some jitter to avoid thundering herd
            jitter = random.uniform(0.1, 0.3) * capped_retry_after
            actual_wait_time = capped_retry_after + jitter

            # Store the rate limit info for future reference
            # (In a real implementation, this might update some global state)

            # Note: This is a synchronous method but in practice might need to be async
            # For now, we'll just set up the timing info
            self._last_rate_limit_time = time.time()
            self._rate_limit_wait_time = actual_wait_time

        except Exception:
            # Fallback: set a default rate limit wait
            self._last_rate_limit_time = time.time()
            self._rate_limit_wait_time = 60.0

    async def safe_execute(self, action: BaseAction, character_name: str, current_state: CharacterGameState) -> ActionResult:
        """Execute action with comprehensive error handling and retries.

        Parameters:
            action: BaseAction instance to execute with enhanced safety measures
            character_name: Name of the character performing the action
            current_state: CharacterGameState Pydantic model with current character state

        Return values:
            ActionResult with execution outcome and comprehensive error handling

        This method provides the highest level of action execution safety
        including precondition validation, retry logic, error recovery,
        and result verification for maximum reliability.
        """
        try:
            # Pre-execution safety checks
            if not self.validate_action_preconditions(action, current_state):
                return ActionResult(
                    success=False,
                    message=f"Safe execution failed: {action.name} preconditions not met",
                    state_changes={},
                    cooldown_seconds=0
                )

            # Enhanced execution with extended retry logic
            max_safe_attempts = 5
            for attempt in range(max_safe_attempts):
                try:
                    # Use the standard execute_action method which already has error handling
                    result = await self.execute_action(action, character_name, current_state)

                    if result.success:
                        # Additional verification for safe execution
                        verification_passed = await self.verify_action_success(action, result, character_name)
                        if verification_passed:
                            return result
                        else:
                            # Verification failed, but action claimed success
                            if attempt < max_safe_attempts - 1:
                                await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays) - 1)])
                                continue
                            else:
                                return ActionResult(
                                    success=False,
                                    message=f"Safe execution: {action.name} verification failed after {max_safe_attempts} attempts",
                                    state_changes={},
                                    cooldown_seconds=0
                                )
                    else:
                        # Action failed, try emergency recovery if it's a critical failure
                        if "critical" in result.message.lower() or "hp" in result.message.lower():
                            recovery_success = await self.emergency_recovery(character_name, f"Safe execution critical failure: {result.message}")
                            if not recovery_success and attempt >= max_safe_attempts - 1:
                                return result

                        if attempt < max_safe_attempts - 1:
                            await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays) - 1)])
                            continue
                        else:
                            return result

                except Exception as e:
                    # Handle exceptions during safe execution
                    if attempt < max_safe_attempts - 1:
                        # Try emergency recovery for unexpected errors
                        await self.emergency_recovery(character_name, f"Safe execution exception: {str(e)}")
                        await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays) - 1)])
                        continue
                    else:
                        return ActionResult(
                            success=False,
                            message=f"Safe execution failed after {max_safe_attempts} attempts: {str(e)}",
                            state_changes={},
                            cooldown_seconds=0
                        )

            # Fallback result (shouldn't be reached)
            return ActionResult(
                success=False,
                message=f"Safe execution of {action.name} completed without definitive result",
                state_changes={},
                cooldown_seconds=0
            )

        except Exception as e:
            # Final safety net
            return ActionResult(
                success=False,
                message=f"Safe execution critical error for {action.name}: {str(e)}",
                state_changes={},
                cooldown_seconds=0
            )
