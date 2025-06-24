"""
AI Player Controller

This module implements the main controller class for the AI player that integrates
with the GOAP (Goal-Oriented Action Planning) system.
"""

import logging
from typing import Dict, List, Optional, Any

from src.lib.goap import World, Planner, Action_List
from src.lib.actions_data import ActionsData
from src.controller.world.state import WorldState
from src.controller.actions.move import MoveAction
from src.controller.actions.map_lookup import MapLookupAction
from src.controller.actions.find_monsters import FindMonstersAction
from src.controller.actions.attack import AttackAction
from src.controller.actions.rest import RestAction
from src.game.character.state import CharacterState
from src.game.map.state import MapState


class AIPlayerController:
    """
    Main controller class for the AI player that coordinates GOAP planning
    and execution with game state management.
    """
    
    def __init__(self, client=None):
        """Initialize the AI player controller."""
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.world_state = WorldState()
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
        
        # Add actions from configuration
        for action_name, config in actions_config.items():
            conditions = config.get('conditions', {})
            reactions = config.get('reactions', {})
            weight = config.get('weight', 1.0)
            
            action_list.add_condition(action_name, **conditions)
            action_list.add_reaction(action_name, **reactions)
            action_list.set_weight(action_name, weight)
            
        planner.set_action_list(action_list)
        return planner
        
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
        Execute a specific action based on its name.

        Args:
            action_name: Name of the action to execute
            action_data: Action data from the plan

        Returns:
            True if successful, False otherwise
        """
        response = None
        success = False
        
        try:
            if action_name == 'move':
                if self.character_state and hasattr(self.character_state, 'name'):
                    char_name = self.character_state.name
                    target_x = action_data.get('x', 0)
                    target_y = action_data.get('y', 1)
                    move_action = MoveAction(char_name, target_x, target_y)
                    response = move_action.execute(self.client)
                    success = response is not None
                    
            elif action_name == 'map_lookup':
                lookup_x = action_data.get('x', 0)
                lookup_y = action_data.get('y', 0)
                map_action = MapLookupAction(lookup_x, lookup_y)
                response = map_action.execute(self.client)
                success = response is not None
                
            elif action_name == 'find_monsters':
                search_radius = action_data.get('search_radius', 10)
                monster_types = action_data.get('monster_types', None)
                success = self.find_and_move_to_level_appropriate_monster(search_radius)
                # Create a mock response for state update
                response = {'found_monster': success} if success else None
                
            elif action_name == 'attack':
                if self.character_state and hasattr(self.character_state, 'name'):
                    char_name = self.character_state.name
                    attack_action = AttackAction(char_name)
                    response = attack_action.execute(self.client, character_state=self.character_state)
                    success = response is not None
                    
                    if success:
                        self.logger.info(f"Attack action completed successfully")
                        
            elif action_name == 'rest':
                if self.character_state and hasattr(self.character_state, 'name'):
                    char_name = self.character_state.name
                    rest_action = RestAction(char_name)
                    response = rest_action.execute(self.client, character_state=self.character_state)
                    success = response is not None
                    
                    if success:
                        self.logger.info(f"Rest action completed successfully")
                
            else:
                self.logger.warning(f"Unknown action: {action_name}")
                return False
            
            # Update world state based on the action response
            if success:
                self.update_world_state_from_response(action_name, response)
                
            return success
            
        except Exception as e:
            self.logger.error(f"Error executing action {action_name}: {e}")
            return False
            
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
        GOAP-based leveling method to replace hardcoded hunt_slimes_until_level_2.
        
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
        
        # Create comprehensive goal state for level up
        goal_state = {
            'character_level': target_level,
            'character_safe': True,
            'character_alive': True,
            'has_hunted_monsters': True  # Ensure we've actively hunted
        }
        
        # Track progress
        initial_xp = self.character_state.data.get('xp', 0)
        initial_hp = self.character_state.data.get('hp', 0)
        
        self.logger.info(f"📊 Initial state: Level {current_level}, XP {initial_xp}, HP {initial_hp}")
        self.logger.info(f"🎯 Goal state: Level {target_level}, Safe=True, Alive=True, Hunted=True")
        
        # Reset hunting status for this goal
        if hasattr(self.world_state, 'data'):
            self.world_state.data['has_hunted_monsters'] = False
            self.world_state.save()
        
        # Use GOAP to achieve the goal with extended iterations for complex hunting
        max_iterations = 100  # Allow more iterations for comprehensive hunting
        success = self.achieve_goal_with_goap(goal_state, config_file, max_iterations)
        
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

