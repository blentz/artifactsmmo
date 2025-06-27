"""
GOAP State Calculation Engine

This module provides a metaprogramming-based state calculation system that replaces
hardcoded if-elif blocks with YAML-driven state computation and response handling.
"""

import logging
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timezone

from src.lib.yaml_data import YamlData
from src.game.globals import DATA_PREFIX


class StateCalculationEngine:
    """
    Metaprogramming-based state calculation and response handling system.
    
    Replaces hardcoded state computation and response processing with
    configurable rules and dynamic dispatch.
    """
    
    def __init__(self, config_file: str = None):
        """Initialize state calculation engine."""
        self.logger = logging.getLogger(__name__)
        
        # Load state calculation configuration
        if config_file is None:
            config_file = f"{DATA_PREFIX}/state_engine.yaml"
        
        self.config_data = YamlData(config_file)
        self._load_configuration()
        
        # Response handler registry
        self.response_handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
        
    def _load_configuration(self) -> None:
        """Load state calculation rules and response handlers from configuration."""
        try:
            self.state_rules = self.config_data.data.get('state_calculation', {})
            self.response_rules = self.config_data.data.get('response_handlers', {})
            self.update_rules = self.config_data.data.get('world_state_updates', {})
            self.computed_states = self.config_data.data.get('computed_states', {})
            
            self.logger.info(f"Loaded {len(self.state_rules)} state calculation rules")
            self.logger.info(f"Loaded {len(self.response_rules)} response handler rules")
            
        except Exception as e:
            self.logger.error(f"Failed to load state engine configuration: {e}")
            # Initialize with empty configs as fallback
            self.state_rules = {}
            self.response_rules = {}
            self.update_rules = {}
            self.computed_states = {}
    
    def calculate_derived_state(self, base_state: Dict[str, Any], 
                              thresholds: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Calculate derived state values using configuration rules.
        
        Replaces hardcoded state computation in get_current_world_state().
        
        Args:
            base_state: Base state values from character/game data
            thresholds: Configuration thresholds for calculations
            
        Returns:
            Dictionary with derived state values added
        """
        if thresholds is None:
            thresholds = {}
            
        derived_state = base_state.copy()
        
        # Apply state calculation rules
        for state_key, rule_config in self.state_rules.items():
            try:
                value = self._evaluate_state_rule(rule_config, derived_state, thresholds)
                derived_state[state_key] = value
                
            except Exception as e:
                self.logger.warning(f"Failed to calculate derived state '{state_key}': {e}")
                derived_state[state_key] = False  # Safe default
                
        # Apply computed state rules (more complex calculations)
        for state_key, computation_config in self.computed_states.items():
            try:
                value = self._compute_complex_state(computation_config, derived_state, thresholds)
                derived_state[state_key] = value
                
            except Exception as e:
                self.logger.warning(f"Failed to compute complex state '{state_key}': {e}")
                
        return derived_state
    
    def _evaluate_state_rule(self, rule_config: Any, state: Dict[str, Any], 
                           thresholds: Dict[str, Any]) -> Any:
        """Evaluate a single state calculation rule."""
        if isinstance(rule_config, dict):
            if 'formula' in rule_config:
                return self._evaluate_formula(rule_config['formula'], state, thresholds)
            elif 'condition' in rule_config:
                return self._evaluate_condition(rule_config['condition'], state, thresholds)
            elif 'computation' in rule_config:
                return self._perform_computation(rule_config['computation'], state, thresholds)
        elif isinstance(rule_config, str):
            # Simple formula or reference
            if rule_config.startswith('${') and rule_config.endswith('}'):
                # Variable reference
                var_name = rule_config[2:-1]
                return state.get(var_name) or thresholds.get(var_name)
            else:
                # Formula
                return self._evaluate_formula(rule_config, state, thresholds)
        else:
            # Literal value
            return rule_config
    
    def _evaluate_formula(self, formula: str, state: Dict[str, Any], 
                        thresholds: Dict[str, Any]) -> bool:
        """Evaluate a formula string with variable substitution."""
        try:
            # Substitute variables
            evaluated_formula = formula
            
            # Substitute threshold references
            for key, value in thresholds.items():
                placeholder = f"${{thresholds.{key}}}"
                if placeholder in evaluated_formula:
                    evaluated_formula = evaluated_formula.replace(placeholder, str(value))
            
            # Substitute state references
            for key, value in state.items():
                if f"{key}" in evaluated_formula and isinstance(value, (int, float, bool)):
                    # Replace whole word matches to avoid partial replacements
                    import re
                    pattern = r'\b' + re.escape(key) + r'\b'
                    evaluated_formula = re.sub(pattern, str(value), evaluated_formula)
            
            # Handle boolean logic
            if ' and ' in evaluated_formula:
                parts = evaluated_formula.split(' and ')
                return all(self._evaluate_simple_expression(part.strip(), state) for part in parts)
            elif ' or ' in evaluated_formula:
                parts = evaluated_formula.split(' or ')
                return any(self._evaluate_simple_expression(part.strip(), state) for part in parts)
            else:
                return self._evaluate_simple_expression(evaluated_formula, state)
                
        except Exception as e:
            self.logger.warning(f"Formula evaluation failed for '{formula}': {e}")
            return False
    
    def _evaluate_simple_expression(self, expression: str, state: Dict[str, Any]) -> bool:
        """Evaluate a simple comparison expression."""
        try:
            # Handle negation
            if expression.startswith('not '):
                inner_expr = expression[4:].strip()
                return not self._evaluate_simple_expression(inner_expr, state)
            
            # Handle comparisons
            for op in ['>=', '<=', '>', '<', '==', '!=']:
                if op in expression:
                    left, right = expression.split(op, 1)
                    left_val = self._resolve_value(left.strip(), state)
                    right_val = self._resolve_value(right.strip(), state)
                    
                    if op == '>=':
                        return left_val >= right_val
                    elif op == '<=':
                        return left_val <= right_val
                    elif op == '>':
                        return left_val > right_val
                    elif op == '<':
                        return left_val < right_val
                    elif op == '==':
                        return left_val == right_val
                    elif op == '!=':
                        return left_val != right_val
            
            # Simple boolean reference
            return bool(self._resolve_value(expression, state))
            
        except Exception as e:
            self.logger.warning(f"Expression evaluation failed for '{expression}': {e}")
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
    
    def _compute_complex_state(self, computation_config: Dict[str, Any], 
                             state: Dict[str, Any], thresholds: Dict[str, Any]) -> Any:
        """Perform complex state computation using configuration."""
        computation_type = computation_config.get('type', 'formula')
        
        if computation_type == 'cooldown_check':
            return self._compute_cooldown_status(state)
        elif computation_type == 'location_distance':
            return self._compute_distance(computation_config, state)
        elif computation_type == 'aggregation':
            return self._compute_aggregation(computation_config, state)
        elif computation_type == 'equipment_analysis':
            return self._compute_equipment_analysis(computation_config, state, thresholds)
        elif computation_type == 'equipment_check':
            return self._compute_equipment_check(computation_config, state, thresholds)
        elif computation_type == 'crafting_analysis':
            return self._compute_crafting_analysis(computation_config, state, thresholds)
        elif computation_type == 'workshop_analysis':
            return self._compute_workshop_analysis(computation_config, state, thresholds)
        elif computation_type == 'inventory_check':
            return self._compute_inventory_check(computation_config, state, thresholds)
        elif computation_type == 'knowledge_check':
            return self._compute_knowledge_check(computation_config, state, thresholds)
        elif computation_type == 'location_check':
            return self._compute_location_check(computation_config, state, thresholds)
        elif computation_type == 'computed':
            # Method dispatch for computed states
            method_name = computation_config.get('method')
            if method_name:
                return self._dispatch_computed_method(method_name, computation_config, state, thresholds)
        else:
            # Default to formula evaluation
            formula = computation_config.get('formula', 'false')
            return self._evaluate_formula(formula, state, thresholds)
    
    def _compute_cooldown_status(self, state: Dict[str, Any]) -> bool:
        """Compute cooldown status from character data."""
        cooldown_seconds = state.get('character_cooldown', 0)
        cooldown_expiration = state.get('character_cooldown_expiration')
        
        if cooldown_seconds <= 0 or not cooldown_expiration:
            return False
            
        try:
            if isinstance(cooldown_expiration, str):
                cooldown_end = datetime.fromisoformat(cooldown_expiration.replace('Z', '+00:00'))
            else:
                cooldown_end = cooldown_expiration
                
            current_time = datetime.now(timezone.utc)
            return current_time < cooldown_end
            
        except Exception as e:
            self.logger.warning(f"Error computing cooldown status: {e}")
            return cooldown_seconds > 0
    
    def _compute_equipment_analysis(self, config: Dict[str, Any], 
                                  state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Compute equipment upgrade analysis based on character stats and level."""
        try:
            analysis_type = config.get('analysis_type', 'general')
            character_level = state.get('character_level', 1)
            
            if analysis_type == 'weapon_upgrade':
                return self._analyze_weapon_upgrade_need(state, thresholds)
            elif analysis_type == 'armor_upgrade':
                return self._analyze_armor_upgrade_need(state, thresholds)
            elif analysis_type == 'complete_equipment':
                return self._analyze_complete_equipment_need(state, thresholds)
            else:
                # General equipment upgrade check
                min_level = thresholds.get('equipment_level_threshold', 3)
                return character_level >= min_level
                
        except Exception as e:
            self.logger.warning(f"Equipment analysis failed: {e}")
            return False
    
    def _analyze_weapon_upgrade_need(self, state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Analyze if character needs a weapon upgrade."""
        try:
            character_level = state.get('character_level', 1)
            min_level = thresholds.get('weapon_upgrade_level_threshold', 2)
            
            if character_level < min_level:
                return False
                
            # Check current weapon level vs character level
            weapon_slot = state.get('weapon_slot', 'wooden_stick')
            level_diff_threshold = thresholds.get('equipment_level_difference', 3)
            
            # Basic heuristic: if character is level 2+, they likely need better weapons
            # This would be enhanced with actual weapon level data in a real implementation
            if weapon_slot in ['wooden_stick', '', None]:
                return character_level >= 2
            
            # For now, use level-based heuristic
            return character_level >= min_level
            
        except Exception as e:
            self.logger.warning(f"Weapon upgrade analysis failed: {e}")
            return False
    
    def _analyze_armor_upgrade_need(self, state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Analyze if character needs armor upgrades."""
        try:
            character_level = state.get('character_level', 1)
            min_level = thresholds.get('armor_upgrade_level_threshold', 2)
            
            if character_level < min_level:
                return False
                
            # Check if character has basic armor equipped
            armor_slots = ['helmet_slot', 'body_armor_slot', 'leg_armor_slot', 'boots_slot']
            equipped_armor = 0
            
            for slot in armor_slots:
                if state.get(slot, '') not in ['', None]:
                    equipped_armor += 1
            
            # Need armor if less than 2 pieces equipped at level 2+
            min_armor_pieces = thresholds.get('min_equipment_slots', 2)
            return equipped_armor < min_armor_pieces and character_level >= min_level
            
        except Exception as e:
            self.logger.warning(f"Armor upgrade analysis failed: {e}")
            return False
    
    def _analyze_complete_equipment_need(self, state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Analyze if character needs a complete equipment set."""
        try:
            character_level = state.get('character_level', 1)
            min_level = 3  # Complete equipment sets for level 3+
            
            if character_level < min_level:
                return False
                
            # Count equipped slots
            equipment_slots = ['weapon_slot', 'helmet_slot', 'body_armor_slot', 'leg_armor_slot', 'boots_slot']
            equipped_count = 0
            
            for slot in equipment_slots:
                if state.get(slot, '') not in ['', None]:
                    equipped_count += 1
            
            # Need complete set if less than 80% equipped
            min_coverage = thresholds.get('min_equipment_slots', 4)
            return equipped_count < min_coverage
            
        except Exception as e:
            self.logger.warning(f"Complete equipment analysis failed: {e}")
            return False
    
    def _compute_equipment_check(self, config: Dict[str, Any], 
                               state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Check equipment status and improvements."""
        try:
            check_type = config.get('check_type', 'general')
            
            if check_type == 'weapon_improved':
                # Check if weapon has been upgraded recently
                return state.get('equipment_equipped', False)
            elif check_type == 'armor_improved':
                # Check if armor has been upgraded recently
                return state.get('equipment_equipped', False)
            elif check_type == 'set_complete':
                # Check if equipment set is complete
                equipment_slots = ['weapon_slot', 'helmet_slot', 'body_armor_slot', 'leg_armor_slot', 'boots_slot']
                equipped_count = sum(1 for slot in equipment_slots if state.get(slot, '') not in ['', None])
                return equipped_count >= 4  # 80% coverage
            else:
                return state.get('equipment_equipped', False)
                
        except Exception as e:
            self.logger.warning(f"Equipment check failed: {e}")
            return False
    
    def _compute_crafting_analysis(self, config: Dict[str, Any], 
                                 state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Analyze crafting material needs."""
        try:
            analysis_type = config.get('analysis_type', 'materials_needed')
            character_level = state.get('character_level', 1)
            
            if analysis_type == 'materials_needed':
                # Check if character needs to gather materials for crafting
                # This would be enhanced with actual inventory analysis
                return character_level >= 2 and not state.get('has_crafting_materials', False)
            else:
                return False
                
        except Exception as e:
            self.logger.warning(f"Crafting analysis failed: {e}")
            return False
    
    def _compute_workshop_analysis(self, config: Dict[str, Any], 
                                 state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Analyze workshop discovery needs."""
        try:
            analysis_type = config.get('analysis_type', 'discovery_needed')
            character_level = state.get('character_level', 1)
            
            if analysis_type == 'discovery_needed':
                # Need workshop discovery if level 2+ and workshops not discovered
                return character_level >= 2 and not state.get('workshops_discovered', False)
            else:
                return False
                
        except Exception as e:
            self.logger.warning(f"Workshop analysis failed: {e}")
            return False
    
    def _compute_inventory_check(self, config: Dict[str, Any], 
                               state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Check inventory status for materials and items."""
        try:
            check_type = config.get('check_type', 'general')
            
            if check_type == 'materials_available':
                # Check if character has crafting materials
                return state.get('has_resources', False) or state.get('inventory_updated', False)
            elif check_type == 'required_materials':
                # Check if character has required materials for crafting
                return state.get('has_resources', False)
            elif check_type == 'sufficient_quantity':
                # Check if materials are sufficient for crafting
                return state.get('has_resources', False)
            else:
                return state.get('inventory_updated', False)
                
        except Exception as e:
            self.logger.warning(f"Inventory check failed: {e}")
            return False
    
    def _compute_knowledge_check(self, config: Dict[str, Any], 
                               state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Check knowledge base for discovered information."""
        try:
            check_type = config.get('check_type', 'general')
            
            if check_type == 'workshops_known':
                # Check if workshops have been discovered and recorded
                return state.get('crafting_opportunities_known', False)
            else:
                return state.get('map_explored', False)
                
        except Exception as e:
            self.logger.warning(f"Knowledge check failed: {e}")
            return False
    
    def _compute_location_check(self, config: Dict[str, Any], 
                              state: Dict[str, Any], thresholds: Dict[str, Any]) -> bool:
        """Check character location relative to objectives."""
        try:
            check_type = config.get('check_type', 'general')
            
            if check_type == 'workshop_location':
                # Check if character is at a workshop
                # This would be enhanced with actual map content checking
                return state.get('at_target_location', False)
            elif check_type == 'resource_location':
                # Check if character is at a resource location
                return state.get('at_target_location', False)
            else:
                return state.get('at_target_location', False)
                
        except Exception as e:
            self.logger.warning(f"Location check failed: {e}")
            return False
    
    def process_action_response(self, action_name: str, response: Any, 
                              current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process action response using configuration-driven handlers.
        
        Replaces the hardcoded update_world_state_from_response() method.
        
        Args:
            action_name: Name of the executed action
            response: Action response object
            current_state: Current world state
            
        Returns:
            Dictionary of state updates to apply
        """
        state_updates = {}
        
        # Get response handler configuration for this action
        handler_config = self.response_rules.get(action_name, {})
        
        if not handler_config:
            self.logger.debug(f"No response handler configured for action '{action_name}'")
            return state_updates
        
        try:
            # Apply configured response processing rules
            for update_key, update_rule in handler_config.items():
                update_value = self._process_response_rule(update_rule, response, current_state)
                if update_value is not None:
                    state_updates[update_key] = update_value
                    
            self.logger.debug(f"Processed response for '{action_name}': {state_updates}")
            
        except Exception as e:
            self.logger.warning(f"Failed to process response for '{action_name}': {e}")
            
        return state_updates
    
    def _process_response_rule(self, rule_config: Any, response: Any, 
                             current_state: Dict[str, Any]) -> Any:
        """Process a single response rule."""
        if isinstance(rule_config, dict):
            rule_type = rule_config.get('type', 'static')
            
            if rule_type == 'static':
                return rule_config.get('value')
            elif rule_type == 'response_field':
                field_path = rule_config.get('field')
                return self._extract_response_field(response, field_path)
            elif rule_type == 'conditional':
                condition = rule_config.get('condition', {})
                if self._check_response_condition(condition, response, current_state):
                    return rule_config.get('true_value')
                else:
                    return rule_config.get('false_value')
            elif rule_type == 'computation':
                return self._compute_response_value(rule_config, response, current_state)
        else:
            # Simple static value
            return rule_config
    
    def _compute_response_value(self, rule_config: Dict[str, Any], response: Any, 
                              current_state: Dict[str, Any]) -> Any:
        """Compute a response value using configuration rules."""
        try:
            computation_type = rule_config.get('computation_type', 'field_extraction')
            
            if computation_type == 'field_extraction':
                # Extract field from response with optional transformation
                field_path = rule_config.get('field')
                value = self._extract_response_field(response, field_path)
                
                # Apply transformation if specified
                transform = rule_config.get('transform')
                if transform and value is not None:
                    if transform == 'boolean':
                        return bool(value)
                    elif transform == 'string':
                        return str(value)
                    elif transform == 'int':
                        return int(value) if value else 0
                    elif transform == 'float':
                        return float(value) if value else 0.0
                
                return value
                
            elif computation_type == 'formula':
                # Use formula evaluation
                formula = rule_config.get('formula', 'false')
                # Create extended state with response fields
                extended_state = current_state.copy()
                if hasattr(response, 'data'):
                    extended_state['response_success'] = True
                else:
                    extended_state['response_success'] = False
                
                return self._evaluate_formula(formula, extended_state, {})
                
            elif computation_type == 'conditional':
                # Conditional computation
                condition = rule_config.get('condition', {})
                if self._check_response_condition(condition, response, current_state):
                    return rule_config.get('true_value')
                else:
                    return rule_config.get('false_value')
            
            else:
                self.logger.warning(f"Unknown computation type: {computation_type}")
                return None
                
        except Exception as e:
            self.logger.warning(f"Response value computation failed: {e}")
            return None
    
    def _extract_response_field(self, response: Any, field_path: str) -> Any:
        """Extract a field from response using dot notation path."""
        try:
            value = response
            for field in field_path.split('.'):
                if hasattr(value, field):
                    value = getattr(value, field)
                elif isinstance(value, dict):
                    value = value.get(field)
                else:
                    return None
            return value
        except Exception:
            return None
    
    def _check_response_condition(self, condition: Dict[str, Any], response: Any, 
                                current_state: Dict[str, Any]) -> bool:
        """Check if a response condition is met."""
        try:
            condition_type = condition.get('type', 'response_field')
            
            if condition_type == 'response_field':
                field_path = condition.get('field')
                expected_value = condition.get('value')
                actual_value = self._extract_response_field(response, field_path)
                return actual_value == expected_value
            elif condition_type == 'state_check':
                state_key = condition.get('state_key')
                expected_value = condition.get('value')
                return current_state.get(state_key) == expected_value
                
            return False
            
        except Exception as e:
            self.logger.warning(f"Response condition check failed: {e}")
            return False
    
    def register_response_handler(self, action_name: str, handler: Callable) -> None:
        """Register a custom response handler for an action."""
        self.response_handlers[action_name] = handler
        self.logger.info(f"Registered custom response handler for '{action_name}'")
    
    def _register_default_handlers(self) -> None:
        """Register default response handlers for common actions."""
        # Move action handler
        def handle_move_response(response, current_state):
            updates = {}
            if hasattr(response, 'data') and hasattr(response.data, 'character'):
                char = response.data.character
                updates['character_x'] = getattr(char, 'x', current_state.get('character_x', 0))
                updates['character_y'] = getattr(char, 'y', current_state.get('character_y', 0))
                updates['at_target_location'] = True
            return updates
        
        # Combat action handler
        def handle_attack_response(response, current_state):
            updates = {'monster_present': False}
            if hasattr(response, 'data') and hasattr(response.data, 'fight'):
                fight = response.data.fight
                if hasattr(fight, 'result') and fight.result in ['win', 'loss']:
                    updates['has_hunted_monsters'] = True
                    if fight.result == 'win':
                        updates['monster_defeated'] = True
            return updates
        
        self.response_handlers['move'] = handle_move_response
        self.response_handlers['attack'] = handle_attack_response
    
    def _dispatch_computed_method(self, method_name: str, config: Dict[str, Any], 
                                  state: Dict[str, Any], thresholds: Dict[str, Any]) -> Any:
        """Dispatch to specific computed state method."""
        if method_name == 'check_combat_viability':
            return self._check_combat_viability(config, state, thresholds)
        elif method_name == 'check_weapon_upgrade_needed':
            return self._check_weapon_upgrade_needed(config, state, thresholds)
        elif method_name == 'check_armor_upgrade_needed':
            return self._check_armor_upgrade_needed(config, state, thresholds)
        elif method_name == 'check_complete_equipment_needed':
            return self._check_complete_equipment_needed(config, state, thresholds)
        elif method_name == 'check_crafting_materials_needed':
            return self._check_crafting_materials_needed(config, state, thresholds)
        elif method_name == 'check_workshop_discovery_needed':
            return self._check_workshop_discovery_needed(config, state, thresholds)
        else:
            self.logger.warning(f"Unknown computed method: {method_name}")
            return False
    
    def _check_combat_viability(self, config: Dict[str, Any], state: Dict[str, Any], 
                               thresholds: Dict[str, Any]) -> bool:
        """
        Check if combat is viable based on monster win rates in the area.
        Returns True if combat is NOT viable (poor win rates).
        """
        try:
            # Get knowledge base and character location from state
            knowledge_base = state.get('knowledge_base')
            character_x = state.get('character_x', 0)
            character_y = state.get('character_y', 0)
            
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                # No knowledge base available, assume combat is viable
                return False
            
            # Check nearby monsters for win rates
            monsters_data = knowledge_base.data.get('monsters', {})
            poor_win_rate_count = 0
            total_nearby_monsters = 0
            
            # Check monsters within a small radius (2-3 tiles)
            search_radius = 3
            for monster_code, monster_data in monsters_data.items():
                locations = monster_data.get('locations', [])
                
                for location in locations:
                    loc_x = location.get('x', 0)
                    loc_y = location.get('y', 0)
                    
                    # Check if monster is nearby
                    distance = ((loc_x - character_x) ** 2 + (loc_y - character_y) ** 2) ** 0.5
                    if distance <= search_radius:
                        total_nearby_monsters += 1
                        
                        # Check win rate
                        combat_results = monster_data.get('combat_results', [])
                        if len(combat_results) >= 3:  # Only check if sufficient data
                            wins = sum(1 for result in combat_results if result.get('result') == 'win')
                            win_rate = wins / len(combat_results)
                            
                            # Consider win rate poor if < 20%
                            if win_rate < 0.2:
                                poor_win_rate_count += 1
            
            # Combat is not viable if:
            # 1. We have at least 2 nearby monsters with data
            # 2. More than 50% of them have poor win rates
            if total_nearby_monsters >= 2 and poor_win_rate_count >= (total_nearby_monsters * 0.5):
                self.logger.warning(f"🚫 Combat not viable: {poor_win_rate_count}/{total_nearby_monsters} "
                                  f"nearby monsters have poor win rates")
                return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"Error checking combat viability: {e}")
            return False
    
    def _check_weapon_upgrade_needed(self, config: Dict[str, Any], state: Dict[str, Any], 
                                   thresholds: Dict[str, Any]) -> bool:
        """Check if weapon upgrade is needed."""
        # Placeholder implementation - can be expanded
        return state.get('character_level', 1) >= 2
    
    def _check_armor_upgrade_needed(self, config: Dict[str, Any], state: Dict[str, Any], 
                                  thresholds: Dict[str, Any]) -> bool:
        """Check if armor upgrade is needed."""
        # Placeholder implementation - can be expanded
        return state.get('character_level', 1) >= 3
    
    def _check_complete_equipment_needed(self, config: Dict[str, Any], state: Dict[str, Any], 
                                       thresholds: Dict[str, Any]) -> bool:
        """Check if complete equipment set is needed."""
        # Placeholder implementation - can be expanded
        return state.get('character_level', 1) >= 2
    
    def _check_crafting_materials_needed(self, config: Dict[str, Any], state: Dict[str, Any], 
                                       thresholds: Dict[str, Any]) -> bool:
        """Check if crafting materials are needed."""
        # Placeholder implementation - can be expanded
        return state.get('character_level', 1) >= 2
    
    def _check_workshop_discovery_needed(self, config: Dict[str, Any], state: Dict[str, Any], 
                                       thresholds: Dict[str, Any]) -> bool:
        """Check if workshop discovery is needed."""
        # Placeholder implementation - can be expanded
        return state.get('character_level', 1) >= 2

    def reload_configuration(self) -> None:
        """Reload state engine configuration."""
        self.config_data.load()
        self._load_configuration()
        self.logger.info("State calculation engine configuration reloaded")