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
from src.game.map.state import MapState
from src.lib.action_context import ActionContext
from src.lib.state_parameters import StateParameters
from src.lib.unified_state_context import UnifiedStateContext, get_unified_context

# GOAP functionality now handled by GOAPExecutionManager
from src.lib.state_loader import StateManagerMixin

# Metaprogramming components
from .action_executor import ActionExecutor, ActionResult
# CooldownManager removed - using ActionBase cooldown handling for architecture compliance

# Additional imports
from .goal_manager import GOAPGoalManager
from .goap_execution_manager import GOAPExecutionManager
from .learning_manager import LearningManager
from .mission_executor import MissionExecutor
# SkillGoalManager removed - use existing goals instead

# Specialized managers for business logic
from .state_computation_manager import StateComputationManager
from .action_result_processor import ActionResultProcessor


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
        # Cooldown handling moved to ActionBase for architecture compliance
        self.mission_executor = MissionExecutor(self.goal_manager, self)
        # SkillGoalManager removed - use existing goals instead
        self.goap_execution_manager = GOAPExecutionManager(self.action_executor.factory)
        
        # Initialize specialized managers for business logic
        self.state_computation_manager = StateComputationManager()
        self.action_result_processor = ActionResultProcessor()
        
        # Initialize learning manager (will be set up after states are created)
        self.learning_manager = None
        
        # Initialize YAML-driven state management
        self.initialize_state_management()
        
        # Create managed states using YAML configuration
        self.world_state = self.create_managed_state('world_state', 'world_state')
        self.knowledge_base = self.create_managed_state('knowledge_base', 'knowledge_base')
        
        # Character and map states are created when needed
        self.character_state: Optional[CharacterState] = None
        
        # Initialize learning manager after states are available
        self.learning_manager = LearningManager(self.knowledge_base, self.knowledge_base.map_state, self.client)
        
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
        Set the current character state by updating the unified context singleton.
        
        Following docs/ARCHITECTURE.md: UnifiedStateContext is the single source of truth.
        No separate character state storage - all data goes directly to the singleton.
        
        Args:
            character_state: The character state to use
        """
        # Store reference for API compatibility but don't use for state data
        self.character_state = character_state
        
        # Update the singleton directly - no separate state storage
        unified_context = get_unified_context()
        
        if hasattr(character_state, 'data') and character_state.data:
            char_data = character_state.data
            current_hp = char_data.get('hp', 0)
            max_hp = char_data.get('max_hp', 100)
            cooldown_active = char_data.get('cooldown_expiry', 0) > 0
            
            # Compute character_status.healthy from HP and cooldown data automatically
            hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
            is_alive = current_hp > 0
            is_safe = hp_percentage >= 30.0  # Safe threshold
            is_healthy = is_alive and is_safe and not cooldown_active
            
            unified_context.update({
                StateParameters.CHARACTER_NAME: character_state.name,
                StateParameters.CHARACTER_LEVEL: char_data.get('level', 1),
                StateParameters.CHARACTER_HP: current_hp,
                StateParameters.CHARACTER_MAX_HP: max_hp,
                StateParameters.CHARACTER_X: char_data.get('x', 0),
                StateParameters.CHARACTER_Y: char_data.get('y', 0),
                StateParameters.CHARACTER_COOLDOWN_ACTIVE: cooldown_active,
                StateParameters.CHARACTER_HEALTHY: is_healthy,  # Computed automatically from HP and cooldown
            })
            
            self.logger.debug(f"Character health automatically computed: HP={current_hp}/{max_hp} ({hp_percentage:.1f}%), healthy={is_healthy}")
        
        self.logger.info(f"Updated unified context with character data: {character_state.name}")
        # Invalidate location-based states when character is set/changed
        self._invalidate_location_states()
        
    def _invalidate_location_states(self) -> None:
        """
        Invalidate location-based states using knowledge base as single source of truth.
        
        Pure orchestration - delegate to knowledge base for all location state management.
        """
        from src.lib.unified_state_context import UnifiedStateContext
        
        # Pure orchestration - delegate to knowledge base for location state management
        if self.knowledge_base:
            # Get singleton UnifiedStateContext
            context = UnifiedStateContext()
            
            # Get current character position from context
            char_x = context.get(StateParameters.CHARACTER_X, 0)
            char_y = context.get(StateParameters.CHARACTER_Y, 0)
            
            # Delegate to knowledge base for location state invalidation
            self.knowledge_base.invalidate_location_states(char_x, char_y, context)
            
            self.logger.debug(f"Delegated location state invalidation to knowledge base")
        else:
            self.logger.warning("Cannot invalidate location states - no knowledge base available")
        
    def set_map_state(self, map_state: MapState) -> None:
        """
        Set the map state in knowledge base (single source of truth).
        
        Args:
            map_state: The map state to use
        """
        # Update knowledge base with map state - single source of truth
        if self.knowledge_base:
            self.knowledge_base.map_state = map_state
            
        self.logger.info("Map state set in knowledge base (single source of truth)")
        
    # GOAP planning is now handled by GOAPExecutionManager
            
    def check_and_handle_cooldown(self) -> bool:
        """
        Architecture-compliant cooldown handling.
        
        Cooldown detection is now handled by ActionBase through exception detection (status 499).
        Actions automatically request wait_for_cooldown subgoals when cooldown errors occur.
        
        Returns:
            True if ready to act, False if should abort
        """
        # Architecture-compliant approach: Let actions handle cooldown detection through exceptions
        # Actions will catch 499 status codes and request wait_for_cooldown subgoals automatically
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
        Execute a specific action using pure orchestration pattern.

        Args:
            action_name: Name of the action to execute

        Returns:
            Tuple of (success: bool, result_data: dict)
        """
        try:
            # Handle cooldown (orchestration)
            if self._handle_cooldown_for_action(action_name):
                return True, {}
            
            # Prepare execution context (orchestration)
            context = self._build_execution_context(action_name=action_name)
            
            # Execute action through existing ActionExecutor (orchestration)
            result: ActionResult = self.action_executor.execute_action(
                action_name, self.client, context
            )
            
            # Process result through specialized manager (orchestration)
            result_data = self.action_result_processor.process_result(result, action_name, context)
            
            # Handle execution result (orchestration)
            self._handle_execution_result(result, action_name)
            
            return result.success, result_data
            
        except Exception as e:
            self.logger.error(f"Error executing action {action_name}: {e}")
            return False, {}
    
    def _handle_cooldown_for_action(self, action_name: str) -> bool:
        """
        Architecture-compliant cooldown handling.
        
        Cooldown detection is now handled by ActionBase through exception detection (status 499).
        Actions automatically request wait_for_cooldown subgoals when cooldown errors occur.
        
        Args:
            action_name: Name of the action to check cooldown for
            
        Returns:
            False (always continue - let actions handle cooldown through exceptions)
        """
        # Architecture-compliant approach: Let actions handle cooldown detection through exceptions
        # Actions will catch 499 status codes and request wait_for_cooldown subgoals automatically
        return False
    
    def _handle_execution_result(self, result: ActionResult, action_name: str) -> None:
        """
        Handle the result of action execution.
        
        Args:
            result: ActionResult from execution
            action_name: Name of the executed action
        """
        # Log execution result
        if result.success:
            self.logger.info(f"Action {action_name} executed successfully")
        else:
            self.logger.error(f"Action {action_name} failed: {result.error}")
            
            # If action failed, check if it's a cooldown error and refresh character state
            if result.error and "cooldown" in result.error.lower():
                self.logger.info("Cooldown detected - refreshing character state")
                self._refresh_character_state()
    
    # Cooldown methods removed - ActionBase now handles cooldown detection and wait_for_cooldown subgoals
    
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
                
                # Character state refreshed successfully (cache tracking removed per architecture)
                
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
        Get ActionContext singleton - already populated from UnifiedStateContext.
        
        Args:
            action_name: Name of the action being executed (optional)
            
        Returns:
            ActionContext instance using singleton pattern
        """
        # Return the existing singleton context to maintain persistence between actions
        return self.plan_action_context
    
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
        # SkillGoalManager removed - use existing goals instead
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
        


    def get_current_world_state(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Get current state from UnifiedStateContext singleton.
        
        Args:
            force_refresh: If True, forces character state refresh and context update.
            
        Returns:
            Dictionary representing current world state from UnifiedStateContext
        """
        # Get singleton UnifiedStateContext
        context = UnifiedStateContext()
        
        # Refresh context from external sources if requested
        if force_refresh:
            self._refresh_character_state()
            
            # Update unified context directly (singleton pattern - no external state objects)
            if hasattr(self, 'character_state') and self.character_state and hasattr(self.character_state, 'data'):
                char_data = self.character_state.data
                current_hp = char_data.get('hp', 0)
                max_hp = char_data.get('max_hp', 100)
                # Check cooldown using numeric cooldown field (always present)
                cooldown_seconds = char_data.get('cooldown', 0)
                cooldown_active = cooldown_seconds > 0
                
                # Compute character_status.healthy from HP and cooldown data
                hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
                is_alive = current_hp > 0
                is_safe = hp_percentage >= 30.0  # Safe threshold
                is_healthy = is_alive and is_safe and not cooldown_active
                
                context.update({
                    StateParameters.CHARACTER_NAME: self.character_state.name,
                    StateParameters.CHARACTER_LEVEL: char_data.get('level', 1),
                    StateParameters.CHARACTER_HP: current_hp,
                    StateParameters.CHARACTER_MAX_HP: max_hp,
                    StateParameters.CHARACTER_X: char_data.get('x', 0),
                    StateParameters.CHARACTER_Y: char_data.get('y', 0),
                    StateParameters.CHARACTER_COOLDOWN_ACTIVE: cooldown_active,
                    StateParameters.CHARACTER_HEALTHY: is_healthy,  # Computed from HP and cooldown
                })
                
                self.logger.debug(f"Character health computed: HP={current_hp}/{max_hp} ({hp_percentage:.1f}%), healthy={is_healthy}")
        
        # Return all parameters from unified state context
        state = context.get_all_parameters()
        
        self.logger.debug(f"Current world state from UnifiedStateContext: {len(state)} parameters")
        return state

    def update_world_state(self, state_updates: Dict[str, Any]) -> None:
        """
        Update world state using UnifiedStateContext singleton.
        
        This is the UNIFIED method for all state updates, called by the
        post-execution handler in ActionExecutor.
        
        Args:
            state_updates: Dictionary of state updates to apply using StateParameters
        """
        # Get singleton UnifiedStateContext
        context = UnifiedStateContext()
        
        # Apply updates to unified state context
        context.update(state_updates)
        
        self.logger.debug(f"Updated UnifiedStateContext with {len(state_updates)} changes")



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
    
    


    # Learning and Knowledge Methods


    def find_known_monsters_nearby(self, max_distance: int = 15, character_level: int = None, 
                                 level_range: int = 2) -> Optional[List[Dict]]:
        """
        Find known monster locations near the character using learned knowledge and MapState.
        
        Uses KnowledgeBase directly for data lookup (architecturally compliant).
        
        Args:
            max_distance: Maximum distance to search
            character_level: Character level for level filtering
            level_range: Acceptable level range for monsters
            
        Returns:
            List of monster location info dictionaries or None
        """
        if not self.character_state:
            return None
            
        try:
            current_x = self.character_state.data.get('x', 0)
            current_y = self.character_state.data.get('y', 0)
            char_level = character_level or self.character_state.data.get('level', 1)
            
            # Use knowledge base directly for monster search
            suitable_monsters = self.knowledge_base.find_suitable_monsters(
                character_level=char_level,
                level_range=level_range,
                max_distance=max_distance,
                current_x=current_x,
                current_y=current_y
            )
            
            return suitable_monsters if suitable_monsters else None
            
        except Exception as e:
            self.logger.warning(f"Error finding known monsters nearby: {e}")
            return None



    def learn_all_game_data_efficiently(self) -> Dict:
        """
        Learn about all available game data using efficient get_all_* API calls.
        
        Uses KnowledgeBase directly for data loading (architecturally compliant).
        This replaces inefficient map tile-by-tile scanning with direct API queries.
        
        Returns:
            Dictionary with comprehensive learning results and statistics
        """
        if not self.client:
            return {
                'success': False,
                'error': 'API client not available',
                'stats': {'total': 0}
            }
        
        self.logger.info("🚀 Starting comprehensive game data learning...")
        
        # Use KnowledgeBase bulk learning methods directly
        total_stats = {'resources': 0, 'total': 0}
        results = {'success': True, 'stats': total_stats, 'details': {}, 'errors': []}
        
        try:
            # Learn all data types using KnowledgeBase methods directly
            if hasattr(self.knowledge_base, 'learn_all_resources_bulk'):
                resource_result = self.knowledge_base.learn_all_resources_bulk(self.client)
                total_stats['resources'] = resource_result.get('total_resources_learned', 0)
                results['details']['resources'] = resource_result
                if not resource_result.get('success'):
                    results['errors'].append(f"Resources: {resource_result.get('error', 'Unknown error')}")
            
            # Calculate total
            total_stats['total'] = total_stats['resources']
            
            # Update overall success based on errors
            if results['errors']:
                results['success'] = False
                
            self.logger.info(f"✅ Game data learning complete: {total_stats['total']} total items learned")
            return results
            
        except Exception as e:
            error_msg = f"Failed bulk learning: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'stats': total_stats,
                'details': results.get('details', {}),
                'errors': results.get('errors', []) + [error_msg]
            }

