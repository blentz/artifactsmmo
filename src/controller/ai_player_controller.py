"""
AI Player Controller

This module implements the main controller class for the AI player that integrates
with the GOAP (Goal-Oriented Action Planning) system using metaprogramming for
YAML-driven action execution.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.lib.goap import World, Planner, Action_List
from src.lib.actions_data import ActionsData
from src.lib.state_loader import StateManagerMixin

# Metaprogramming components
from .action_executor import ActionExecutor, ActionResult

# Import action classes only for GOAP class defaults (no direct instantiation)
from src.controller.actions.move import MoveAction
from src.controller.actions.map_lookup import MapLookupAction
from src.controller.actions.find_monsters import FindMonstersAction
from src.controller.actions.attack import AttackAction
from src.controller.actions.rest import RestAction

# State classes for type hints and learning method access
from src.game.character.state import CharacterState
from src.game.map.state import MapState


class AIPlayerController(StateManagerMixin):
    """
    Main controller class for the AI player that coordinates GOAP planning
    and execution with game state management using YAML-driven metaprogramming.
    """
    
    def __init__(self, client=None):
        """Initialize the AI player controller with full metaprogramming integration."""
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.client = client
        
        # Initialize metaprogramming components
        self.action_executor = ActionExecutor()
        
        # Initialize YAML-driven state management
        self.initialize_state_management()
        
        # Create managed states using YAML configuration
        self.world_state = self.create_managed_state('world_state', 'world_state')
        self.knowledge_base = self.create_managed_state('knowledge_base', 'knowledge_base')
        
        # Character and map states are created when needed
        self.character_state: Optional[CharacterState] = None
        self.map_state: Optional[MapState] = None
        
        # Current plan and execution state
        self.current_plan: List[Dict] = []
        self.current_action_index: int = 0
        self.is_executing: bool = False
        
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
        
    def set_map_state(self, map_state: MapState) -> None:
        """
        Set the current map state.
        
        Args:
            map_state: The map state to use
        """
        self.map_state = map_state
        self.logger.info(f"Map state set")
        
    def create_planner(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                      actions_config: Dict[str, Dict]) -> Planner:
        """
        Create a GOAP planner with the given start and goal states.
        
        Args:
            start_state: The starting state as a dictionary
            goal_state: The desired goal state as a dictionary
            actions_config: Configuration for available actions
            
        Returns:
            A configured GOAP planner
        """
        # Get all unique keys from start and goal states
        keys = set(list(start_state.keys()) + list(goal_state.keys()))
        
        # Create planner
        planner = Planner(*keys)
        planner.set_start_state(**start_state)
        planner.set_goal_state(**goal_state)
        
        # Create action list
        action_list = Action_List()
        
        # Add actions from configuration, with support for class-defined defaults
        for action_name, config in actions_config.items():
            # Get action class defaults if available
            action_class_defaults = self._get_action_class_defaults(action_name)
            
            # Merge config with class defaults (config takes precedence)
            conditions = {**action_class_defaults.get('conditions', {}), **config.get('conditions', {})}
            reactions = {**action_class_defaults.get('reactions', {}), **config.get('reactions', {})}
            weight = config.get('weight', action_class_defaults.get('weight', 1.0))
            
            action_list.add_condition(action_name, **conditions)
            action_list.add_reaction(action_name, **reactions)
            action_list.set_weight(action_name, weight)
            
        planner.set_action_list(action_list)
        return planner
        
    def _get_action_class_defaults(self, action_name: str) -> Dict[str, Any]:
        """
        Get default GOAP parameters from action class definitions.
        
        Args:
            action_name: Name of the action to get defaults for
            
        Returns:
            Dictionary with default conditions, reactions, and weight
        """
        # Map action names to their corresponding classes
        action_class_map = {
            'move': MoveAction,
            'attack': AttackAction,
            'rest': RestAction,
            'map_lookup': MapLookupAction,
            'find_monsters': FindMonstersAction,
            'hunt': None,  # hunt is a composite action, no specific class
        }
        
        action_class = action_class_map.get(action_name)
        if not action_class:
            return {}
            
        # Get class attributes
        defaults = {}
        if hasattr(action_class, 'conditions') and action_class.conditions:
            defaults['conditions'] = action_class.conditions.copy()
        if hasattr(action_class, 'reactions') and action_class.reactions:
            defaults['reactions'] = action_class.reactions.copy()
        if hasattr(action_class, 'weights') and action_class.weights:
            # If weights is a dict, get the weight for this action
            if isinstance(action_class.weights, dict) and action_name in action_class.weights:
                defaults['weight'] = action_class.weights[action_name]
            # If weights is a single value (unlikely but possible)
            elif isinstance(action_class.weights, (int, float)):
                defaults['weight'] = action_class.weights
        
        return defaults
        
    def plan_goal(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                  actions_config: Dict[str, Dict]) -> bool:
        """
        Plan a sequence of actions to achieve the given goal.
        
        Args:
            start_state: The starting state as a dictionary
            goal_state: The desired goal state as a dictionary
            actions_config: Configuration for available actions
            
        Returns:
            True if a plan was found, False otherwise
        """
        if not self.client:
            self.logger.error("Cannot plan without API client")
            return False
            
        try:
            # Create planner
            planner = self.create_planner(start_state, goal_state, actions_config)
            
            # Calculate plan
            self.current_plan = planner.calculate()
            
            if self.current_plan:
                self.logger.info(f"Plan created with {len(self.current_plan)} actions")
                self.current_action_index = 0
                for i, action in enumerate(self.current_plan):
                    self.logger.debug(f"Action {i+1}: {action['name']}")
                return True
            else:
                self.logger.warning("No plan found for the given goal")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during planning: {e}")
            return False
            
    def check_and_wait_for_cooldown(self) -> bool:
        """
        Check if character is in cooldown and wait if necessary.
        
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
                    self.logger.info(f"Character in cooldown, waiting {wait_seconds:.1f} seconds...")
                    time.sleep(min(wait_seconds + 1, 30))  # Cap wait time at 30 seconds
                    return True
                    
            return True
            
        except Exception as e:
            self.logger.warning(f"Error checking cooldown: {e}")
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
        if not self.check_and_wait_for_cooldown():
            self.logger.error("Cooldown check failed")
            self.is_executing = False
            return False
        
        try:
            # Create and execute the appropriate action
            success = self._execute_action(action_name, action_data)
            
            if success:
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
            
    def _execute_action(self, action_name: str, action_data: Dict) -> bool:
        """
        Execute a specific action using YAML-driven metaprogramming approach.

        Args:
            action_name: Name of the action to execute
            action_data: Action data from the plan

        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare execution context
            context = self._build_execution_context(action_data)
            
            # Execute action through the metaprogramming executor
            result: ActionResult = self.action_executor.execute_action(
                action_name, action_data, self.client, context
            )
            
            # Log execution result
            if result.success:
                self.logger.info(f"Action {action_name} executed successfully")
                if result.execution_time:
                    self.logger.debug(f"Execution time: {result.execution_time:.3f}s")
            else:
                self.logger.error(f"Action {action_name} failed: {result.error_message}")
            
            return result.success
            
        except Exception as e:
            self.logger.error(f"Error executing action {action_name}: {e}")
            return False
    
    def _build_execution_context(self, action_data: Dict) -> Dict[str, Any]:
        """
        Build execution context for action execution.
        
        Args:
            action_data: Action data from the plan
            
        Returns:
            Context dictionary with controller state and character info
        """
        context = {
            'controller': self,
            'character_state': self.character_state,
            'world_state': self.world_state,
            'map_state': self.map_state,
            'knowledge_base': self.knowledge_base,
        }
        
        # Add character information if available
        if self.character_state and hasattr(self.character_state, 'name'):
            context.update({
                'character_name': self.character_state.name,
                'character_x': self.character_state.data.get('x', 0),
                'character_y': self.character_state.data.get('y', 0),
                'character_level': self.character_state.data.get('level', 1),
                'pre_combat_hp': self.character_state.data.get('hp', 0),
            })
        
        return context
    
    def get_available_actions(self) -> List[str]:
        """Get list of available actions from the metaprogramming executor."""
        return self.action_executor.get_available_actions()
    
    def reload_action_configurations(self) -> None:
        """Reload action and state configurations from YAML."""
        self.action_executor.reload_configuration()
        self.reload_state_configurations()
            
    def execute_plan(self) -> bool:
        """
        Execute the entire current plan.

        Returns:
            True if all actions were executed successfully, False otherwise
        """
        if not self.current_plan:
            self.logger.warning("No plan to execute")
            return False
            
        self.is_executing = True
        
        while self.is_executing and self.current_action_index < len(self.current_plan):
            if not self.execute_next_action():
                return False
        
        # Plan completed successfully - set executing to False
        self.is_executing = False        
        return True
        
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
        
    def create_world_with_planner(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                                  actions_config: Dict[str, Dict]) -> World:
        """
        Create a GOAP world with a planner for the given scenario.
        
        Args:
            start_state: The starting state as a dictionary
            goal_state: The desired goal state as a dictionary
            actions_config: Configuration for available actions
            
        Returns:
            A World instance with the planner added
        """
        world = World()
        planner = self.create_planner(start_state, goal_state, actions_config)
        world.add_planner(planner)
        return world
        
    def calculate_best_plan(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                           actions_config: Dict[str, Dict]) -> Optional[List[Dict]]:
        """
        Calculate the best plan for the given scenario using the World system.

        Args:
            start_state: The starting state as a dictionary
            goal_state: The desired goal state as a dictionary
            actions_config: Configuration for available actions

        Returns:
            The best plan as a list of action dictionaries, or None if no plan found
        """
        world = self.create_world_with_planner(start_state, goal_state, actions_config)
        world.calculate()
        plans = world.get_plan()
        
        if plans:
            best_plan = plans[0]  # First plan is the best (lowest cost)
            self.logger.info(f"Best plan found with {len(best_plan)} actions")
            return best_plan
        else:
            self.logger.warning("No plans found")
            return None

    def get_current_world_state(self) -> Dict[str, Any]:
        """
        Get the current world state for GOAP planning.
        
        Returns:
            Dictionary representing current world state
        """
        state = {}
        
        # Character state
        if self.character_state:
            char_data = self.character_state.data
            current_hp = char_data.get('hp', 100)
            max_hp = char_data.get('max_hp', 100)
            hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
            
            current_level = char_data.get('level', 1)
            current_xp = char_data.get('xp', 0)
            max_xp = char_data.get('max_xp', 150)
            xp_percentage = (current_xp / max_xp * 100) if max_xp > 0 else 0
            
            state.update({
                'character_x': char_data.get('x', 0),
                'character_y': char_data.get('y', 0),
                'character_level': current_level,
                'character_hp': current_hp,
                'character_max_hp': max_hp,
                'character_xp': current_xp,
                'character_max_xp': max_xp,
                'character_alive': current_hp > 0,
                'character_safe': hp_percentage >= 30,  # Safe HP threshold (30% of max HP)
                'needs_rest': hp_percentage < 30,       # Need rest if HP < 30%
                'can_move': current_hp > 0,
                'can_attack': hp_percentage >= 15,      # Need at least 15% HP to attack safely
                'need_combat': current_level < 10,      # Need combat if level < 10
                'needs_xp': xp_percentage < 100,        # Need XP to level up
                'close_to_levelup': xp_percentage >= 80, # Close to leveling up
                'has_hunted_monsters': False,           # Track if we've hunted this session
            })
        
        # World state from world_state object
        if hasattr(self.world_state, 'data') and self.world_state.data:
            world_data = self.world_state.data
            state.update({
                'monsters_available': world_data.get('monsters_available', False),
                'at_target_location': world_data.get('at_target_location', False),
                'monster_present': world_data.get('monster_present', False),
                'has_hunted_monsters': world_data.get('has_hunted_monsters', False),
            })
        else:
            # Default world state values
            state.update({
                'monsters_available': False,
                'at_target_location': False,
                'monster_present': False,
                'has_hunted_monsters': False,
            })
        
        self.logger.debug(f"Current world state: {state}")
        return state

    def update_world_state_from_response(self, action_name: str, response) -> None:
        """
        Update world state based on action response.
        
        Args:
            action_name: Name of the action that was executed
            response: Response from the action execution
        """
        if not response:
            return
            
        try:
            # Update character state if response contains character data
            if hasattr(response, 'data') and hasattr(response.data, 'character'):
                char_data = response.data.character
                if self.character_state:
                    self.character_state.data.update({
                        'level': char_data.level,
                        'xp': char_data.xp,
                        'hp': char_data.hp,
                        'x': char_data.x,
                        'y': char_data.y,
                    })
                    self.character_state.save()
                    self.logger.debug(f"Updated character state: Level {char_data.level}, XP {char_data.xp}, HP {char_data.hp}")
            
            # Update world state based on action type
            if action_name == 'move':
                self.world_state.data['at_target_location'] = True
                self.world_state.data['monster_present'] = False  # Moved away from current location
                
            elif action_name == 'find_monsters':
                self.world_state.data['monsters_available'] = response is not None
                self.world_state.data['monster_present'] = response is not None
                
            elif action_name == 'attack':
                if hasattr(response, 'data') and hasattr(response.data, 'fight'):
                    fight_data = response.data.fight
                    if hasattr(fight_data, 'result') and fight_data.result == 'win':
                        self.world_state.data['monster_present'] = False
                        self.world_state.data['monsters_available'] = False
                        self.world_state.data['has_hunted_monsters'] = True  # Mark that we've hunted
                        
            elif action_name == 'rest':
                # After resting, character should be safe and not need rest
                if hasattr(response, 'data') and hasattr(response.data, 'character'):
                    char_data = response.data.character
                    hp_percentage = (char_data.hp / char_data.max_hp * 100) if char_data.max_hp > 0 else 0
                    self.world_state.data['character_safe'] = hp_percentage >= 30
                    self.world_state.data['needs_rest'] = hp_percentage < 30
                        
            self.world_state.save()
            
        except Exception as e:
            self.logger.error(f"Error updating world state from response: {e}")

    def load_actions_from_config(self, config_file: str = None) -> Dict[str, Dict]:
        """
        Load action configurations for GOAP planning.
        
        Args:
            config_file: Path to action configuration file (optional, defaults to actions.yaml)
            
        Returns:
            Dictionary of action configurations
        """
        # Try to load from specified config file first
        if config_file:
            try:
                config_actions = ActionsData(config_file)
                actions = config_actions.get_actions()
                if actions:
                    self.logger.info(f"Loaded {len(actions)} actions from {config_file}")
                    return actions
                else:
                    self.logger.warning(f"No actions found in {config_file}")
            except Exception as e:
                self.logger.warning(f"Could not load action config from {config_file}: {e}")
        
        # Fall back to default actions from default_actions.yaml
        try:
            default_actions_data = ActionsData("data/default_actions.yaml")
            default_actions = default_actions_data.get_actions()
            if default_actions:
                self.logger.info(f"Loaded {len(default_actions)} default actions from data/default_actions.yaml")
                return default_actions
            else:
                self.logger.error("No actions found in default_actions.yaml")
                return {}
        except Exception as e:
            self.logger.error(f"Could not load default actions: {e}")
            return {}

    def achieve_goal_with_goap(self, goal_state: Dict[str, Any], config_file: str = None, max_iterations: int = 50) -> bool:
        """
        Use GOAP planning to achieve a specific goal.
        
        Args:
            goal_state: The desired end state
            config_file: Optional path to action configuration file
            max_iterations: Maximum planning iterations to prevent infinite loops
            
        Returns:
            True if goal was achieved, False otherwise
        """
        if not self.client:
            self.logger.error("Cannot achieve goal without API client")
            return False
            
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            self.logger.info(f"GOAP planning iteration {iterations}/{max_iterations}")
            
            # Get current state
            current_state = self.get_current_world_state()
            
            # Check if goal is already achieved
            goal_achieved = True
            for key, value in goal_state.items():
                if key not in current_state:
                    goal_achieved = False
                    break
                if isinstance(value, str) and value.startswith('>'):
                    # Handle greater-than conditions like "character_level: >2"
                    target_value = int(value[1:])
                    if current_state[key] <= target_value:
                        goal_achieved = False
                        break
                elif isinstance(value, int) and key == 'character_level':
                    # For level goals, check if current level >= target level
                    if current_state[key] < value:
                        goal_achieved = False
                        break
                elif current_state[key] != value:
                    goal_achieved = False
                    break
            
            if goal_achieved:
                self.logger.info(f"Goal achieved after {iterations} iterations!")
                return True
            
            # Load action configuration
            actions_config = self.load_actions_from_config(config_file)
            
            # Plan next actions
            if self.plan_goal(current_state, goal_state, actions_config):
                # Execute the plan
                plan_success = self.execute_plan()
                if not plan_success:
                    self.logger.warning(f"Plan execution failed on iteration {iterations}")
                    # Continue to next iteration to try again
            else:
                self.logger.error(f"Could not create plan on iteration {iterations}")
                return False
                
        self.logger.warning(f"Goal not achieved after {max_iterations} iterations")
        return False

    def hunt_until_level(self, target_level: int, config_file: str = None) -> bool:
        """
        GOAP-based leveling method 
        
        Args:
            target_level: The level to reach
            config_file: Optional path to action configuration file
            
        Returns:
            True if target level was reached, False otherwise
        """
        goal_state = {
            'character_level': target_level,
            'character_safe': True,
            'character_alive': True
        }
        
        self.logger.info(f"Starting GOAP-based hunt to reach level {target_level}")
        return self.achieve_goal_with_goap(goal_state, config_file)

    def level_up_goal(self, target_level: int = None, config_file: str = None) -> bool:
        """
        Execute the level_up goal using GOAP planning with comprehensive monster hunting.
        
        This method implements an intelligent leveling strategy that:
        - Prioritizes safety (rests when HP is low)
        - Hunts monsters systematically for XP
        - Adapts strategy based on character state
        - Uses configurable goals from YAML templates
        
        Args:
            target_level: The level to reach (defaults to current level + 1)
            config_file: Optional path to action configuration file
            
        Returns:
            True if target level was reached, False otherwise
        """
        if not self.client:
            self.logger.error("Cannot execute level_up goal without API client")
            return False
            
        if not self.character_state:
            self.logger.error("Cannot execute level_up goal without character state")
            return False
        
        # Determine target level
        current_level = self.character_state.data.get('level', 1)
        if target_level is None:
            target_level = current_level + 1
            
        self.logger.info(f"🎯 Starting level_up goal: {current_level} → {target_level}")
        
        # Load goal template configuration
        try:
            actions_data = ActionsData(config_file) if config_file else ActionsData("data/default_actions.yaml")
            level_up_template = actions_data.get_goal_template('level_up')
            
            if level_up_template:
                strategy = level_up_template.get('strategy', {})
                hunt_radius = strategy.get('hunt_radius', 15)
                xp_target = strategy.get('xp_target', 150)
                self.logger.info(f"📋 Using level_up strategy: hunt_radius={hunt_radius}, xp_target={xp_target}")
            else:
                self.logger.warning("No level_up template found, using defaults")
                hunt_radius = 15
                
        except Exception as e:
            self.logger.warning(f"Could not load goal template: {e}")
            hunt_radius = 15
        
        # Create comprehensive goal state for level up - focus on actual level achievement
        goal_state = {
            'character_level': target_level,  # Must reach the target level
            'character_safe': True,
            'character_alive': True
        }
        
        # Track progress
        initial_xp = self.character_state.data.get('xp', 0)
        initial_hp = self.character_state.data.get('hp', 0)
        
        self.logger.info(f"📊 Initial state: Level {current_level}, XP {initial_xp}, HP {initial_hp}")
        self.logger.info(f"🎯 Goal state: Level {target_level}, Safe=True, Alive=True, Hunted=True")
        
        # Reset hunting status and clean world state for this goal
        if hasattr(self.world_state, 'data'):
            self.world_state.data.update({
                'has_hunted_monsters': False,
                'monsters_available': False,
                'monster_present': False,
                'at_target_location': False
            })
            self.world_state.save()
        
        # Use GOAP to achieve the goal with extended iterations for complex hunting
        max_iterations = 10  # Limit iterations to prevent infinite loops
        
        # Track if we've made progress toward the level goal
        hunt_iterations = 0
        max_hunt_iterations = 20  # Allow more iterations to reach level goal
        
        while hunt_iterations < max_hunt_iterations:
            hunt_iterations += 1
            current_level = self.character_state.data.get('level', 1)
            current_xp = self.character_state.data.get('xp', 0)
            current_hp = self.character_state.data.get('hp', 0)
            
            self.logger.info(f"🔄 Hunting cycle {hunt_iterations}/{max_hunt_iterations}")
            self.logger.info(f"📊 Current: Level {current_level}, XP {current_xp}, HP {current_hp}")
            
            # Check if we've reached the target level
            if current_level >= target_level:
                self.logger.info(f"🎉 Target level {target_level} reached!")
                success = True
                break
            
            # Reset world state for fresh hunting cycle
            if hasattr(self.world_state, 'data'):
                self.world_state.data.update({
                    'monsters_available': False,
                    'monster_present': False,
                    'at_target_location': False
                })
                self.world_state.save()
            
            # Create a hunting goal that requires finding and attacking monsters
            hunting_goal = {
                'monsters_available': True,
                'character_safe': True,
                'character_alive': True
            }
            
            # Execute one round of hunting with limited iterations
            self.logger.info("🎯 Executing hunting cycle...")
            hunt_success = self.achieve_goal_with_goap(hunting_goal, config_file, 3)
            
            # Check progress after hunting cycle
            new_xp = self.character_state.data.get('xp', 0)
            new_level = self.character_state.data.get('level', 1)
            
            if new_level >= target_level:
                self.logger.info(f"🎉 Level up achieved! {current_level} → {new_level}")
                success = True
                break
            elif new_xp > current_xp:
                xp_gained = new_xp - current_xp
                self.logger.info(f"📈 XP gained this cycle: +{xp_gained} (total: {new_xp}/{self.character_state.data.get('max_xp', 150)})")
            else:
                self.logger.warning(f"⚠️  No XP progress in cycle {hunt_iterations}")
                
        success = self.character_state.data.get('level', 1) >= target_level
        
        # Report final results
        final_xp = self.character_state.data.get('xp', 0)
        final_level = self.character_state.data.get('level', 1)
        final_hp = self.character_state.data.get('hp', 0)
        
        xp_gained = final_xp - initial_xp
        levels_gained = final_level - current_level
        
        self.logger.info("=" * 50)
        self.logger.info("🏆 LEVEL UP GOAL RESULTS")
        self.logger.info(f"📈 Levels gained: {levels_gained} ({current_level} → {final_level})")
        self.logger.info(f"⭐ XP gained: {xp_gained} ({initial_xp} → {final_xp})")
        self.logger.info(f"❤️  Final HP: {final_hp}")
        self.logger.info(f"🎯 Goal achieved: {'✅ YES' if success else '❌ NO'}")
        self.logger.info("=" * 50)
        
        return success

    def find_and_move_to_level_appropriate_monster(self, search_radius: int = 10, level_range: int = 2) -> bool:
        """
        Find the nearest level-appropriate monster location and move the character there.

        Args:
            search_radius: The maximum radius to search for monsters (default: 10)
            level_range: Acceptable level range (+/-) for monster selection (default: 2)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Cannot find monsters without API client")
            return False

        if not self.character_state:
            self.logger.error("Cannot find monsters without character state")
            return False

        try:
            # Get current character position and level
            char_data = self.character_state.data
            current_x = char_data.get('x', 0)
            current_y = char_data.get('y', 0)
            character_level = char_data.get('level', 1)
            char_name = self.character_state.name

            self.logger.info(f"Searching for level-appropriate monsters near character at ({current_x}, {current_y}), character level: {character_level}")

            # Create and execute find monsters action with level filtering
            find_monsters_action = FindMonstersAction(
                character_x=current_x,
                character_y=current_y,
                search_radius=search_radius,
                monster_types=None,  # Search for any monster type
                character_level=character_level,
                level_range=level_range
            )

            monster_result = find_monsters_action.execute(self.client)

            if not monster_result:
                self.logger.warning(f"No level-appropriate monsters found within search radius (level {character_level} ±{level_range})")
                return False

            monster_location = monster_result['location']
            monster_x, monster_y = monster_location
            distance = monster_result['distance']
            monster_code = monster_result['monster_code']

            self.logger.info(f"Found level-appropriate monster '{monster_code}' at ({monster_x}, {monster_y}), distance: {distance:.2f}")

            # Move character to monster location
            move_action = MoveAction(char_name, monster_x, monster_y)
            move_response = move_action.execute(self.client)

            if move_response:
                self.logger.info(f"Successfully moved character to monster location ({monster_x}, {monster_y})")
                
                # Update character state with new position
                self.character_state.data['x'] = monster_x
                self.character_state.data['y'] = monster_y
                self.character_state.save()
                
                return True
            else:
                self.logger.error("Failed to move character to monster location")
                return False

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
                    from src.game.map.state import MapState
                    self.map_state = MapState(self.client)
                
                # MapState will handle the location caching automatically when scan() is called
                # We just need to learn from the content if it exists
                content = map_data.get('content')
                if content:
                    content_type = content.get('type_', 'unknown')
                    content_code = content.get('code', 'unknown')
                    
                    # Learn from content discovery
                    self.knowledge_base.learn_from_content_discovery(
                        content_type, content_code, x, y, content
                    )
                    self.knowledge_base.save()
                    
                    self.logger.info(f"🧠 Learned: {content_type} '{content_code}' at ({x}, {y})")
                else:
                    self.logger.debug(f"🧠 Explored empty location ({x}, {y})")
                    
        except Exception as e:
            self.logger.warning(f"Failed to learn from map exploration at ({x}, {y}): {e}")

    def learn_from_combat(self, monster_code: str, result: str, pre_combat_hp: int = None) -> None:
        """
        Learn from combat experience.
        
        Args:
            monster_code: Code of the monster fought
            result: Combat result ('win', 'loss', 'flee')
            pre_combat_hp: Character HP before combat
        """
        try:
            if not self.character_state:
                return
                
            character_data = self.character_state.data.copy()
            if pre_combat_hp is not None:
                character_data['hp_before'] = pre_combat_hp
                
            self.knowledge_base.record_combat_result(monster_code, result, character_data)
            self.knowledge_base.save()
            
            # Log learning insights
            success_rate = self.knowledge_base.get_monster_combat_success_rate(
                monster_code, character_data.get('level', 1)
            )
            
            if success_rate >= 0:
                self.logger.info(f"🧠 Combat learning: {monster_code} success rate at level {character_data.get('level', 1)}: {success_rate:.1%}")
            else:
                self.logger.info(f"🧠 First combat data recorded for {monster_code}")
                
        except Exception as e:
            self.logger.warning(f"Failed to learn from combat with {monster_code}: {e}")

    def find_known_monsters_nearby(self, max_distance: int = 15, character_level: int = None, 
                                 level_range: int = 2) -> Optional[List[Dict]]:
        """
        Find known monster locations near the character using learned knowledge and MapState.
        
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
            
            # Use integrated knowledge base with MapState
            suitable_monsters = self.knowledge_base.find_suitable_monsters(
                map_state=self.map_state,
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

    def intelligent_monster_search(self, search_radius: int = 15) -> bool:
        """
        Intelligent monster search that combines learned knowledge with exploration.
        
        This method first checks for known monster locations, then falls back to
        systematic exploration if no known locations are available.
        
        Args:
            search_radius: Maximum radius to search
            
        Returns:
            True if monster was found and character moved to it, False otherwise
        """
        if not self.character_state:
            return False
            
        try:
            char_level = self.character_state.data.get('level', 1)
            
            # First, try to use known monster locations
            known_monsters = self.find_known_monsters_nearby(
                max_distance=search_radius, character_level=char_level
            )
            
            if known_monsters:
                # Try the most promising known location first
                best_monster = known_monsters[0]
                target_x, target_y = best_monster['location']
                monster_code = best_monster['monster_code']
                success_rate = best_monster.get('success_rate', -1)
                
                self.logger.info(f"🧠 Using learned knowledge: Moving to known {monster_code} at ({target_x}, {target_y})")
                if success_rate >= 0:
                    self.logger.info(f"🧠 Expected success rate: {success_rate:.1%}")
                
                # Move to the known location
                if self.character_state and hasattr(self.character_state, 'name'):
                    char_name = self.character_state.name
                    move_action = MoveAction(char_name, target_x, target_y)
                    move_response = move_action.execute(self.client)
                    
                    if move_response:
                        # Learn from this exploration
                        self.learn_from_map_exploration(target_x, target_y, move_response)
                        
                        # Update character position
                        self.character_state.data['x'] = target_x
                        self.character_state.data['y'] = target_y
                        self.character_state.save()
                        
                        self.logger.info(f"🧠 Successfully moved to known monster location")
                        return True
            
            # Fallback to regular monster finding if no known locations work
            self.logger.info("🧠 No suitable known monsters, falling back to exploration")
            return self.find_and_move_to_level_appropriate_monster(search_radius)
            
        except Exception as e:
            self.logger.error(f"Error in intelligent monster search: {e}")
            return False

    def get_learning_insights(self) -> Dict:
        """
        Get insights and statistics about what the AI has learned.
        
        Returns:
            Dictionary containing learning statistics and insights
        """
        try:
            summary = self.knowledge_base.get_knowledge_summary(self.map_state)
            learning_stats = self.knowledge_base.get_learning_stats()
            
            insights = {
                'knowledge_summary': summary,
                'learning_stats': learning_stats,
                'recommendations': []
            }
            
            # Add some intelligent recommendations based on learned data
            if summary['monsters_discovered'] == 0:
                insights['recommendations'].append("Explore more areas to discover monsters for combat")
            elif summary['monsters_discovered'] < 3:
                insights['recommendations'].append("Continue exploring to find more monster varieties")
                
            if summary['total_locations_discovered'] < 20:
                insights['recommendations'].append("Expand exploration radius to learn about more locations")
                
            return insights
            
        except Exception as e:
            self.logger.warning(f"Error getting learning insights: {e}")
            return {'error': str(e)}

    def optimize_with_knowledge(self, goal_type: str = None) -> Dict[str, Any]:
        """
        Use learned knowledge to optimize planning and decision making.
        
        Args:
            goal_type: Type of goal to optimize for ('combat', 'exploration', 'resources')
            
        Returns:
            Dictionary with optimization suggestions
        """
        try:
            if not self.character_state:
                return {'error': 'No character state available'}
                
            char_level = self.character_state.data.get('level', 1)
            current_x = self.character_state.data.get('x', 0)
            current_y = self.character_state.data.get('y', 0)
            
            optimizations = {
                'goal_type': goal_type,
                'character_level': char_level,
                'current_position': (current_x, current_y),
                'suggestions': []
            }
            
            if goal_type == 'combat' or goal_type is None:
                # Combat optimization
                known_monsters = self.find_known_monsters_nearby(
                    max_distance=20, character_level=char_level
                )
                
                if known_monsters:
                    # Find monsters with good success rates
                    good_targets = [m for m in known_monsters if m.get('success_rate', 0) > 0.7]
                    if good_targets:
                        best_target = good_targets[0]
                        optimizations['suggestions'].append({
                            'type': 'combat_target',
                            'description': f"High success rate target: {best_target['monster_code']} at {best_target['location']}",
                            'success_rate': best_target['success_rate'],
                            'location': best_target['location']
                        })
                    
                    # Warn about dangerous monsters
                    dangerous = [m for m in known_monsters if m.get('success_rate', 1) < 0.3]
                    if dangerous:
                        optimizations['suggestions'].append({
                            'type': 'combat_warning',
                            'description': f"Avoid dangerous monsters: {[m['monster_code'] for m in dangerous[:3]]}",
                            'dangerous_monsters': dangerous[:3]
                        })
            
            if goal_type == 'exploration' or goal_type is None:
                # Exploration optimization using MapState
                total_locations = 0
                if self.map_state and hasattr(self.map_state, 'data'):
                    total_locations = len(self.map_state.data)
                    
                if total_locations < 50:
                    optimizations['suggestions'].append({
                        'type': 'exploration',
                        'description': f"Explore more areas (visited {total_locations} locations so far)",
                        'recommended_action': 'systematic_exploration'
                    })
                    
            return optimizations
            
        except Exception as e:
            self.logger.warning(f"Error optimizing with knowledge: {e}")
            return {'error': str(e)}

