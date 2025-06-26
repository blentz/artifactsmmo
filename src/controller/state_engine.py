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
    
    def reload_configuration(self) -> None:
        """Reload state engine configuration."""
        self.config_data.load()
        self._load_configuration()
        self.logger.info("State calculation engine configuration reloaded")