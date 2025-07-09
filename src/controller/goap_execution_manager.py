"""
GOAP Execution Management System

This module provides centralized GOAP planning and execution services,
eliminating redundant GOAP methods from the AI controller.
"""

import copy
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from src.lib.goap import World, Planner, Action_List
from src.lib.hierarchical_goap import HierarchicalPlanner, HierarchicalWorld
from src.lib.actions_data import ActionsData
from src.lib.yaml_data import YamlData
from src.game.globals import CONFIG_PREFIX
from src.controller.knowledge.base import KnowledgeBase


class GOAPExecutionManager:
    """
    Centralized GOAP planning and execution system.
    
    Handles world creation, planning, and goal achievement using GOAP,
    eliminating redundant GOAP logic from the AI controller.
    """
    
    def __init__(self):
        """Initialize GOAP execution manager with hierarchical planning for performance."""
        self.logger = logging.getLogger(__name__)
        
        # Current GOAP state
        self.current_world = None
        self.current_planner = None
        
        # Cached start state configuration
        self._start_state_config = None
        
        # Goal context stack for recursive subgoal execution
        self.goal_stack = []  # Stack of (goal_name, goal_state, plan, action_index)
        
        # Load state mappings for consolidated-to-flat transformation
        
    def _handle_subgoal_request(self, subgoal_request: Dict[str, Any], controller, 
                               current_plan: List, action_index: int, current_goal_state: Dict,
                               config_file: str, parent_world: Any = None, parent_planner: Any = None) -> bool:
        """
        Handle a subgoal request by executing the subgoal recursively.
        
        Args:
            subgoal_request: Subgoal request from action result
            controller: AI controller
            current_plan: Current plan being executed
            action_index: Current action index
            current_goal_state: Current goal state
            config_file: Action configuration file
            parent_world: Parent GOAP world (passed from caller)
            parent_planner: Parent GOAP planner (passed from caller)
            
        Returns:
            True if subgoal was completed successfully, False otherwise
        """
        goal_name = subgoal_request.get("goal_name")
        parameters = subgoal_request.get("parameters", {})
        preserve_context = subgoal_request.get("preserve_context", [])
        
        self.logger.info(f"🎯 Executing subgoal: {goal_name} with parameters: {parameters}")
        
        # Use passed world references if available, otherwise use instance variables
        if parent_world is None:
            parent_world = self.current_world
            parent_planner = self.current_planner
            
        # Validate we have a valid world with the expected structure
        if not parent_world:
            self.logger.error("No parent world available for subgoal execution")
            return False
            
        # Check if this is a GOAP World object with values
        if hasattr(parent_world, 'values'):
            world_values = parent_world.values
        # Or if it's a planner with values
        elif hasattr(parent_world, 'planners') and parent_world.planners and hasattr(parent_world.planners[0], 'values'):
            world_values = parent_world.planners[0].values
        else:
            self.logger.error(f"Parent world has unexpected structure: {type(parent_world)}")
            return False
            
        self.logger.debug(f"Parent world type: {type(parent_world)}, has values: {world_values is not None}")
        
        # Store goal stack for resumption (ActionContext is singleton - no context capture needed)
        self.goal_stack.append({
            "goal_state": current_goal_state,
            "plan": current_plan,
            "action_index": action_index
        })
        
        try:
            # Get current state from the parent world
            current_state = copy.deepcopy(world_values)
            
            # ActionContext is now a unified singleton - state is maintained throughout execution
            
            # Generate subgoal state using the current state
            # Get the goal template from the goal manager
            goal_template = controller.goal_manager.goal_templates.get(goal_name)
            if not goal_template:
                self.logger.error(f"No goal template found for subgoal: {goal_name}")
                return False
            
            # Merge subgoal parameters into the current state before goal generation
            # This ensures subgoal starts with the right context from parent goal
            if parameters:
                # Handle special subgoal parameter mappings
                if 'missing_materials' in parameters and parameters['missing_materials']:
                    # Set materials as insufficient and store the missing materials
                    if 'materials' not in current_state:
                        current_state['materials'] = {}
                    current_state['materials'].update({
                        'status': 'insufficient',
                        'availability_checked': True,
                        'requirements_determined': True,
                        'gathered': False
                    })
                    # Store missing materials for action access
                    current_state['missing_materials'] = parameters['missing_materials']
                    self.logger.debug(f"Subgoal inheriting missing materials: {parameters['missing_materials']}")
                
                if 'selected_item' in parameters and parameters['selected_item']:
                    # Use UnifiedStateContext directly - no nested state
                    from src.lib.unified_state_context import UnifiedStateContext
                    context = UnifiedStateContext()
                    context.selected_item = parameters['selected_item']
                    context.has_selected_item = True
                    context.upgrade_status = 'ready'
                    # Update current_state to match flattened format
                    current_state['selected_item'] = parameters['selected_item']
                    current_state['has_selected_item'] = True
                    current_state['upgrade_status'] = 'ready'
                    self.logger.debug(f"Subgoal inheriting selected item: {parameters['selected_item']}")
                
                # Handle gather_resource parameters
                if goal_name == 'gather_resource' and 'resource' in parameters:
                    # Set up gathering goal for gather_resource_quantity action
                    current_state['current_gathering_goal'] = {
                        'material': parameters.get('resource'),
                        'quantity': parameters.get('quantity', 1)
                    }
                    self.logger.debug(f"Set current_gathering_goal: {current_state['current_gathering_goal']}")
                    
                    # For gather_resource, ensure materials are set up for resource gathering
                    if 'materials' not in current_state:
                        current_state['materials'] = {}
                    current_state['materials'].update({
                        'status': 'insufficient',
                        'quantities_calculated': True,
                        'raw_materials_needed': True
                    })
                    self.logger.debug(f"Set up materials state for resource gathering")
            
            # Generate goal state using the existing goal manager logic
            subgoal_state = controller.goal_manager.generate_goal_state(
                goal_name, goal_template, current_state, **parameters
            )
            
            # Check if subgoal is already achieved
            if self._is_goal_achieved(subgoal_state, current_state):
                self.logger.info(f"🎯 Subgoal {goal_name} already achieved!")
                return True
            
            # Load actions configuration
            actions_config = self._load_actions_from_config(config_file)
            if not actions_config:
                self.logger.error("No actions available for subgoal planning")
                return False
            
            # Create subgoal plan - preserve the current world's state
            self.logger.info(f"📋 Creating plan for subgoal: {goal_name}")
            self.logger.debug(f"Current state for subgoal planning: materials={current_state.get('materials', {})}")
            self.logger.debug(f"SUBGOAL STATE ANALYSIS:")
            self.logger.debug(f"  current_state.equipment_status: {current_state.get('equipment_status', {})}")
            self.logger.debug(f"  current_state.materials: {current_state.get('materials', {})}")
            self.logger.debug(f"  subgoal_state: {subgoal_state}")
            
            # Create a new world and planner for the subgoal but use current state
            subgoal_world = self.create_world_with_planner(
                current_state, subgoal_state, actions_config
            )
            subgoal_planner = self.current_planner
            
            # Store the subgoal world temporarily
            saved_world = self.current_world
            saved_planner = self.current_planner
            self.current_world = subgoal_world
            self.current_planner = subgoal_planner
            
            # Create the plan using the subgoal world
            # Extract the plan from the planner
            best_plan = subgoal_planner.calculate()
            
            if best_plan:
                # Convert GOAP actions to controller-compatible format
                subgoal_plan = []
                for action in best_plan:
                    if isinstance(action, dict):
                        # GOAP node is a dictionary with action name
                        action_name = action.get('name', 'unknown')
                        action_dict = {'name': action_name}
                        subgoal_plan.append(action_dict)
                    else:
                        # Action is an object with name and reactions
                        action_dict = {
                            'name': getattr(action, 'name', str(action)),
                            **getattr(action, 'reactions', {})
                        }
                        subgoal_plan.append(action_dict)
            else:
                subgoal_plan = None
            
            if not subgoal_plan:
                self.logger.error(f"Could not create plan for subgoal: {goal_name}")
                return False
            
            # Execute subgoal plan
            self.logger.info(f"🚀 Executing subgoal plan with {len(subgoal_plan)} actions")
            subgoal_success = self._execute_plan_with_selective_replanning(
                subgoal_plan, controller, subgoal_state, config_file, max_iterations=25
            )
            
            # Restore parent world and planner
            self.current_world = parent_world
            self.current_planner = parent_planner
            
            # Update parent world with subgoal's state changes
            if subgoal_success and subgoal_world and hasattr(subgoal_world, 'values'):
                # Merge subgoal state changes back to parent world
                if parent_world and hasattr(parent_world, 'values'):
                    # Direct GOAP World object
                    for key, value in subgoal_world.values.items():
                        if key in parent_world.values:
                            parent_world.values[key] = copy.deepcopy(value)
                    self.logger.debug("Merged subgoal state changes back to parent world")
                elif parent_world and hasattr(parent_world, 'planners') and parent_world.planners:
                    # World with planners
                    for planner in parent_world.planners:
                        if hasattr(planner, 'values'):
                            for key, value in subgoal_world.values.items():
                                if key in planner.values:
                                    planner.values[key] = copy.deepcopy(value)
                    self.logger.debug("Merged subgoal state changes back to parent world planners")
            
            # ActionContext is a singleton that maintains state - no restoration needed
            self.logger.debug("Subgoal execution completed, ActionContext state preserved throughout")
            
            return subgoal_success
            
        finally:
            # Pop goal stack
            if self.goal_stack:
                self.goal_stack.pop()
            # Ensure parent world is still active after subgoal
            if parent_world and parent_planner:
                self.current_world = parent_world
                self.current_planner = parent_planner
                self.logger.debug("Ensured parent world is active after subgoal completion")
    
        
    def _create_plan_from_current_state(self, goal_state: Dict, current_state: Dict, config_file: str) -> List[Dict]:
        """
        Create a new plan from the current world state to achieve the goal.
        
        Args:
            goal_state: The target goal state
            current_state: Current world state
            config_file: Path to action configuration file
            
        Returns:
            List of actions to execute, or empty list if goal is achieved
        """
        try:
            # Check if goal is already achieved
            if self._is_goal_achieved(goal_state, current_state):
                self.logger.info("🎯 Goal already achieved in current state")
                return []
            
            # Load actions configuration
            actions_config = self._load_actions_from_config(config_file)
            if not actions_config:
                self.logger.error("No actions available for replanning")
                return []
            
            # Create a new planner with current state
            temp_world = self.create_world_with_planner(
                start_state=current_state,
                goal_state=goal_state,
                actions_config=actions_config
            )
            temp_planner = self.current_planner
            
            if not temp_planner:
                self.logger.error("Failed to create planner for replanning")
                return []
            
            # Generate plan
            plan = temp_planner.calculate()
            
            if plan:
                self.logger.debug(f"Created new plan with {len(plan)} actions")
                # Update current world and planner
                self.current_world = temp_world
                self.current_planner = temp_planner
                return plan
            else:
                self.logger.warning("No valid plan found from current state")
                return []
                
        except Exception as e:
            self.logger.error(f"Error creating plan from current state: {e}")
            return []
    
    def _load_start_state_defaults(self) -> Dict[str, Any]:
        """
        Load default start state configuration from YAML file.
        
        Returns:
            Dictionary of default state variables with their initial values
        """
        if self._start_state_config is not None:
            return self._start_state_config
            
        try:
            # Use consolidated state defaults instead of goap_start_state
            start_state_data = YamlData(f"{CONFIG_PREFIX}/consolidated_state_defaults.yaml")
            
            # Get the state defaults section
            defaults = start_state_data.data.get('state_defaults', {})
            
            self._start_state_config = defaults
            self.logger.debug(f"Loaded {len(defaults)} default start state variables from configuration")
            return defaults
            
        except Exception as e:
            self.logger.warning(f"Could not load start state configuration: {e}")
            # Return empty dict - no fallback
            return {}
    
    
    
    
    def _get_nested_value(self, data: Dict[str, Any], key_path: str) -> Any:
        """
        Get value from nested dictionary using dot notation.
        
        Args:
            data: Dictionary to search
            key_path: Dot-separated path like "character_status.safe"
            
        Returns:
            Value at the path or None if not found
        """
        if '.' not in key_path:
            return data.get(key_path)
        
        parts = key_path.split('.')
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def _check_conditions_for_action(self, state: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Check if all conditions are met in the current state"""
        for cond_key, cond_value in conditions.items():
            if cond_key not in state:
                return False
            current = state[cond_key]
            if isinstance(cond_value, dict) and isinstance(current, dict):
                # Check nested conditions
                for sub_key, sub_value in cond_value.items():
                    if sub_key not in current:
                        return False
                    if current[sub_key] != sub_value:
                        return False
            elif current != cond_value:
                return False
        return True
    
    def _convert_goal_value_to_goap_format(self, goal_value: Any) -> Any:
        """
        Convert special goal values to GOAP-compatible format.
        
        Args:
            goal_value: Goal value like '!null', 'completed', '>0', etc.
            
        Returns:
            GOAP-compatible value (boolean, numeric)
        """
        if isinstance(goal_value, str):
            # Handle special string values
            if goal_value == '!null':
                return True  # Non-null means True
            elif goal_value == 'null':
                return False  # Null means False
            elif goal_value == 'completed':
                return True  # Completed state means True
            elif goal_value == 'idle':
                return False  # Idle state means False  
            elif goal_value.startswith('>'):
                # Convert ">0" to a positive number that GOAP can target
                try:
                    threshold = float(goal_value[1:])
                    return int(threshold) + 1  # Target slightly above threshold
                except ValueError:
                    return True
            elif goal_value.startswith('>='):
                # Convert ">=0" to a number that GOAP can target
                try:
                    threshold = float(goal_value[2:])
                    return int(threshold)  # Target at least the threshold
                except ValueError:
                    return True
            else:
                # For other string values, return as-is for now
                return goal_value
        else:
            # Return non-string values as-is
            return goal_value
    
    def _check_condition_matches(self, state: Dict[str, Any], cond_key: str, cond_value: Any) -> bool:
        """
        Check if a condition matches the current state, supporting nested state structures.
        
        Args:
            state: Current state dictionary
            cond_key: The state key to check
            cond_value: Expected value (can be nested dict or simple value)
            
        Returns:
            True if condition matches, False otherwise
        """
        current_value = state.get(cond_key)
        
        # Handle simple value comparison
        if not isinstance(cond_value, dict):
            # Handle special comparison operators
            if isinstance(cond_value, str):
                if cond_value == '!null':
                    return current_value is not None
                elif cond_value.startswith('<'):
                    try:
                        threshold = float(cond_value[1:])
                        return isinstance(current_value, (int, float)) and current_value < threshold
                    except (ValueError, TypeError):
                        return False
                elif cond_value.startswith('>'):
                    try:
                        threshold = float(cond_value[1:])
                        return isinstance(current_value, (int, float)) and current_value > threshold
                    except (ValueError, TypeError):
                        return False
            
            return current_value == cond_value
        
        # Handle nested dict comparison
        if not isinstance(current_value, dict):
            return False
        
        # Check that all required nested conditions are satisfied
        for nested_key, nested_value in cond_value.items():
            if nested_key not in current_value:
                return False
            
            # Recursive check for deeper nesting
            if not self._check_condition_matches(current_value, nested_key, nested_value):
                return False
        
        return True
    
    
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
        world = HierarchicalWorld()
        
        # Load default start state configuration first to get all possible state keys
        start_state_defaults = self._load_start_state_defaults()
        
        # Get top-level keys only (not nested keys) for planner initialization
        # GOAP library handles nested dictionaries properly when given top-level keys
        top_level_keys = set(start_state.keys()) | set(goal_state.keys())
        if start_state_defaults:
            top_level_keys.update(start_state_defaults.keys())
        
        # Don't flatten nested keys - GOAP library handles nested dictionaries natively
        # Only collect top-level state categories like 'equipment_status', 'combat_context', etc.
        
        # Create hierarchical planner with only top-level state keys for optimization
        self.logger.debug(f"Creating hierarchical planner with top-level keys: {sorted(top_level_keys)}")
        planner = HierarchicalPlanner(*top_level_keys)
        
        # Override the planner's default -1 values with proper defaults
        # This is crucial for nested dictionary states
        if start_state_defaults:
            for key, value in start_state_defaults.items():
                if key in planner.values:
                    planner.values[key] = value
        
        # Build complete start state with proper precedence:
        # 1. Start with configuration defaults
        # 2. Override with actual start_state values
        complete_start_state = start_state_defaults.copy() if start_state_defaults else {}
        
        # Add any missing top-level keys with appropriate defaults
        for key in top_level_keys:
            if key not in complete_start_state:
                # Check if this is a nested state key from defaults
                if start_state_defaults and key in start_state_defaults:
                    complete_start_state[key] = start_state_defaults[key]
                else:
                    # Set empty dict for nested states, False for simple states
                    complete_start_state[key] = {} if key.endswith('_status') or key.endswith('_context') else False
        
        # Override with actual runtime state values
        # Need to do a deep merge for nested dictionaries
        for key, value in start_state.items():
            if isinstance(value, dict) and key in complete_start_state and isinstance(complete_start_state[key], dict):
                # Deep merge nested dictionary
                complete_start_state[key] = complete_start_state[key].copy()
                complete_start_state[key].update(value)
            else:
                complete_start_state[key] = value
        
        # Calculate boolean flags for initial state (GOAP planning needs them)
        # The post-execution pipeline will maintain consistency after each action
        self._calculate_initial_boolean_flags(complete_start_state)
        
        # Set start and goal states on the planner
        planner.set_start_state(**complete_start_state)
        self.logger.debug(f"Planner start state after setting: {planner.start_state}")
        self.logger.debug(f"Equipment status in planner: {planner.start_state.get('equipment_status', 'MISSING')}")
        
        # The planner might not handle nested dicts properly, so we need to restore them
        for key, value in complete_start_state.items():
            if isinstance(value, dict):
                planner.values[key] = value
        
        # For goal state, we only want to set the specific values we're checking for
        # We don't need a complete state - GOAP will only check the specified values
        # First, create a minimal goal state with only the keys we care about
        minimal_goal_state = {}
        
        # Add all keys from goal_state to ensure they exist in planner.values
        for key in goal_state.keys():
            if key not in minimal_goal_state:
                if key in complete_start_state:
                    minimal_goal_state[key] = complete_start_state[key]
                else:
                    minimal_goal_state[key] = False
        
        # Now set the goal state with all keys present
        planner.set_goal_state(**minimal_goal_state)
        
        # Override with only the specific goal values we want to check
        # This ensures GOAP only validates the fields we care about
        planner.goal_state = {}
        for key, value in goal_state.items():
            planner.goal_state[key] = value
        
        # Filter actions based on goal state to reduce A* search complexity
        try:
            knowledge_base = KnowledgeBase()
            relevant_action_names = knowledge_base.get_relevant_actions(goal_state, complete_start_state)
            
            # Filter actions_config to only include relevant actions
            filtered_actions_config = {}
            for action_name in relevant_action_names:
                if action_name in actions_config:
                    filtered_actions_config[action_name] = actions_config[action_name]
            
            original_count = len(actions_config)
            filtered_count = len(filtered_actions_config)
            self.logger.info(f"🎯 Pre-filtering action space: {original_count} → {filtered_count} actions")
            
            # Use filtered actions for planning
            planning_actions_config = filtered_actions_config if filtered_actions_config else actions_config
            
        except Exception as e:
            self.logger.warning(f"Action filtering failed, using full action set: {e}")
            planning_actions_config = actions_config
        
        # Create actions from filtered configuration
        action_list = Action_List()
        eligible_actions = []
        for action_name, action_config in planning_actions_config.items():
            conditions = action_config.get('conditions', {})
            weight = action_config.get('weight', 1.0)
            
            # Check if action conditions are met by current start state
            conditions_met = self._check_conditions_for_action(complete_start_state, conditions)
            if conditions_met:
                eligible_actions.append((action_name, weight))
            
            action_list.add_condition(
                action_name,
                **conditions
            )
            action_list.add_reaction(
                action_name,
                **action_config.get('reactions', {})
            )
            action_list.set_weight(action_name, weight)
        
        # Log eligible actions for debugging
        eligible_actions.sort(key=lambda x: x[1], reverse=True)  # Sort by weight descending
        self.logger.debug(f"ELIGIBLE ACTIONS for planning: {eligible_actions[:10]}")  # Top 10
        
        # Set action list on planner
        planner.set_action_list(action_list)
        
        # Add planner to world
        world.add_planner(planner)
        
        # Store for potential reuse
        self.current_world = world
        self.current_planner = planner
        
        self.logger.debug(f"Created GOAP world with {len(actions_config)} actions and {len(top_level_keys)} state variables")
        return world
    
    def create_plan(self, start_state: Dict[str, Any], goal_state: Dict[str, Any], 
                   actions_config: Dict[str, Dict]) -> Optional[List[Dict]]:
        """
        Create a GOAP plan to achieve a goal.
        
        Args:
            start_state: Current state in consolidated format
            goal_state: Desired state
            actions_config: Available actions
            
        Returns:
            List of action dictionaries or None if no plan found
        """
        # 🕐 Performance timing for optimization
        planning_start_time = time.time()
        self.logger.info(f"🕐 GOAP Planning Started at: {time.strftime('%H:%M:%S.%f')[:-3]}")
        
        try:
            # World creation timing
            world_creation_start = time.time()
            world = self.create_world_with_planner(start_state, goal_state, actions_config)
            world_creation_time = time.time() - world_creation_start
            self.logger.info(f"🕐 World Creation Time: {world_creation_time:.3f}s")
            
            planner = self.current_planner
            
            # GOAP calculation timing - using hierarchical optimization
            calculation_start = time.time()
            self.logger.debug(f"📊 Starting hierarchical GOAP calculation with {len(actions_config)} actions...")
            if isinstance(planner, HierarchicalPlanner):
                plans = planner.calculate_with_subgoal_optimization()
            else:
                plans = planner.calculate()
            calculation_time = time.time() - calculation_start
            self.logger.info(f"🕐 GOAP Calculation Time: {calculation_time:.3f}s")
            self.logger.debug(f"📊 Hierarchical GOAP calculation completed successfully")
            
            if plans:
                best_plan = plans  # Plans is already the list of nodes
                self.logger.info(f"GOAP plan created with {len(best_plan)} actions")
                
                
                # Convert GOAP actions to controller-compatible format
                plan_actions = []
                for action in best_plan:
                    if isinstance(action, dict):
                        # GOAP node is a dictionary with action name
                        action_name = action.get('name', 'unknown')
                        action_dict = {'name': action_name}
                        plan_actions.append(action_dict)
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
                self.logger.debug(f"Start state: {start_state}")
                self.logger.debug(f"Goal state: {goal_state}")
                self.logger.debug(f"Available actions: {list(actions_config.keys())}")
                # Check which actions have their conditions met
                self.logger.debug("Checking action conditions:")
                for action_name, action_config in actions_config.items():
                    conditions = action_config.get('conditions', {})
                    all_met = True
                    unmet_conditions = []
                    for cond_key, cond_value in conditions.items():
                        # Check against state for nested conditions
                        if not self._check_condition_matches(start_state, cond_key, cond_value):
                            all_met = False
                            current_value = self._get_nested_value(start_state, cond_key) if '.' in str(cond_key) else start_state.get(cond_key)
                            unmet_conditions.append(f"{cond_key}: need {cond_value}, have {current_value}")
                    if all_met:
                        self.logger.debug(f"  ✓ {action_name}: all conditions met")
                    else:
                        self.logger.debug(f"  ✗ {action_name}: unmet conditions - {unmet_conditions}")
                return None
                
        except Exception as e:
            total_planning_time = time.time() - planning_start_time
            self.logger.info(f"🕐 GOAP Planning FAILED - Total Time: {total_planning_time:.3f}s")
            self.logger.error(f"Error creating GOAP plan: {e}")
            return None
        finally:
            total_planning_time = time.time() - planning_start_time
            self.logger.info(f"🕐 GOAP Planning COMPLETED - Total Time: {total_planning_time:.3f}s")
    
    def achieve_goal_with_goap(self, goal_state: Dict[str, Any], 
                             controller, 
                             config_file: str = None, 
                             max_iterations: int = 50) -> bool:
        """
        Use GOAP planning to achieve a specific goal.
        
        Simplified Architecture:
        1. Create complete GOAP plan
        2. Execute plan through to completion
        3. Handle failures with targeted replanning
        
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
        
        # Get current state - use active world if available (for subgoals), 
        # otherwise get from controller (for top-level goals)
        if self.current_world and hasattr(self.current_world, 'values'):
            # Subgoal execution - use in-memory state
            current_state = copy.deepcopy(self.current_world.values)
            self.logger.debug("Using in-memory world state for planning")
        else:
            # Top-level goal - get fresh state
            current_state = controller.get_current_world_state(force_refresh=False)
        
        # Check if goal is already achieved
        if self._is_goal_achieved(goal_state, current_state):
            self.logger.info("🎯 Goal already achieved!")
            return True
        
        # Load actions configuration
        actions_config = self._load_actions_from_config(config_file)
        if not actions_config:
            self.logger.error("No actions available for planning")
            return False
        
        # Create complete GOAP plan
        self.logger.info("📋 Creating GOAP plan...")
        plan = self.create_plan(current_state, goal_state, actions_config)
        
        if not plan:
            self.logger.error("Could not create GOAP plan")
            return False
        
        # Execute complete plan
        self.logger.info(f"🚀 Executing plan with {len(plan)} actions: {[action.get('name', 'unknown') for action in plan]}")
        return self._execute_plan_with_selective_replanning(
            plan, controller, goal_state, config_file, max_iterations
        )
    
    
    def _execute_plan_with_selective_replanning(self, plan: List[Dict], controller, 
                                              goal_state: Dict[str, Any], 
                                              config_file: str = None,
                                              max_iterations: int = 50) -> bool:
        """
        Execute plan with selective replanning based on action types.
        
        Discovery actions trigger replanning, execution actions continue plan.
        Cooldowns insert wait actions into current plan.
        """
        current_plan = plan.copy()
        action_index = 0
        iterations = 0
        
        # The controller should always have a plan_action_context - it's a singleton
        if not hasattr(controller, 'plan_action_context') or controller.plan_action_context is None:
            self.logger.error("Controller missing plan_action_context - this should be initialized by AIPlayerController")
            return False
        
        self.logger.debug("Using existing ActionContext singleton for GOAP plan execution")
        
        while action_index < len(current_plan) and iterations < max_iterations:
            iterations += 1
            
            # Check for cooldown and handle by inserting wait action and replanning
            # Force refresh to ensure we have accurate cooldown status
            current_state = controller.get_current_world_state(force_refresh=True)
            # Check nested state structure for cooldown status
            character_status = current_state.get('character_status', {})
            if character_status.get('cooldown_active', False):
                # Only insert wait action if current action isn't already a wait action
                if action_index < len(current_plan):
                    current_action = current_plan[action_index]
                    if current_action.get('name') != 'wait':
                        # Insert wait action and replan
                        current_plan = self._handle_cooldown_with_plan_insertion(
                            current_plan, action_index, controller
                        )
                        # Reset action index to start of new plan with wait action
                        action_index = 0
                        continue
            
            # Check if goal is achieved
            if self._is_goal_achieved(goal_state, current_state):
                self.logger.info("🎯 Goal achieved during plan execution!")
                return True
            
            # Execute next action
            if action_index >= len(current_plan):
                self.logger.warning("Reached end of plan without achieving goal")
                break
                
            current_action = current_plan[action_index]
            action_name = current_action.get('name', 'unknown')
            
            self.logger.info(f"Executing action {action_index + 1}/{len(current_plan)}: {action_name}")
            
            # Execute the action
            success = controller._execute_single_action(action_name, current_action)
            
            # Update GOAP world state with any changes from the action
            if success and self.current_world and hasattr(self.current_world, 'values'):
                # Get the latest world state which includes action updates
                updated_state = controller.get_current_world_state(force_refresh=False)
                # Update the GOAP world's values with the new state
                for key, value in updated_state.items():
                    if key in self.current_world.values:
                        self.current_world.values[key] = copy.deepcopy(value)
                    # Also update planner values if it exists
                    if self.current_planner and hasattr(self.current_planner, 'values') and key in self.current_planner.values:
                        self.current_planner.values[key] = copy.deepcopy(value)
                self.logger.debug(f"Updated GOAP world state after {action_name} execution")
            
            # Check if action requested a subgoal
            if hasattr(controller, 'last_action_result') and controller.last_action_result:
                action_result = controller.last_action_result
                if hasattr(action_result, 'subgoal_request') and action_result.subgoal_request:
                    subgoal_success = self._handle_subgoal_request(
                        action_result.subgoal_request, 
                        controller, 
                        current_plan, 
                        action_index, 
                        goal_state,
                        config_file,
                        self.current_world,
                        self.current_planner
                    )
                    if subgoal_success:
                        # Subgoal completed successfully
                        # Resume parent goal context instead of complete replanning
                        self.logger.info(f"✅ Subgoal completed successfully, resuming parent goal context")
                        
                        # Get fresh world state that includes subgoal changes
                        current_state = controller.get_current_world_state(force_refresh=True)
                        
                        # Update GOAP world with fresh state
                        if self.current_world and hasattr(self.current_world, 'values'):
                            for key, value in current_state.items():
                                if key in self.current_world.values:
                                    self.current_world.values[key] = copy.deepcopy(value)
                        
                        # ActionContext is singleton - no context restoration needed
                        
                        # Resume parent plan intelligently instead of complete replanning
                        resumed_plan = self._resume_parent_plan_after_subgoal(
                            current_plan, action_index, goal_state, current_state, config_file
                        )
                        
                        if resumed_plan:
                            current_plan = resumed_plan
                            # DO NOT increment action_index - re-execute the same action for continuation
                            # The action that requested the subgoal should handle continuation logic
                            self.logger.info(f"🔄 Re-executing action {action_index + 1}/{len(current_plan)}: {current_action.get('name')} for continuation")
                        else:
                            # No plan needed - goal might be achieved
                            self.logger.info("✅ No further actions needed after subgoal")
                            action_index = len(current_plan)
                        continue
                    else:
                        # Subgoal failed, current goal also fails
                        self.logger.error(f"Subgoal failed for action {action_name}")
                        return False
            
            if not success:
                self.logger.warning(f"Action {action_name} failed")
                
                # Handle specific failure types with targeted recovery
                if self._is_authentication_failure(action_name, controller):
                    self.logger.error("🚨 Authentication failure detected - aborting execution")
                    return False
                elif self._is_cooldown_failure(action_name, controller):
                    self.logger.warning("⏱️ Cooldown failure detected - inserting wait action")
                    # Insert wait action at current position to handle cooldown
                    current_plan = self._handle_cooldown_with_plan_insertion(
                        current_plan, action_index, controller
                    )
                    # Don't increment action_index - retry the same action after wait
                    continue
                elif self._is_coordinate_failure(action_name, controller):
                    self.logger.error("📍 Coordinate failure detected - goal execution failed")
                    return False
                elif self._is_hp_validation_failure(action_name, controller):
                    self.logger.error("💚 HP validation failure detected - goal execution failed")
                    return False
                else:
                    # Action failed and no specific recovery strategy applies
                    # Propagate failure up the recursion stack - no replanning at this level
                    self.logger.error(f"❌ Action {action_name} failed - propagating failure up recursion stack")
                    return False
            
            # Check if this action requires replanning
            if self._is_discovery_action(action_name):
                self.logger.info(f"🔍 Discovery action {action_name} completed - checking for replanning")
                
                # Learn from the action
                self._learn_from_action_response(action_name, controller)
                
                # Check if we need to replan based on new knowledge
                updated_state = controller.get_current_world_state(force_refresh=True)
                if self._should_replan_after_discovery(current_action, updated_state):
                    self.logger.info("📋 New knowledge acquired - replanning remaining actions")
                    remaining_plan = self._replan_from_current_position(
                        controller, goal_state, config_file, current_plan[action_index + 1:]
                    )
                    if remaining_plan:
                        current_plan = current_plan[:action_index + 1] + remaining_plan
                    
            action_index += 1
            
            # Check for cooldown after action execution
            # Move and attack actions can put character on cooldown
            if action_name in ['move', 'attack', 'gather_resources', 'craft_item', 'rest']:
                current_state = controller.get_current_world_state(force_refresh=True)
                # Check nested state structure for cooldown status
                character_status = current_state.get('character_status', {})
                if character_status.get('cooldown_active', False):
                    # Insert wait action at next position if not already present
                    if action_index < len(current_plan) and current_plan[action_index].get('name') != 'wait':
                        self.logger.info("🕐 Cooldown detected after action - inserting wait action")
                        current_plan = self._handle_cooldown_with_plan_insertion(
                            current_plan, action_index, controller
                        )
        
        # Check final goal achievement after all actions complete
        final_state = controller.get_current_world_state(force_refresh=True)
        return self._is_goal_achieved(goal_state, final_state)
    
    
    def _create_discovery_plan(self, current_state: Dict[str, Any], 
                             goal_state: Dict[str, Any], 
                             actions_config: Dict[str, Dict]) -> Optional[List[Dict]]:
        """
        Create a plan focused on discovery actions to gather needed knowledge.
        """
        # Create plan that prioritizes discovery actions
        discovery_focused_state = current_state.copy()
        
        # Note: Removed hardcoded discovery states (need_workshop_discovery, 
        # equipment_info_unknown, material_requirements_known) as they are:
        # 1. Not used as conditions by any actions
        # 2. Only set as reactions by some actions
        # 3. Causing GOAP to initialize them as -1 which breaks nested state handling
        
        return self.create_plan(discovery_focused_state, goal_state, actions_config)
    
    def _handle_cooldown_with_plan_insertion(self, current_plan: List[Dict], 
                                           action_index: int, 
                                           controller) -> List[Dict]:
        """
        Handle cooldown by inserting wait action into current plan instead of replanning.
        """
        # Get cooldown duration
        character_state = controller.get_current_world_state(force_refresh=True)
        cooldown_seconds = self._get_cooldown_duration(controller)
        
        # Check if we have a more accurate cooldown from the error response
        if hasattr(controller, 'last_action_result') and isinstance(controller.last_action_result, dict):
            error_cooldown = controller.last_action_result.get('cooldown_seconds')
            if error_cooldown and error_cooldown > 0:
                self.logger.info(f"Using cooldown duration from error response: {error_cooldown}s")
                cooldown_seconds = error_cooldown
        
        if cooldown_seconds > 0:
            # Create wait action
            wait_action = {
                'name': 'wait',
                'wait_duration': cooldown_seconds,
                'description': f'Wait for {cooldown_seconds}s cooldown'
            }
            
            # Insert wait action at current position
            new_plan = current_plan.copy()
            new_plan.insert(action_index, wait_action)
            
            self.logger.info(f"🕐 Inserted {cooldown_seconds}s wait action into plan at position {action_index}")
            return new_plan
        
        return current_plan
    
    def _get_cooldown_duration(self, controller) -> float:
        """Get remaining cooldown duration in seconds."""
        try:
            if hasattr(controller, 'character_state') and controller.character_state:
                char_data = controller.character_state.data
                cooldown_seconds = char_data.get('cooldown', 0)
                cooldown_expiration = char_data.get('cooldown_expiration', None)
                
                if cooldown_seconds > 0 and cooldown_expiration:
                    try:
                        # Parse expiration timestamp
                        if isinstance(cooldown_expiration, str):
                            cooldown_end = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
                        else:
                            cooldown_end = cooldown_expiration
                        
                        # Calculate remaining time
                        current_time = datetime.now(timezone.utc)
                        if current_time < cooldown_end:
                            remaining = (cooldown_end - current_time).total_seconds()
                            # Clamp to reasonable bounds and add small buffer
                            return max(0.1, min(remaining + 0.5, 60.0))
                        else:
                            # Cooldown has already expired
                            return 0.0
                            
                    except Exception as e:
                        self.logger.warning(f"Error parsing cooldown expiration: {e}")
                        # Fall back to raw cooldown value
                        return min(cooldown_seconds, 60.0)
                else:
                    # Use raw cooldown seconds if no expiration time
                    return min(cooldown_seconds, 60.0) if cooldown_seconds > 0 else 0.0
                    
        except Exception as e:
            self.logger.warning(f"Could not get cooldown duration: {e}")
        return 0
    
    def _is_discovery_action(self, action_name: str) -> bool:
        """
        Determine if an action is a discovery action that might provide new knowledge.
        
        Discovery actions should trigger replanning, execution actions should not.
        """
        discovery_actions = {
            'analyze_crafting_chain',
            'evaluate_weapon_recipes', 
            'find_monsters',
            'find_resources',
            'find_workshops',
            'find_correct_workshop',
            'lookup_item_info',
            'explore_map'
        }
        
        return action_name in discovery_actions
    
    def _should_replan_after_discovery(self, action: Dict[str, Any], 
                                     updated_state: Dict[str, Any]) -> bool:
        """
        Determine if replanning is needed after a discovery action.
        
        This should check if the discovery action provided significant new knowledge
        that would change the optimal plan.
        """
        action_name = action.get('name', '')
        
        # Configuration-driven replan decisions with lazy evaluation
        if action_name == 'find_correct_workshop':
            return False  # Don't replan if workshop was already found
        elif action_name == 'analyze_crafting_chain':
            return self._should_replan_chain_analysis()
        elif action_name == 'evaluate_weapon_recipes':
            return True  # Replan after weapon evaluation
        else:
            return False
    
    def _should_replan_chain_analysis(self) -> bool:
        """Determine if chain analysis should trigger replanning."""
        # Only replan if this provided new crafting knowledge
        # For now, allow one replan per chain analysis
        chain_replans = getattr(self, '_chain_analysis_replans', 0)
        if chain_replans >= 1:
            return False
        self._chain_analysis_replans = chain_replans + 1
        return True
    
    def _replan_from_current_position(self, controller, goal_state: Dict[str, Any],
                                    config_file: str = None, 
                                    remaining_actions: List[Dict] = None) -> Optional[List[Dict]]:
        """
        Replan from current position when action fails or new knowledge is acquired.
        """
        current_state = controller.get_current_world_state(force_refresh=True)
        actions_config = self._load_actions_from_config(config_file)
        
        if not actions_config:
            return None
        
        # Create new plan using standard GOAP planning
        new_plan = self.create_plan(current_state, goal_state, actions_config)
        
        if new_plan:
            return new_plan
        
        # Fall back to discovery planning
        return self._create_discovery_plan(current_state, goal_state, actions_config)
    
    
    def _learn_from_action_response(self, action_name: str, controller) -> None:
        """
        Learn from action execution and update world knowledge.
        
        This is where we incorporate API responses into our planning knowledge.
        Each action type may provide different kinds of learning opportunities.
        """
        try:
            # Update character state to reflect any changes
            controller._refresh_character_state()
            
            # Configuration-driven learning patterns
            learning_callbacks = {
                "evaluate_weapon_recipes": self._learn_from_weapon_evaluation,
                "find_correct_workshop": self._learn_from_workshop_discovery,
                "transform_raw_materials": self._learn_from_material_transformation,
                "craft_item": self._learn_from_crafting,
                "move": self._learn_from_exploration,
                "gather_resources": self._learn_from_exploration,
                "find_resources": self._learn_from_exploration
            }
            
            # Execute learning callback if configured
            learning_callback = learning_callbacks.get(action_name)
            if learning_callback:
                learning_callback(controller)
            
            # Save learned knowledge
            if hasattr(controller, 'knowledge_base') and controller.knowledge_base:
                controller.knowledge_base.save()
            if hasattr(controller, 'map_state') and controller.map_state:
                controller.map_state.save()
                
        except Exception as e:
            self.logger.warning(f"Learning from action {action_name} failed: {e}")
    
    def _learn_from_weapon_evaluation(self, controller) -> None:
        """Learn from weapon recipe evaluation results."""
        # Check if we have learned about available recipes
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'item_code' in context:
                self.logger.info(f"🧠 Learned: Selected weapon {context.get('item_code')} for crafting")
    
    def _learn_from_workshop_discovery(self, controller) -> None:
        """Learn from workshop finding results."""
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'workshop_location' in context:
                location = context['workshop_location']
                self.logger.info(f"🧠 Learned: Found workshop at {location}")
    
    def _learn_from_material_transformation(self, controller) -> None:
        """Learn from material transformation attempts."""
        # This is where we can learn about what materials are actually available
        # and what transformations are possible at different workshops
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'transformation_results' in context:
                results = context['transformation_results']
                self.logger.info(f"🧠 Learned: Material transformation results: {results}")
    
    def _learn_from_crafting(self, controller) -> None:
        """Learn from crafting attempts."""
        # Learn about successful/failed crafting attempts and requirements
        if hasattr(controller, 'action_context') and controller.action_context:
            context = controller.action_context
            if 'crafting_result' in context:
                result = context['crafting_result']
                self.logger.info(f"🧠 Learned: Crafting result: {result}")
    
    def _learn_from_exploration(self, controller) -> None:
        """Learn from movement and exploration actions."""
        # Update map knowledge and resource/monster locations
        if hasattr(controller, 'map_state') and controller.map_state:
            self.logger.debug("🧠 Updated map knowledge from exploration")
    
    def _is_goal_achieved(self, goal_state: Dict[str, Any], 
                         current_state: Dict[str, Any]) -> bool:
        """Check if the goal state has been achieved."""
        self.logger.debug(f"🔍 Checking goal achievement:")
        self.logger.debug(f"  Goal state: {goal_state}")
        
        return self._check_nested_state_match(goal_state, current_state, "")
    
    def _check_nested_state_match(self, goal: Dict[str, Any], current: Dict[str, Any], path: str) -> bool:
        """Recursively check if goal state matches current state (subset matching)."""
        for key, goal_value in goal.items():
            current_path = f"{path}.{key}" if path else key
            
            if key not in current:
                self.logger.debug(f"  ❌ Missing key '{current_path}' in current state")
                return False
            
            current_value = current[key]
            self.logger.debug(f"  Checking {current_path}: goal={goal_value}, current={current_value}")
            
            if isinstance(goal_value, dict) and isinstance(current_value, dict):
                # Recursive check for nested dictionaries
                if not self._check_nested_state_match(goal_value, current_value, current_path):
                    return False
            elif isinstance(goal_value, str) and goal_value.startswith('>'):
                # Handle greater-than conditions like ">80"
                try:
                    target_value = float(goal_value[1:])
                    if current_value <= target_value:
                        self.logger.debug(f"  ❌ {current_path}: {current_value} <= {target_value}")
                        return False
                except ValueError:
                    self.logger.debug(f"  ❌ Invalid comparison format: {goal_value}")
                    return False
            elif isinstance(goal_value, str) and goal_value.startswith('<'):
                # Handle less-than conditions like "<30"
                try:
                    target_value = float(goal_value[1:])
                    if current_value >= target_value:
                        self.logger.debug(f"  ❌ {current_path}: {current_value} >= {target_value}")
                        return False
                except ValueError:
                    self.logger.debug(f"  ❌ Invalid comparison format: {goal_value}")
                    return False
            else:
                # Direct equality check
                if current_value != goal_value:
                    self.logger.debug(f"  ❌ {current_path}: {current_value} != {goal_value}")
                    return False
                else:
                    self.logger.debug(f"  ✅ {current_path}: {current_value} == {goal_value}")
        
        self.logger.debug(f"🎯 Goal achieved: All conditions met!")
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
            default_actions_data = ActionsData(f"{CONFIG_PREFIX}/default_actions.yaml")
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
    
    def initialize_session_state(self, controller) -> None:
        """
        Initialize clean session state for XP-seeking goal achievement.
        
        This method ensures that GOAP planning starts with a clean state that
        requires find_monsters action, preventing incomplete 2-action plans.
        
        Args:
            controller: AI controller for state access and data persistence
        """
        try:
            # Reset action context to prevent stale coordinates
            if hasattr(controller, 'action_context'):
                controller.action_context = {}
            
            # Load start state defaults from configuration
            start_state_defaults = self._load_start_state_defaults()
            
            # Use configured start state defaults for session initialization
            session_state = start_state_defaults.copy()
            
            # Initialize world state for GOAP planning
            if hasattr(controller, 'world_state') and controller.world_state:
                # Preserve existing structure but update critical values
                current_data = controller.world_state.data.copy()
                current_data.update(session_state)
                controller.world_state.data = current_data
                controller.world_state.save()
                
                self.logger.info(f"🔧 Initialized session state with {len(session_state)} GOAP variables")
                self.logger.info("🎯 Ensured find_monsters → move → attack cycle will be planned")
            else:
                self.logger.warning("No world state available for session state initialization")
                
        except Exception as e:
            self.logger.error(f"Failed to initialize session state: {e}")
            # Continue execution with default behavior
    
    def _is_authentication_failure(self, action_name: str, controller) -> bool:
        """
        Detect authentication failures to prevent infinite retry loops.
        
        Args:
            action_name: Name of the failed action
            controller: AI controller for error context
            
        Returns:
            True if authentication failure detected, False otherwise
        """
        try:
            # Check for authentication-related errors in recent log messages
            # This is a simple heuristic - could be enhanced with actual error inspection
            return False  # For now, let authentication failures be handled by the application
        except Exception:
            return False
    
    def _is_coordinate_failure(self, action_name: str, controller) -> bool:
        """
        Detect coordinate/movement failures that require find_monsters replan.
        
        Args:
            action_name: Name of the failed action
            controller: AI controller for error context
            
        Returns:
            True if coordinate failure detected, False otherwise
        """
        try:
            # Check if this is a move action failing due to missing coordinates
            if action_name == 'move':
                # Check if action context lacks target coordinates
                if hasattr(controller, 'action_context'):
                    context = controller.action_context
                    if context.get('target_x') is None or context.get('target_y') is None:
                        self.logger.info("🔍 Move action failed due to missing target coordinates")
                        return True
            return False
        except Exception as e:
            self.logger.warning(f"Error checking coordinate failure: {e}")
            return False
    
    def _is_cooldown_failure(self, action_name: str, controller) -> bool:
        """
        Detect if action failed due to character being on cooldown.
        
        This typically happens with HTTP 499 status code errors.
        
        Args:
            action_name: Name of the failed action
            controller: AI controller for error context
            
        Returns:
            True if cooldown failure detected, False otherwise
        """
        try:
            # Check if the last action result indicates cooldown
            if hasattr(controller, 'last_action_result'):
                result = controller.last_action_result
                if isinstance(result, dict):
                    # Check for error messages indicating cooldown
                    error_msg = result.get('error', '').lower()
                    if 'cooldown' in error_msg or '499' in error_msg:
                        self.logger.info(f"⏱️ Action {action_name} failed due to cooldown")
                        return True
                    
                    # Check response data for cooldown indicators
                    response = result.get('response')
                    if response and hasattr(response, 'status_code') and response.status_code == 499:
                        self.logger.info(f"⏱️ Action {action_name} failed with HTTP 499 (cooldown)")
                        return True
                        
            # Also check current world state with fresh data
            world_state = controller.get_current_world_state(force_refresh=True)
            character_status = world_state.get('character_status', {})
            if character_status.get('cooldown_active', False):
                self.logger.info(f"⏱️ Character is on cooldown after {action_name}")
                return True
                
            return False
        except Exception as e:
            self.logger.warning(f"Error checking cooldown failure: {e}")
            return False
    
    def _is_hp_validation_failure(self, action_name: str, controller) -> bool:
        """
        Detect if action failed due to character HP validation (HP too low).
        
        This happens when the action validator detects that character HP is below
        the required threshold for the action. When this occurs, we need to force
        a fresh world state calculation and replan to include healing actions.
        
        Args:
            action_name: Name of the failed action
            controller: AI controller instance
            
        Returns:
            True if HP validation failure detected, False otherwise
        """
        try:
            # Check if the last action result indicates HP validation failure
            if hasattr(controller, 'last_action_result'):
                result = controller.last_action_result
                if isinstance(result, dict):
                    # Check for validation errors indicating HP issues
                    validation_errors = result.get('data', {}).get('validation_errors', [])
                    for error in validation_errors:
                        if isinstance(error, dict) and error.get('validator') == 'character_hp_above':
                            self.logger.info(f"💚 Action {action_name} failed due to low HP validation")
                            return True
                    
                    # Check error message for HP-related issues
                    error_msg = result.get('error', '').lower()
                    if 'character hp' in error_msg and 'below' in error_msg:
                        self.logger.info(f"💚 Action {action_name} failed due to HP requirement")
                        return True
                        
            return False
        except Exception as e:
            self.logger.warning(f"Error checking HP validation failure: {e}")
            return False
    
    def _create_recovery_plan_with_find_monsters(self, controller, goal_state: Dict[str, Any],
                                               config_file: str = None) -> Optional[List[Dict]]:
        """
        Create a recovery plan that starts with find_monsters to get fresh coordinates.
        
        Args:
            controller: AI controller
            goal_state: Desired goal state  
            config_file: Optional action configuration file
            
        Returns:
            List of action dictionaries for recovery plan
        """
        try:
            # Get fresh state and then force it to require find_monsters
            recovery_state = controller.get_current_world_state(force_refresh=True)
            recovery_state.update({
                'monsters_available': False,
                'monster_present': False,
                'at_target_location': False
            })
            
            # Clear action context to force fresh coordinate discovery
            if hasattr(controller, 'action_context'):
                # Keep some context but remove location data
                preserved_context = {}
                for key in ['item_code', 'recipe_item_code', 'craft_skill']:
                    if key in controller.action_context:
                        preserved_context[key] = controller.action_context[key]
                controller.action_context = preserved_context
            
            # Load actions configuration
            actions_config = self._load_actions_from_config(config_file)
            if not actions_config:
                return None
            
            # Create plan with forced find_monsters requirement
            recovery_plan = self.create_plan(recovery_state, goal_state, actions_config)
            if recovery_plan:
                self.logger.info(f"🔄 Created recovery plan with {len(recovery_plan)} actions")
                return recovery_plan
            else:
                self.logger.warning("Failed to create recovery plan")
                return None
                
        except Exception as e:
            self.logger.error(f"Error creating recovery plan: {e}")
            return None
    
    
    def _resume_parent_plan_after_subgoal(self, current_plan: List[Dict], action_index: int, 
                                        goal_state: Dict[str, Any], current_state: Dict[str, Any],
                                        config_file: str) -> Optional[List[Dict]]:
        """
        Resume parent plan intelligently after subgoal completion.
        
        Instead of creating a completely new plan, this method:
        1. Checks if the current plan is still valid
        2. Only replans if absolutely necessary
        3. Preserves parent plan structure when possible
        
        Args:
            current_plan: Current plan being executed
            action_index: Current action index in plan
            goal_state: Target goal state
            current_state: Current world state
            config_file: Action configuration file
            
        Returns:
            Plan to continue execution (may be original plan or new plan)
        """
        # Check if goal is already achieved
        if self._is_goal_achieved(goal_state, current_state):
            self.logger.info("🎯 Goal achieved after subgoal completion")
            return []
            
        # Check if remaining actions in current plan are still valid
        remaining_actions = current_plan[action_index + 1:] if action_index + 1 < len(current_plan) else []
        
        if remaining_actions:
            # Validate remaining actions against current state
            actions_config = self._load_actions_from_config(config_file)
            if actions_config and self._are_remaining_actions_valid(remaining_actions, current_state, actions_config):
                self.logger.info(f"📋 Resuming parent plan with {len(remaining_actions)} remaining actions")
                return current_plan  # Continue with original plan
        
        # Only create new plan if necessary
        self.logger.info("📋 Creating new plan due to invalid remaining actions")
        return self._create_plan_from_current_state(goal_state, current_state, config_file)
    
    def _are_remaining_actions_valid(self, remaining_actions: List[Dict], current_state: Dict[str, Any], 
                                   actions_config: Dict[str, Dict]) -> bool:
        """
        Check if remaining actions in the plan are still valid given current state.
        
        Args:
            remaining_actions: List of remaining actions to validate
            current_state: Current world state
            actions_config: Available actions configuration
            
        Returns:
            True if remaining actions are valid, False otherwise
        """
        if not remaining_actions:
            return False
            
        # Check first few remaining actions for validity
        for i, action in enumerate(remaining_actions[:3]):  # Check first 3 actions
            action_name = action.get('name', '')
            if action_name not in actions_config:
                self.logger.debug(f"Action {action_name} not available in config")
                return False
                
            action_config = actions_config[action_name]
            conditions = action_config.get('conditions', {})
            
            # Check if action conditions are met
            if not self._check_conditions_for_action(current_state, conditions):
                self.logger.debug(f"Action {action_name} conditions not met in current state")
                return False
                
        self.logger.debug(f"Remaining {len(remaining_actions)} actions are valid")
        return True
    
    def _calculate_initial_boolean_flags(self, world_state: Dict[str, Any]) -> None:
        """
        Calculate boolean flags for initial state to maintain consistency with post-execution pipeline.
        
        This ensures boolean flags like has_target_slot, has_selected_item, etc.
        are calculated correctly for the initial state passed to GOAP planning.
        
        Mirrors the logic in ActionExecutor._recalculate_boolean_flags to maintain consistency.
        """
        # Calculate equipment status boolean flags
        if 'equipment_status' in world_state and isinstance(world_state['equipment_status'], dict):
            equipment = world_state['equipment_status']
            equipment['has_target_slot'] = equipment.get('target_slot') is not None
            equipment['has_selected_item'] = equipment.get('selected_item') is not None
            self.logger.debug(f"Calculated initial equipment flags: has_target_slot={equipment['has_target_slot']}, has_selected_item={equipment['has_selected_item']}")
        
        # Calculate combat context boolean flags
        if 'combat_context' in world_state and isinstance(world_state['combat_context'], dict):
            combat = world_state['combat_context']
            win_rate = combat.get('recent_win_rate', 1.0)
            combat['low_win_rate'] = win_rate < 0.2
            self.logger.debug(f"Calculated initial combat flags: low_win_rate={combat['low_win_rate']} (win_rate={win_rate})")
        
        # Calculate materials boolean flags
        if 'materials' in world_state and isinstance(world_state['materials'], dict):
            materials = world_state['materials']
            # Set default boolean flags if not present
            if 'requirements_determined' not in materials:
                materials['requirements_determined'] = False
            if 'availability_checked' not in materials:
                materials['availability_checked'] = False
            self.logger.debug(f"Calculated initial materials flags: requirements_determined={materials['requirements_determined']}, availability_checked={materials['availability_checked']}")
        
        # Calculate skill requirements boolean flags
        if 'skill_requirements' in world_state and isinstance(world_state['skill_requirements'], dict):
            skill_req = world_state['skill_requirements']
            if 'verified' not in skill_req:
                skill_req['verified'] = False
            if 'sufficient' not in skill_req:
                skill_req['sufficient'] = False
            self.logger.debug(f"Calculated initial skill requirement flags: verified={skill_req['verified']}, sufficient={skill_req['sufficient']}")
        
        # Add more boolean flag calculations here as needed
