"""
Action Validation Framework

This module provides a centralized validation system for action execution,
validating parameters, state preconditions, and dependencies before execution.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.game.globals import CONFIG_PREFIX
from src.lib.yaml_data import YamlData


@dataclass
class ValidationError:
    """Represents a validation error."""
    validator: str
    message: str
    field_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationWarning:
    """Represents a validation warning."""
    validator: str
    message: str
    field_name: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationResult:
    """Result of action validation."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def summary(self) -> str:
        """Human-readable summary of validation issues."""
        if self.is_valid:
            return "Validation passed"
        
        error_messages = [f"{e.validator}: {e.message}" for e in self.errors]
        return "; ".join(error_messages)


class ValidatorRegistry:
    """Registry of validation functions."""
    
    _validators: Dict[str, Callable] = {}
    
    @classmethod
    def register(cls, validator_type: str):
        """Decorator to register a validator function."""
        def decorator(func):
            cls._validators[validator_type] = func
            return func
        return decorator
    
    @classmethod
    def get(cls, validator_type: str) -> Optional[Callable]:
        """Get a validator function by type."""
        return cls._validators.get(validator_type)


class ActionValidator:
    """
    Centralized validation system for action execution.
    Validates parameters, state preconditions, and dependencies.
    """
    
    def __init__(self, config_path: str = None):
        """Initialize the action validator."""
        self.logger = logging.getLogger(__name__)
        
        # Load validation rules from YAML
        if config_path is None:
            config_path = f"{CONFIG_PREFIX}/validation_rules.yaml"
        
        self.config_data = YamlData(config_path)
        self._load_validation_rules()
        
        # Register built-in validators
        self._register_built_in_validators()
    
    def _load_validation_rules(self) -> None:
        """Load validation rules from configuration."""
        try:
            self.global_rules = self.config_data.data.get('validation_rules', {}).get('global', [])
            self.action_rules = self.config_data.data.get('validation_rules', {}).get('actions', {})
            
            self.logger.info(f"Loaded {len(self.global_rules)} global validation rules")
            self.logger.info(f"Loaded validation rules for {len(self.action_rules)} actions")
            
        except Exception as e:
            self.logger.error(f"Failed to load validation rules: {e}")
            self.global_rules = []
            self.action_rules = {}
    
    def _register_built_in_validators(self) -> None:
        """Register built-in validator functions."""
        # These are defined as methods below and registered here
        pass
    
    def validate_action(self, action_name: str, params: Dict[str, Any], 
                       context: Any, client: Any = None) -> ValidationResult:
        """
        Main validation entry point for an action.
        
        Args:
            action_name: Name of the action to validate
            params: Action parameters
            context: Execution context (ActionContext or dict)
            
        Returns:
            ValidationResult with success/failure and detailed errors
        """
        errors = []
        warnings = []
        
        # Run global validation rules
        for rule in self.global_rules:
            result = self._run_validation_rule(rule, action_name, params, context, client)
            if result:
                if isinstance(result, ValidationError):
                    errors.append(result)
                elif isinstance(result, ValidationWarning):
                    warnings.append(result)
        
        # Run action-specific validation rules
        action_rules = self.action_rules.get(action_name, [])
        for rule in action_rules:
            result = self._run_validation_rule(rule, action_name, params, context, client)
            if result:
                if isinstance(result, ValidationError):
                    errors.append(result)
                elif isinstance(result, ValidationWarning):
                    warnings.append(result)
        
        # Create validation result
        is_valid = len(errors) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            metadata={
                'action': action_name,
                'validated_params': list(params.keys()) if params else []
            }
        )
    
    def _run_validation_rule(self, rule: Dict[str, Any], action_name: str,
                            params: Dict[str, Any], context: Any, client: Any = None) -> Optional[ValidationError]:
        """Run a single validation rule."""
        rule_type = rule.get('type')
        if not rule_type:
            return None
        
        # Get validator function
        validator_func = ValidatorRegistry.get(rule_type)
        if not validator_func:
            # Try to find it as a method on this class
            method_name = f"_validate_{rule_type}"
            if hasattr(self, method_name):
                validator_func = getattr(self, method_name)
            else:
                self.logger.warning(f"No validator found for type: {rule_type}")
                return None
        
        try:
            # Run validator
            return validator_func(params, rule, context, client)
        except Exception as e:
            self.logger.error(f"Validator {rule_type} failed: {e}")
            return ValidationError(
                validator=rule_type,
                message=f"Validator failed with error: {str(e)}"
            )
    
    # Built-in validators
    
    def _validate_required_params(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Ensure all required parameters are present and not None."""
        required_params = rule.get('params', [])
        missing_params = []
        
        for param_name in required_params:
            # Check in params dict
            if param_name not in params or params[param_name] is None:
                # Also check nested params key (for actions that nest parameters)
                if 'params' in params and param_name in params['params']:
                    continue
                missing_params.append(param_name)
        
        if missing_params:
            return ValidationError(
                validator="required_params",
                message=f"Missing required parameters: {', '.join(missing_params)}",
                details={'missing': missing_params}
            )
        
        return None
    
    def _validate_required_context(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Ensure required context fields are present."""
        required_fields = rule.get('fields', [])
        missing_fields = []
        
        for field in required_fields:
            # Check if context has the field
            if hasattr(context, field):
                if getattr(context, field) is None:
                    missing_fields.append(field)
            elif isinstance(context, dict):
                if field not in context or context[field] is None:
                    missing_fields.append(field)
            else:
                missing_fields.append(field)
        
        if missing_fields:
            return ValidationError(
                validator="required_context",
                message=f"Missing required context fields: {', '.join(missing_fields)}",
                details={'missing': missing_fields}
            )
        
        return None
    
    def _validate_character_alive(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Ensure character is alive before action."""
        # Get character state from context
        character_state = None
        if hasattr(context, 'character_state'):
            character_state = context.character_state
        elif isinstance(context, dict) and 'character_state' in context:
            character_state = context['character_state']
        
        if not character_state:
            return ValidationWarning(
                validator="character_alive",
                message="Could not verify character is alive (no character state in context)"
            )
        
        # Check HP
        hp = 0
        if hasattr(character_state, 'data') and isinstance(character_state.data, dict):
            hp = character_state.data.get('hp', 0)
        elif hasattr(character_state, 'hp'):
            hp = character_state.hp
        
        # Handle Mock objects
        try:
            hp_value = int(hp) if hp is not None else 0
        except (ValueError, TypeError):
            # Can't validate with mock/invalid data
            return None
        
        if hp_value <= 0:
            return ValidationError(
                validator="character_alive",
                message="Character is not alive (HP is 0)",
                details={'current_hp': hp_value}
            )
        
        return None
    
    def _validate_valid_coordinates(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Validate x,y coordinates are valid integers."""
        coord_params = rule.get('params', ['x', 'y'])
        
        for coord in coord_params:
            value = params.get(coord)
            if value is None:
                # Will be caught by required_params validator
                continue
                
            # Check if it's a valid number
            try:
                int_value = int(value)
                # Basic range check (can be made configurable)
                if int_value < -100 or int_value > 100:
                    return ValidationError(
                        validator="valid_coordinates",
                        message=f"Coordinate {coord}={value} is out of valid range (-100 to 100)",
                        field_name=coord,
                        details={'value': value, 'valid_range': [-100, 100]}
                    )
            except (ValueError, TypeError):
                return ValidationError(
                    validator="valid_coordinates",
                    message=f"Coordinate {coord}={value} is not a valid integer",
                    field_name=coord,
                    details={'value': value}
                )
        
        return None
    
    def _validate_not_at_location(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Ensure character is not already at the target location."""
        coord_params = rule.get('params', ['x', 'y'])
        
        # Get target coordinates
        target_x = params.get(coord_params[0])
        target_y = params.get(coord_params[1])
        
        if target_x is None or target_y is None:
            return None  # Will be caught by required_params
        
        # Get current character position
        character_state = None
        if hasattr(context, 'character_state'):
            character_state = context.character_state
        elif isinstance(context, dict) and 'character_state' in context:
            character_state = context['character_state']
        
        if not character_state:
            return None  # Can't validate without character state
        
        # Get current position
        current_x = None
        current_y = None
        if hasattr(character_state, 'data') and isinstance(character_state.data, dict):
            current_x = character_state.data.get('x')
            current_y = character_state.data.get('y')
        elif hasattr(character_state, 'x') and hasattr(character_state, 'y'):
            current_x = character_state.x
            current_y = character_state.y
        
        # Check if already at location
        if current_x == int(target_x) and current_y == int(target_y):
            return ValidationError(
                validator="not_at_location",
                message=f"Character is already at location ({target_x}, {target_y})",
                details={
                    'current_position': (current_x, current_y),
                    'target_position': (target_x, target_y)
                }
            )
        
        return None
    
    def _validate_valid_item(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Validate that item code is not empty."""
        param_name = rule.get('param', 'item_code')
        
        # Check in params
        item_code = params.get(param_name)
        
        # Also check in nested params
        if not item_code and 'params' in params:
            item_code = params['params'].get(param_name)
        
        if not item_code or (isinstance(item_code, str) and not item_code.strip()):
            return ValidationError(
                validator="valid_item",
                message="Invalid or empty item code",
                field_name=param_name,
                details={'value': item_code}
            )
        
        return None
    
    def _validate_character_hp_above(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Ensure character HP is above a threshold."""
        threshold = rule.get('threshold', 10)
        
        # Get character state from context
        character_state = None
        if hasattr(context, 'character_state'):
            character_state = context.character_state
        elif isinstance(context, dict) and 'character_state' in context:
            character_state = context['character_state']
        
        if not character_state:
            return None  # Can't validate without character state
        
        # Get current HP
        hp = 0
        if hasattr(character_state, 'data') and isinstance(character_state.data, dict):
            hp = character_state.data.get('hp', 0)
        elif hasattr(character_state, 'hp'):
            hp = character_state.hp
        
        if hp < threshold:
            return ValidationError(
                validator="character_hp_above",
                message=f"Character HP ({hp}) is below required threshold ({threshold})",
                details={'current_hp': hp, 'threshold': threshold}
            )
        
        return None
    
    def _validate_location_has_content(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Validate that character's current location has expected content type."""
        expected_type = rule.get('content_type', 'workshop')
        
        # Get character position
        character_state = None
        if hasattr(context, 'character_state'):
            character_state = context.character_state
        elif isinstance(context, dict) and 'character_state' in context:
            character_state = context['character_state']
            
        if not character_state:
            return ValidationWarning(
                validator="location_has_content",
                message="Could not verify location content (no character state)"
            )
        
        # Get position
        x, y = None, None
        if hasattr(character_state, 'data') and isinstance(character_state.data, dict):
            x = character_state.data.get('x')
            y = character_state.data.get('y')
        elif hasattr(character_state, 'x') and hasattr(character_state, 'y'):
            x = character_state.x
            y = character_state.y
            
        if x is None or y is None:
            return ValidationWarning(
                validator="location_has_content",
                message="Could not determine character position"
            )
        
        # Get map state
        map_state = None
        if hasattr(context, 'map_state'):
            map_state = context.map_state
        elif isinstance(context, dict) and 'map_state' in context:
            map_state = context['map_state']
            
        if not map_state:
            return ValidationWarning(
                validator="location_has_content",
                message="Could not verify location content (no map state)"
            )
        
        # Check location content
        location_key = f"{x},{y}"
        if hasattr(map_state, 'data') and isinstance(map_state.data, dict):
            location_data = map_state.data.get(location_key, {})
            content = location_data.get('content', {})
            content_type = content.get('type', '')
            
            if content_type != expected_type:
                return ValidationError(
                    validator="location_has_content",
                    message=f"Location ({x},{y}) does not have expected content type '{expected_type}' (found: '{content_type}')",
                    details={
                        'position': (x, y),
                        'expected_type': expected_type,
                        'actual_type': content_type
                    }
                )
        
        return None
    
    def _validate_workshop_compatible(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Validate that current workshop is compatible with the item to craft."""
        item_code = params.get(rule.get('item_param', 'recipe_code'))
        
        if not item_code:
            return None  # Will be caught by required_params
        
        # Get knowledge base
        knowledge_base = None
        if hasattr(context, 'knowledge_base'):
            knowledge_base = context.knowledge_base
        elif isinstance(context, dict) and 'knowledge_base' in context:
            knowledge_base = context['knowledge_base']
            
        if not knowledge_base:
            return ValidationWarning(
                validator="workshop_compatible",
                message="Could not verify workshop compatibility (no knowledge base)"
            )
        
        # Get item details
        item_data = None
        if hasattr(knowledge_base, 'get_item_data'):
            item_data = knowledge_base.get_item_data(item_code)
        elif hasattr(knowledge_base, 'data') and isinstance(knowledge_base.data, dict):
            items = knowledge_base.data.get('items', {})
            item_data = items.get(item_code)
            
        if not item_data:
            return ValidationWarning(
                validator="workshop_compatible",
                message=f"Could not find item data for '{item_code}'"
            )
        
        # Get required workshop type
        required_workshop = None
        if isinstance(item_data, dict):
            craft_data = item_data.get('craft', {})
            if not craft_data:
                return ValidationError(
                    validator="workshop_compatible",
                    message=f"Item {item_code} is not craftable",
                    details={'item_code': item_code}
                )
            required_workshop = craft_data.get('skill')
        elif hasattr(item_data, 'craft'):
            if not item_data.craft:
                return ValidationError(
                    validator="workshop_compatible",
                    message=f"Item {item_code} is not craftable",
                    details={'item_code': item_code}
                )
            if hasattr(item_data.craft, 'skill'):
                required_workshop = item_data.craft.skill
            
        if not required_workshop:
            return ValidationWarning(
                validator="workshop_compatible",
                message=f"Could not determine workshop requirement for '{item_code}'"
            )
        
        # Get character position
        x, y = None, None
        if hasattr(context, 'character_state'):
            character_state = context.character_state
            if hasattr(character_state, 'data') and isinstance(character_state.data, dict):
                x = character_state.data.get('x')
                y = character_state.data.get('y')
            elif hasattr(character_state, 'x') and hasattr(character_state, 'y'):
                x = character_state.x
                y = character_state.y
        elif isinstance(context, dict) and 'character_state' in context:
            character_state = context['character_state']
            if isinstance(character_state, dict):
                x = character_state.get('x')
                y = character_state.get('y')
                
        if x is None or y is None:
            return ValidationWarning(
                validator="workshop_compatible",
                message="Could not verify workshop compatibility (no character position)"
            )
        
        # Get map state to check current workshop
        map_state = None
        if hasattr(context, 'map_state'):
            map_state = context.map_state
        elif isinstance(context, dict) and 'map_state' in context:
            map_state = context['map_state']
            
        if not map_state:
            return ValidationWarning(
                validator="workshop_compatible",
                message="Could not verify workshop compatibility (no map state)"
            )
        
        # Check workshop at location
        location_key = f"{x},{y}"
        if hasattr(map_state, 'data') and isinstance(map_state.data, dict):
            location_data = map_state.data.get(location_key, {})
            content = location_data.get('content', {})
            workshop_code = content.get('code', '')
            
            if content.get('type') != 'workshop':
                return ValidationError(
                    validator="workshop_compatible",
                    message=f"Location ({x},{y}) does not have a workshop",
                    details={'position': (x, y), 'content_type': content.get('type')}
                )
            
            if workshop_code != required_workshop:
                return ValidationError(
                    validator="workshop_compatible",
                    message=f"Workshop type mismatch: item requires {required_workshop} but at {workshop_code} workshop",
                    details={
                        'item_code': item_code,
                        'required_skill': required_workshop,
                        'current_workshop': workshop_code
                    }
                )
        
        return None
    
    def _validate_resource_matches_target(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Validate that resource at current location matches target resource."""
        target_resource = params.get(rule.get('resource_param', 'resource_type'))
        
        if not target_resource:
            return None  # Will be caught by required_params if needed
        
        # Get character position and map state (similar to location_has_content)
        character_state = None
        if hasattr(context, 'character_state'):
            character_state = context.character_state
        elif isinstance(context, dict) and 'character_state' in context:
            character_state = context['character_state']
            
        if not character_state:
            return ValidationWarning(
                validator="resource_matches_target",
                message="Could not verify resource (no character state)"
            )
        
        # Get position
        x, y = None, None
        if hasattr(character_state, 'data') and isinstance(character_state.data, dict):
            x = character_state.data.get('x')
            y = character_state.data.get('y')
        elif hasattr(character_state, 'x') and hasattr(character_state, 'y'):
            x = character_state.x
            y = character_state.y
            
        # Get map state
        map_state = None
        if hasattr(context, 'map_state'):
            map_state = context.map_state
        elif isinstance(context, dict) and 'map_state' in context:
            map_state = context['map_state']
            
        if not map_state:
            return ValidationWarning(
                validator="resource_matches_target",
                message="Could not verify resource (no map state)"
            )
        
        # Check location content
        location_key = f"{x},{y}"
        if hasattr(map_state, 'data') and isinstance(map_state.data, dict):
            location_data = map_state.data.get(location_key, {})
            content = location_data.get('content', {})
            resource_code = content.get('code', '')
            
            if content.get('type') != 'resource':
                return ValidationError(
                    validator="resource_matches_target",
                    message=f"Location ({x},{y}) does not contain a resource",
                    details={'position': (x, y), 'content_type': content.get('type')}
                )
            
            if resource_code != target_resource:
                return ValidationError(
                    validator="resource_matches_target",
                    message=f"Resource at location ({x},{y}) is '{resource_code}', expected '{target_resource}'",
                    details={
                        'position': (x, y),
                        'found_resource': resource_code,
                        'expected_resource': target_resource
                    }
                )
        
        return None

    def _validate_valid_client(self, params: Dict[str, Any], rule: Dict[str, Any],
                              context: Any, client: Any = None) -> Optional[ValidationError]:
        """Validate that a valid API client is provided."""
        # Check if client was provided
        if client is None:
            return ValidationError(
                validator='valid_client',
                message='No API client provided'
            )
        return None
    
    def reload_configuration(self) -> None:
        """Reload validation rules from configuration."""
        self.config_data.load()
        self._load_validation_rules()
        self.logger.info("Validation rules reloaded")