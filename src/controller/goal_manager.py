"""
GOAP Goal Manager

This module implements a configuration-driven goal management system that replaces
hardcoded goal logic with YAML-defined templates and state-driven goal selection.
"""

import logging
import random
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.controller.state_engine import StateCalculationEngine
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
            
            # Equipment slots for equipment status checks
            'weapon_slot': char_data.get('weapon_slot', ''),
            'helmet_slot': char_data.get('helmet_slot', ''),
            'body_armor_slot': char_data.get('body_armor_slot', ''),
            'leg_armor_slot': char_data.get('leg_armor_slot', ''),
            'boots_slot': char_data.get('boots_slot', ''),
            'shield_slot': char_data.get('shield_slot', ''),
            'ring1_slot': char_data.get('ring1_slot', ''),
            'ring2_slot': char_data.get('ring2_slot', ''),
            'amulet_slot': char_data.get('amulet_slot', ''),
            
            # Skill levels for crafting viability checks
            'mining_level': char_data.get('mining_level', 1),
            'woodcutting_level': char_data.get('woodcutting_level', 1),
            'fishing_level': char_data.get('fishing_level', 1),
            'weaponcrafting_level': char_data.get('weaponcrafting_level', 1),
            'gearcrafting_level': char_data.get('gearcrafting_level', 1),
            'jewelrycrafting_level': char_data.get('jewelrycrafting_level', 1),
            'cooking_level': char_data.get('cooking_level', 1),
            'alchemy_level': char_data.get('alchemy_level', 1),
            
            # Character inventory for material checks
            'character_inventory': char_data.get('inventory', []),
            'inventory': char_data.get('inventory', []),
            
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
            'equipment_info_unknown': True,  # Always start unknown to trigger lookup_item_info 
            'resource_location_known': False,
            'workshop_location_known': False,
            'equipment_info_known': False,  # Will be set by lookup_item_info action
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
            
            # Equipment analysis and slot selection states
            'equipment_gaps_analyzed': False,  # Will be set by AnalyzeEquipmentGapsAction
            'optimal_slot_selected': False,  # Will be set by SelectOptimalSlotAction
            'target_slot_specified': False,  # Will be set by SelectOptimalSlotAction
            'best_recipe_selected': False,  # Will be set by EvaluateRecipesAction
            'craftable_item_identified': False,  # Will be set by EvaluateRecipesAction
            'item_crafted': False,  # Will be set by crafting actions
            
            '_knowledge_base': knowledge_base,  # Store reference for computed state methods
        }
        
        # Apply configuration-driven state calculation rules
        calculated_state = self._apply_state_calculation_rules(base_state)
        state.update(calculated_state)
        
        # Apply state engine computed states (preserve critical base calculations)
        # Preserve existing critical state calculations that should not be overridden
        critical_states = {
            'is_on_cooldown': state.get('is_on_cooldown'),
            'character_alive': state.get('character_alive'),
            'character_safe': state.get('character_safe'),
            'needs_rest': state.get('needs_rest'),
            'can_attack': state.get('can_attack'),
            'can_move': state.get('can_move'),
            'need_equipment': state.get('need_equipment'),
            'need_combat': state.get('need_combat'),
            'hp_percentage': state.get('hp_percentage'),
            'character_level': state.get('character_level'),
            'character_hp': state.get('character_hp'),
            'character_max_hp': state.get('character_max_hp')
        }
        
        computed_state = self.state_engine.calculate_derived_state(state, self.thresholds)
        
        # Don't override critical base calculations if they were already computed correctly
        for key, value in critical_states.items():
            if key in computed_state and value is not None:
                computed_state[key] = value
                
        state.update(computed_state)
        
        # Debug: Log critical state values for get_to_safety goal
        self.logger.debug(f"🩺 HP state: hp={current_hp}/{max_hp} ({hp_percentage:.1f}%), needs_rest={state.get('needs_rest')}, character_safe={state.get('character_safe')}, is_on_cooldown={state.get('is_on_cooldown')}")
        
        # Debug: Log equipment and computed state values 
        equipment_states = {k: v for k, v in state.items() if 'armor' in k or 'weapon' in k or 'equipment' in k}
        if equipment_states:
            self.logger.debug(f"🔧 Equipment states: {equipment_states}")
        
        # Debug: Log key computed states from state engine
        computed_states = {k: v for k, v in state.items() if k in [
            'has_raw_materials', 'has_refined_materials', 'at_correct_workshop',
            'workshops_discovered', 'has_crafting_materials', 'materials_sufficient',
            'best_weapon_selected', 'craftable_weapon_identified', 'material_requirements_known',
            'need_workshop_discovery', 'need_specific_workshop', 'at_workshop', 'combat_not_viable'
        ]}
        if computed_states:
            self.logger.debug(f"🔧 Computed states: {computed_states}")
        
        return state
    
    def _compute_state_method(self, method_name: str, state: Dict[str, Any]) -> bool:
        """Compute state values using specific methods."""
        try:
            if method_name == 'check_armor_improved':
                # For now, always return False since we don't have armor comparison logic
                return False
            elif method_name == 'check_weapon_improved':
                # For now, always return False since we don't have weapon comparison logic  
                return False
            elif method_name == 'check_equipment_set_complete':
                # Check if all major equipment slots are filled
                # This would need character data to check actual slots
                return False
            elif method_name == 'check_workshops_known':
                # For now, assume workshops are not discovered initially
                return False
            elif method_name == 'check_at_workshop':
                # Would need to check if current location is a workshop
                return False
            elif method_name == 'check_at_resource_location':
                # Would need to check if current location has resources
                return False
            elif method_name == 'check_required_materials':
                # Would need to check inventory for required materials
                return False
            elif method_name == 'check_weapon_upgrade_needed':
                # For low-level characters, always need weapon upgrades
                character_level = state.get('character_level', 1)
                return character_level < 5
            elif method_name == 'check_armor_upgrade_needed':
                # For low-level characters, always need armor upgrades
                character_level = state.get('character_level', 1)
                return character_level < 5
            elif method_name == 'check_complete_equipment_needed':
                # For characters below level 3, need complete equipment
                character_level = state.get('character_level', 1)
                return character_level < 3
            elif method_name == 'check_workshop_discovery_needed':
                # Need workshop discovery at level 2+
                character_level = state.get('character_level', 1)
                return character_level >= 2
            elif method_name == 'check_combat_viability':
                # Delegate to state engine which has the weighted calculation
                try:
                    config = {'type': 'computed', 'method': method_name}
                    result = self.state_engine._dispatch_computed_method(method_name, config, state, self.thresholds)
                    return result
                except Exception as e:
                    self.logger.warning(f"Error delegating combat viability check to state engine: {e}")
                    return False  # Assume combat is viable if error
            else:
                # Delegate to state engine for all computed state methods
                try:
                    config = {'type': 'computed', 'method': method_name}
                    result = self.state_engine._dispatch_computed_method(method_name, config, state, self.thresholds)
                    return result
                except Exception as e:
                    self.logger.warning(f"Error delegating to state engine for '{method_name}': {e}")
                    return False
                
        except Exception as e:
            self.logger.warning(f"Error computing state method '{method_name}': {e}")
            return False
    
    def _apply_state_calculation_rules(self, base_state: Dict[str, Any]) -> Dict[str, Any]:
        """Apply YAML-defined state calculation rules to compute derived state."""
        calculated_state = base_state.copy()
        
        # Apply each state calculation rule
        for state_key, rule_config in self.state_calculation_rules.items():
            try:
                if isinstance(rule_config, dict):
                    if rule_config.get('type') == 'computed':
                        # Special computed values (like cooldown checking)
                        method_name = rule_config.get('method')
                        if method_name == 'check_cooldown_expiration':
                            # Already computed in base_state as 'is_on_cooldown'
                            continue
                        else:
                            # Try to compute the state using the specified method
                            computed_value = self._compute_state_method(method_name, calculated_state)
                            calculated_state[state_key] = computed_value
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
                                self.logger.info(f"🎯 Applied persistence bonus to safety goal '{goal_name}': "
                                               f"{priority} + {persistence_bonus:.2f} = {weighted_priority:.2f}")
                            else:
                                weighted_priority = priority
                            
                            if weighted_priority > best_priority:
                                best_goal = (goal_name, goal_config)
                                best_priority = weighted_priority
                                self.logger.info(f"🛡️ Selected safety goal '{goal_name}' (priority {weighted_priority:.2f}) "
                                               f"from category '{category_name}'")
        return best_goal
    
    def _select_xp_goal_hierarchical(self, current_state: Dict[str, Any], 
                                    available_goals: List[str],
                                    goal_weights: Dict[str, float] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Select XP-gaining goals with hierarchical combat vs crafting balance.
        
        Combat XP is weighted slightly higher than crafting XP as requested.
        
        Args:
            current_state: Current world state
            available_goals: List of goals to consider
            goal_weights: Optional persistence weight bonuses
            
        Returns:
            XP-gaining goal or None
        """
        # Check if character is safe for XP activities
        if not current_state.get('character_safe', False) or not current_state.get('character_alive', False):
            return None
        
        xp_goals = []
        
        # Combat XP goals (weighted higher as requested)
        if self._is_combat_viable(current_state):
            combat_weight = 3.0  # Higher weight for combat as requested
            persistence_bonus = goal_weights.get('hunt_monsters', 0.0) if goal_weights else 0.0
            total_weight = combat_weight + persistence_bonus
            
            if 'hunt_monsters' in available_goals and self.goal_templates.get('hunt_monsters'):
                xp_goals.append({
                    'goal_name': 'hunt_monsters',
                    'goal_config': self.goal_templates['hunt_monsters'],
                    'weight': total_weight,
                    'type': 'combat'
                })
                
                if persistence_bonus > 0:
                    self.logger.info(f"🎯 Applied persistence bonus to combat: "
                                   f"{combat_weight} + {persistence_bonus:.2f} = {total_weight:.2f}")
        
        # Crafting XP goals (all crafting skills with lower base weight)
        crafting_skills = ['weaponcrafting', 'gearcrafting', 'jewelrycrafting', 'cooking', 'alchemy']
        crafting_goals = ['upgrade_weapon', 'upgrade_armor', 'complete_equipment_set', 'craft_selected_weapon']
        
        for goal_name in crafting_goals:
            if goal_name in available_goals and self._is_crafting_goal_viable(goal_name, current_state):
                goal_config = self.goal_templates.get(goal_name)
                if goal_config:
                    crafting_weight = 2.0  # Lower than combat (3.0)
                    persistence_bonus = goal_weights.get(goal_name, 0.0) if goal_weights else 0.0
                    total_weight = crafting_weight + persistence_bonus
                    
                    xp_goals.append({
                        'goal_name': goal_name,
                        'goal_config': goal_config,
                        'weight': total_weight,
                        'type': 'crafting'
                    })
                    
                    if persistence_bonus > 0:
                        self.logger.info(f"🎯 Applied persistence bonus to crafting '{goal_name}': "
                                       f"{crafting_weight} + {persistence_bonus:.2f} = {total_weight:.2f}")
        
        if not xp_goals:
            return None
        
        # Weighted random selection
        total_weight = sum(goal['weight'] for goal in xp_goals)
        random_value = random.uniform(0, total_weight)
        
        cumulative_weight = 0
        for goal in xp_goals:
            cumulative_weight += goal['weight']
            if random_value <= cumulative_weight:
                self.logger.info(f"⚡ Selected XP goal '{goal['goal_name']}' "
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
                                self.logger.info(f"🎯 Applied persistence bonus to support goal '{goal_name}': "
                                               f"{priority} + {persistence_bonus:.2f} = {weighted_priority:.2f}")
                            else:
                                weighted_priority = priority
                            
                            if weighted_priority > best_priority:
                                best_goal = (goal_name, goal_config)
                                best_priority = weighted_priority
                                self.logger.info(f"🔧 Selected support goal '{goal_name}' (priority {weighted_priority:.2f}) "
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
        character_level = current_state.get('character_level', 1)
        
        # Basic viability check
        if character_level < 2:  # Need level 2+ for most crafting
            return False
        
        # Specific goal checks
        if goal_name == 'craft_selected_weapon':
            return current_state.get('best_weapon_selected', False) and not current_state.get('weapon_crafted', True)
        
        return True
    
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
        
        # Check if combat is explicitly marked as not viable
        if current_state.get('combat_not_viable', False):
            return False
        
        return True
    
    def _check_goal_condition(self, condition: Dict[str, Any], state: Dict[str, Any]) -> bool:
        """Check if a goal selection condition is met by current state."""
        try:
            for key, expected_value in condition.items():
                actual_value = state.get(key)
                
                if isinstance(expected_value, str) and expected_value.startswith('<='):
                    # Handle numeric comparisons like "<=15"
                    threshold = float(expected_value[2:])
                    if actual_value is None or actual_value > threshold:
                        return False
                elif isinstance(expected_value, str) and expected_value.startswith('>='):
                    # Handle numeric comparisons like ">=10"  
                    threshold = float(expected_value[2:])
                    if actual_value is None or actual_value < threshold:
                        return False
                elif isinstance(expected_value, str) and expected_value.startswith('<'):
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
        strategy.setdefault('hunt_radius', self.thresholds.get('default_search_radius', 8))
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