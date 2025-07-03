"""
GOAP Goal Manager

This module implements a configuration-driven goal management system that replaces
hardcoded goal logic with YAML-defined templates and state-driven goal selection.
"""

import copy
import logging
import random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


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
            config_file = f"{CONFIG_PREFIX}/goal_templates.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
        # Load state defaults configuration
        self.state_defaults_config = YamlData(f"{CONFIG_PREFIX}/consolidated_state_defaults.yaml")
        self.state_defaults = self.state_defaults_config.data.get('state_defaults', {})
        
        self.logger.info("Goal manager initialized with consolidated state system")
        
    def _load_configuration(self) -> None:
        """Load goal templates and rules from YAML configuration."""
        try:
            self.goal_templates = self.config_data.data.get('goal_templates', {})
            self.goal_selection_rules = self.config_data.data.get('goal_selection_rules', {})
            self.state_calculation_rules = self.config_data.data.get('state_calculation_rules', {})
            self.state_mappings = self.config_data.data.get('state_mappings', {})
            self.thresholds = self.config_data.data.get('thresholds', {})
            
            self.logger.debug(f"Loaded {len(self.goal_templates)} goal templates")
            self.logger.debug(f"Loaded {len(self.goal_selection_rules)} goal selection rule categories")
            
        except Exception as e:
            self.logger.error(f"Failed to load goal configuration: {e}")
            # Initialize with empty configs as fallback
            self.goal_templates = {}
            self.goal_selection_rules = {}
            self.state_calculation_rules = {}
            self.thresholds = {}
    
    def calculate_world_state(self, character_state: Any, map_state: Any = None, 
                            knowledge_base: Any = None) -> Dict[str, Any]:
        """
        Calculate current world state using consolidated state system.
        
        This returns a dramatically simplified state representation using
        complex data types instead of numerous boolean flags.
        
        Args:
            character_state: Current character state object
            map_state: Optional map state for location data
            knowledge_base: Optional knowledge base for learned data
            
        Returns:
            Dictionary with consolidated state structure
        """
        # Initialize consolidated state structure from YAML configuration
        state = copy.deepcopy(self.state_defaults)
        
        # Initialize skills with empty dict if not loaded from config
        if 'skills' not in state:
            state['skills'] = {}
        
        if not character_state or not hasattr(character_state, 'data'):
            self.logger.warning("No character state available for world state calculation")
            return state
            
        char_data = character_state.data
        
        # Update character status
        current_hp = char_data.get('hp', 100)
        max_hp = char_data.get('max_hp', 100)
        hp_percentage = (current_hp / max_hp * 100) if max_hp > 0 else 0
        
        current_level = char_data.get('level', 1)
        current_xp = char_data.get('xp', 0)
        max_xp = char_data.get('max_xp', 150)
        xp_percentage = (current_xp / max_xp * 100) if max_xp > 0 else 0
        
        state['character_status'] = {
            'level': current_level,
            'hp_percentage': hp_percentage,
            'xp_percentage': xp_percentage,
            'alive': current_hp > 0,
            'safe': hp_percentage >= 30,
            'cooldown_active': self._check_cooldown_status(char_data)
        }
        
        # Update equipment status
        state['equipment_status']['weapon'] = char_data.get('weapon_slot') or None
        state['equipment_status']['armor'] = char_data.get('body_armor_slot') or None
        state['equipment_status']['shield'] = char_data.get('shield_slot') or None
        state['equipment_status']['helmet'] = char_data.get('helmet_slot') or None
        state['equipment_status']['boots'] = char_data.get('boots_slot') or None
        
        # Update location context
        state['location_context']['current'] = {
            'x': char_data.get('x', 0),
            'y': char_data.get('y', 0),
            'type': self._determine_location_type(char_data, map_state)
        }
        
        # Update materials from inventory
        inventory = {}
        for item in char_data.get('inventory', []):
            if item.get('code'):
                inventory[item['code']] = item.get('quantity', 0)
        state['materials']['inventory'] = inventory
        
        # Update skills dynamically from character data
        # Look for any keys ending with '_level' to identify skills
        for key in char_data:
            if key.endswith('_level') and key != 'level':
                skill_name = key[:-6]  # Remove '_level' suffix
                state['skills'][skill_name] = {
                    'level': char_data.get(key, 1),
                    'required': 0,  # Will be set by actions
                    'xp': char_data.get(f'{skill_name}_xp', 0)
                }
        
        # Log the consolidated state structure
        self.logger.debug(f"📊 Consolidated state keys: {list(state.keys())}")
        self.logger.debug(f"🔧 Equipment: {state['equipment_status']}")
        self.logger.debug(f"📍 Location: {state['location_context']['current']}")
        self.logger.debug(f"💰 Materials: {len(state['materials']['inventory'])} types")
        self.logger.debug(f"🎓 Skills: {list(state['skills'].keys())}")
        
        # Apply state mappings to add derived states (like has_gained_xp)
        enhanced_state = self._apply_state_mappings_to_selection_state(state)
        
        # Calculate additional boolean flags for equipment
        enhanced_state['equipment_status']['has_target_slot'] = enhanced_state['equipment_status'].get('target_slot') is not None
        enhanced_state['equipment_status']['has_selected_item'] = enhanced_state['equipment_status'].get('selected_item') is not None
        
        # Calculate combat context flags
        win_rate = enhanced_state['combat_context'].get('recent_win_rate', 1.0)
        enhanced_state['combat_context']['low_win_rate'] = win_rate < 0.2
        
        # Return consolidated state with derived states
        self.logger.debug(f"🔄 Using consolidated state format with {len(enhanced_state)} state groups")
        
        return enhanced_state
    
    def _determine_location_type(self, char_data: Dict, map_state: Any) -> str:
        """Determine the type of current location from map data."""
        if not map_state:
            return "unknown"
            
        x = char_data.get('x', 0)
        y = char_data.get('y', 0)
        
        # Use map state to determine location type
        location_data = getattr(map_state, 'get_location', lambda x, y: None)(x, y)
        if location_data:
            return location_data.get('type', 'unknown')
        
        return "unknown"
    
    def _check_cooldown_status(self, char_data: Dict[str, Any]) -> bool:
        """Check if character is currently on cooldown."""
        cooldown_seconds = char_data.get('cooldown', 0)
        cooldown_expiration = char_data.get('cooldown_expiration', None)
        
        # Debug log to see what data we're actually getting
        self.logger.debug(f"Cooldown check - cooldown: {cooldown_seconds}, cooldown_expiration: {cooldown_expiration}")
        self.logger.debug(f"Available char_data keys: {list(char_data.keys())}")
        
        # First check if we have a cooldown expiration time
        if cooldown_expiration:
            try:
                if isinstance(cooldown_expiration, str):
                    cooldown_end = datetime.fromisoformat(cooldown_expiration)
                else:
                    cooldown_end = cooldown_expiration
                    
                current_time = datetime.now(timezone.utc)
                if current_time < cooldown_end:
                    remaining = (cooldown_end - current_time).total_seconds()
                    self.logger.debug(f"Cooldown check: expiration={cooldown_expiration}, current_time={current_time.isoformat()}, remaining={remaining:.1f}s")
                    if remaining > 0.5:  # Only consider significant cooldowns
                        self.logger.debug(f"Cooldown ACTIVE: {remaining:.1f}s remaining")
                        return True
                else:
                    # Cooldown has expired
                    self.logger.debug(f"Cooldown EXPIRED: expiration={cooldown_expiration}, current_time={current_time.isoformat()}")
                    return False
                        
            except Exception as e:
                self.logger.warning(f"Error parsing cooldown expiration: {e}")
        else:
            self.logger.debug("No cooldown_expiration found in char_data")
        
        # Check legacy cooldown field if no expiration time
        if cooldown_seconds > 0.5:
            self.logger.debug(f"Legacy cooldown ACTIVE: {cooldown_seconds}s")
        return cooldown_seconds > 0.5
    
    def select_goal(self, current_state: Dict[str, Any], 
                   available_goals: List[str] = None,
                   goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select the most appropriate goal using unified weighted scoring system.
        
        Replaces the previous three-method approach (emergency, probabilistic XP, standard)
        with a single weighted scoring system that evaluates all goals and selects the
        highest scoring viable option.
        
        Args:
            current_state: Current world state
            available_goals: Optional list to restrict goal selection
            goal_weights: Optional dictionary of goal_name -> bonus_weight for persistence
            
        Returns:
            Tuple of (goal_name, goal_config) or None if no suitable goal found
        """
        if available_goals is None:
            available_goals = list(self.goal_templates.keys())
        
        return self._select_goal_with_weighted_scoring(current_state, available_goals, goal_weights)
    
    def _select_goal_with_weighted_scoring(self, current_state: Dict[str, Any], 
                                          available_goals: List[str],
                                          goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Hierarchical goal selection system.
        
        Implements user-requested hierarchy:
        1. Safety vs Leveling up (first level decision)
        2. XP-gaining goals (second level - combat vs crafting, combat weighted higher)
        
        Args:
            current_state: Current world state
            available_goals: List of goals to consider
            goal_weights: Optional persistence weight bonuses
            
        Returns:
            Tuple of (goal_name, goal_config) for selected goal
        """
        # First level: Safety vs Leveling up
        safety_goal = self._select_safety_goal(current_state, available_goals, goal_weights)
        if safety_goal:
            return safety_goal
        
        # Second level: XP-gaining goals (combat vs crafting)
        xp_goal = self._select_xp_goal_hierarchical(current_state, available_goals, goal_weights)
        if xp_goal:
            return xp_goal
        
        # Fallback: Equipment and other support goals
        return self._select_support_goal(current_state, available_goals, goal_weights)
    
    def _select_safety_goal(self, current_state: Dict[str, Any], 
                           available_goals: List[str],
                           goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select safety-related goals (emergency and maintenance).
        
        Args:
            current_state: Current world state
            available_goals: List of goals to consider
            goal_weights: Optional persistence weight bonuses
            
        Returns:
            Safety goal if needed, None otherwise
        """
        safety_categories = ['emergency', 'maintenance']
        best_goal = None
        best_priority = -1
        
        for category_name in safety_categories:
            if category_name not in self.goal_selection_rules:
                continue
                
            for rule in self.goal_selection_rules[category_name]:
                if self._check_goal_condition(rule.get('condition', {}), current_state):
                    goal_name = rule.get('goal')
                    if goal_name in available_goals:
                        goal_config = self.goal_templates.get(goal_name)
                        if goal_config:
                            priority = rule.get('priority', 0)
                            
                            # Apply persistence weight bonus if available
                            if goal_weights and goal_name in goal_weights:
                                persistence_bonus = goal_weights[goal_name]
                                weighted_priority = priority + persistence_bonus
                                self.logger.debug(f"🎯 Applied persistence bonus to safety goal '{goal_name}': "
                                               f"{priority} + {persistence_bonus:.2f} = {weighted_priority:.2f}")
                            else:
                                weighted_priority = priority
                            
                            if weighted_priority > best_priority:
                                best_goal = (goal_name, goal_config)
                                best_priority = weighted_priority
                                self.logger.debug(f"🛡️ Selected safety goal '{goal_name}' (priority {weighted_priority:.2f}) "
                                               f"from category '{category_name}'")
        return best_goal
    
    def _select_xp_goal_hierarchical(self, current_state: Dict[str, Any], 
                                    available_goals: List[str],
                                    goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select XP-gaining goals using rule-based system from configuration.
        
        Evaluates progression category goals from goal_selection_rules with
        weighted selection based on goal types and persistence bonuses.
        
        Args:
            current_state: Current world state
            available_goals: List of goals to consider
            goal_weights: Optional persistence weight bonuses
            
        Returns:
            XP-gaining goal or None
        """
        # Check if character is safe for XP activities
        char_status = current_state.get('character_status', {})
        if not char_status.get('safe', False) or not char_status.get('alive', False):
            return None
        
        # Use rule-based evaluation for progression goals
        progression_goals = []
        
        if 'progression' in self.goal_selection_rules:
            for rule in self.goal_selection_rules['progression']:
                if self._check_goal_condition(rule.get('condition', {}), current_state):
                    goal_name = rule.get('goal')
                    if goal_name in available_goals:
                        goal_config = self.goal_templates.get(goal_name)
                        if goal_config:
                            # Base priority from rule
                            base_priority = rule.get('priority', 50)
                            
                            # Determine goal type and apply type-based weight
                            goal_type = 'other'
                            type_weight = 1.0
                            
                            # Check goal objective type from config
                            objective_type = goal_config.get('objective_type', '')
                            if objective_type == 'combat' or 'hunt' in goal_name.lower():
                                goal_type = 'combat'
                                type_weight = 3.0  # Higher weight for combat
                            elif (objective_type in ['equipment_progression', 'crafting'] or 
                                  any(skill in goal_name.lower() for skill in ['craft', 'weapon', 'armor', 'equipment'])):
                                goal_type = 'crafting'
                                type_weight = 2.0  # Lower weight for crafting
                            
                            # Apply persistence bonus if available
                            persistence_bonus = goal_weights.get(goal_name, 0.0) if goal_weights else 0.0
                            
                            # Calculate total weight
                            total_weight = (base_priority / 10.0) * type_weight + persistence_bonus
                            
                            progression_goals.append({
                                'goal_name': goal_name,
                                'goal_config': goal_config,
                                'weight': total_weight,
                                'type': goal_type,
                                'base_priority': base_priority
                            })
                            
                            self.logger.debug(f"📊 Evaluated progression goal '{goal_name}': "
                                           f"priority={base_priority}, type={goal_type}, "
                                           f"weight={total_weight:.2f}")
                            
                            if persistence_bonus > 0:
                                self.logger.debug(f"🎯 Applied persistence bonus: +{persistence_bonus:.2f}")
        
        if not progression_goals:
            self.logger.debug("No progression goals available for current state")
            return None
        
        # Log all available progression goals
        self.logger.debug(f"Available progression goals: {[g['goal_name'] for g in progression_goals]}")
        
        # Weighted random selection
        total_weight = sum(goal['weight'] for goal in progression_goals)
        random_value = random.uniform(0, total_weight)
        
        cumulative_weight = 0
        for goal in progression_goals:
            cumulative_weight += goal['weight']
            if random_value <= cumulative_weight:
                self.logger.debug(f"⚡ Selected progression goal '{goal['goal_name']}' "
                               f"(weight {goal['weight']:.2f}, type {goal['type']})")
                return (goal['goal_name'], goal['goal_config'])
        
        return None
    
    def _select_support_goal(self, current_state: Dict[str, Any], 
                            available_goals: List[str],
                            goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select support goals (equipment, skill progression, exploration).
        
        Args:
            current_state: Current world state
            available_goals: List of goals to consider
            goal_weights: Optional persistence weight bonuses
            
        Returns:
            Support goal or None
        """
        support_categories = ['equipment', 'skill_progression', 'exploration']
        best_goal = None
        best_priority = -1
        
        for category_name in support_categories:
            if category_name not in self.goal_selection_rules:
                continue
                
            for rule in self.goal_selection_rules[category_name]:
                if self._check_goal_condition(rule.get('condition', {}), current_state):
                    goal_name = rule.get('goal')
                    if goal_name in available_goals:
                        goal_config = self.goal_templates.get(goal_name)
                        if goal_config:
                            priority = rule.get('priority', 0)
                            
                            # Apply persistence weight bonus
                            if goal_weights and goal_name in goal_weights:
                                persistence_bonus = goal_weights[goal_name]
                                weighted_priority = priority + persistence_bonus
                                self.logger.debug(f"🎯 Applied persistence bonus to support goal '{goal_name}': "
                                               f"{priority} + {persistence_bonus:.2f} = {weighted_priority:.2f}")
                            else:
                                weighted_priority = priority
                            
                            if weighted_priority > best_priority:
                                best_goal = (goal_name, goal_config)
                                best_priority = weighted_priority
                                self.logger.debug(f"🔧 Selected support goal '{goal_name}' (priority {weighted_priority:.2f}) "
                                               f"from category '{category_name}'")
                                break
            
            # If we found a goal in this category, use it
            if best_goal:
                break
        
        if not best_goal:
            self.logger.warning("No suitable goal found for current state")
            
        return best_goal
    
    def _is_crafting_goal_viable(self, goal_name: str, current_state: Dict[str, Any]) -> bool:
        """
        Check if a crafting goal is viable.
        
        Args:
            goal_name: Name of the goal
            current_state: Current world state
            
        Returns:
            True if crafting goal is viable
        """
        char_status = current_state.get('character_status', {})
        character_level = char_status.get('level', 1)
        
        # Basic viability check
        if character_level < 2:  # Need level 2+ for most crafting
            return False
        
        # Check if on cooldown - crafting actions require no cooldown
        if char_status.get('cooldown_active', False):
            return False
        
        # Specific goal checks
        if goal_name == 'craft_selected_item':
            equipment_status = current_state.get('equipment_status', {})
            return (equipment_status.get('selected_item') is not None and 
                    equipment_status.get('upgrade_status') != 'completed')
        
        return True
    
    def _is_combat_viable(self, current_state: Dict[str, Any]) -> bool:
        """Check if combat is viable based on character state and monster availability."""
        char_status = current_state.get('character_status', {})
        combat_context = current_state.get('combat_context', {})
        
        # Basic combat requirements
        if char_status.get('hp_percentage', 0) < 15:  # Need at least 15% HP
            return False
        
        if char_status.get('cooldown_active', False):
            return False
        
        character_level = char_status.get('level', 1)
        if character_level < 1:  # Safety check
            return False
        
        # Check if combat is explicitly marked as not viable
        if combat_context.get('recent_win_rate', 1.0) < 0.2:
            return False
        
        return True
    
    def _check_goal_condition(self, condition: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """
        Check if a goal selection condition is met by current state.
        
        This method works with simple boolean flags from state mappings but 
        maintains backward compatibility for existing test operators.
        
        Args:
            condition: Dictionary of conditions to check
            state: Current world state
            
        Returns:
            True if all conditions are met, False otherwise
        """
        try:
            # Apply state mappings to get computed boolean flags (if available)
            enhanced_state = self._apply_state_mappings_to_selection_state(state)
            
            for key, expected_value in condition.items():
                # Get actual value from enhanced state first, then fallback to original state
                actual_value = self._get_nested_value(enhanced_state, key)
                if actual_value is None:
                    actual_value = self._get_nested_value(state, key)
                
                # Handle dict conditions (for nested states)
                if isinstance(expected_value, dict) and isinstance(actual_value, dict):
                    # Recursively check nested conditions with the actual nested data
                    if not self._check_goal_condition(expected_value, actual_value):
                        return False
                    continue
                
                # Handle string comparison operators (backward compatibility)
                if isinstance(expected_value, str):
                    # Numeric comparisons for backward compatibility
                    if expected_value.startswith('>='):
                        threshold = float(expected_value[2:])
                        if actual_value is None or float(actual_value) < threshold:
                            return False
                    elif expected_value.startswith('<='):
                        threshold = float(expected_value[2:])
                        if actual_value is None or float(actual_value) > threshold:
                            return False
                    elif expected_value.startswith('<'):
                        threshold = float(expected_value[1:])
                        if actual_value is None or float(actual_value) >= threshold:
                            return False
                    elif expected_value.startswith('>'):
                        threshold = float(expected_value[1:])
                        if actual_value is None or float(actual_value) <= threshold:
                            return False
                    elif expected_value == "!null":
                        if actual_value is None:
                            return False
                    elif expected_value == "null":
                        if actual_value is not None:
                            return False
                    else:
                        # Direct string equality
                        if str(actual_value) != expected_value:
                            return False
                else:
                    # Simple equality check - preferred new approach
                    if actual_value != expected_value:
                        return False
                        
            return True
            
        except Exception as e:
            self.logger.warning(f"Goal condition check failed: {e}")
            return False
    
    def _apply_state_mappings_to_selection_state(self, state: Dict[str, Any], 
                                                  parameters: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Apply state mappings to current state for goal selection.
        
        This creates computed boolean flags from the raw state values
        using the state_mappings configuration.
        
        Args:
            state: Current world state
            parameters: Optional parameters for condition substitution
            
        Returns:
            Enhanced state with computed boolean flags
        """
        enhanced_state = state.copy()
        if parameters is None:
            parameters = {}
        
        # Apply all state mappings to create computed flags
        for category_name, category_mappings in self.state_mappings.items():
            if category_name not in enhanced_state:
                enhanced_state[category_name] = {}
                
            for flag_name, mapping in category_mappings.items():
                source_path = mapping['source']
                condition = mapping['condition']
                
                # Apply parameter substitution to condition if needed
                if '{target_level}' in condition:
                    if 'target_level' in parameters:
                        condition = condition.replace('{target_level}', str(parameters['target_level']))
                    else:
                        # Skip this mapping if parameter is not available
                        continue
                
                # Get source value
                source_value = self._get_nested_value(state, source_path)
                if source_value is not None:
                    # Compute flag value
                    flag_value = self._evaluate_condition(source_value, condition)
                    enhanced_state[category_name][flag_name] = flag_value
                    
        return enhanced_state
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Any:
        """Get value from nested dictionary using dot notation.
        
        Example: 'character_status.level' returns data['character_status']['level']
        """
        if '.' not in key:
            return data.get(key)
        
        parts = key.split('.')
        current = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    def _resolve_comparison_operators(self, target_state: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert comparison operators in target state to concrete GOAP target values.
        
        This traverses nested state structures and converts string comparisons like '>0'
        to actual target values that the GOAP planner can work with.
        
        Args:
            target_state: Target state potentially containing comparison operators
            current_state: Current state for determining appropriate target values
            
        Returns:
            Updated target state with comparison operators resolved to concrete values
        """
        def _resolve_nested_value(key_path: str, value: Any) -> Any:
            """Resolve a single nested value, handling comparison operators."""
            if not isinstance(value, str):
                return value
                
            # Get current value using nested key access
            current_value = self._get_nested_value(current_state, key_path)
            if current_value is None:
                current_value = 0  # Default for numeric comparisons
                
            # Handle comparison operators
            if value.startswith('>='):
                try:
                    threshold = float(value[2:])
                    # Target should be at least the threshold
                    target = max(current_value + 1, int(threshold)) if isinstance(current_value, (int, float)) else int(threshold)
                    self.logger.debug(f"Resolved goal {key_path}: '{value}' -> {target} (current: {current_value})")
                    return target
                except ValueError:
                    return value
                    
            elif value.startswith('>'):
                try:
                    threshold = float(value[1:])
                    # Target should be greater than threshold
                    target = max(current_value + 1, int(threshold) + 1) if isinstance(current_value, (int, float)) else int(threshold) + 1
                    self.logger.debug(f"Resolved goal {key_path}: '{value}' -> {target} (current: {current_value})")
                    return target
                except ValueError:
                    return value
                    
            elif value.startswith('<='):
                try:
                    threshold = float(value[2:])
                    # Target should be at most the threshold
                    target = min(current_value - 1, int(threshold)) if isinstance(current_value, (int, float)) else int(threshold)
                    self.logger.debug(f"Resolved goal {key_path}: '{value}' -> {target} (current: {current_value})")
                    return target
                except ValueError:
                    return value
                    
            elif value.startswith('<'):
                try:
                    threshold = float(value[1:])
                    # Target should be less than threshold
                    target = min(current_value - 1, int(threshold) - 1) if isinstance(current_value, (int, float)) else int(threshold) - 1
                    self.logger.debug(f"Resolved goal {key_path}: '{value}' -> {target} (current: {current_value})")
                    return target
                except ValueError:
                    return value
            
            return value
        
        def _resolve_recursive(state_dict: Dict[str, Any], prefix: str = '') -> Dict[str, Any]:
            """Recursively resolve comparison operators in nested dictionaries."""
            resolved = {}
            for key, value in state_dict.items():
                full_key = f"{prefix}.{key}" if prefix else key
                
                if isinstance(value, dict):
                    # Recursively process nested dictionaries
                    resolved[key] = _resolve_recursive(value, full_key)
                else:
                    # Resolve leaf values
                    resolved[key] = _resolve_nested_value(full_key, value)
            return resolved
        
        return _resolve_recursive(target_state)
    
    def generate_goal_state(self, goal_name: str, goal_config: Dict[str, Any], 
                          current_state: Dict[str, Any], **parameters) -> Dict[str, Any]:
        """
        Generate a GOAP goal state from template configuration.
        
        This method now processes simple, declarative target states and applies
        any necessary parameter substitution from the goal's parameter configuration.
        
        Args:
            goal_name: Name of the goal template
            goal_config: Goal template configuration  
            current_state: Current world state
            **parameters: Additional parameters for goal customization
            
        Returns:
            Dictionary representing the target goal state
        """
        target_state = goal_config.get('target_state', {}).copy()
        goal_parameters = goal_config.get('parameters', {}).copy()
        
        # Merge runtime parameters with goal template parameters
        goal_parameters.update(parameters)
        
        # Apply state mappings to resolve computed boolean flags
        target_state = self._apply_state_mappings(target_state, current_state, goal_parameters)
        
        self.logger.debug(f"Generated goal state for '{goal_name}': {target_state}")
        return target_state
    
    def _apply_state_mappings(self, target_state: Dict[str, Any], current_state: Dict[str, Any], 
                             parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply state mappings to resolve computed boolean flags in target state.
        
        This replaces complex template expressions and operators with simple boolean
        flags that are computed from the current state using the state_mappings configuration.
        
        Args:
            target_state: Target state with potential computed flags
            current_state: Current world state
            parameters: Goal parameters for dynamic values
            
        Returns:
            Target state with computed flags resolved to boolean values
        """
        def _resolve_nested_mappings(state_dict: Dict[str, Any], path_prefix: str = "") -> Dict[str, Any]:
            """Recursively resolve state mappings in nested dictionaries."""
            resolved_dict = {}
            
            for key, value in state_dict.items():
                current_path = f"{path_prefix}.{key}" if path_prefix else key
                
                if isinstance(value, dict):
                    # Recursive case for nested dictionaries
                    resolved_dict[key] = _resolve_nested_mappings(value, current_path)
                elif isinstance(value, bool):
                    # Simple boolean value - no mapping needed
                    resolved_dict[key] = value
                elif isinstance(value, (str, int, float)):
                    # Simple value - no mapping needed
                    resolved_dict[key] = value
                else:
                    # Check if this is a computed flag that needs mapping
                    mapping_path = f"{path_prefix}.{key}" if path_prefix else key
                    if self._is_computed_flag(mapping_path, current_state):
                        resolved_dict[key] = self._compute_flag_value(mapping_path, current_state, parameters)
                    else:
                        resolved_dict[key] = value
                        
            return resolved_dict
        
        return _resolve_nested_mappings(target_state)
    
    def _is_computed_flag(self, flag_path: str, current_state: Dict[str, Any]) -> bool:
        """Check if a flag path corresponds to a computed state mapping."""
        # Check if the flag exists in state_mappings
        parts = flag_path.split('.')
        mappings = self.state_mappings
        
        for part in parts[:-1]:
            if part in mappings:
                mappings = mappings[part]
            else:
                return False
                
        return parts[-1] in mappings
    
    def _compute_flag_value(self, flag_path: str, current_state: Dict[str, Any], 
                           parameters: Dict[str, Any]) -> bool:
        """Compute the boolean value for a mapped flag based on current state."""
        parts = flag_path.split('.')
        mappings = self.state_mappings
        
        # Navigate to the flag mapping
        for part in parts[:-1]:
            mappings = mappings[part]
        
        flag_mapping = mappings[parts[-1]]
        source_path = flag_mapping['source']
        condition = flag_mapping['condition']
        
        # Get the source value from current state
        source_value = self._get_nested_value(current_state, source_path)
        if source_value is None:
            return False
            
        # Apply parameter substitution to condition if needed
        if '{target_level}' in condition and 'target_level' in parameters:
            condition = condition.replace('{target_level}', str(parameters['target_level']))
        
        # Evaluate the condition
        return self._evaluate_condition(source_value, condition)
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get a value from nested dictionary using dot notation."""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
                
        return current
    
    def _evaluate_condition(self, value: Any, condition: str) -> bool:
        """Evaluate a simple condition against a value."""
        condition = condition.strip()
        
        if condition.startswith('< '):
            threshold = float(condition[2:])
            return float(value) < threshold
        elif condition.startswith('<= '):
            threshold = float(condition[3:])
            return float(value) <= threshold
        elif condition.startswith('>= '):
            threshold = float(condition[3:])
            return float(value) >= threshold
        elif condition.startswith('> '):
            threshold = float(condition[2:])
            return float(value) > threshold
        elif condition.startswith('== '):
            expected = condition[3:]
            if expected == 'true':
                return bool(value)
            elif expected == 'false':
                return not bool(value)
            elif expected == 'null':
                return value is None
            else:
                try:
                    return float(value) == float(expected)
                except ValueError:
                    return str(value) == expected
        elif condition.startswith('!= '):
            expected = condition[3:].strip()
            if expected == 'null':
                return value is not None
            else:
                try:
                    return float(value) != float(expected)
                except ValueError:
                    return str(value) != expected
        else:
            # Default: treat as equality check
            try:
                return float(value) == float(condition)
            except ValueError:
                return str(value) == condition
    
    def get_goal_strategy(self, goal_name: str, goal_config: Dict[str, Any]) -> Dict[str, Any]:
        """Get strategy configuration for a goal, merged with defaults."""
        strategy = goal_config.get('strategy', {}).copy()
        
        # Apply default thresholds
        strategy.setdefault('max_iterations', self.thresholds.get('max_goap_iterations', 10))
        strategy.setdefault('hunt_radius', self.thresholds.get('default_search_radius', 8))
        strategy.setdefault('safety_priority', True)
        
        return strategy
    
    
    def get_threshold(self, key: str, default: Any = None) -> Any:
        """Get a configuration threshold value."""
        return self.thresholds.get(key, default)
    
    def reload_configuration(self) -> None:
        """Reload goal configuration from YAML file."""
        self.config_data.load()
        self._load_configuration()
        self.logger.info("Goal manager configuration reloaded")
