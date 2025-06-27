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
from src.controller.state_engine import StateCalculationEngine


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
        
        # Initialize state calculation engine for computed states
        self.state_engine = StateCalculationEngine()
        
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
            
            # Skill levels for crafting viability checks
            'mining_level': char_data.get('mining_level', 1),
            'woodcutting_level': char_data.get('woodcutting_level', 1),
            'fishing_level': char_data.get('fishing_level', 1),
            'weaponcrafting_level': char_data.get('weaponcrafting_level', 1),
            'gearcrafting_level': char_data.get('gearcrafting_level', 1),
            'jewelrycrafting_level': char_data.get('jewelrycrafting_level', 1),
            'cooking_level': char_data.get('cooking_level', 1),
            'alchemy_level': char_data.get('alchemy_level', 1),
            
            # Default state flags (may be overridden by rules)
            'has_hunted_monsters': False,
            'monsters_available': False,
            'monster_present': False,
            'monster_defeated': False,  # Required by GOAP actions
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
            'equipment_equipped': False,  # Should be computed based on actual equipment
            'character_stats_improved': False,  # Should be computed based on equipment improvements
            'map_explored': False,
            'exploration_data_available': False,
            'equipment_analysis_available': False,
            'crafting_opportunities_known': False,
            'workshops_discovered': False,  # Required by crafting goals
            'has_crafting_materials': False,  # Required by crafting goals
            'materials_sufficient': False,  # Required by crafting goals
            'need_crafting_materials': current_level >= 2,  # Need materials for crafting at level 2+
            'recipe_known': False,  # Will be set by lookup_item_info action
            'resource_found': False,  # Will be set by find_resources action
            'has_better_weapon': False,  # Required by upgrade goals
            'has_better_armor': False,  # Required by upgrade goals
            'has_complete_equipment_set': False,  # Required by equipment goals
            'all_slots_equipped': False,  # Required by equipment goals
            'need_workshop_discovery': current_level >= 2,  # Need workshops at level 2+
            'need_combat': current_level < 40,  # Need combat XP until max level
            'need_equipment': current_level < 10,  # Need better equipment at low levels
            'need_resources': current_level < 15,  # Need resources for crafting
        }
        
        # Apply configuration-driven state calculation rules
        calculated_state = self._apply_state_calculation_rules(base_state)
        state.update(calculated_state)
        
        # Apply state engine computed states (preserve existing cooldown calculation)
        current_cooldown_state = state.get('is_on_cooldown')
        computed_state = self.state_engine.calculate_derived_state(state, self.thresholds)
        # Don't override existing cooldown calculation with state engine
        if 'is_on_cooldown' in computed_state and current_cooldown_state is not None:
            computed_state['is_on_cooldown'] = current_cooldown_state
        state.update(computed_state)
        
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
        
        Uses probabilistic selection for XP-gaining goals (combat and crafting) to ensure
        balanced progression between both activities.
        
        Args:
            current_state: Current world state
            available_goals: Optional list to restrict goal selection
            
        Returns:
            Tuple of (goal_name, goal_config) or None if no suitable goal found
        """
        if available_goals is None:
            available_goals = list(self.goal_templates.keys())
        
        # First check emergency and maintenance goals (non-probabilistic)
        emergency_goal = self._select_emergency_goal(current_state, available_goals)
        if emergency_goal:
            return emergency_goal
        
        # Then try probabilistic XP goal selection for balanced progression
        xp_goal = self._select_xp_goal_probabilistically(current_state, available_goals)
        if xp_goal:
            return xp_goal
        
        # Fallback to standard priority-based selection for other goals
        return self._select_standard_goal(current_state, available_goals)
    
    def _select_emergency_goal(self, current_state: Dict[str, Any], 
                              available_goals: List[str]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Select emergency and maintenance goals with highest priority."""
        emergency_categories = ['emergency', 'maintenance']
        
        for category_name in emergency_categories:
            if category_name not in self.goal_selection_rules:
                continue
                
            for rule in self.goal_selection_rules[category_name]:
                if self._check_goal_condition(rule.get('condition', {}), current_state):
                    goal_name = rule.get('goal')
                    if goal_name in available_goals:
                        goal_config = self.goal_templates.get(goal_name)
                        if goal_config:
                            priority = rule.get('priority', 0)
                            self.logger.info(f"🚨 Selected emergency goal '{goal_name}' (priority {priority}) "
                                           f"from category '{category_name}'")
                            return (goal_name, goal_config)
        return None
    
    def _select_xp_goal_probabilistically(self, current_state: Dict[str, Any], 
                                         available_goals: List[str]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select XP-gaining goals probabilistically based on GOAP weights.
        
        Balances combat and crafting activities unless limited by conditions:
        - Crafting skill advancement limited by current character level
        - No viable monsters available for combat
        """
        import random
        
        # Check if character is safe and can perform XP activities
        if not current_state.get('character_safe', False) or not current_state.get('character_alive', False):
            return None
        
        # Identify XP-gaining goals with their weights and viability
        xp_goals = []
        
        # Combat goals
        combat_goals = ['hunt_monsters']
        for goal_name in combat_goals:
            if goal_name in available_goals and self._is_combat_viable(current_state):
                # Balanced weight for equal probability with crafting
                weight = 2.5
                xp_goals.append((goal_name, weight, 'combat'))
        
        # Crafting goals - check each crafting skill
        crafting_skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy']
        viable_crafting_skills = []
        for skill in crafting_skills:
            if self._is_crafting_skill_viable(skill, current_state):
                viable_crafting_skills.append(skill)
        
        # Add crafting goals with weight adjusted for balance
        # Total crafting weight should equal combat weight for 50/50 balance
        if viable_crafting_skills:
            # Distribute weight evenly among viable crafting skills
            crafting_weight_per_skill = 2.5 / len(viable_crafting_skills)
            
            for skill in viable_crafting_skills:
                skill_goal_name = f"skill_{skill}_progression"
                xp_goals.append((skill_goal_name, crafting_weight_per_skill, 'crafting'))
        
        if not xp_goals:
            return None
        
        # Calculate total weight for probabilistic selection
        total_weight = sum(weight for _, weight, _ in xp_goals)
        
        # Weighted random selection
        random_value = random.uniform(0, total_weight)
        cumulative_weight = 0
        
        for goal_name, weight, goal_type in xp_goals:
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                # For crafting skills, use existing goal templates or create dynamic goal
                if goal_type == 'crafting':
                    # Use existing crafting-related goals from goal_templates
                    crafting_goal_mappings = {
                        'skill_weaponcrafting_progression': 'upgrade_weapon',
                        'skill_gearcrafting_progression': 'upgrade_armor', 
                        'skill_jewelrycrafting_progression': 'complete_equipment_set',
                        'skill_cooking_progression': 'gather_crafting_materials',
                        'skill_alchemy_progression': 'gather_crafting_materials'
                    }
                    mapped_goal = crafting_goal_mappings.get(goal_name, 'gather_crafting_materials')
                    goal_config = self.goal_templates.get(mapped_goal)
                    if goal_config:
                        self.logger.info(f"🎯 Probabilistically selected crafting goal '{mapped_goal}' "
                                       f"(weight {weight}, type {goal_type})")
                        return (mapped_goal, goal_config)
                else:
                    # Combat goal
                    goal_config = self.goal_templates.get(goal_name)
                    if goal_config:
                        self.logger.info(f"⚔️ Probabilistically selected combat goal '{goal_name}' "
                                       f"(weight {weight}, type {goal_type})")
                        return (goal_name, goal_config)
        
        return None
    
    def _is_combat_viable(self, current_state: Dict[str, Any]) -> bool:
        """Check if combat is viable based on character state and monster availability."""
        # Basic combat requirements
        if not current_state.get('can_attack', False):
            return False
        
        if current_state.get('is_on_cooldown', False):
            return False
        
        character_level = current_state.get('character_level', 1)
        if character_level < 1:  # Safety check
            return False
        
        # Enhanced viability check: look for viable monsters in knowledge base
        # If we have learned about monsters with poor success rates, combat may not be viable
        # This integrates with the knowledge base to make informed decisions
        
        # For now, combat is generally viable unless we have evidence it's not
        # The knowledge base contains combat results that can inform this decision
        
        # Future enhancement: Access knowledge base here to check:
        # - Are there any known monsters with reasonable success rates?
        # - Have we learned about monsters that are too dangerous?
        # - Do we need to upgrade equipment before combat becomes viable again?
        
        return True
    
    def _is_crafting_skill_viable(self, skill: str, current_state: Dict[str, Any]) -> bool:
        """
        Check if crafting skill advancement is viable.
        
        Crafting skills are limited by character level - can't advance crafting skills
        beyond current character level.
        """
        character_level = current_state.get('character_level', 1)
        
        # Get current skill level from character state
        skill_level_key = f'{skill}_level'
        current_skill_level = current_state.get(skill_level_key, 1)
        
        # Can't advance crafting skills beyond character level
        if current_skill_level >= character_level:
            return False
        
        # Check if we have basic requirements for crafting
        # For most crafting skills, we need to be at workshops and have materials
        # This is a simplified check - could be enhanced with more specific requirements
        
        return True
    
    def _select_standard_goal(self, current_state: Dict[str, Any], 
                             available_goals: List[str]) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Standard priority-based goal selection for non-XP goals."""
        best_goal = None
        best_priority = -1
        
        # Check progression and equipment categories
        standard_categories = ['progression', 'equipment', 'exploration']
        
        for category_name in standard_categories:
            if category_name not in self.goal_selection_rules:
                continue
                
            for rule in self.goal_selection_rules[category_name]:
                if self._check_goal_condition(rule.get('condition', {}), current_state):
                    goal_name = rule.get('goal')
                    priority = rule.get('priority', 0)
                    
                    if goal_name in available_goals and priority > best_priority:
                        goal_config = self.goal_templates.get(goal_name)
                        if goal_config:
                            best_goal = (goal_name, goal_config)
                            best_priority = priority
                            
                            # Log goal selection reasoning
                            self.logger.info(f"🎯 Selected standard goal '{goal_name}' (priority {priority}) "
                                           f"from category '{category_name}'")
                            break
            
            # If we found a goal in this category, use it
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