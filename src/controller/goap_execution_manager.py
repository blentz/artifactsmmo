"""
GOAP Execution Management System

This module provides centralized GOAP planning and execution services,
eliminating redundant GOAP methods from the AI controller.
"""

import logging
from typing import Dict, List, Optional, Any

from src.lib.goap import World, Planner, Action_List
from src.lib.actions_data import ActionsData


class GOAPExecutionManager:
    """
    Centralized GOAP planning and execution system.
    
    Handles world creation, planning, and goal achievement using GOAP,
    eliminating redundant GOAP logic from the AI controller.
    """
    
    def __init__(self):
        """Initialize GOAP execution manager."""
        self.logger = logging.getLogger(__name__)
        
        # Current GOAP state
        self.current_world = None
        self.current_planner = None
        
    def create_world_with_planner(self, start_state: Dict[str, Any], 
                                goal_state: Dict[str, Any], 
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
        
        # Get all keys from both start and goal states
        all_keys = set(start_state.keys()) | set(goal_state.keys())
        
        # Create planner with all required state keys
        planner = Planner(*all_keys)
        
        # Set start and goal states on the planner
        planner.set_start_state(**start_state)
        planner.set_goal_state(**goal_state)
        
        # Create actions from configuration
        action_list = Action_List()
        for action_name, action_config in actions_config.items():
            action_list.add_condition(
                action_name,
                **action_config.get('conditions', {})
            )
            action_list.add_reaction(
                action_name,
                **action_config.get('reactions', {})
            )
            weight = action_config.get('weight', 1.0)
            action_list.set_weight(action_name, weight)
        
        # Set action list on planner
        planner.set_action_list(action_list)
        
        # Add planner to world
        world.add_planner(planner)
        
        # Store for potential reuse
        self.current_world = world
        self.current_planner = planner
        
        self.logger.debug(f"Created GOAP world with {len(actions_config)} actions")
        return world
    
    def create_plan(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                   actions_config: Dict[str, Dict]) -> Optional[List[Dict]]:
        """
        Create a GOAP plan to achieve a goal.
        
        Args:
            start_state: Current state
            goal_state: Desired state
            actions_config: Available actions
            
        Returns:
            List of action dictionaries or None if no plan found
        """
        try:
            world = self.create_world_with_planner(start_state, goal_state, actions_config)
            planner = self.current_planner
            plans = planner.calculate()
            
            if plans:
                best_plan = plans[0]  # First plan is the best (lowest cost)
                self.logger.info(f"GOAP plan created with {len(best_plan)} actions")
                
                # Convert GOAP actions to controller-compatible format
                plan_actions = []
                for action in best_plan:
                    if isinstance(action, dict):
                        # Action is already a dictionary
                        plan_actions.append(action)
                    else:
                        # Action is an object with name and reactions
                        action_dict = {
                            'name': getattr(action, 'name', str(action)),
                            **getattr(action, 'reactions', {})
                        }
                        plan_actions.append(action_dict)
                
                return plan_actions
            else:
                self.logger.warning("No GOAP plan found for goal")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating GOAP plan: {e}")
            return None
    
    def achieve_goal_with_goap(self, goal_state: Dict[str, Any], 
                             controller, 
                             config_file: str = None, 
                             max_iterations: int = 50) -> bool:
        """
        Use GOAP planning to achieve a specific goal.
        
        Args:
            goal_state: The desired end state
            controller: AI controller for execution and state access
            config_file: Optional path to action configuration file
            max_iterations: Maximum planning iterations to prevent infinite loops
            
        Returns:
            True if goal was achieved, False otherwise
        """
        if not controller.client:
            self.logger.error("Cannot achieve goal without API client")
            return False
            
        iterations = 0
        
        while iterations < max_iterations:
            iterations += 1
            self.logger.info(f"GOAP planning iteration {iterations}/{max_iterations}")
            
            # Get current state - force refresh only on first iteration
            force_refresh = (iterations == 1)
            current_state = controller.get_current_world_state(force_refresh=force_refresh)
            
            # Check for active cooldown and handle it first
            if current_state.get('is_on_cooldown', False):
                self.logger.info("🕐 Cooldown detected - executing wait action")
                wait_success = controller._execute_cooldown_wait()
                if wait_success:
                    # Refresh character state after waiting
                    controller._refresh_character_state()
                    continue  # Go to next iteration with fresh state
                else:
                    self.logger.warning("Wait action failed during cooldown")
                    return False
            
            # Check if goal is already achieved
            if self._is_goal_achieved(goal_state, current_state):
                self.logger.info("🎯 Goal achieved!")
                return True
            
            # Load actions and create plan
            actions_config = self._load_actions_from_config(config_file)
            if not actions_config:
                self.logger.error("No actions available for planning")
                return False
            
            # Create and execute plan
            plan = self.create_plan(current_state, goal_state, actions_config)
            if not plan:
                self.logger.warning("No plan found - goal may not be achievable")
                return False
            
            # Execute the plan
            controller.current_plan = plan
            controller.current_action_index = 0
            success = controller.execute_plan()
            
            if not success:
                self.logger.warning("Plan execution failed")
                # Continue to next iteration to try replanning
                continue
            
            # Check if goal was achieved after plan execution
            updated_state = controller.get_current_world_state(force_refresh=True)
            if self._is_goal_achieved(goal_state, updated_state):
                self.logger.info("🎯 Goal achieved after plan execution!")
                return True
        
        self.logger.warning(f"Goal not achieved after {max_iterations} iterations")
        return False
    
    def _is_goal_achieved(self, goal_state: Dict[str, Any], 
                         current_state: Dict[str, Any]) -> bool:
        """Check if the goal state has been achieved."""
        for key, value in goal_state.items():
            if key not in current_state:
                return False
                
            if isinstance(value, str) and value.startswith('>'):
                # Handle greater-than conditions like "character_level: >2"
                target_value = int(value[1:])
                if current_state[key] <= target_value:
                    return False
            elif isinstance(value, str) and value.startswith('<'):
                # Handle less-than conditions
                target_value = int(value[1:])
                if current_state[key] >= target_value:
                    return False
            else:
                # Direct equality check
                if current_state[key] != value:
                    return False
        
        return True
    
    def _load_actions_from_config(self, config_file: str = None) -> Dict[str, Dict]:
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
                    self.logger.debug(f"Loaded {len(actions)} actions from {config_file}")
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
                self.logger.debug(f"Loaded {len(default_actions)} default actions")
                return default_actions
            else:
                self.logger.error("No actions found in default_actions.yaml")
                return {}
        except Exception as e:
            self.logger.error(f"Could not load default actions: {e}")
            return {}
    
    def get_current_world(self) -> Optional[World]:
        """Get the current GOAP world instance."""
        return self.current_world
    
    def get_current_planner(self) -> Optional[Planner]:
        """Get the current GOAP planner instance."""
        return self.current_planner
    
    def reset_world(self) -> None:
        """Reset the current world and planner."""
        self.current_world = None
        self.current_planner = None