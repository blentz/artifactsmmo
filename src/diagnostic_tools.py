"""
Diagnostic Tools for GOAP Planning and Action Evaluation

This module provides improved diagnostic functionality for testing and debugging
GOAP plans and action sequences with both offline simulation and live execution modes.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from src.controller.ai_player_controller import AIPlayerController
from src.controller.goal_manager import GOAPGoalManager
from src.controller.goap_execution_manager import GOAPExecutionManager
from src.game.character.state import CharacterState
from src.game.map.state import MapState
from src.lib.actions_data import ActionsData
from src.lib.goap_data import GoapData
from src.lib.yaml_data import YamlData


class DiagnosticTools:
    """Enhanced diagnostic tools for GOAP planning and action evaluation."""
    
    def __init__(self, client=None, offline=True, clean_state=False, custom_state=None, args=None):
        """
        Initialize diagnostic tools.
        
        Args:
            client: API client (required for live mode)
            offline: Whether to run in offline simulation mode
            clean_state: Whether to start with clean default state
            custom_state: Custom initial state (JSON string or dict)
            args: CLI arguments to pass through to execution pipeline
        """
        self.logger = logging.getLogger(__name__)
        self.client = client
        self.offline = offline
        self.args = args
        self.goap_executor = GOAPExecutionManager()
        self.goal_manager = GOAPGoalManager()
        
        # Initialize state
        if clean_state:
            self.current_state = self._get_clean_state()
        elif custom_state:
            self.current_state = self._parse_custom_state(custom_state)
        else:
            # Load existing world state
            goap_data = GoapData("data/world.yaml")
            self.current_state = goap_data.data.copy()
            
        # For live mode, initialize controller
        self.controller = None
        if not offline and client:
            self.controller = AIPlayerController(client=client, goal_manager=self.goal_manager)
            # Initialize with test character state if needed
            if clean_state:
                char_state = CharacterState(self.current_state.get('character_status', {}), name="test")
                self.controller.set_character_state(char_state)
                self.controller.set_map_state(MapState(client, name="test_map"))
    
    def _get_clean_state(self) -> Dict[str, Any]:
        """Get a clean default state for testing using the existing GOAP planner facilities."""
        # Use the GOAP execution manager to get the canonical clean state
        # This ensures we use exactly the same state initialization logic
        return self.goap_executor._load_start_state_defaults()
    
    def _parse_custom_state(self, custom_state) -> Dict[str, Any]:
        """Parse custom state from JSON string or dict and merge with clean state."""
        import copy
        
        # Start with clean state as base
        merged_state = copy.deepcopy(self._get_clean_state())
        
        # Parse the custom state
        if isinstance(custom_state, str):
            try:
                custom_dict = json.loads(custom_state)
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON state: {e}")
                return merged_state
        elif isinstance(custom_state, dict):
            custom_dict = custom_state
        else:
            self.logger.warning("Invalid custom state format, using clean state")
            return merged_state
        
        # Deep merge custom state into clean state
        self._deep_merge_dict(merged_state, custom_dict)
        
        # Calculate boolean flags after merging, just like GOAP planner does
        self.goap_executor._calculate_initial_boolean_flags(merged_state)
        
        return merged_state
    
    def _deep_merge_dict(self, target: Dict, source: Dict):
        """Deep merge source dict into target dict."""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge_dict(target[key], value)
            else:
                target[key] = value
    
    def show_goal_plan(self, goal_string: str):
        """
        Show or execute the GOAP plan for achieving a specified goal.
        
        Args:
            goal_string: Goal specification (template name or state expression)
        """
        self.logger.info(f"\n=== GOAP Plan Analysis for Goal: {goal_string} ===")
        self.logger.info(f"Mode: {'OFFLINE simulation' if self.offline else 'LIVE execution'}")
        
        # Load actions configuration
        actions_data = ActionsData("config/default_actions.yaml")
        actions_config = actions_data.get_actions()
        self.logger.info(f"Loaded {len(actions_config)} available actions")
        
        # Parse goal
        goal_state = self._parse_goal_string(goal_string)
        if not goal_state:
            self.logger.error("Failed to parse goal string")
            return
            
        self.logger.info(f"Goal state: {self._format_state_for_display(goal_state)}")
        self.logger.info(f"\nCurrent state summary:")
        self._display_relevant_state(self.current_state, goal_state)
        
        # Generate plan
        self.logger.info("\nGenerating GOAP plan...")
        plan = self.goap_executor.create_plan(self.current_state, goal_state, actions_config)
        
        if plan:
            self._display_plan(plan, actions_config)
            
            if not self.offline:
                # Execute plan with live API
                self.logger.info("\n=== Executing Plan with Live API ===")
                success = self._execute_plan_live(plan)
                if success:
                    self.logger.info("✅ Plan executed successfully!")
                else:
                    self.logger.error("❌ Plan execution failed!")
        else:
            self._display_no_plan_found(goal_state)
    
    def evaluate_user_plan(self, plan_string: str):
        """
        Evaluate or execute a user-defined plan using the same mechanisms as the GOAP planner.
        
        Args:
            plan_string: Plan specification (e.g., "move->fight->rest")
        """
        self.logger.info(f"\n=== Evaluating User Plan: {plan_string} ===")
        self.logger.info(f"Mode: {'OFFLINE simulation' if self.offline else 'LIVE execution'}")
        
        # Parse plan
        plan_actions = self._parse_plan_string(plan_string)
        self.logger.info(f"\nPlan contains {len(plan_actions)} actions: {plan_actions}")
        
        # Load actions configuration using same mechanism as GOAP planner
        actions_data = ActionsData("config/default_actions.yaml")
        actions_config = actions_data.get_actions()
        
        self.logger.info(f"\nStarting state summary:")
        self._display_state_summary(self.current_state)
        
        if self.offline:
            # Use GOAP execution manager for consistent state handling
            self._evaluate_plan_offline(plan_actions, actions_config)
        else:
            # Use live execution through controller
            self._evaluate_plan_online(plan_actions, actions_config)
    
    def _evaluate_plan_offline(self, plan_actions: List[str], actions_config: Dict):
        """Evaluate plan using GOAP execution manager for consistent state handling."""
        plan_valid = True
        total_cost = 0
        
        # Create a copy of current state for simulation
        simulated_state = self.current_state.copy()
        
        for i, action_name in enumerate(plan_actions, 1):
            self.logger.info(f"\n{i}. Evaluating action: {action_name}")
            
            if action_name not in actions_config:
                self.logger.error(f"   ❌ ERROR: Unknown action '{action_name}'")
                self.logger.info("   Available actions: " + ", ".join(sorted(actions_config.keys())))
                plan_valid = False
                break
            
            action_cfg = actions_config[action_name]
            
            # Use GOAP execution manager's condition checking logic
            valid, cost = self._simulate_action_with_goap_logic(action_name, action_cfg, simulated_state)
            if not valid:
                plan_valid = False
                break
            total_cost += cost
        
        # Summary
        self._display_plan_summary(plan_valid, total_cost, self.current_state, simulated_state)
    
    def _evaluate_plan_online(self, plan_actions: List[str], actions_config: Dict):
        """Evaluate plan using live execution through controller."""
        if not self.controller:
            self.logger.error("Online execution requires controller initialization")
            return
        
        plan_valid = True
        
        for i, action_name in enumerate(plan_actions, 1):
            self.logger.info(f"\n{i}. Executing action: {action_name}")
            
            if action_name not in actions_config:
                self.logger.error(f"   ❌ ERROR: Unknown action '{action_name}'")
                plan_valid = False
                break
            
            # Execute through controller using same pipeline as normal execution
            if not self._execute_action_live(action_name, actions_config[action_name]):
                plan_valid = False
                break
        
        self.logger.info(f"\n=== Plan Execution Summary ===")
        if plan_valid:
            self.logger.info("✅ Plan executed successfully")
        else:
            self.logger.info("❌ Plan execution failed")
    
    def _simulate_action_with_goap_logic(self, action_name: str, action_cfg: Dict, state: Dict) -> Tuple[bool, float]:
        """
        Simulate action using the same logic as GOAP execution manager.
        This ensures consistency between diagnostic tool and planner.
        """
        conditions = action_cfg.get('conditions', {})
        reactions = action_cfg.get('reactions', {})
        weight = action_cfg.get('weight', 1.0)
        
        # Use GOAP execution manager's condition checking logic
        conditions_met = True
        failures = []
        
        for cond_key, cond_value in conditions.items():
            if not self.goap_executor._check_condition_matches(state, cond_key, cond_value):
                conditions_met = False
                current_value = state.get(cond_key, None)
                failures.append(f"{cond_key}: required={cond_value}, current={current_value}")
        
        if conditions_met:
            self.logger.info("   ✓ All conditions met")
        else:
            self.logger.error("   ❌ Conditions not met:")
            for failure in failures:
                self.logger.error(f"     - {failure}")
            return False, 0
        
        # Apply reactions using same logic as GOAP
        self.logger.info("   Applying effects:")
        for key, value in reactions.items():
            old_value = state.get(key, None)
            
            # Handle nested reactions
            if isinstance(value, dict) and key in state and isinstance(state[key], dict):
                # Merge nested dictionaries
                for nested_key, nested_value in value.items():
                    old_nested = state[key].get(nested_key, None)
                    state[key][nested_key] = nested_value
                    self.logger.info(f"     - {key}.{nested_key}: {old_nested} → {nested_value}")
            else:
                state[key] = value
                self.logger.info(f"     - {key}: {old_value} → {value}")
        
        self.logger.info(f"   ✓ Action executable (cost: {weight})")
        return True, weight
    
    def _parse_goal_string(self, goal_string: str) -> Dict[str, Any]:
        """Parse goal string into goal state dictionary."""
        # Check if it's a goal template
        if goal_string in self.goal_manager.goal_templates:
            template = self.goal_manager.goal_templates[goal_string]
            goal_state = template.get('target_state', {}).copy()
            self.logger.info(f"Using goal template '{goal_string}'")
            return goal_state
        
        # Parse custom goal expressions
        goal_state = {}
        
        # Handle nested state expressions (e.g., "character_status.alive=true")
        if '.' in goal_string and '=' in goal_string:
            path, value = goal_string.split('=', 1)
            parts = path.strip().split('.')
            
            # Build nested dictionary
            current = goal_state
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            
            # Set the value
            key = parts[-1]
            current[key] = self._parse_value(value.strip())
            
        # Handle simple expressions
        elif '=' in goal_string:
            key, value = goal_string.split('=', 1)
            goal_state[key.strip()] = self._parse_value(value.strip())
            
        # Handle predefined goal types
        elif "level" in goal_string:
            level_match = re.search(r'level[\s_]*(\d+)', goal_string, re.IGNORECASE)
            if level_match:
                target_level = int(level_match.group(1))
                goal_state = {
                    'character_status': {
                        'level': target_level
                    }
                }
        else:
            # Default to boolean true
            goal_state[goal_string] = True
            
        return goal_state
    
    def _parse_value(self, value: str) -> Any:
        """Parse string value to appropriate type."""
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        elif value.lower() == 'null' or value.lower() == 'none':
            return None
        else:
            try:
                return int(value)
            except ValueError:
                try:
                    return float(value)
                except ValueError:
                    return value
    
    def _parse_plan_string(self, plan_string: str) -> List[str]:
        """Parse plan string into list of actions."""
        separators = ['->', ',', '|', ';']
        plan_actions = None
        
        for sep in separators:
            if sep in plan_string:
                plan_actions = [a.strip() for a in plan_string.split(sep)]
                break
                
        if not plan_actions:
            plan_actions = [plan_string.strip()]
            
        return plan_actions
    
    def _check_conditions_nested(self, conditions: Dict[str, Any], state: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check if conditions are met with proper nested state handling.
        
        Returns:
            Tuple of (all_conditions_met, list_of_failure_messages)
        """
        failures = []
        
        for key, required_value in conditions.items():
            current_value = state.get(key, None)
            
            # Handle nested dictionary conditions
            if isinstance(required_value, dict) and isinstance(current_value, dict):
                # Check each nested condition
                for nested_key, nested_required in required_value.items():
                    nested_current = current_value.get(nested_key, None)
                    
                    if nested_current != nested_required:
                        failures.append(
                            f"{key}.{nested_key}: required={nested_required}, "
                            f"current={nested_current}"
                        )
            elif current_value != required_value:
                failures.append(
                    f"{key}: required={required_value}, "
                    f"current={current_value}"
                )
        
        return len(failures) == 0, failures
    
    def _simulate_action(self, action_name: str, action_cfg: Dict, state: Dict) -> Tuple[bool, float]:
        """
        Simulate an action in offline mode.
        
        Returns:
            Tuple of (success, cost)
        """
        conditions = action_cfg.get('conditions', {})
        reactions = action_cfg.get('reactions', {})
        weight = action_cfg.get('weight', 1.0)
        
        # Check conditions
        conditions_met, failures = self._check_conditions_nested(conditions, state)
        
        if conditions_met:
            self.logger.info("   ✓ All conditions met")
        else:
            self.logger.error("   ❌ Conditions not met:")
            for failure in failures:
                self.logger.error(f"     - {failure}")
            return False, 0
        
        # Apply reactions
        self.logger.info("   Applying effects:")
        for key, value in reactions.items():
            old_value = state.get(key, None)
            
            # Handle nested reactions
            if isinstance(value, dict) and key in state and isinstance(state[key], dict):
                # Merge nested dictionaries
                for nested_key, nested_value in value.items():
                    old_nested = state[key].get(nested_key, None)
                    state[key][nested_key] = nested_value
                    self.logger.info(f"     - {key}.{nested_key}: {old_nested} → {nested_value}")
            else:
                state[key] = value
                self.logger.info(f"     - {key}: {old_value} → {value}")
        
        self.logger.info(f"   ✓ Action executable (cost: {weight})")
        return True, weight
    
    def _execute_action_live(self, action_name: str, action_cfg: Dict) -> bool:
        """Execute a single action with live API."""
        if not self.controller:
            self.logger.error("Live execution requires controller initialization")
            return False
        
        try:
            # Create action data
            action_data = {'name': action_name}
            
            # Execute action
            self.logger.info(f"   🚀 Executing {action_name} via API...")
            success = self.controller._execute_single_action(action_name, action_data)
            
            if success:
                self.logger.info(f"   ✅ {action_name} executed successfully")
                # Update current state from controller
                self.current_state = self.controller.get_current_world_state()
            else:
                self.logger.error(f"   ❌ {action_name} execution failed")
                
            return success
            
        except Exception as e:
            self.logger.error(f"   ❌ Exception during {action_name}: {e}")
            return False
    
    def _execute_plan_live(self, plan: List[Dict]) -> bool:
        """Execute entire plan with live API."""
        if not self.controller:
            self.logger.error("Live execution requires controller initialization")
            return False
        
        try:
            # Set plan on controller
            self.controller.current_plan = plan
            self.controller.current_action_index = 0
            
            # Execute plan
            success = self.controller.execute_plan()
            
            # Update state
            self.current_state = self.controller.get_current_world_state()
            
            return success
            
        except Exception as e:
            self.logger.error(f"Plan execution error: {e}")
            return False
    
    def _display_plan(self, plan: List[Dict], actions_config: Dict):
        """Display formatted plan details."""
        self.logger.info(f"\n✅ Plan found with {len(plan)} actions:\n")
        
        total_weight = 0
        for i, action in enumerate(plan, 1):
            action_name = action.get('name', 'unknown')
            action_cfg = actions_config.get(action_name, {})
            weight = action_cfg.get('weight', 1.0)
            total_weight += weight
            
            self.logger.info(f"{i}. {action_name} (weight: {weight})")
            
            # Show conditions
            conditions = action_cfg.get('conditions', {})
            if conditions:
                self.logger.info("   Requires:")
                self._display_conditions(conditions)
            
            # Show effects
            reactions = action_cfg.get('reactions', {})
            if reactions:
                self.logger.info("   Effects:")
                self._display_reactions(reactions)
            
            self.logger.info("")
        
        self.logger.info(f"Total plan cost: {total_weight:.2f}")
    
    def _display_conditions(self, conditions: Dict, indent: int = 5):
        """Display conditions in readable format."""
        for key, value in conditions.items():
            if isinstance(value, dict):
                self.logger.info(f"{' ' * indent}- {key}:")
                for nested_key, nested_value in value.items():
                    self.logger.info(f"{' ' * (indent + 2)}  {nested_key}: {nested_value}")
            else:
                self.logger.info(f"{' ' * indent}- {key}: {value}")
    
    def _display_reactions(self, reactions: Dict, indent: int = 5):
        """Display reactions in readable format."""
        self._display_conditions(reactions, indent)  # Same format
    
    def _display_no_plan_found(self, goal_state: Dict):
        """Display helpful information when no plan is found."""
        self.logger.info("\n❌ No plan found!")
        self.logger.info("\nPossible reasons:")
        self.logger.info("- Goal is already satisfied in current state")
        self.logger.info("- No action sequence can achieve the goal")
        self.logger.info("- Missing prerequisite states")
        
        self.logger.info("\nGoal requirements:")
        self._display_state_requirements(goal_state)
        
        self.logger.info("\nCurrent state values:")
        self._display_relevant_state(self.current_state, goal_state)
    
    def _display_state_requirements(self, state: Dict, prefix: str = ""):
        """Display state requirements in readable format."""
        for key, value in state.items():
            if isinstance(value, dict):
                self.logger.info(f"{prefix}{key}:")
                self._display_state_requirements(value, prefix + "  ")
            else:
                self.logger.info(f"{prefix}{key}: {value}")
    
    def _display_relevant_state(self, current_state: Dict, goal_state: Dict, prefix: str = ""):
        """Display current state values relevant to the goal."""
        for key, goal_value in goal_state.items():
            current_value = current_state.get(key, "<not set>")
            
            if isinstance(goal_value, dict) and isinstance(current_value, dict):
                self.logger.info(f"{prefix}{key}:")
                self._display_relevant_state(current_value, goal_value, prefix + "  ")
            else:
                self.logger.info(f"{prefix}{key}: {current_value}")
    
    def _display_state_summary(self, state: Dict):
        """Display a summary of the current state."""
        # Character status
        char_status = state.get('character_status', {})
        self.logger.info(f"Character: Level {char_status.get('level', 1)}, "
                        f"HP: {char_status.get('hp_percentage', 100)}%, "
                        f"Alive: {char_status.get('alive', True)}")
        
        # Combat context
        combat = state.get('combat_context', {})
        self.logger.info(f"Combat: Status={combat.get('status', 'idle')}, "
                        f"Win rate={combat.get('recent_win_rate', 1.0)}")
        
        # Location
        location = state.get('location_context', {}).get('current', {})
        self.logger.info(f"Location: ({location.get('x', 0)}, {location.get('y', 0)}) "
                        f"Type: {location.get('type', 'unknown')}")
    
    def _display_plan_summary(self, plan_valid: bool, total_cost: float, 
                             initial_state: Dict, final_state: Dict):
        """Display plan evaluation summary."""
        self.logger.info("\n=== Plan Evaluation Summary ===")
        
        if plan_valid:
            self.logger.info("✅ Plan is VALID and executable")
            self.logger.info(f"Total cost: {total_cost}")
            
            if self.offline:
                self.logger.info("\nState changes (simulated):")
                self._display_state_changes(initial_state, final_state)
        else:
            self.logger.info("❌ Plan is INVALID and cannot be executed")
            self.logger.info("Fix the issues above before the plan can work")
    
    def _display_state_changes(self, initial: Dict, final: Dict, prefix: str = ""):
        """Display changes between initial and final states."""
        all_keys = set(initial.keys()) | set(final.keys())
        
        for key in sorted(all_keys):
            initial_val = initial.get(key, None)
            final_val = final.get(key, None)
            
            if isinstance(initial_val, dict) and isinstance(final_val, dict):
                # Check if any nested values changed
                if self._has_nested_changes(initial_val, final_val):
                    self.logger.info(f"{prefix}{key}:")
                    self._display_state_changes(initial_val, final_val, prefix + "  ")
            elif initial_val != final_val:
                self.logger.info(f"{prefix}{key}: {initial_val} → {final_val}")
    
    def _has_nested_changes(self, dict1: Dict, dict2: Dict) -> bool:
        """Check if there are any changes between two dictionaries."""
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            if dict1.get(key) != dict2.get(key):
                return True
        return False
    
    def _format_state_for_display(self, state: Dict) -> str:
        """Format state dictionary for concise display."""
        def format_value(v):
            if isinstance(v, dict):
                return "{...}"
            elif isinstance(v, list):
                return f"[{len(v)} items]"
            else:
                return str(v)
        
        items = []
        for k, v in state.items():
            if isinstance(v, dict):
                # For nested dicts, show the nested structure
                nested_items = [f"{nk}: {format_value(nv)}" for nk, nv in v.items()]
                items.append(f"{k}: {{{', '.join(nested_items)}}}")
            else:
                items.append(f"{k}: {format_value(v)}")
        
        return "{" + ", ".join(items) + "}"