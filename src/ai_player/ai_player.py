"""
AI Player Main Orchestrator

This module contains the main AI Player class that orchestrates the entire
autonomous gameplay system. It coordinates state management, GOAP planning,
goal selection, and action execution in a continuous game loop.

The AI Player serves as the central controller that integrates all system
components to provide intelligent, goal-oriented character automation
for the ArtifactsMMO game.
"""

import asyncio
import logging
from typing import Any

from .action_executor import ActionExecutor
from .actions import ActionRegistry
from .goal_manager import GoalManager
from .state.game_state import GameState
from .state.character_game_state import CharacterGameState
from .state.state_manager import StateManager


class AIPlayer:
    """Main AI Player orchestrator for autonomous gameplay.

    Coordinates state management, GOAP planning, and action execution
    to provide intelligent character automation with goal-oriented behavior.
    """

    def __init__(self, character_name: str):
        """Initialize AI Player for the specified character.

        Parameters:
            character_name: Name of the character to control autonomously

        Return values:
            None (constructor)

        This constructor initializes all component managers (StateManager, GoalManager,
        ActionExecutor) and sets up the AI player for autonomous gameplay of the
        specified character in the ArtifactsMMO game.
        """
        self.character_name = character_name
        self.logger = logging.getLogger(f"ai_player.{character_name}")

        # Initialize component managers - will be set when dependencies are available
        self.state_manager: StateManager | None = None
        self.goal_manager: GoalManager | None = None
        self.action_executor: ActionExecutor | None = None
        self.action_registry: ActionRegistry | None = None

        # AI player state
        self._running = False
        self._stop_requested = False
        self._current_goal: dict[GameState, Any] | None = None
        self._current_plan: list[dict[str, Any]] | None = None
        self._execution_stats = {
            "actions_executed": 0,
            "successful_actions": 0,
            "failed_actions": 0,
            "replanning_count": 0,
            "emergency_interventions": 0
        }

        self.logger.info(f"AIPlayer initialized for character: {character_name}")

    async def start(self) -> None:
        """Start the AI player main game loop.

        Parameters:
            None

        Return values:
            None (async operation)

        This method initializes the AI player and begins the main autonomous
        gameplay loop, continuing until stopped or the character reaches maximum
        level, handling all state management and error recovery.
        """
        if self._running:
            self.logger.warning("AI Player is already running")
            return

        if not self._check_dependencies():
            self.logger.error("Cannot start AI Player: required dependencies not initialized")
            raise RuntimeError("Dependencies not initialized")

        self.logger.info(f"Starting AI Player for {self.character_name}")
        self._running = True
        self._stop_requested = False

        try:
            await self.main_loop()
        except Exception as e:
            self.logger.error(f"AI Player encountered fatal error: {e}")
            raise
        finally:
            self._running = False
            self.logger.info(f"AI Player stopped for {self.character_name}")

    async def stop(self) -> None:
        """Stop the AI player and perform cleanup.

        Parameters:
            None

        Return values:
            None (async operation)

        This method gracefully stops the AI player main loop, saves current
        state to cache, and performs necessary cleanup operations to ensure
        data integrity and proper resource management.
        """
        if not self._running:
            self.logger.info("AI Player is not running")
            return

        self.logger.info(f"Stopping AI Player for {self.character_name}")
        self._stop_requested = True

        # Wait for main loop to finish gracefully
        while self._running:
            await asyncio.sleep(0.1)

        # Save state to cache if state manager is available
        if self.state_manager:
            try:
                current_state = self.state_manager.get_cached_state()
                if current_state:
                    self.state_manager.save_state_to_cache(current_state)
                    self.logger.info("Character state saved to cache")
            except Exception as e:
                self.logger.error(f"Failed to save state to cache: {e}")

        self.logger.info(f"AI Player cleanup completed for {self.character_name}")

    async def main_loop(self) -> None:
        """Main game loop: plan -> execute -> update cycle.

        Parameters:
            None

        Return values:
            None (continuous async operation)

        This method implements the core AI player logic with a continuous
        plan-execute-update cycle, handling goal selection, GOAP planning,
        action execution, and state synchronization until stopped.
        """
        self.logger.info("Starting main game loop")

        while self._running and not self._stop_requested:
            try:
                # Get current character state
                if not self.state_manager:
                    self.logger.error("StateManager not available")
                    break

                current_state = await self.state_manager.get_current_state()

                # Check for emergency situations first
                await self.handle_emergency(current_state)

                # Check if we need to replan
                if self.should_replan(current_state) or self._current_plan is None:
                    self.logger.info("Planning new action sequence")

                    # Select next goal
                    if not self.goal_manager:
                        self.logger.error("GoalManager not available")
                        break

                    goal = self.goal_manager.select_next_goal(current_state)
                    self._current_goal = goal

                    # Plan actions to achieve goal
                    plan = await self.plan_actions(current_state, goal)
                    self._current_plan = plan
                    self._execution_stats["replanning_count"] += 1

                    if not plan:
                        self.logger.warning("No valid plan found, waiting before retry")
                        await asyncio.sleep(5.0)
                        continue

                    self.logger.info(f"Generated plan with {len(plan)} actions")

                # Execute the current plan
                if self._current_plan:
                    success = await self.execute_plan(self._current_plan)
                    if success:
                        self.logger.info("Plan executed successfully")
                        self._current_plan = None  # Plan completed
                    else:
                        self.logger.warning("Plan execution failed, will replan")
                        self._current_plan = None  # Force replanning

                # Brief pause before next cycle
                await asyncio.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(5.0)  # Wait before retrying

        self.logger.info("Main game loop ended")

    async def plan_actions(
        self, current_state: CharacterGameState, goal: dict[GameState, Any]
    ) -> list[dict[str, Any]]:
        """Generate action sequence using GOAP planner.

        Parameters:
            current_state: CharacterGameState instance with current character state
            goal: Dictionary with GameState enum keys and target values

        Return values:
            List of action dictionaries representing the planned sequence

        This method uses the GOAP planner to generate an optimal action sequence
        that will transition the character from the current state to the goal
        state, considering action costs and preconditions.
        """
        if not self.goal_manager:
            self.logger.error("GoalManager not available for planning")
            return []

        try:
            # Use cooldown-aware planning with character name
            target_state = goal.get('target_state', {})
            plan = await self.goal_manager.plan_with_cooldown_awareness(
                self.character_name, current_state, target_state
            )
            self.logger.debug(f"Generated cooldown-aware plan: {plan}")
            return plan
        except Exception as e:
            self.logger.error(f"Planning failed: {e}")
            return []

    async def execute_plan(self, plan: list[dict[str, Any]]) -> bool:
        """Execute planned action sequence.

        Parameters:
            plan: List of action dictionaries to execute in sequence

        Return values:
            Boolean indicating whether the entire plan executed successfully

        This method executes each action in the planned sequence, handling
        cooldowns, API calls, and error recovery while updating character
        state after each successful action.
        """
        if not self.action_executor:
            self.logger.error("ActionExecutor not available")
            return False

        if not plan:
            self.logger.warning("Empty plan provided")
            return True

        self.logger.info(f"Executing plan with {len(plan)} actions")

        try:
            success = await self.action_executor.execute_plan(plan, self.character_name)
            if success:
                self._execution_stats["successful_actions"] += len(plan)
            else:
                self._execution_stats["failed_actions"] += 1
            self._execution_stats["actions_executed"] += len(plan)
            return success
        except Exception as e:
            self.logger.error(f"Plan execution failed: {e}")
            self._execution_stats["failed_actions"] += 1
            return False

    def should_replan(self, current_state: CharacterGameState) -> bool:
        """Determine if replanning is needed due to state changes.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            Boolean indicating whether the current plan should be abandoned

        This method analyzes the current state against expected plan outcomes
        to determine if unexpected changes require generating a new plan for
        more effective goal achievement.
        """
        # Always replan if no current plan
        if self._current_plan is None:
            return True

        # Always replan if no current goal
        if self._current_goal is None:
            return True

        # Check if goal has been achieved
        goal_achieved = True
        for goal_key, goal_value in self._current_goal.items():
            # Convert to GOAP state to check current values
            goap_state = current_state.to_goap_state()
            current_value = goap_state.get(goal_key.value if isinstance(goal_key, GameState) else goal_key)
            if current_value != goal_value:
                goal_achieved = False
                break

        if goal_achieved:
            self.logger.info("Current goal achieved, replanning needed")
            return True

        # Check for critical state changes that invalidate current plan
        if current_state.hp_critical:
            self.logger.warning("Critical HP detected, replanning needed")
            return True
        elif not current_state.inventory_space_available:
            self.logger.info("Inventory full, may need to replan")
            return True

        return False

    async def handle_emergency(self, current_state: CharacterGameState) -> None:
        """Handle emergency situations (low HP, unexpected state).

        Parameters:
            current_state: Dictionary with GameState enum keys and current values

        Return values:
            None (async operation)

        This method detects and responds to emergency situations such as
        critically low HP, dangerous locations, or unexpected state changes
        by executing immediate recovery actions.
        """
        emergency_handled = False

        # Check for critical HP
        if current_state.hp_critical:
            self.logger.warning("EMERGENCY: Critical HP detected")

            # Clear current plan to force emergency actions
            self._current_plan = None

            # Set emergency goal for HP recovery
            self._current_goal = {
                GameState.HP_CURRENT: current_state.max_hp
            }

            emergency_handled = True
            self._execution_stats["emergency_interventions"] += 1

        # Check for low HP (less critical but still concerning)
        elif current_state.hp_low:
            hp_current = current_state.hp
            hp_max = current_state.max_hp

            if hp_current < (hp_max * 0.3):  # Less than 30% HP
                self.logger.warning(f"EMERGENCY: Low HP detected ({hp_current}/{hp_max})")

                # Interrupt current plan for safety
                self._current_plan = None

                # Set recovery goal
                self._current_goal = {
                    GameState.HP_CURRENT: int(hp_max * 0.8)  # Recover to 80%
                }

                emergency_handled = True
                self._execution_stats["emergency_interventions"] += 1

        # Check if character is stuck or in invalid state (only if no other emergency handled)
        if not emergency_handled:
            if not current_state.cooldown_ready:
                # Character is on cooldown, this is normal
                pass
            elif not any([
                current_state.can_fight, current_state.can_gather, current_state.can_craft,
                current_state.can_trade, current_state.can_move, current_state.can_rest
            ]):
                self.logger.warning("EMERGENCY: Character appears to be in invalid state (no actions available)")

                # Force state refresh
                if self.state_manager:
                    try:
                        await self.state_manager.force_refresh()
                        emergency_handled = True
                        self._execution_stats["emergency_interventions"] += 1
                    except Exception as e:
                        self.logger.error(f"Failed to refresh state during emergency: {e}")

        if emergency_handled:
            self.logger.info("Emergency intervention completed")

    def get_status(self) -> dict[str, Any]:
        """Get current AI player status and statistics.

        Parameters:
            None

        Return values:
            Dictionary containing current status, progress metrics, and statistics

        This method provides comprehensive status information including
        character state, current goals, execution statistics, and progress
        metrics for monitoring and debugging purposes.
        """
        status = {
            "character_name": self.character_name,
            "running": self._running,
            "stop_requested": self._stop_requested,
            "current_goal": self._current_goal,
            "has_current_plan": self._current_plan is not None,
            "plan_length": len(self._current_plan) if self._current_plan else 0,
            "execution_stats": self._execution_stats.copy(),
            "dependencies_initialized": self._check_dependencies()
        }

        # Add current state if available
        if self.state_manager:
            try:
                cached_state = self.state_manager.get_cached_state()
                if cached_state:
                    # Include key state information
                    status["character_state"] = {
                        "level": cached_state.get(GameState.CHARACTER_LEVEL),
                        "hp": f"{cached_state.get(GameState.HP_CURRENT, 0)}/{cached_state.get(GameState.HP_MAX, 0)}",
                        "position": f"({cached_state.get(GameState.CURRENT_X, 0)}, "
                                   f"{cached_state.get(GameState.CURRENT_Y, 0)})",
                        "cooldown_ready": cached_state.get(GameState.COOLDOWN_READY, False),
                        "gold": cached_state.get(GameState.CHARACTER_GOLD, 0)
                    }
            except Exception as e:
                status["character_state_error"] = str(e)
        else:
            status["character_state"] = "StateManager not available"

        return status

    async def set_goal(self, goal: dict[GameState, Any]) -> None:
        """Set a new goal for the AI player.

        Parameters:
            goal: Dictionary with GameState enum keys defining the target state

        Return values:
            None (async operation)

        This method overrides the current goal with a new target state,
        triggering replanning and adjusting the AI player behavior to
        pursue the new objective.
        """
        self.logger.info(f"Setting new goal: {goal}")

        # Validate goal uses GameState enum keys
        for key in goal.keys():
            if not isinstance(key, GameState):
                raise ValueError(f"Goal key {key} is not a GameState enum")

        self._current_goal = goal.copy()

        # Clear current plan to force replanning
        self._current_plan = None

        self.logger.info("Goal set successfully, will replan on next cycle")

    def is_running(self) -> bool:
        """Check if AI player is currently running.

        Parameters:
            None

        Return values:
            Boolean indicating whether the AI player main loop is active

        This method checks the AI player's operational status to determine
        if the main autonomous gameplay loop is currently executing or
        has been stopped.
        """
        return self._running

    def _check_dependencies(self) -> bool:
        """Check if all required dependencies are initialized.

        Parameters:
            None

        Return values:
            Boolean indicating whether all dependencies are available

        This method validates that all required component managers are
        properly initialized before starting the AI player main loop.
        """
        if self.state_manager is None:
            self.logger.error("StateManager not initialized")
            return False

        if self.goal_manager is None:
            self.logger.error("GoalManager not initialized")
            return False

        if self.action_executor is None:
            self.logger.error("ActionExecutor not initialized")
            return False

        return True

    def initialize_dependencies(self, state_manager: 'StateManager', goal_manager: 'GoalManager',
                              action_executor: 'ActionExecutor', action_registry: 'ActionRegistry') -> None:
        """Initialize component dependencies.

        Parameters:
            state_manager: StateManager instance for state synchronization
            goal_manager: GoalManager instance for goal selection and planning
            action_executor: ActionExecutor instance for action execution
            action_registry: ActionRegistry instance for action discovery

        Return values:
            None (modifies internal state)

        This method sets up all required component dependencies that the
        AI player needs to operate, enabling modular initialization of
        the system components.
        """
        self.state_manager = state_manager
        self.goal_manager = goal_manager
        self.action_executor = action_executor
        self.action_registry = action_registry

        self.logger.info("Dependencies initialized successfully")
