"""
GOAP Goal Manager

This module implements a configuration-driven goal management system that replaces
hardcoded goal logic with YAML-defined templates and state-driven goal selection.
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path

from src.lib.yaml_data import YamlData
from src.game.globals import DATA_PREFIX


class GOAPGoalManager:
    """
    YAML-driven goal management system for GOAP planning.
    
    Replaces hardcoded goal definitions and selection logic with configurable
    templates and rule-based goal selection.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize goal manager with configuration."""
        self.logger = logging.getLogger(__name__)
        
        # Load goal configuration
        if config_file is None:
            config_file = f"{DATA_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
    def _load_configuration(self) -> None:
        """Load goal templates and rules from YAML configuration."""
        try:
            self.goal_templates = self.config_data.data.get('goal_templates', {})
            self.goal_selection_rules = self.config_data.data.get('goal_selection_rules', {})
            self.state_calculation_rules = self.config_data.data.get('state_calculation_rules', {})
            self.thresholds = self.config_data.data.get('thresholds', {})
            self.content_classification = self.config_data.data.get('content_classification', {})
            
            self.logger.info(f"Loaded {len(self.goal_templates)} goal templates")
            self.logger.info(f"Loaded {len(self.goal_selection_rules)} goal selection rule categories")
            
        except Exception as e:
            self.logger.error(f"Failed to load goal configuration: {e}")
            # Initialize with empty configs as fallback
            self.goal_templates = {}
            self.goal_selection_rules = {}
            self.state_calculation_rules = {}
            self.thresholds = {}
            self.content_classification = {}
    
    def calculate_world_state(self, character_state: Any, map_state: Any = None, 
                            knowledge_base: Any = None) -> Dict[str, Any]:
        """
        Calculate current world state using configuration-driven rules.
        
        Replaces the hardcoded get_current_world_state() method with rule-based computation.
        
        Args:
            character_state: Current character state object
            map_state: Optional map state for location data
            knowledge_base: Optional knowledge base for learned data
            
        Returns:
            Dictionary representing current world state
        """
        state = {}
        
        if not character_state or not hasattr(character_state, 'data'):
            self.logger.warning("No character state available for world state calculation")
            return state
            
        char_data = character_state.data
        
        # Basic character data
        current_hp = char_data.get('hp', 100)
        max_hp = char_data.get('max_hp', 100)
        hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
        
        current_level = char_data.get('level', 1)
        current_xp = char_data.get('xp', 0)
        max_xp = char_data.get('max_xp', 150)
        xp_percentage = (current_xp / max_xp * 100) if max_xp > 0 else 0
        
        # Compute cooldown status
        is_on_cooldown = self._check_cooldown_status(char_data)
        
        # Base state values
        base_state = {
            'character_x': char_data.get('x', 0),
            'character_y': char_data.get('y', 0),
            'character_level': current_level,
            'character_hp': current_hp,
            'character_max_hp': max_hp,
            'character_xp': current_xp,
            'character_max_xp': max_xp,
            'character_alive': current_hp > 0,
            'hp_percentage': hp_percentage,
            'xp_percentage': xp_percentage,
            'is_on_cooldown': is_on_cooldown,
            
            # Default state flags (may be overridden by rules)
            'has_hunted_monsters': False,
            'monsters_available': False,
            'monster_present': False,
            'at_target_location': False,
            'has_resources': False,
            'has_materials': False,
            'has_equipment': False,
            'need_exploration': False,
            'at_resource_location': False,
            'at_workshop': False,
            'equipment_info_unknown': current_level < 3,
            'resource_location_known': False,
            'workshop_location_known': False,
            'equipment_info_known': current_level >= 3,
            'craft_plan_available': False,
            'inventory_updated': False,
            'equipment_equipped': current_level >= 2,
            'character_stats_improved': current_level >= 2,
            'map_explored': False,
            'exploration_data_available': False,
            'equipment_analysis_available': False,
            'crafting_opportunities_known': False,
        }
        
        # Apply configuration-driven state calculation rules
        calculated_state = self._apply_state_calculation_rules(base_state)
        state.update(calculated_state)
        
        return state
    
    def _apply_state_calculation_rules(self, base_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply YAML-defined state calculation rules to compute derived state."""
        calculated_state = base_state.copy()
        
        # Apply each state calculation rule
        for state_key, rule_config in self.state_calculation_rules.items():
            try:
                if isinstance(rule_config, dict):
                    if rule_config.get('type') == 'computed':
                        # Special computed values (like cooldown checking)
                        if rule_config.get('method') == 'check_cooldown_expiration':
                            # Already computed in base_state as 'is_on_cooldown'
                            continue
                    elif 'formula' in rule_config:
                        # Formula-based calculation
                        formula = rule_config['formula']
                        result = self._evaluate_formula(formula, calculated_state)
                        calculated_state[state_key] = result
                elif isinstance(rule_config, str):
                    # Simple formula string
                    result = self._evaluate_formula(rule_config, calculated_state)
                    calculated_state[state_key] = result
                    
            except Exception as e:
                self.logger.warning(f"Failed to calculate state '{state_key}': {e}")
                # Use safe default
                calculated_state[state_key] = False
                
        return calculated_state
    
    def _evaluate_formula(self, formula: str, state: Dict[str, Any]) -> bool:
        """
        Safely evaluate a state calculation formula.
        
        Supports simple comparisons and boolean operations using threshold substitution.
        """
        try:
            # First handle complex boolean expressions with 'and'/'or'
            if " and " in formula:
                parts = formula.split(" and ")
                return all(self._evaluate_single_condition(part.strip(), state) for part in parts)
            elif " or " in formula:
                parts = formula.split(" or ")
                return any(self._evaluate_single_condition(part.strip(), state) for part in parts)
            else:
                return self._evaluate_single_condition(formula, state)
                
        except Exception as e:
            self.logger.warning(f"Formula evaluation failed for '{formula}': {e}")
            return False
    
    def _evaluate_single_condition(self, condition: str, state: Dict[str, Any]) -> bool:
        """Evaluate a single condition (no and/or operators)."""
        try:
            # Substitute threshold values
            evaluated_condition = condition
            for key, value in self.thresholds.items():
                placeholder = f"${{thresholds.{key}}}"
                if placeholder in evaluated_condition:
                    evaluated_condition = evaluated_condition.replace(placeholder, str(value))
            
            # Handle negation
            if evaluated_condition.startswith("not "):
                inner_condition = evaluated_condition[4:].strip()
                return not self._evaluate_single_condition(inner_condition, state)
            
            # Handle comparison operators
            for op in [">=", "<=", ">", "<", "==", "!="]:
                if op in evaluated_condition:
                    left, right = evaluated_condition.split(op, 1)
                    left_val = self._resolve_value(left.strip(), state)
                    right_val = self._resolve_value(right.strip(), state)
                    
                    if op == ">=":
                        return left_val >= right_val
                    elif op == "<=":
                        return left_val <= right_val
                    elif op == ">":
                        return left_val > right_val
                    elif op == "<":
                        return left_val < right_val
                    elif op == "==":
                        return left_val == right_val
                    elif op == "!=":
                        return left_val != right_val
            
            # Simple boolean state reference
            return bool(self._resolve_value(evaluated_condition, state))
            
        except Exception as e:
            self.logger.warning(f"Single condition evaluation failed for '{condition}': {e}")
            return False
    
    def _resolve_value(self, value_str: str, state: Dict[str, Any]) -> Any:
        """Resolve a value string to actual value."""
        value_str = value_str.strip()
        
        # Check if it's a number
        try:
            if '.' in value_str:
                return float(value_str)
            else:
                return int(value_str)
        except ValueError:
            pass
        
        # Check if it's a boolean
        if value_str.lower() == 'true':
            return True
        elif value_str.lower() == 'false':
            return False
        
        # Check if it's a state reference
        if value_str in state:
            return state[value_str]
        
        # Return as string literal
        return value_str
    
    
    def _check_cooldown_status(self, char_data: Dict[str, Any]) -> bool:
        """Check if character is currently on cooldown."""
        cooldown_seconds = char_data.get('cooldown', 0)
        cooldown_expiration = char_data.get('cooldown_expiration', None)
        
        # First check if we have a cooldown expiration time
        if cooldown_expiration:
            try:
                if isinstance(cooldown_expiration, str):
                    cooldown_end = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
                else:
                    cooldown_end = cooldown_expiration
                    
                current_time = datetime.now(timezone.utc)
                if current_time < cooldown_end:
                    remaining = (cooldown_end - current_time).total_seconds()
                    if remaining > 0.5:  # Only consider significant cooldowns
                        return True
                else:
                    # Cooldown has expired - ignore legacy cooldown field
                    return False
                        
            except Exception as e:
                self.logger.warning(f"Error parsing cooldown expiration: {e}")
        
        # Only check legacy cooldown field if no expiration time is available
        # When expiration time exists but has passed, we already returned False above
        if cooldown_expiration is None:
            return cooldown_seconds > 0.5
        
        # If we have expiration time but it's expired, cooldown is not active
        return False
    
    def select_goal(self, current_state: Dict[str, Any], 
                   available_goals: List[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select the most appropriate goal based on current state and priority rules.
        
        Args:
            current_state: Current world state
            available_goals: Optional list to restrict goal selection
            
        Returns:
            Tuple of (goal_name, goal_config) or None if no suitable goal found
        """
        if available_goals is None:
            available_goals = list(self.goal_templates.keys())
        
        best_goal = None
        best_priority = -1
        
        # Check each rule category in priority order
        for category_name, rules in self.goal_selection_rules.items():
            for rule in rules:
                if self._check_goal_condition(rule.get('condition', {}), current_state):
                    goal_name = rule.get('goal')
                    priority = rule.get('priority', 0)
                    
                    if goal_name in available_goals and priority > best_priority:
                        goal_config = self.goal_templates.get(goal_name)
                        if goal_config:
                            best_goal = (goal_name, goal_config)
                            best_priority = priority
                            
                            # Log goal selection reasoning
                            self.logger.info(f"🎯 Selected goal '{goal_name}' (priority {priority}) "
                                           f"from category '{category_name}'")
                            break
            
            # If we found a goal in this category, use it (categories are in priority order)
            if best_goal:
                break
        
        if not best_goal:
            self.logger.warning("No suitable goal found for current state")
            
        return best_goal
    
    def _check_goal_condition(self, condition: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Check if a goal selection condition is met by current state."""
        try:
            for key, expected_value in condition.items():
                actual_value = state.get(key)
                
                if isinstance(expected_value, str) and expected_value.startswith('<'):
                    # Handle numeric comparisons like "<15"
                    threshold = float(expected_value[1:])
                    if actual_value is None or actual_value >= threshold:
                        return False
                elif isinstance(expected_value, str) and expected_value.startswith('>'):
                    # Handle numeric comparisons like ">10"  
                    threshold = float(expected_value[1:])
                    if actual_value is None or actual_value <= threshold:
                        return False
                else:
                    # Direct equality check
                    if actual_value != expected_value:
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.warning(f"Goal condition check failed: {e}")
            return False
    
    def generate_goal_state(self, goal_name: str, goal_config: Dict[str, Any], 
                          current_state: Dict[str, Any], **parameters) -> Dict[str, Any]:
        """
        Generate a GOAP goal state from template configuration.
        
        Args:
            goal_name: Name of the goal template
            goal_config: Goal template configuration
            current_state: Current world state for variable substitution
            **parameters: Additional parameters for goal customization
            
        Returns:
            Dictionary representing the target goal state
        """
        target_state = goal_config.get('target_state', {}).copy()
        
        # Substitute template variables
        for key, value in target_state.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                # Template variable substitution
                var_expr = value[2:-1]  # Remove ${ and }
                
                if var_expr == 'current_level + 1':
                    target_state[key] = current_state.get('character_level', 1) + 1
                elif var_expr == 'target_level':
                    target_state[key] = parameters.get('target_level', current_state.get('character_level', 1) + 1)
                elif var_expr.startswith('strategy.'):
                    # Strategy parameter reference
                    strategy = goal_config.get('strategy', {})
                    param_name = var_expr[9:]  # Remove 'strategy.'
                    target_state[key] = strategy.get(param_name, value)
                else:
                    # Try to resolve from current state or parameters
                    resolved_value = current_state.get(var_expr) or parameters.get(var_expr)
                    if resolved_value is not None:
                        target_state[key] = resolved_value
        
        self.logger.info(f"Generated goal state for '{goal_name}': {target_state}")
        return target_state
    
    def get_goal_strategy(self, goal_name: str, goal_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get strategy configuration for a goal, merged with defaults."""
        strategy = goal_config.get('strategy', {}).copy()
        
        # Apply default thresholds
        strategy.setdefault('max_iterations', self.thresholds.get('max_goap_iterations', 10))
        strategy.setdefault('hunt_radius', self.thresholds.get('default_search_radius', 15))
        strategy.setdefault('safety_priority', True)
        
        return strategy
    
    def classify_content(self, content_code: str, content_data: Dict[str, Any], 
                        raw_content_type: str = None) -> str:
        """
        Classify content using YAML-defined rules instead of hardcoded logic.
        
        Replaces the complex _categorize_content_by_attributes() method chain.
        """
        # Check raw content type first
        if raw_content_type and raw_content_type != 'unknown':
            # Try direct mapping
            type_mappings = {
                'monster': 'monster',
                'resource': 'resource',
                'npc': 'npc', 
                'workshop': 'workshop',
                'bank': 'facility',
                'grand_exchange': 'facility',
                'tasks_master': 'npc'
            }
            if raw_content_type in type_mappings:
                return type_mappings[raw_content_type]
        
        # Apply classification rules
        for content_type, rules in self.content_classification.items():
            if self._matches_classification_rules(content_code, content_data, rules):
                return content_type
        
        # Default fallback
        self.logger.warning(f"Unknown content type for '{content_code}' "
                          f"(raw_type: '{raw_content_type}'), defaulting to 'resource'")
        return 'resource'
    
    def _matches_classification_rules(self, content_code: str, content_data: Dict[str, Any], 
                                    rules: Dict[str, Any]) -> bool:
        """Check if content matches classification rules."""
        # Check required attributes first (must all be present)
        required_attrs = rules.get('required_attributes', [])
        for attr in required_attrs:
            if attr not in content_data:
                return False
        
        # At least one of the following conditions must be true:
        # 1. Type pattern matches
        # 2. Name pattern matches
        # 3. Optional attributes match (if no type/name patterns defined)
        
        has_type_match = False
        has_name_match = False
        has_attr_match = False
        
        # Check type patterns
        type_patterns = rules.get('type_patterns', [])
        if type_patterns:
            content_type = content_data.get('type_', '').lower()
            has_type_match = any(pattern in content_type for pattern in type_patterns)
        
        # Check name patterns
        name_patterns = rules.get('name_patterns', [])
        if name_patterns:
            import re
            content_name = content_code.lower()
            has_name_match = any(re.match(pattern, content_name) for pattern in name_patterns)
        
        # Check optional attributes (if present, indicates a possible match)
        optional_attrs = rules.get('optional_attributes', [])
        if optional_attrs:
            has_attr_match = any(attr in content_data for attr in optional_attrs)
        
        # Must match at least one pattern type or have attributes if no patterns defined
        if type_patterns or name_patterns:
            return has_type_match or has_name_match
        else:
            # If no patterns defined, require attribute match
            return has_attr_match
    
    def get_threshold(self, key: str, default: Any = None) -> Any:
        """Get a configuration threshold value."""
        return self.thresholds.get(key, default)
    
    def reload_configuration(self) -> None:
        """Reload goal configuration from YAML file."""
        self.config_data.load()
        self._load_configuration()
        self.logger.info("Goal manager configuration reloaded")