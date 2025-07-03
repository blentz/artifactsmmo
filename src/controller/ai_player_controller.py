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
        
        # Action context for passing data between actions
        self.action_context: Dict[str, Any] = {}
        
        # Current goal parameters for passing to actions
        self.current_goal_parameters: Dict[str, Any] = {}
        
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
                    wait_action_data = {'wait_duration': optimal_duration}
                    success, _ = self._execute_action('wait', wait_action_data)
                    
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
            # Create and execute the appropriate action
            success, result_data = self._execute_action(action_name, action_data)
            
            if success:
                # Store action result data for use by subsequent actions
                if result_data and hasattr(self, 'action_context'):
                    self.action_context.update(result_data)
                
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
            
    def _execute_action(self, action_name: str, action_data: Dict) -> tuple[bool, dict]:
        """
        Execute a specific action using YAML-driven metaprogramming approach.

        Args:
            action_name: Name of the action to execute
            action_data: Action data from the plan

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
            context = self._build_execution_context(action_data, action_name)
            
            # Execute action through the metaprogramming executor
            result: ActionResult = self.action_executor.execute_action(
                action_name, action_data, self.client, context
            )
            
            # Extract useful data from action result
            result_data = {}
            if result.response:
                # Extract location data for move actions
                if action_name == 'find_monsters' and hasattr(result.response, 'get'):
                    location = result.response.get('location')
                    if location:
                        result_data.update({
                            'x': location[0],
                            'y': location[1],
                            'target_x': location[0],
                            'target_y': location[1]
                        })
                        self.logger.info(f"Found monster location: {location}")
                elif action_name == 'find_workshops' and hasattr(result.response, 'get'):
                    location = result.response.get('location')
                    if location:
                        result_data.update({
                            'target_x': location[0],
                            'target_y': location[1],
                            'workshop_x': location[0],
                            'workshop_y': location[1]
                        })
                        self.logger.info(f"Found workshop location: {location}")
                elif action_name == 'lookup_item_info' and hasattr(result.response, 'get'):
                    # Extract recipe information for use by find_resources
                    if result.response.get('success') and result.response.get('recipe_found'):
                        materials_needed = result.response.get('materials_needed', [])
                        resource_types = []
                        for material in materials_needed:
                            if material.get('is_resource'):
                                # Use resource_source mapping if available, otherwise fall back to code
                                resource_code = material.get('resource_source', material.get('code'))
                                resource_types.append(resource_code)
                        
                        # Check for crafting chain
                        crafting_chain = result.response.get('crafting_chain', [])
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
                            'recipe_item_code': result.response.get('item_code'),
                            'recipe_item_name': result.response.get('item_name'),
                            'resource_types': resource_types,
                            'craft_skill': result.response.get('craft_skill'),
                            'materials_needed': materials_needed,
                            'crafting_chain': crafting_chain,
                            'smelting_required': smelting_required
                        })
                        self.logger.info(f"📋 Recipe selected: {result.response.get('item_name')} - needs {resource_types}")
                        if smelting_required:
                            self.logger.info(f"🔥 Smelting required: {result_data.get('smelt_item_code')}")
                elif action_name == 'evaluate_weapon_recipes' and hasattr(result.response, 'get'):
                    # Extract selected weapon information for use by find_correct_workshop
                    if result.response.get('success') and result.response.get('item_code'):
                        result_data.update({
                            'item_code': result.response.get('item_code'),
                            'selected_weapon': result.response.get('selected_weapon'),
                            'weapon_name': result.response.get('weapon_name'),
                            'workshop_type': result.response.get('workshop_type')
                        })
                        self.logger.info(f"🗡️ Weapon selected: {result.response.get('weapon_name')} (code: {result.response.get('item_code')})")
                elif action_name == 'find_resources' and hasattr(result.response, 'get'):
                    location = result.response.get('location')
                    if location:
                        result_data.update({
                            'target_x': location[0],
                            'target_y': location[1],
                            'resource_x': location[0],
                            'resource_y': location[1]
                        })
                        self.logger.info(f"Found resource location: {location}")
                elif action_name == 'attack' and hasattr(result.response, 'get'):
                    # Track monster kills internally for goal progress
                    if result.response.get('success') and result.response.get('monster_defeated'):
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
                if result.execution_time:
                    self.logger.debug(f"Execution time: {result.execution_time:.3f}s")
            else:
                self.logger.error(f"Action {action_name} failed: {result.error_message}")
                
                # If action failed, check if it's a cooldown error and refresh character state
                if result.error_message and "cooldown" in result.error_message.lower():
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
    
    def _build_execution_context(self, action_data: Dict, action_name: str = None) -> 'ActionContext':
        """
        Build unified execution context for action execution.
        
        Args:
            action_data: Action data from the plan
            action_name: Name of the action being executed (optional)
            
        Returns:
            ActionContext instance with all execution dependencies
        """
        
        # Create unified context from controller state
        context = ActionContext.from_controller(self, action_data)
        
        # Add shared action context data from previous actions
        if hasattr(self, 'action_context') and self.action_context:
            for key, value in self.action_context.items():
                context.set_result(key, value)
                self.logger.debug(f"Added shared action data to context: {key}")
        
        # Add action configurations if available
        if hasattr(self.action_executor, 'config_data') and self.action_executor.config_data:
            eval_config = self.action_executor.config_data.data.get('evaluate_weapon_recipes', {})
            if eval_config:
                context.set_parameter('action_config', eval_config)
        
        # Include current goal parameters if available
        if hasattr(self, 'current_goal_parameters') and self.current_goal_parameters:
            for param_name, param_value in self.current_goal_parameters.items():
                context.set_parameter(param_name, param_value)
                self.logger.debug(f"Added goal parameter to action context: {param_name} = {param_value}")
        
        # For wait actions, calculate and add wait_duration if not already present
        # Check both action_data.name and action_name parameter
        detected_action_name = action_name or action_data.get('name')
        if detected_action_name == 'wait' and 'wait_duration' not in action_data:
            # Refresh character state to get current cooldown info
            self._refresh_character_state()
            wait_duration = self.cooldown_manager.calculate_wait_duration(self.character_state)
            context.set_parameter('wait_duration', wait_duration)
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
            
        # Preserve action context between plan iterations
        # This allows actions to pass information to subsequent actions
        if not hasattr(self, 'action_context'):
            self.action_context = {}
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
            context = self._build_execution_context(action_data, action_name)
            
            # Execute the action using the action executor
            result = self.action_executor.execute_action(action_name, action_data, self.client, context)
            
            if result and hasattr(result, 'success') and result.success:
                # Update action context with results for future actions
                if hasattr(result, 'response') and result.response:
                    self._update_action_context_from_response(action_name, result.response)
                
                # Also capture data stored in the action context results
                if hasattr(context, 'action_results') and context.action_results:
                    self._update_action_context_from_results(action_name, context.action_results)
                
                return True
            else:
                self.logger.warning(f"Action {action_name} failed: {result}")
                # Store the failure result for cooldown detection
                self.last_action_result = result if isinstance(result, dict) else {'error': str(result)}
                return False
                
        except Exception as e:
            self.logger.error(f"Error executing single action {action_name}: {e}")
            return False

    def _update_action_context_from_response(self, action_name: str, response) -> None:
        """
        Update action context based on action execution response.
        Used to pass data between actions in a plan.
        """
        if not response:
            return
            
        # If response is a dictionary, merge it into action context
        if isinstance(response, dict):
            if not hasattr(self, 'action_context'):
                self.action_context = {}
            self.action_context.update(response)
            
            # Extract coordinates from location tuple if present
            if 'location' in response and isinstance(response['location'], tuple) and len(response['location']) >= 2:
                self.action_context['target_x'] = response['location'][0]
                self.action_context['target_y'] = response['location'][1]
                self.logger.info(f"Extracted coordinates from {action_name}: ({response['location'][0]}, {response['location'][1]})")
            
            # Log coordinate updates if present
    
    def _update_action_context_from_results(self, action_name: str, action_results: Dict) -> None:
        """
        Update action context based on action context results.
        Used to pass data stored via context.set_result() between actions in a plan.
        """
        if not action_results:
            return
            
        if not hasattr(self, 'action_context'):
            self.action_context = {}
        
        # Merge action results into shared context
        self.action_context.update(action_results)
        self.logger.debug(f"Updated shared action context from {action_name} with {len(action_results)} items")
        
        # Log key data transfers for important actions
        if action_name == 'analyze_equipment_gaps' and 'equipment_gap_analysis' in action_results:
            gap_count = len(action_results['equipment_gap_analysis']) if action_results['equipment_gap_analysis'] else 0
            self.logger.info(f"📊 Captured equipment gap analysis from {action_name}: {gap_count} slots analyzed")
        elif action_name == 'select_optimal_slot' and 'target_equipment_slot' in action_results:
            slot = action_results['target_equipment_slot']
            self.logger.info(f"🎯 Captured slot selection from {action_name}: {slot}")
        elif action_name == 'evaluate_recipes' and 'selected_item' in action_results:
            item = action_results['selected_item']
            self.logger.info(f"🔧 Captured recipe selection from {action_name}: {item}")
            if 'target_x' in response and 'target_y' in response:
                self.logger.info(f"Updated coordinates from {action_name}: ({response['target_x']}, {response['target_y']})")
        
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
                    # Merge nested dictionaries - persistent values first, then calculated values override
                    merged_state = value.copy()  # Start with persistent state
                    merged_state.update(state[key])  # Let calculated state override persistent state
                    state[key] = merged_state
                    self.logger.debug(f"Merged nested state for {key}: {state[key]}")
                elif key not in state:
                    # Only update if the key doesn't already exist in the calculated state
                    # This allows calculated states to override persisted states when needed
                    state[key] = value
        
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

    # DEPRECATED: Use update_world_state() instead
    # This method is replaced by the unified post-execution handler in ActionExecutor

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
        
        Now uses composite action execution for YAML-configurable monster search and movement.

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
            action_data = {
                'search_radius': search_radius,
                'level_range': level_range
            }
            
            context = self._build_execution_context(action_data, 'find_and_move_to_monster')
            result = self.action_executor.execute_action('find_and_move_to_monster', action_data, self.client, context)
            
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
        
        Now uses composite action execution for YAML-configurable intelligent search.
        
        Args:
            search_radius: Maximum radius to search
            
        Returns:
            True if monster was found and character moved to it, False otherwise
        """
        if not self.client or not self.character_state:
            return False
            
        try:
            action_data = {'search_radius': search_radius}
            context = self._build_execution_context(action_data, 'intelligent_monster_search')
            result = self.action_executor.execute_action('intelligent_monster_search', action_data, self.client, context)
            
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

