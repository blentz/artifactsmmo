"""
GOAP State Calculation Engine

This module provides a metaprogramming-based state calculation system that replaces
hardcoded if-elif blocks with YAML-driven state computation and response handling.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict

from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


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
            config_file = f"{CONFIG_PREFIX}/state_engine.yaml"
        
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
    
    
    # REMOVED: _analyze_weapon_upgrade_need, _analyze_armor_upgrade_need, _analyze_complete_equipment_need
    # These functions duplicated functionality now available in AnalyzeEquipmentAction.
    # AnalyzeEquipmentAction provides superior functionality with:
    # - Real-time character equipment data from API
    # - Item database integration for equipment stats and tiers
    # - Comprehensive upgrade priority analysis
    # - Dynamic equipment coverage calculations
    # - Integration with character level and goals
    # 
    # Use AnalyzeEquipmentAction through ActionExecutor instead of these hardcoded functions.
    
    
    
    
    
    # REMOVED: _check_inventory_for_item, _check_for_raw_materials, _check_for_refined_materials
    # These functions duplicated functionality available in CheckInventoryAction.
    # CheckInventoryAction provides superior functionality with:
    # - Dynamic item categorization using API data
    # - Configurable patterns and requirements
    # - Better error handling and logging
    # - Consistent with metaprogramming architecture
    # 
    # Use CheckInventoryAction through ActionExecutor instead of these hardcoded functions.
    
    
    
    def process_action_response(self, action_name: str, response: Any, 
                              current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        DEPRECATED: This functionality is now handled by the unified post-execution handler.
        
        Process action response using configuration-driven handlers.
        
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
        Check if combat is viable using weighted win rate calculation.
        Returns True if combat is NOT viable (poor performance).
        """
        try:
            # Get knowledge base to assess combat performance
            knowledge_base = state.get('knowledge_base') or state.get('_knowledge_base')
            if not knowledge_base or not hasattr(knowledge_base, 'data'):
                return False  # Assume combat is viable if no data
            
            char_level = state.get('character_level', 1)
            character_data = state
            min_win_rate = thresholds.get('min_combat_win_rate', 0.2)  # 20% minimum win rate
            recency_decay = thresholds.get('recency_decay_factor', 0.9)
            
            # Analyze all known monsters to determine overall viability
            total_weighted_wins = 0.0
            total_weight = 0.0
            recent_combats = []
            
            # Collect recent combat results across all monsters
            for monster_code, monster_data in knowledge_base.data.get('monsters', {}).items():
                combat_results = monster_data.get('combat_results', [])
                
                # Filter for recent combats at current level
                level_filtered = [
                    result for result in combat_results
                    if abs(result.get('character_level', 1) - char_level) <= 1
                ]
                
                # Add to recent combats list with monster code
                for result in level_filtered:
                    recent_combats.append({
                        'monster': monster_code,
                        'result': result.get('result'),
                        'timestamp': result.get('timestamp', ''),
                        'monster_level': monster_data.get('level', 1)
                    })
            
            # Sort by timestamp to get truly recent fights
            recent_combats.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Calculate weighted win rate for recent combats
            for i, combat in enumerate(recent_combats[:20]):  # Consider last 20 combats
                weight = recency_decay ** i
                total_weight += weight
                
                if combat['result'] == 'win':
                    total_weighted_wins += weight
                    
                # Apply level-based penalty for fighting higher level monsters
                level_diff = combat.get('monster_level', 1) - char_level
                if level_diff > 0:
                    # Reduce effective weight for fights against higher level monsters
                    penalty = 0.1 * level_diff  # 10% penalty per level difference
                    total_weight += penalty
            
            # Need at least 5 combats to make a determination
            if len(recent_combats) < 5:
                self.logger.debug(f"⚔️ Insufficient combat data ({len(recent_combats)} combats) - assuming viable")
                return False  # Combat is viable by default
            
            # Calculate weighted win rate
            weighted_win_rate = total_weighted_wins / total_weight if total_weight > 0 else 0.0
            
            # Check if combat is not viable
            if weighted_win_rate < min_win_rate:
                # Log detailed analysis
                total_wins = sum(1 for c in recent_combats[:10] if c['result'] == 'win')
                self.logger.warning(
                    f"⚠️ Combat not viable: Recent win rate {weighted_win_rate:.1%} "
                    f"({total_wins}/{min(10, len(recent_combats))} recent wins) below threshold {min_win_rate:.1%}"
                )
                
                # Log recent combat results
                for combat in recent_combats[:5]:
                    self.logger.info(f"  - {combat['monster']}: {combat['result']}")
                
                return True  # combat_not_viable = True
            
            return False  # Combat is viable
            
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