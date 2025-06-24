"""
AI Player Controller

This module implements the main controller class for the AI player that integrates
with the GOAP (Goal-Oriented Action Planning) system.
"""

import logging
from typing import Dict, List, Optional, Any

from src.lib.goap import World, Planner, Action_List
from src.controller.world.state import WorldState
from src.controller.actions.move import MoveAction
from src.controller.actions.map_lookup import MapLookupAction
from src.controller.actions.find_slime import FindSlimeAction
from src.controller.actions.attack import AttackAction
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
        # This is a simplified implementation - in reality, you'd need to
        # extract parameters from the current state and action requirements
        
        if action_name == 'move':
            # For move action, we'd need to determine target coordinates
            # This is a placeholder - actual implementation would need to
            # extract coordinates from the plan or current state
            if self.character_state and hasattr(self.character_state, 'name'):
                char_name = self.character_state.name
                # Extract coordinates from action data or use placeholder
                target_x = action_data.get('x', 0)
                target_y = action_data.get('y', 1)
                move_action = MoveAction(char_name, target_x, target_y)
                response = move_action.execute(self.client)
                return response is not None
                
        elif action_name == 'map_lookup':
            # For map lookup, we'd determine which coordinates to look up
            lookup_x = action_data.get('x', 0)
            lookup_y = action_data.get('y', 0)
            map_action = MapLookupAction(lookup_x, lookup_y)
            response = map_action.execute(self.client)
            return response is not None
            
        elif action_name == 'find_slime':
            # Execute find and move to slime action
            search_radius = action_data.get('search_radius', 10)
            return self.find_and_move_to_nearest_slime(search_radius)
            
        elif action_name == 'attack':
            # Execute attack action
            if self.character_state and hasattr(self.character_state, 'name'):
                char_name = self.character_state.name
                attack_action = AttackAction(char_name)
                response = attack_action.execute(self.client)
                
                # Update character state if attack was successful
                if response and hasattr(response, 'data') and hasattr(response.data, 'character'):
                    new_char_data = response.data.character
                    self.character_state.data['level'] = new_char_data.level
                    self.character_state.data['xp'] = new_char_data.xp
                    self.character_state.data['hp'] = new_char_data.hp
                    self.character_state.save()
                    
                    self.logger.info(f"Attack completed. Character level: {new_char_data.level}, "
                                   f"XP: {new_char_data.xp}, HP: {new_char_data.hp}")
                
                return response is not None
            
        else:
            self.logger.warning(f"Unknown action: {action_name}")
            return False
            
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

    def find_and_move_to_nearest_slime(self, search_radius: int = 10) -> bool:
        """
        Find the nearest slime location and move the character there.

        Args:
            search_radius: The maximum radius to search for slimes (default: 10)

        Returns:
            True if successful, False otherwise
        """
        if not self.client:
            self.logger.error("Cannot find slime without API client")
            return False

        if not self.character_state:
            self.logger.error("Cannot find slime without character state")
            return False

        try:
            # Get current character position
            char_data = self.character_state.data
            current_x = char_data.get('x', 0)
            current_y = char_data.get('y', 0)
            char_name = self.character_state.name

            self.logger.info(f"Searching for slimes near character at ({current_x}, {current_y})")

            # Create and execute find slime action
            find_slime_action = FindSlimeAction(
                character_x=current_x,
                character_y=current_y,
                search_radius=search_radius
            )

            slime_result = find_slime_action.execute(self.client)

            if not slime_result:
                self.logger.warning("No slimes found within search radius")
                return False

            slime_location = slime_result['location']
            slime_x, slime_y = slime_location
            distance = slime_result['distance']

            self.logger.info(f"Found slime at ({slime_x}, {slime_y}), distance: {distance:.2f}")

            # Move character to slime location
            move_action = MoveAction(char_name, slime_x, slime_y)
            move_response = move_action.execute(self.client)

            if move_response:
                self.logger.info(f"Successfully moved character to slime location ({slime_x}, {slime_y})")
                
                # Update character state with new position
                self.character_state.data['x'] = slime_x
                self.character_state.data['y'] = slime_y
                self.character_state.save()
                
                return True
            else:
                self.logger.error("Failed to move character to slime location")
                return False

        except Exception as e:
            self.logger.error(f"Error finding and moving to slime: {e}")
            return False

    def hunt_slimes_until_level_2(self, search_radius: int = 10, max_attempts: int = 100) -> bool:
        """
        Hunt slimes until the character reaches level 2.

        Args:
            search_radius: The maximum radius to search for slimes (default: 10)
            max_attempts: Maximum number of attempts to prevent infinite loops (default: 100)

        Returns:
            True if character reached level 2, False otherwise
        """
        if not self.client:
            self.logger.error("Cannot hunt slimes without API client")
            return False

        if not self.character_state:
            self.logger.error("Cannot hunt slimes without character state")
            return False

        try:
            current_level = self.character_state.data.get('level', 1)
            self.logger.info(f"Starting slime hunt. Current level: {current_level}")

            if current_level >= 2:
                self.logger.info("Character is already level 2 or higher!")
                return True

            char_name = self.character_state.name
            attempts = 0

            while current_level < 2 and attempts < max_attempts:
                attempts += 1
                self.logger.info(f"Hunt attempt {attempts}/{max_attempts}")

                # Step 1: Find and move to nearest slime
                if not self.find_and_move_to_nearest_slime(search_radius):
                    self.logger.warning(f"Failed to find slime on attempt {attempts}")
                    continue

                # Step 2: Attack the slime
                attack_action = AttackAction(char_name)
                attack_response = attack_action.execute(self.client)

                if attack_response and hasattr(attack_response, 'data'):
                    attack_data = attack_response.data
                    
                    # Update character state with new stats
                    if hasattr(attack_data, 'character'):
                        new_char_data = attack_data.character
                        self.character_state.data['level'] = new_char_data.level
                        self.character_state.data['xp'] = new_char_data.xp
                        self.character_state.data['hp'] = new_char_data.hp
                        self.character_state.data['x'] = new_char_data.x
                        self.character_state.data['y'] = new_char_data.y
                        self.character_state.save()

                        current_level = new_char_data.level
                        
                        # Log fight details
                        if hasattr(attack_data, 'fight'):
                            fight_data = attack_data.fight
                            self.logger.info(f"Fight completed! Level: {new_char_data.level}, "
                                           f"XP: {new_char_data.xp}, HP: {new_char_data.hp}")
                            
                            if hasattr(fight_data, 'result'):
                                self.logger.info(f"Fight result: {fight_data.result}")
                            
                            if hasattr(fight_data, 'xp') and fight_data.xp > 0:
                                self.logger.info(f"XP gained: {fight_data.xp}")

                        # Check if we reached level 2
                        if current_level >= 2:
                            self.logger.info(f"SUCCESS! Character reached level {current_level}!")
                            return True
                    else:
                        self.logger.warning("Attack response missing character data")
                else:
                    self.logger.warning(f"Attack failed on attempt {attempts}")

                # Wait a moment between attacks (respect cooldowns)
                if hasattr(attack_response, 'data') and hasattr(attack_response.data, 'cooldown'):
                    cooldown_data = attack_response.data.cooldown
                    if hasattr(cooldown_data, 'remaining_seconds') and cooldown_data.remaining_seconds > 0:
                        self.logger.info(f"Waiting {cooldown_data.remaining_seconds} seconds for cooldown...")
                        import time
                        time.sleep(cooldown_data.remaining_seconds + 1)  # Add 1 second buffer

            if attempts >= max_attempts:
                self.logger.error(f"Failed to reach level 2 after {max_attempts} attempts")
                return False

            return current_level >= 2

        except Exception as e:
            self.logger.error(f"Error during slime hunting: {e}")
            return False
