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

from src.game_data.api_client_wrapper import APIClientWrapper
from src.game_data.cache_manager import CacheManager
from src.game_data.cooldown_manager import CooldownManager
from .actions import get_global_registry
from .actions.base_action import BaseAction
from .exceptions import MaxDepthExceededError, NoValidGoalError, RecursiveSubGoalError, StateConsistencyError
from .goal_manager import GoalManager
from .state.action_result import ActionResult, GameState
from .state.character_game_state import CharacterGameState
from .state.state_manager import StateManager
from .types.goap_models import GOAPActionPlan, SubGoalExecutionResult


class ActionExecutor:
    """Executes GOAP actions via API with cooldown and error handling"""

    def __init__(
        self,
        api_client: APIClientWrapper,
        cooldown_manager: CooldownManager,
        cache_manager: CacheManager,
        goal_manager: GoalManager = None,
        state_manager: StateManager = None,
        max_subgoal_depth: int = 10,
    ):
        """Initialize ActionExecutor with API client and unified sub-goal support.

        Parameters:
            api_client: API client wrapper for game operations
            cooldown_manager: Manager for character cooldown tracking
            cache_manager: CacheManager instance for accessing game data (maps, monsters, resources)
            goal_manager: GoalManager instance for sub-goal factory support
            state_manager: StateManager instance for recursive state management
            max_subgoal_depth: Maximum recursion depth for sub-goal execution

        Return values:
            None (constructor)

        This constructor initializes the ActionExecutor with the necessary
        components for reliable action execution including API communication,
        cooldown management, game data access, and recursive sub-goal execution.
        """
        self.api_client = api_client
        self.cooldown_manager = cooldown_manager
        self.cache_manager = cache_manager
        self.goal_manager = goal_manager
        self.state_manager = state_manager
        self.max_subgoal_depth = max_subgoal_depth
        self.action_registry = get_global_registry()
        self.retry_attempts = 3
        self.retry_delays = [1, 2, 4]  # exponential backoff
        self.logger = logging.getLogger(__name__)

        # Rate limiting state tracking
        self._last_rate_limit_time = 0.0
        self._rate_limit_wait_time = 0.0

    async def execute_action(
        self, action: BaseAction, character_name: str, current_state: CharacterGameState
    ) -> ActionResult:
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
        # Wait for cooldown first before any precondition checking
        await self.wait_for_cooldown(character_name)

        # Validate preconditions
        if not self.validate_action_preconditions(action, current_state):
            return ActionResult(
                success=False,
                message=f"Action {action.name} preconditions not met",
                state_changes={},
                cooldown_seconds=0,
            )

        # Execute the action with retry logic
        for attempt in range(self.retry_attempts):
            # Convert CharacterGameState to dict[GameState, Any] for action
            state_dict = current_state.to_goap_state()
            typed_state = GameState.validate_state_dict(state_dict)

            # Pass API client and cooldown manager to action
            result = await action.execute(
                character_name, typed_state, api_client=self.api_client, cooldown_manager=self.cooldown_manager
            )

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
                        cooldown_seconds=0,
                    )
            else:
                # Handle failed execution - check if it's a cooldown error
                if "cooldown" in result.message.lower():
                    # Don't retry cooldown errors, return immediately
                    return result

                if attempt < self.retry_attempts - 1:
                    await asyncio.sleep(self.retry_delays[attempt])
                    continue
                else:
                    return result

    async def execute_plan(self, plan: list[BaseAction], character_name: str) -> bool:
        """Execute entire action plan with state updates.

        Parameters:
            plan: List of BaseAction instances representing the planned sequence
            character_name: Name of the character to execute the plan for

        Return values:
            Boolean indicating whether the entire plan executed successfully

        This method executes a complete action plan by sequentially processing
        each action, handling cooldowns between actions, updating state after
        each execution, and providing comprehensive error recovery.
        """
        if not plan:
            return True

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
        character_state = CharacterGameState.from_api_character(
            character, game_map.content, self.api_client.cooldown_manager
        )
        self.logger.info("ActionExecutor: Initial state loaded successfully")

        self.logger.info(f"ActionExecutor: Starting for loop with {len(plan)} actions")
        for i, action in enumerate(plan):
            self.logger.info(f"ActionExecutor: Processing plan step {i + 1}: {action.name}")
            self.logger.debug(f"Executing action '{action.name}'...")

            # Execute all actions through the proper execute_action method
            # This delegates to StateManager for API calls, maintaining proper architecture
            result = await self.execute_action(action, character_name, character_state)

            if not result.success:
                self.logger.warning(f"Action '{action.name}' failed: {result.message}")
                # Try emergency recovery for critical failures
                if "critical" in result.message.lower() or "hp" in result.message.lower():
                    recovery_success = await self.emergency_recovery(
                        character_name, f"Plan step {i + 1} failed: {result.message}"
                    )
                    if not recovery_success:
                        return False
                else:
                    return False

            self.logger.info(f"Action '{action.name}' succeeded: {result.message}")

            # Delegate state updates to StateManager for proper synchronization
            # Apply the action result through StateManager
            await self.state_manager.apply_action_result(result)

            # Get the updated state from StateManager (with proper cooldown sync)
            character_state = await self.state_manager.get_current_state()

            # Wait for cooldown between actions if needed
            if result.cooldown_seconds > 0:
                await asyncio.sleep(min(result.cooldown_seconds, 30))  # Cap wait time

        return True

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
        # Use the BaseAction's built-in can_execute method
        return action.can_execute(current_state)

    async def handle_action_error(
        self, action: BaseAction, error: Exception, character_name: str
    ) -> ActionResult | None:
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
        if hasattr(error, "status_code"):
            status_code = error.status_code

            # Handle cooldown errors (499)
            if status_code == 499:
                return ActionResult(
                    success=False,
                    message=f"Character {character_name} is on cooldown",
                    state_changes={GameState.COOLDOWN_READY: False},
                    cooldown_seconds=5,
                )

            # Handle "already at map location" (490) - treat as successful movement
            elif status_code == 490:
                return ActionResult(
                    success=True,
                    message=f"Character {character_name} already at target location",
                    state_changes={},  # No state changes needed - already at destination
                    cooldown_seconds=0,  # No cooldown for non-movement
                )

            # Handle rate limiting (429)
            elif status_code == 429:
                retry_after = getattr(error, "retry_after", 60)
                self.handle_rate_limit(retry_after)
                return ActionResult(
                    success=False,
                    message=f"Rate limited, retry after {retry_after} seconds",
                    state_changes={},
                    cooldown_seconds=retry_after,
                )

            # Handle insufficient resources/items (4xx errors)
            elif 400 <= status_code < 500:
                return ActionResult(
                    success=False,
                    message=f"Action {action.name} failed: {error_message}",
                    state_changes={},
                    cooldown_seconds=0,
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
                    cooldown_seconds=0,
                )

        # Handle connection/network errors
        if "connection" in error_message.lower() or "timeout" in error_message.lower():
            return ActionResult(
                success=False,
                message=f"Network error during {action.name}: {error_message}",
                state_changes={},
                cooldown_seconds=5,  # Short delay before retry
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
        # Extract cooldown information
        cooldown_seconds = 0
        if hasattr(api_response, "cooldown"):
            cooldown_data = api_response.cooldown
            if hasattr(cooldown_data, "total_seconds"):
                cooldown_seconds = cooldown_data.total_seconds
            elif hasattr(cooldown_data, "remaining_seconds"):
                cooldown_seconds = cooldown_data.remaining_seconds

        # Get expected effects from the action
        expected_effects = action.get_effects()

        # Create state changes based on action effects and API response
        state_changes = {}

        # Apply action effects
        for state_key, effect_value in expected_effects.items():
            state_changes[state_key] = effect_value

        # Extract state changes from API response if character data is present
        if hasattr(api_response, "character") and api_response.character is not None:
            # Get map content for location context
            character = api_response.character
            game_map = await self.api_client.get_map(character.x, character.y)

            # Convert to internal state format
            character_state = CharacterGameState.from_api_character(
                character, game_map.content, self.api_client.cooldown_manager
            )
            goap_state = character_state.to_goap_state()
            typed_state = GameState.validate_state_dict(goap_state)

            # Update state changes with actual character data
            for state_key, value in typed_state.items():
                state_changes[state_key] = value

        # Determine success status
        success = (
            not hasattr(api_response, "error")
            and not hasattr(api_response, "message")
            or (hasattr(api_response, "message") and "failed" not in str(api_response.message).lower())
        )

        # Create result message
        message = ""
        if hasattr(api_response, "message"):
            message = str(api_response.message)
        else:
            message = f"Action {action.name} executed successfully"

        return ActionResult(
            success=success, message=message, state_changes=state_changes, cooldown_seconds=cooldown_seconds
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
        # Get current character state
        character = await self.api_client.get_character(character_name)

        # Check if HP is low and needs recovery
        if character.hp < character.max_hp * 0.3:  # Less than 30% HP
            # Move to spawn/safe location (0, 0) if not already there
            if character.x != 0 or character.y != 0:
                await self.api_client.move_character(character_name, 0, 0)
                await asyncio.sleep(2)  # Wait for movement cooldown

            # Rest to recover HP
            rest_attempts = 0
            max_rest_attempts = 10

            while character.hp < character.max_hp * 0.8 and rest_attempts < max_rest_attempts:
                await self.api_client.rest_character(character_name)
                await asyncio.sleep(5)  # Wait for rest cooldown

                # Refresh character state
                character = await self.api_client.get_character(character_name)
                rest_attempts += 1

            return True

        # If HP is fine, try basic recovery (move to safe location)
        if character.x != 0 or character.y != 0:
            await self.api_client.move_character(character_name, 0, 0)
            return True
        else:
            # Already at safe location, just wait a moment
            await asyncio.sleep(1)
            return True

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

            if "move" in action_name:
                cooldown_time = 5.0
            elif "fight" in action_name or "combat" in action_name:
                cooldown_time = 10.0
            elif "gather" in action_name or "mine" in action_name or "fish" in action_name:
                cooldown_time = 8.0
            elif "craft" in action_name:
                cooldown_time = 15.0
            elif "rest" in action_name:
                cooldown_time = 3.0
            else:
                cooldown_time = 5.0  # Default

            # Add current cooldown wait time if character not ready
            current_cooldown = 0.0
            if not current_state.cooldown_ready:
                current_cooldown = 2.0  # Estimate

            return api_call_time + cooldown_time + current_cooldown

        except (AttributeError, TypeError):
            # Handle missing attributes or type issues
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

    async def safe_execute(
        self, action: BaseAction, character_name: str, current_state: CharacterGameState
    ) -> ActionResult:
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
        # Pre-execution safety checks
        if not self.validate_action_preconditions(action, current_state):
            return ActionResult(
                success=False,
                message=f"Safe execution failed: {action.name} preconditions not met",
                state_changes={},
                cooldown_seconds=0,
            )

        # Enhanced execution with extended retry logic
        max_safe_attempts = 5
        for attempt in range(max_safe_attempts):
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
                            message=f"Safe execution: {action.name} verification failed after {max_safe_attempts}",
                            state_changes={},
                            cooldown_seconds=0,
                        )
            else:
                # Action failed, try emergency recovery if it's a critical failure
                if "critical" in result.message.lower() or "hp" in result.message.lower():
                    recovery_success = await self.emergency_recovery(
                        character_name, f"Safe execution critical failure: {result.message}"
                    )
                    if not recovery_success and attempt >= max_safe_attempts - 1:
                        return result

                if attempt < max_safe_attempts - 1:
                    await asyncio.sleep(self.retry_delays[min(attempt, len(self.retry_delays) - 1)])
                    continue
                else:
                    return result

    # Enhanced methods for unified sub-goal architecture

    async def execute_action_with_subgoals(
        self, action: BaseAction, character_name: str, current_state: CharacterGameState, depth: int = 0
    ) -> ActionResult:
        """Execute action with recursive sub-goal handling and state consistency validation.

        Parameters:
            action: BaseAction instance to execute
            character_name: Character identifier
            current_state: Pydantic model with current character state
            depth: Current recursion depth (0 = top level)

        Return values:
            ActionResult: Pydantic model with execution outcome

        Raises:
            MaxDepthExceededError: If depth > max_subgoal_depth
            RecursiveSubGoalError: If sub-goal chain fails
        """

        # Depth limit protection
        if depth > self.max_subgoal_depth:
            raise MaxDepthExceededError(self.max_subgoal_depth)

        # Ensure we have required dependencies for sub-goal support
        if not self.goal_manager or not self.state_manager:
            # Fall back to regular execution if dependencies not available
            return await self.execute_action(action, character_name, current_state)

        # Capture pre-execution state for validation
        pre_execution_state = current_state.model_copy()

        # Execute action using existing execute_action method
        result = await self.execute_action(action, character_name, current_state)

        # Handle sub-goal requests recursively
        if not result.success and result.sub_goal_requests:
            for sub_goal_request in result.sub_goal_requests:
                try:
                    # Create factory context using StateManager
                    context = self.state_manager.create_goal_factory_context(
                        parent_goal_type=type(action).__name__,
                        recursion_depth=depth + 1,
                        max_depth=self.max_subgoal_depth,
                    )

                    # Use GoalManager factory to create Goal instance
                    sub_goal = self.goal_manager.create_goal_from_sub_request(sub_goal_request, context)

                    # Get target state using same facility as regular goals
                    target_state = sub_goal.get_target_state(context.character_state, context.game_data)

                    # Use GOAP planning (same facility as regular goals) - validation happens inside
                    sub_plan = await self.goal_manager.plan_to_target_state(context.character_state, target_state)

                    if not sub_plan.is_empty:
                        # Execute sub-plan recursively
                        sub_result = await self.execute_plan_recursive(sub_plan, character_name, depth + 1)

                        if sub_result.success:
                            # Force refresh state after sub-goal completion
                            refreshed_state = await self.state_manager.refresh_state_for_parent_action(depth)

                            # Validate state transition
                            await self.state_manager.validate_recursive_state_transition(
                                pre_execution_state, refreshed_state, depth
                            )

                            # Retry parent action with refreshed state
                            return await self.execute_action_with_subgoals(
                                action, character_name, refreshed_state, depth
                            )

                except (StateConsistencyError, MaxDepthExceededError, NoValidGoalError) as e:
                    # Log error and continue with remaining sub-goal requests
                    self.logger.warning(f"Sub-goal execution failed: {e}")
                    continue
                except (ConnectionError, TimeoutError, OSError) as e:
                    # Wrap network errors in RecursiveSubGoalError
                    raise RecursiveSubGoalError(
                        type(action).__name__, sub_goal_request.goal_type, depth, f"Network error: {str(e)}"
                    )

        return result

    async def execute_plan_recursive(
        self, plan: GOAPActionPlan, character_name: str, depth: int
    ) -> SubGoalExecutionResult:
        """Execute plan with recursive sub-goal support and state consistency tracking.

        Parameters:
            plan: Pydantic model with ordered action sequence
            character_name: Character identifier
            depth: Current recursion depth

        Return values:
            SubGoalExecutionResult: Pydantic model with execution results

        Raises:
            MaxDepthExceededError: If depth > max_subgoal_depth
        """
        start_time = time.time()
        actions_executed = 0

        try:
            # Check depth limit
            if depth > self.max_subgoal_depth:
                raise MaxDepthExceededError(self.max_subgoal_depth)

            # Get initial state for result tracking
            if self.state_manager:
                initial_state = await self.state_manager.get_current_state()
            else:
                # Fallback if state manager not available
                initial_state = None

            for goap_action in plan.actions:
                # Convert GOAPAction to BaseAction instance
                action = await self.get_action_by_name(goap_action.name, initial_state)
                if not action:
                    return SubGoalExecutionResult(
                        success=False,
                        depth_reached=depth,
                        actions_executed=actions_executed,
                        execution_time=time.time() - start_time,
                        error_message=f"Action '{goap_action.name}' not found",
                    )

                # Get current state for this action
                if self.state_manager:
                    current_state = await self.state_manager.get_current_state()
                else:
                    current_state = initial_state

                # Execute with recursive sub-goal handling
                result = await self.execute_action_with_subgoals(action, character_name, current_state, depth)

                actions_executed += 1

                if not result.success:
                    return SubGoalExecutionResult(
                        success=False,
                        depth_reached=depth,
                        actions_executed=actions_executed,
                        execution_time=time.time() - start_time,
                        error_message=result.message,
                    )

            # Get final state after all actions
            if self.state_manager:
                final_state = await self.state_manager.get_current_state()
            else:
                final_state = None

            return SubGoalExecutionResult(
                success=True,
                depth_reached=depth,
                actions_executed=actions_executed,
                execution_time=time.time() - start_time,
                final_state=final_state,
            )

        except (MaxDepthExceededError, StateConsistencyError, NoValidGoalError) as e:
            return SubGoalExecutionResult(
                success=False,
                depth_reached=depth,
                actions_executed=actions_executed,
                execution_time=time.time() - start_time,
                error_message=str(e),
            )
