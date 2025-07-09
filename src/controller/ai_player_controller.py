"""
AI Player Controller

This module implements the main controller class for the AI player that integrates
with the GOAP (Goal-Oriented Action Planning) system using metaprogramming for
YAML-driven action execution.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character

# Action classes are now loaded dynamically via ActionFactory from YAML configuration
# State classes for type hints and learning method access
from src.game.character.state import CharacterState
from src.game.globals import CONFIG_PREFIX
from src.game.map.state import MapState
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.character_utils import calculate_hp_percentage, is_character_safe, is_hp_critically_low, is_hp_sufficient_for_combat

# GOAP functionality now handled by GOAPExecutionManager
from src.lib.state_loader import StateManagerMixin
from src.lib.yaml_data import YamlData

# Metaprogramming components
from .action_executor import ActionExecutor, ActionResult
from .cooldown_manager import CooldownManager

# Additional imports
from .goal_manager import GOAPGoalManager
from .goap_execution_manager import GOAPExecutionManager
from .learning_manager import LearningManager
from .mission_executor import MissionExecutor
from .skill_goal_manager import SkillGoalManager, SkillType


class AIPlayerController(StateManagerMixin):
    """
    Main controller class for the AI player that coordinates GOAP planning
    and execution with game state management using YAML-driven metaprogramming.
    """
    
    def __init__(self, client=None, goal_manager=None):
        """Initialize the AI player controller with full metaprogramming integration."""
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.client = client
        
        # Initialize goal-driven system
        self.goal_manager = goal_manager
        if self.goal_manager is None:
            self.goal_manager = GOAPGoalManager()
        
        # Initialize metaprogramming components
        self.action_executor = ActionExecutor()
        self.cooldown_manager = CooldownManager()
        self.mission_executor = MissionExecutor(self.goal_manager, self)
        self.skill_goal_manager = SkillGoalManager()
        self.goap_execution_manager = GOAPExecutionManager()
        
        # Initialize learning manager (will be set up after states are created)
        self.learning_manager = None
        
        # Initialize YAML-driven state management
        self.initialize_state_management()
        
        # Create managed states using YAML configuration
        self.world_state = self.create_managed_state('world_state', 'world_state')
        self.knowledge_base = self.create_managed_state('knowledge_base', 'knowledge_base')
        
        # Character and map states are created when needed
        self.character_state: Optional[CharacterState] = None
        self.map_state: Optional[MapState] = None
        
        # Initialize learning manager after states are available
        self.learning_manager = LearningManager(self.knowledge_base, self.map_state, self.client)
        
        # Current plan and execution state
        self.current_plan: List[Dict] = []
        self.current_action_index: int = 0
        self.is_executing: bool = False
        
        # Current goal parameters for passing to actions
        self.current_goal_parameters: Dict[str, Any] = {}
        
        # Unified ActionContext that persists across all actions in a plan
        # Initialize immediately as it's a singleton that should always exist
        self.plan_action_context: ActionContext = ActionContext.from_controller(self, {})
        self.logger.debug("Initialized singleton ActionContext for plan execution")
        
    def set_client(self, client) -> None:
        """
        Set the API client for making requests.
        
        Args:
            client: The authenticated API client
        """
        self.client = client
        
    def set_character_state(self, character_state: CharacterState) -> None:
        """
        Set the current character state.
        
        Args:
            character_state: The character state to use
        """
        self.character_state = character_state
        self.logger.info(f"Character state set: {character_state}")
        # Invalidate location-based states when character is set/changed
        self._invalidate_location_states()
        
    def _invalidate_location_states(self) -> None:
        """
        Invalidate location-based states that may be stale from previous runs.
        
        This prevents the GOAP planner from using outdated location information
        like at_correct_workshop, at_target_location, etc.
        """
        if not self.world_state or not hasattr(self.world_state, 'data'):
            return
            
        # Load location states from YAML configuration
        try:
            location_config = YamlData(f"{CONFIG_PREFIX}/location_states.yaml")
            location_states = location_config.data.get('location_based_states', [])
            
            if not location_states:
                self.logger.warning("No location-based states found in configuration")
                return
                
        except Exception as e:
            self.logger.warning(f"Could not load location states config: {e}")
            # Fallback to essential states if config can't be loaded
            location_states = ['at_correct_workshop', 'at_target_location', 'at_resource_location']
        
        # Invalidate each location-based state using unified API
        state_updates = {}
        for state in location_states:
            if state in self.world_state.data:
                state_updates[state] = False
                
        if state_updates:
            self.update_world_state(state_updates)
            self.logger.debug(f"Invalidated {len(state_updates)} location-based world states")
        
    def set_map_state(self, map_state: MapState) -> None:
        """
        Set the current map state.
        
        Args:
            map_state: The map state to use
        """
        self.map_state = map_state
        self.logger.info("Map state set")
        
    # GOAP planning is now handled by GOAPExecutionManager
            
    def check_and_handle_cooldown(self) -> bool:
        """
        Check if character is in cooldown and handle it by executing a wait action.
        
        Returns:
            True if ready to act, False if should abort
        """
        if not self.character_state:
            return True
            
        try:
            cooldown_expiration = self.character_state.data.get('cooldown_expiration')
            if not cooldown_expiration:
                return True
                
            # Parse the cooldown expiration time
            if isinstance(cooldown_expiration, str):
                expiration_time = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
            else:
                return True
                
            current_time = datetime.now(timezone.utc)
            
            if current_time < expiration_time:
                wait_seconds = (expiration_time - current_time).total_seconds()
                if wait_seconds > 0:
                    self.logger.info(f"Character in cooldown, executing wait action for {wait_seconds:.1f} seconds...")
                    
                    # Execute wait action instead of just sleeping - use CooldownManager for duration calculation
                    optimal_duration = self.cooldown_manager.calculate_wait_duration(self.character_state)
                    # Set wait duration in unified context
                    self.plan_action_context.wait_duration = optimal_duration
                    success, _ = self._execute_action('wait')
                    
                    if success:
                        self.logger.info("Cooldown wait completed successfully")
                        # Refresh character state to check if cooldown is cleared
                        self._refresh_character_state()
                        return True
                    else:
                        self.logger.warning("Wait action failed during cooldown")
                        return False
                    
            return True
            
        except Exception as e:
            self.logger.warning(f"Error handling cooldown: {e}")
            return True

    def execute_next_action(self) -> bool:
        """
        Execute the next action in the current plan.
        
        Returns:
            True if action was executed successfully, False if plan is complete or failed
        """
        if not self.current_plan or self.current_action_index >= len(self.current_plan):
            self.logger.info("Plan execution complete")
            self.is_executing = False
            return False
            
        if not self.client:
            self.logger.error("Cannot execute action without API client")
            return False
            
        action_data = self.current_plan[self.current_action_index]
        action_name = action_data['name']
        
        self.logger.info(f"Executing action {self.current_action_index + 1}/{len(self.current_plan)}: {action_name}")
        
        # Check for cooldown before executing action
        if not self.check_and_handle_cooldown():
            self.logger.error("Cooldown handling failed")
            self.is_executing = False
            return False
        
        try:
            # The unified context should already have all necessary parameters
            # Actions should read from the unified context, not from action_data
            
            # Create and execute the appropriate action
            success, result_data = self._execute_action(action_name)
            
            if success:
                # No need to update context - unified ActionContext persists data automatically
                self.current_action_index += 1
                self.logger.debug("Action executed successfully")
                return True
            else:
                self.logger.error("Action execution failed")
                self.is_executing = False
                return False
                
        except Exception as e:
            self.logger.error(f"Exception during action execution: {e}")
            self.is_executing = False
            return False
            
    def _execute_action(self, action_name: str) -> tuple[bool, dict]:
        """
        Execute a specific action using YAML-driven metaprogramming approach.

        Args:
            action_name: Name of the action to execute

        Returns:
            Tuple of (success: bool, result_data: dict)
        """
        try:
            # Refresh character state to get current cooldown status
            if action_name not in ['wait', 'rest']:
                self._refresh_character_state()
            
            # Check for cooldown before attempting any action (except wait and rest)
            if action_name not in ['wait', 'rest'] and self._is_character_on_cooldown():
                self.logger.info(f"🕐 Cooldown detected before {action_name} - executing wait action instead")
                # Execute wait action to handle cooldown
                wait_success = self._execute_cooldown_wait()
                if wait_success:
                    # Refresh character state after waiting
                    self._refresh_character_state()
                    # Continue with the original action if cooldown is cleared
                    if not self._is_character_on_cooldown():
                        self.logger.info(f"✅ Cooldown cleared, proceeding with {action_name}")
                    else:
                        self.logger.info(f"⏰ Still on cooldown after wait, will retry {action_name} next iteration")
                        return True, {}  # Return success so plan continues
                else:
                    self.logger.warning("❌ Wait action failed during cooldown")
                    return False, {}
            
            # Prepare execution context
            context = self._build_execution_context(action_name=action_name)
            
            # Execute action through the metaprogramming executor
            result: ActionResult = self.action_executor.execute_action(
                action_name, self.client, context
            )
            
            # Extract useful data from action result
            result_data = {}
            if result.data:
                # Extract location data for move actions
                if action_name == 'find_monsters' and hasattr(result.data, 'get'):
                    # Find monsters returns target_x, target_y directly from standardize_coordinate_output
                    target_x = result.data.get('target_x')
                    target_y = result.data.get('target_y')
                    if target_x is not None and target_y is not None:
                        result_data.update({
                            'x': target_x,
                            'y': target_y,
                            'target_x': target_x,
                            'target_y': target_y
                        })
                        self.logger.info(f"Found monster location: ({target_x}, {target_y})")
                elif action_name == 'find_workshops' and hasattr(result.data, 'get'):
                    # Find workshops returns target_x, target_y directly from standardize_coordinate_output
                    target_x = result.data.get('target_x')
                    target_y = result.data.get('target_y')
                    if target_x is not None and target_y is not None:
                        result_data.update({
                            'target_x': target_x,
                            'target_y': target_y,
                            'workshop_x': target_x,
                            'workshop_y': target_y
                        })
                        self.logger.info(f"Found workshop location: ({target_x}, {target_y})")
                elif action_name == 'lookup_item_info' and hasattr(result.data, 'get'):
                    # Extract recipe information for use by find_resources
                    if result.data.get('success') and result.data.get('recipe_found'):
                        materials_needed = result.data.get('materials_needed', [])
                        resource_types = []
                        for material in materials_needed:
                            if material.get('is_resource'):
                                # Use resource_source mapping if available, otherwise fall back to code
                                resource_code = material.get('resource_source', material.get('code'))
                                resource_types.append(resource_code)
                        
                        # Check for crafting chain
                        crafting_chain = result.data.get('crafting_chain', [])
                        smelting_required = False
                        if crafting_chain:
                            # Find intermediate crafting steps (like copper smelting)
                            intermediate_steps = [step for step in crafting_chain if step.get('step_type') == 'craft_intermediate']
                            if intermediate_steps:
                                # Set up smelting context for the first intermediate step
                                first_step = intermediate_steps[0]
                                result_data.update({
                                    'smelt_item_code': first_step.get('item_code'),
                                    'smelt_item_name': first_step.get('item_name'),
                                    'smelt_skill': first_step.get('craft_skill')
                                })
                                smelting_required = True
                                
                        result_data.update({
                            'recipe_item_code': result.data.get('item_code'),
                            'recipe_item_name': result.data.get('item_name'),
                            'resource_types': resource_types,
                            'craft_skill': result.data.get('craft_skill'),
                            'materials_needed': materials_needed,
                            'crafting_chain': crafting_chain,
                            'smelting_required': smelting_required
                        })
                        self.logger.info(f"📋 Recipe selected: {result.data.get('item_name')} - needs {resource_types}")
                        if smelting_required:
                            self.logger.info(f"🔥 Smelting required: {result_data.get('smelt_item_code')}")
                elif action_name == 'evaluate_weapon_recipes' and hasattr(result.data, 'get'):
                    # Extract selected weapon information for use by find_correct_workshop
                    if result.data.get('success') and result.data.get('item_code'):
                        result_data.update({
                            'item_code': result.data.get('item_code'),
                            'selected_weapon': result.data.get('selected_weapon'),
                            'weapon_name': result.data.get('weapon_name'),
                            'workshop_type': result.data.get('workshop_type')
                        })
                        self.logger.info(f"🗡️ Weapon selected: {result.data.get('weapon_name')} (code: {result.data.get('item_code')})")
                elif action_name == 'find_resources' and hasattr(result.data, 'get'):
                    # Find resources returns target_x, target_y directly from standardize_coordinate_output
                    target_x = result.data.get('target_x')
                    target_y = result.data.get('target_y')
                    if target_x is not None and target_y is not None:
                        result_data.update({
                            'target_x': target_x,
                            'target_y': target_y,
                            'resource_x': target_x,
                            'resource_y': target_y
                        })
                        self.logger.info(f"Found resource location: ({target_x}, {target_y})")
                elif action_name == 'attack' and hasattr(result.data, 'get'):
                    # Track monster kills internally for goal progress
                    if result.data.get('success') and result.data.get('monster_defeated'):
                        # Update internal goal progress tracking
                        current_state = self.get_current_world_state()
                        goal_progress = current_state.get('goal_progress', {})
                        current_count = goal_progress.get('monsters_hunted', 0)
                        goal_progress['monsters_hunted'] = current_count + 1
                        
                        # Update the world state with the new count
                        self.update_world_state({'goal_progress': goal_progress})
                        self.logger.info(f"⚔️ Monster defeated! Total monsters hunted: {goal_progress['monsters_hunted']}")
            
            # Log execution result
            if result.success:
                self.logger.info(f"Action {action_name} executed successfully")
            else:
                self.logger.error(f"Action {action_name} failed: {result.error}")
                
                # If action failed, check if it's a cooldown error and refresh character state
                if result.error and "cooldown" in result.error.lower():
                    self.logger.info("Cooldown detected - refreshing character state")
                    self._refresh_character_state()
            
            return result.success, result_data
            
        except Exception as e:
            self.logger.error(f"Error executing action {action_name}: {e}")
            return False, {}
    
    def _execute_cooldown_wait(self) -> bool:
        """
        Execute a wait action to handle active cooldown using CooldownManager.
        
        Returns:
            True if wait action was successful, False otherwise
        """
        return self.cooldown_manager.handle_cooldown_with_wait(self.character_state, self.action_executor, self)
    
    def _is_character_on_cooldown(self) -> bool:
        """
        Check if character is currently on cooldown using CooldownManager.
        
        Returns:
            True if character is on cooldown, False otherwise
        """
        return self.cooldown_manager.is_character_on_cooldown(self.character_state)
    
    def _should_refresh_character_state(self) -> bool:
        """
        Determine if character state should be refreshed using CooldownManager.
        
        Returns:
            True if state should be refreshed, False if cached state is still valid
        """
        # Always refresh if we don't have a character state
        if not self.character_state:
            return True
        
        return self.cooldown_manager.should_refresh_character_state()
    
    def _refresh_character_state(self) -> None:
        """
        Refresh character state from the API to get updated cooldown information.
        """
        if not self.character_state or not self.client:
            return
            
        try:
            
            char_name = self.character_state.name
            response = get_character(name=char_name, client=self.client)
            
            if response and hasattr(response, 'data'):
                # Update character state with fresh data
                self.character_state.update_from_api_response(response.data)
                self.character_state.save()
                
                # Update cache timestamp after successful refresh
                self.cooldown_manager.mark_character_state_refreshed()
                
                # Log cooldown information if present
                cooldown_expiration = self.character_state.data.get('cooldown_expiration')
                if cooldown_expiration:
                    self.logger.info(f"Updated character cooldown expiration: {cooldown_expiration}")
                else:
                    self.logger.debug("Character state refreshed - no active cooldown")
                    
        except Exception as e:
            self.logger.warning(f"Failed to refresh character state: {e}")
    
    def _build_execution_context(self, action_name: str = None) -> 'ActionContext':
        """
        Build unified execution context for action execution.
        
        Args:
            action_name: Name of the action being executed (optional)
            
        Returns:
            ActionContext instance with all execution dependencies
        """
        
        # Always use the singleton plan context - no fallback needed
        # Update controller references to ensure they're current
        # This is important when character_state is set after controller init
        self.plan_action_context.controller = self
        self.plan_action_context.client = self.client
        self.plan_action_context.character_state = self.character_state
        self.plan_action_context.world_state = self.world_state
        self.plan_action_context.map_state = self.map_state
        self.plan_action_context.knowledge_base = self.knowledge_base
        
        # Update character info if character_state is available
        if self.character_state:
            if hasattr(self.character_state, 'name'):
                self.plan_action_context.character_name = self.character_state.name
            if hasattr(self.character_state, 'data'):
                char_data = self.character_state.data
                self.plan_action_context.character_x = char_data.get('x', 0)
                self.plan_action_context.character_y = char_data.get('y', 0)
                self.plan_action_context.character_level = char_data.get('level', 1)
                self.plan_action_context.character_hp = char_data.get('hp', 0)
                self.plan_action_context.character_max_hp = char_data.get('max_hp', 0)
                self.plan_action_context.equipment = char_data
        
        # Action context data is now handled through the unified ActionContext singleton
        # Parameters should already be set on the context before this method is called
        
        # Update context with current world state values
        # This ensures subgoal parameters like current_gathering_goal are available
        current_world_state = self.get_current_world_state(force_refresh=False)
        if current_world_state:
            # Copy relevant world state values to ActionContext
            if 'current_gathering_goal' in current_world_state:
                self.plan_action_context.set(StateParameters.CURRENT_GATHERING_GOAL, current_world_state['current_gathering_goal'])
                self.logger.debug(f"Set current_gathering_goal in ActionContext: {current_world_state['current_gathering_goal']}")
            
            # Set unified context properties directly from world state
            # Use flat properties as per unified context architecture
            location_context = current_world_state.get('location_context', {})
            if location_context.get('target_x') is not None:
                self.plan_action_context.target_x = location_context['target_x']
            if location_context.get('target_y') is not None:
                self.plan_action_context.target_y = location_context['target_y']
            if location_context.get('workshop_x') is not None:
                self.plan_action_context.workshop_x = location_context['workshop_x']
                self.plan_action_context.set(StateParameters.WORKSHOP_X, location_context['workshop_x'])
            if location_context.get('workshop_y') is not None:
                self.plan_action_context.workshop_y = location_context['workshop_y']
                self.plan_action_context.set(StateParameters.WORKSHOP_Y, location_context['workshop_y'])
        
        # Action configurations are now auto-loaded by ActionFactory
        # Legacy hardcoded parameter loading removed
        
        # Include current goal parameters if available
        if hasattr(self, 'current_goal_parameters') and self.current_goal_parameters:
            for param_name, param_value in self.current_goal_parameters.items():
                # All parameters must be registered in StateParameters - no fallbacks
                if StateParameters.validate_parameter(param_name):
                    self.plan_action_context.set(param_name, param_value)
                else:
                    self.logger.error(f"Parameter '{param_name}' not registered in StateParameters - skipping")
                    # Fail fast - don't add backward compatibility
            
        
        context = self.plan_action_context
        
        # For wait actions, calculate and add wait_duration if not already present
        # All actions now use ActionContext - action_data is legacy
        detected_action_name = action_name
        if detected_action_name == 'wait' and getattr(context, 'wait_duration', 1.0) == 1.0:
            # Refresh character state to get current cooldown info
            self._refresh_character_state()
            wait_duration = self.cooldown_manager.calculate_wait_duration(self.character_state)
            context.wait_duration = wait_duration
            self.logger.info(f"Added calculated wait_duration={wait_duration} to wait action context")
        
        return context
    
    def reset_failed_goal(self, goal_name: str) -> None:
        """Reset a failed goal to make it available for selection again."""
        if hasattr(self, 'mission_executor') and self.mission_executor:
            self.mission_executor.reset_failed_goal(goal_name)
            self.logger.info(f"🔄 Reset failed goal: {goal_name}")
    
    def get_available_actions(self) -> List[str]:
        """Get list of available actions from the metaprogramming executor."""
        return self.action_executor.get_available_actions()
    
    def reload_action_configurations(self) -> None:
        """Reload action and state configurations from YAML."""
        self.action_executor.reload_configuration()
        self.reload_state_configurations()
        # Reload mission executor configuration
        if hasattr(self, 'mission_executor'):
            self.mission_executor._load_configuration()
        # Reload learning manager configuration
        if hasattr(self, 'learning_manager'):
            self.learning_manager.reload_configuration()
        # Reload skill goal manager configuration
        if hasattr(self, 'skill_goal_manager'):
            self.skill_goal_manager.reload_configuration()
        self.logger.info("Configurations reloaded including all managers")
            
    def execute_plan(self) -> bool:
        """
        Execute the entire current plan.

        Returns:
            True if all actions were executed successfully, False otherwise
        """
        if not self.current_plan:
            self.logger.warning("No plan to execute")
            return False
            
        # The plan_action_context is already initialized as a singleton in __init__
        # Just ensure it's updated with latest controller state without losing action_results
        self.plan_action_context.controller = self
        self.plan_action_context.client = self.client
        self.plan_action_context.character_state = self.character_state
        self.plan_action_context.world_state = self.world_state
        self.plan_action_context.map_state = self.map_state
        self.plan_action_context.knowledge_base = self.knowledge_base
        
        # Update character info if character_state is available
        if self.character_state:
            if hasattr(self.character_state, 'name'):
                self.plan_action_context.character_name = self.character_state.name
            if hasattr(self.character_state, 'data'):
                char_data = self.character_state.data
                self.plan_action_context.character_x = char_data.get('x', 0)
                self.plan_action_context.character_y = char_data.get('y', 0)
                self.plan_action_context.character_level = char_data.get('level', 1)
                self.plan_action_context.character_hp = char_data.get('hp', 0)
                self.plan_action_context.character_max_hp = char_data.get('max_hp', 0)
                self.plan_action_context.equipment = char_data
        self.is_executing = True
        
        while self.is_executing and self.current_action_index < len(self.current_plan):
            if not self.execute_next_action():
                return False
        
        # Plan completed successfully - set executing to False
        self.is_executing = False        
        return True
    
    def _execute_single_action(self, action_name: str, action_data: Dict) -> bool:
        """
        Execute a single action and return success status.
        Used by iterative GOAP planning for single-action execution with learning.
        
        Args:
            action_name: Name of the action to execute
            action_data: Action data from the plan
            
        Returns:
            True if action executed successfully, False otherwise
        """
        try:
            # Build execution context
            context = self._build_execution_context(action_name)
            
            # Execute the action using the action executor
            result = self.action_executor.execute_action(action_name, self.client, context)
            
            # Store the result for potential access by GOAP manager
            self.last_action_result = result
            
            if result and hasattr(result, 'success') and result.success:
                # Merge result data into unified context if available
                if hasattr(result, 'data') and result.data and isinstance(context, ActionContext):
                    for key, value in result.data.items():
                        context.set_result(key, value)
                    self.logger.debug(f"Merged {len(result.data)} result items from {action_name} into context")
                    
                    # IMPORTANT: If using plan_action_context, it's the same object as context
                    # due to line 499 in _build_execution_context, so no need to update separately
                return True
            else:
                self.logger.warning(f"Action {action_name} failed: {result}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing single action {action_name}: {e}")
            return False

        
    def is_plan_complete(self) -> bool:
        """
        Check if the current plan is complete.
        
        Returns:
            True if plan is complete or no plan exists, False otherwise
        """
        return not self.current_plan or self.current_action_index >= len(self.current_plan)
        
    def cancel_plan(self) -> None:
        """Cancel the current plan execution."""
        self.logger.info("Cancelling current plan")
        self.current_plan = []
        self.current_action_index = 0
        self.is_executing = False
        
    def get_plan_status(self) -> Dict:
        """
        Get the current status of plan execution.
        
        Returns:
            Dictionary containing plan status information
        """
        return {
            'has_plan': bool(self.current_plan),
            'plan_length': len(self.current_plan),
            'current_action_index': self.current_action_index,
            'is_executing': self.is_executing,
            'is_complete': self.is_plan_complete(),
            'current_action': (
                self.current_plan[self.current_action_index]['name']
                if self.current_plan and self.current_action_index < len(self.current_plan)
                else None
            )
        }
        
    # create_world_with_planner and calculate_best_plan moved to GOAPExecutionManager

    def _apply_computed_state_flags(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply computed state flags based on actual data values.
        
        This replaces the non-declarative state_mappings that were in YAML configuration,
        implementing truly computed state based on data rather than configuration logic.
        
        Args:
            state: Current state dictionary
            
        Returns:
            State dictionary with computed boolean flags added
        """
        # Character status computed flags (using fresh character data for HP)
        if 'character_status' in state:
            char_status = state['character_status']
            level = char_status.get('level', 1)
            
            # Get fresh HP data from character state for accurate calculation
            current_hp = self.character_state.data.get('hp', 100)
            max_hp = self.character_state.data.get('max_hp', 100)
            
            # Compute derived boolean flags using fresh HP data
            char_status['hp_critically_low'] = is_hp_critically_low(current_hp, max_hp, 30.0)
            char_status['hp_sufficient_for_combat'] = is_hp_sufficient_for_combat(current_hp, max_hp, 80.0)
            char_status['is_low_level'] = level <= 5
            char_status['safe'] = is_character_safe(current_hp, max_hp, 30.0)
            
        # Equipment status computed flags
        if 'equipment_status' in state:
            eq_status = state['equipment_status']
            weapon = eq_status.get('weapon')
            selected_item = eq_status.get('selected_item')
            equipped = eq_status.get('equipped', False)
            
            # Compute derived boolean flags from data
            eq_status['has_weapon'] = weapon is not None
            eq_status['has_selected_item'] = selected_item is not None
            eq_status['weapon_equipped'] = equipped
            
        # Combat context computed flags
        if 'combat_context' in state:
            combat = state['combat_context']
            win_rate = combat.get('recent_win_rate', 1.0)
            status = combat.get('status', 'idle')
            
            # Compute derived boolean flags from data
            combat['has_recent_combat'] = win_rate > 0
            combat['is_combat_viable'] = status != 'not_viable'
            
        # Goal progress computed flags
        if 'goal_progress' in state:
            progress = state['goal_progress']
            monsters_hunted = progress.get('monsters_hunted', 0)
            
            # Compute derived boolean flags from data
            progress['has_hunted_monsters'] = monsters_hunted > 0
            
            # XP percentage calculation from character status
            if 'character_status' in state:
                xp_pct = state['character_status'].get('xp_percentage', 0.0)
                progress['has_gained_xp'] = xp_pct > 0
            
        return state

    def get_current_world_state(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get the current world state for GOAP planning using configuration-driven state calculation.
        
        Args:
            force_refresh: If True, forces character state refresh. Otherwise uses cached state.
            
        Returns:
            Dictionary representing current world state
        """
        # Only refresh character state when explicitly requested or when state is stale
        if force_refresh or self._should_refresh_character_state():
            self._refresh_character_state()
        
        # Use goal manager for configuration-driven state calculation
        state = self.goal_manager.calculate_world_state(
            character_state=self.character_state,
            map_state=self.map_state,
            knowledge_base=self.knowledge_base
        )
        
        # Apply any additional derived state using state engine
        if hasattr(self.world_state, 'data') and self.world_state.data:
            # Merge ALL persistent world state data, not just a subset
            # This ensures states like inventory_updated, materials_sufficient, etc. are preserved
            world_data = self.world_state.data
            for key, value in world_data.items():
                # Handle nested state merging (e.g., goal_progress)
                if isinstance(value, dict) and key in state and isinstance(state[key], dict):
                    # Merge nested dictionaries - calculated values first, then persistent values override
                    merged_state = state[key].copy()  # Start with calculated state
                    merged_state.update(value)  # Let persistent state override calculated state
                    state[key] = merged_state
                    self.logger.debug(f"Merged nested state for {key}: {state[key]}")
                elif key not in state:
                    # Add any persisted state keys that don't exist in the calculated state
                    # This preserves any additional state that actions may have added
                    state[key] = value
        
        # Apply computed state calculations (moved from YAML for declarative configuration)
        state = self._apply_computed_state_flags(state)
        
        self.logger.debug(f"Current world state: {state}")
        return state

    def update_world_state(self, state_updates: Dict[str, Any]) -> None:
        """
        Update world state with new values.
        
        This is the UNIFIED method for all state updates, called by the
        post-execution handler in ActionExecutor.
        
        Args:
            state_updates: Dictionary of state updates to apply
        """
        if not self.world_state:
            self.logger.error("World state not initialized")
            return
            
        # Apply updates to world state
        self.world_state.data.update(state_updates)
        self.world_state.save()
        
        self.logger.debug(f"Updated world state with {len(state_updates)} changes")

    # load_actions_from_config and achieve_goal_with_goap moved to GOAPExecutionManager
    # hunt_until_level moved to MissionExecutor


    def execute_autonomous_mission(self, mission_parameters: Dict[str, Any]) -> bool:
        """
        Execute an autonomous mission using goal template-driven approach via MissionExecutor.
        
        This method now delegates to the MissionExecutor for YAML-configurable mission execution,
        eliminating hardcoded mission logic.
        
        Args:
            mission_parameters: Parameters for the mission (e.g., target_level)
            
        Returns:
            True if mission objectives were achieved, False otherwise
        """
        return self.mission_executor.execute_progression_mission(mission_parameters)

    def level_up_goal(self, target_level: int = None) -> bool:
        """
        Execute level progression using goal template-driven approach via MissionExecutor.
        
        This method replaces the previous 149-line hardcoded level_up_goal method
        with template-driven execution for configurable level progression.
        
        Args:
            target_level: The level to reach (defaults to current level + 1)
            
        Returns:
            True if target level was reached, False otherwise
        """
        return self.mission_executor.execute_level_progression(target_level)
    
    def skill_up_goal(self, skill_type: SkillType, target_level: int) -> bool:
        """
        Execute skill progression using skill-specific goal templates.
        
        Supports all crafting, gathering, and combat skills with configurable progression.
        
        Args:
            skill_type: The skill to level up (e.g., SkillType.WOODCUTTING)
            target_level: The target skill level to reach
            
        Returns:
            True if target skill level was reached, False otherwise
        """
        if not self.client or not self.character_state:
            self.logger.error("Cannot execute skill progression without client and character state")
            return False
        
        current_state = self.get_current_world_state()
        return self.skill_goal_manager.achieve_skill_goal_with_goap(
            skill_type, target_level, current_state, self
        )
    
    def get_skill_progression_strategy(self, skill_type: SkillType, current_level: int) -> Dict[str, Any]:
        """
        Get optimal progression strategy for a skill at a given level.
        
        Delegates to SkillGoalManager for skill-specific optimization.
        
        Args:
            skill_type: The skill to get strategy for
            current_level: Current skill level
            
        Returns:
            Strategy dictionary with actions and priorities
        """
        return self.skill_goal_manager.get_skill_progression_strategy(skill_type, current_level)
    
    def get_available_skills(self) -> List[SkillType]:
        """
        Get list of skills that have goal templates defined.
        
        Returns:
            List of SkillType enums for available skills
        """
        return self.skill_goal_manager.get_available_skills()

    def find_and_move_to_level_appropriate_monster(self, search_radius: int = 10, level_range: int = 2) -> bool:
        """
        Find the nearest level-appropriate monster location and move the character there.
        
        Now uses GOAP action execution for configurable monster search and movement.

        Args:
            search_radius: The maximum radius to search for monsters (default: 10)
            level_range: Acceptable level range (+/-) for monster selection (default: 2)

        Returns:
            True if successful, False otherwise
        """
        if not self.client or not self.character_state:
            self.logger.error("Cannot find monsters without API client and character state")
            return False

        try:
            # ActionFactory will auto-load parameters from default_actions.yaml
            # Set search parameters in context for the action to use
            context = self._build_execution_context('find_and_move_to_monster')
            context.set(StateParameters.SEARCH_RADIUS, search_radius)
            context.set(StateParameters.LEVEL_RANGE, level_range)
            
            result = self.action_executor.execute_action('find_and_move_to_monster', self.client, context)
            
            return result.success
            
        except Exception as e:
            self.logger.error(f"Error finding and moving to level-appropriate monster: {e}")
            return False

    # Learning and Knowledge Methods

    def learn_from_map_exploration(self, x: int, y: int, map_response) -> None:
        """
        Learn from exploring a map location (integrates with MapState).
        
        Args:
            x: X coordinate explored
            y: Y coordinate explored  
            map_response: Response from map API call
        """
        try:
            if hasattr(map_response, 'data') and map_response.data:
                map_data = map_response.data.to_dict() if hasattr(map_response.data, 'to_dict') else map_response.data
                
                # Ensure map_state exists and let it handle location storage
                if not self.map_state:
                    self.map_state = MapState(self.client)
                
                # MapState will handle the location caching automatically when scan() is called
                # We just need to learn from the content if it exists
                content = map_data.get('content')
                if content:
                    raw_content_type = content.get('type', content.get('type_', 'unknown'))
                    content_code = content.get('code', 'unknown')
                    
                    # Use raw content type directly - knowledge base handles categorization
                    content_type = raw_content_type if raw_content_type != 'unknown' else 'resource'
                    
                    # Learn from content discovery
                    self.logger.debug(f"🔍 About to learn {content_type} '{content_code}' at ({x}, {y})")
                    self.logger.debug(f"🔍 Raw content type: '{raw_content_type}', Categorized as: '{content_type}'")
                    self.logger.debug(f"🔍 Content attributes: {list(content.keys())}")
                    self.logger.debug(f"🔍 Knowledge base type: {type(self.knowledge_base)}")
                    self.logger.debug(f"🔍 Knowledge base filename: {getattr(self.knowledge_base, 'filename', 'no filename')}")
                    
                    self.knowledge_base.learn_from_content_discovery(
                        content_type, content_code, x, y, content
                    )
                    
                    self.logger.debug(f"🔍 Knowledge base data after learning: {list(self.knowledge_base.data.keys())}")
                    
                    self.knowledge_base.save()
                    self.logger.debug("🔍 Knowledge base saved")
                    
                    self.logger.info(f"🧠 Learned: {content_type} '{content_code}' at ({x}, {y})")
                else:
                    self.logger.debug(f"🧠 Explored empty location ({x}, {y})")
                    
        except Exception as e:
            self.logger.warning(f"Failed to learn from map exploration at ({x}, {y}): {e}")
            # If it's a serialization error, try to clean up the knowledge base
            if 'cannot represent an object' in str(e) or 'DropSchema' in str(e):
                self.logger.info("Detected DropSchema serialization error - cleaning knowledge base")
                try:
                    self.knowledge_base._sanitize_data()
                    self.knowledge_base.save()
                    self.logger.info("Knowledge base cleaned and saved successfully")
                except Exception as cleanup_error:
                    self.logger.error(f"Failed to clean knowledge base: {cleanup_error}")
    

    def learn_from_combat(self, monster_code: str, result: str, pre_combat_hp: int = None, fight_data: Dict = None, combat_context: Dict = None) -> None:
        """
        Learn from combat experience.
        
        Args:
            monster_code: Code of the monster fought
            result: Combat result ('win', 'loss', 'flee')
            pre_combat_hp: Character HP before combat
            fight_data: Additional fight information (XP, gold, drops, turns)
            combat_context: Additional combat context (pre_combat_hp, post_combat_hp)
        """
        try:
            if not self.character_state:
                return
                
            character_data = self.character_state.data.copy()
            
            # Use post-combat HP from context if available (more accurate than character_state)
            if combat_context and 'post_combat_hp' in combat_context and combat_context['post_combat_hp'] is not None:
                character_data['hp'] = combat_context['post_combat_hp']
                self.logger.debug(f"🔍 Using post-combat HP from context: {combat_context['post_combat_hp']}")
            
            # Handle pre-combat HP properly - try to calculate actual pre-combat HP
            if pre_combat_hp is not None and pre_combat_hp > 0:
                character_data['hp_before'] = pre_combat_hp
            else:
                # If no pre-combat HP provided, try to estimate from current state
                current_hp = character_data.get('hp', 0)
                max_hp = character_data.get('max_hp', 125)
                
                # If character is at full health now but we know there was a fight,
                # they likely rested between combat and learning
                if current_hp == max_hp and result == 'loss':
                    # For loss, estimate pre-combat HP was full before taking damage
                    # We can estimate damage from fight data or use a reasonable default
                    estimated_damage = 50  # Default damage estimate for failed fights
                    if fight_data and fight_data.get('turns', 0) > 0:
                        # Estimate based on turns - more turns = more damage
                        estimated_damage = min(max_hp - 10, fight_data.get('turns', 1) * 5)
                    character_data['hp_before'] = max_hp
                else:
                    character_data['hp_before'] = current_hp
                
            # Record combat result with fight data
            self.knowledge_base.record_combat_result(monster_code, result, character_data, fight_data)
            self.knowledge_base.save()
            
            # Log learning insights
            success_rate = self.knowledge_base.get_monster_combat_success_rate(
                monster_code, character_data.get('level', 1)
            )
            
            if success_rate >= 0:
                self.logger.info(f"🧠 Combat learning: {monster_code} success rate at level {character_data.get('level', 1)}: {success_rate:.1%}")
            else:
                self.logger.info(f"🧠 First combat data recorded for {monster_code}")
            
            # Log additional fight details if available
            if fight_data:
                xp_gained = fight_data.get('xp', 0)
                gold_gained = fight_data.get('gold', 0)
                turns = fight_data.get('turns', 0)
                if xp_gained > 0:
                    self.logger.info(f"💰 Combat rewards: {xp_gained} XP, {gold_gained} gold ({turns} turns)")
                
        except Exception as e:
            self.logger.warning(f"Failed to learn from combat with {monster_code}: {e}")
            # If it's a serialization error, try to clean up the knowledge base
            if 'cannot represent an object' in str(e) or 'DropSchema' in str(e):
                self.logger.info("Detected DropSchema serialization error - cleaning knowledge base")
                try:
                    self.knowledge_base._sanitize_data()
                    self.knowledge_base.save()
                    self.logger.info("Knowledge base cleaned and saved successfully")
                except Exception as cleanup_error:
                    self.logger.error(f"Failed to clean knowledge base: {cleanup_error}")

    def find_known_monsters_nearby(self, max_distance: int = 15, character_level: int = None, 
                                 level_range: int = 2) -> Optional[List[Dict]]:
        """
        Find known monster locations near the character using learned knowledge and MapState.
        
        Delegates to LearningManager for knowledge-based monster search.
        
        Args:
            max_distance: Maximum distance to search
            character_level: Character level for level filtering
            level_range: Acceptable level range for monsters
            
        Returns:
            List of monster location info dictionaries or None
        """
        return self.learning_manager.find_known_monsters_nearby(
            self.character_state, max_distance, character_level, level_range
        )

    def intelligent_monster_search(self, search_radius: int = 8) -> bool:
        """
        Intelligent monster search that combines learned knowledge with exploration.
        
        Now uses GOAP action execution for configurable intelligent search.
        
        Args:
            search_radius: Maximum radius to search
            
        Returns:
            True if monster was found and character moved to it, False otherwise
        """
        if not self.client or not self.character_state:
            return False
            
        try:
            # ActionFactory will auto-load parameters from default_actions.yaml
            # Set search parameters in context for the action to use
            context = self._build_execution_context('intelligent_monster_search')
            context.set(StateParameters.SEARCH_RADIUS, search_radius)
            
            result = self.action_executor.execute_action('intelligent_monster_search', self.client, context)
            
            return result.success
            
        except Exception as e:
            self.logger.error(f"Error in intelligent monster search: {e}")
            return False

    def get_learning_insights(self) -> Dict:
        """
        Get insights and statistics about what the AI has learned.
        
        Delegates to LearningManager for YAML-configurable insights generation.
        
        Returns:
            Dictionary containing learning statistics and insights
        """
        return self.learning_manager.get_learning_insights()

    def optimize_with_knowledge(self, goal_type: str = None) -> Dict[str, Any]:
        """
        Use learned knowledge to optimize planning and decision making.
        
        Delegates to LearningManager for YAML-configurable optimization suggestions.
        
        Args:
            goal_type: Type of goal to optimize for ('combat', 'exploration', 'resources')
            
        Returns:
            Dictionary with optimization suggestions
        """
        return self.learning_manager.optimize_with_knowledge(self.character_state, goal_type)

    def learn_all_game_data_efficiently(self) -> Dict:
        """
        Learn about all available game data using efficient get_all_* API calls.
        
        This replaces inefficient map tile-by-tile scanning with direct API queries
        for resources, monsters, items, NPCs, and map locations.
        Should be called once during initialization or when comprehensive game knowledge is needed.
        
        Returns:
            Dictionary with comprehensive learning results and statistics
        """
        if not hasattr(self, 'learning_manager') or not self.learning_manager:
            return {
                'success': False,
                'error': 'Learning manager not available',
                'stats': {'total': 0}
            }
        
        if not self.client:
            return {
                'success': False,
                'error': 'API client not available',
                'stats': {'total': 0}
            }
        
        self.logger.info("🚀 Starting comprehensive game data learning...")
        result = self.learning_manager.learn_all_game_data_bulk(self.client)
        
        if result.get('success'):
            stats = result.get('stats', {})
            self.logger.info(f"✅ Game data learning complete: {stats.get('total', 0)} total items learned")
        else:
            errors = result.get('errors', [])
            if errors:
                self.logger.warning(f"⚠️ Game data learning had errors: {'; '.join(errors)}")
            else:
                self.logger.warning(f"⚠️ Game data learning failed: {result.get('error', 'Unknown error')}")
        
        return result

