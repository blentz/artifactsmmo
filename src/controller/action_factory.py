"""
Action Factory for dynamic action instantiation.

This module provides a factory pattern for creating action instances based on YAML configuration,
eliminating the need for hardcoded if-elif blocks in the controller.
"""

import importlib
import inspect
import logging
from typing import Any, Dict, Optional, Type, Callable
from dataclasses import dataclass

from .actions.base import ActionBase


@dataclass
class ActionExecutorConfig:
    """Configuration for action execution including parameters and preprocessing."""
    action_class: Type[ActionBase]
    constructor_params: Dict[str, str]  # Maps constructor param names to action_data keys
    preprocessors: Dict[str, Callable] = None  # Optional data preprocessing functions
    postprocessors: Dict[str, Callable] = None  # Optional response post-processing


class ActionFactory:
    """
    Factory class for creating and executing actions dynamically based on configuration.
    
    Supports YAML-driven action execution without hardcoded if-elif blocks.
    """
    
    def __init__(self, config_data=None):
        self.logger = logging.getLogger(__name__)
        self._action_registry: Dict[str, ActionExecutorConfig] = {}
        self._config_data = config_data
        self._setup_default_actions()
        
        # Load additional action classes from YAML if available
        if self._config_data:
            self._load_action_classes_from_yaml()
    
    def _setup_default_actions(self) -> None:
        """Set up the default action mappings with their parameter configurations."""
        from .actions.move import MoveAction
        from .actions.attack import AttackAction
        from .actions.rest import RestAction
        from .actions.map_lookup import MapLookupAction
        from .actions.find_monsters import FindMonstersAction
        from .actions.wait import WaitAction
        
        # Register default actions with their parameter mappings
        self.register_action('move', ActionExecutorConfig(
            action_class=MoveAction,
            constructor_params={
                'char_name': 'character_name',  # Will be provided by controller
                'x': 'x',
                'y': 'y'
            }
        ))
        
        self.register_action('attack', ActionExecutorConfig(
            action_class=AttackAction,
            constructor_params={
                'char_name': 'character_name'  # Will be provided by controller
            }
        ))
        
        self.register_action('rest', ActionExecutorConfig(
            action_class=RestAction,
            constructor_params={
                'char_name': 'character_name'  # Will be provided by controller
            }
        ))
        
        self.register_action('map_lookup', ActionExecutorConfig(
            action_class=MapLookupAction,
            constructor_params={
                'x': 'x',
                'y': 'y'
            }
        ))
        
        self.register_action('find_monsters', ActionExecutorConfig(
            action_class=FindMonstersAction,
            constructor_params={
                'character_x': 'character_x',
                'character_y': 'character_y',
                'search_radius': 'search_radius',
                'monster_types': 'monster_types',
                'character_level': 'character_level',
                'level_range': 'level_range'
            }
        ))
        
        self.register_action('wait', ActionExecutorConfig(
            action_class=WaitAction,
            constructor_params={
                'wait_duration': 'wait_duration'
            }
        ))
    
    def _load_action_classes_from_yaml(self) -> None:
        """Load action class mappings from YAML configuration."""
        try:
            if not self._config_data or not hasattr(self._config_data, 'data'):
                return
                
            action_classes = self._config_data.data.get('action_classes', {})
            
            for action_name, class_path in action_classes.items():
                # Only register if not already registered (avoid overriding defaults)
                if action_name not in self._action_registry:
                    try:
                        action_class = self._import_action_class(class_path)
                        # Use a basic configuration for YAML-loaded classes
                        config = ActionExecutorConfig(
                            action_class=action_class,
                            constructor_params={}  # Will be determined dynamically
                        )
                        self.register_action(action_name, config)
                        self.logger.debug(f"Loaded action class from YAML: {action_name} -> {class_path}")
                    except Exception as e:
                        self.logger.warning(f"Failed to load action class {action_name} from {class_path}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error loading action classes from YAML: {e}")
    
    def register_action(self, action_name: str, config: ActionExecutorConfig) -> None:
        """
        Register an action with its execution configuration.
        
        Args:
            action_name: Name of the action
            config: Configuration for action execution
        """
        self._action_registry[action_name] = config
        self.logger.debug(f"Registered action: {action_name}")
    
    def register_action_from_yaml(self, action_name: str, yaml_config: Dict[str, Any]) -> None:
        """
        Register an action from YAML configuration.
        
        Args:
            action_name: Name of the action
            yaml_config: YAML configuration dictionary
        """
        if 'class_path' not in yaml_config:
            raise ValueError(f"Action {action_name} missing 'class_path' in YAML config")
        
        # Dynamically import the action class
        action_class = self._import_action_class(yaml_config['class_path'])
        
        # Build constructor parameter mapping
        constructor_params = yaml_config.get('constructor_params', {})
        
        # Set up preprocessors and postprocessors if defined
        preprocessors = self._build_function_map(yaml_config.get('preprocessors', {}))
        postprocessors = self._build_function_map(yaml_config.get('postprocessors', {}))
        
        config = ActionExecutorConfig(
            action_class=action_class,
            constructor_params=constructor_params,
            preprocessors=preprocessors,
            postprocessors=postprocessors
        )
        
        self.register_action(action_name, config)
    
    def _import_action_class(self, class_path: str) -> Type[ActionBase]:
        """
        Dynamically import an action class from a module path.
        
        Args:
            class_path: Module path like 'src.controller.actions.move.MoveAction'
            
        Returns:
            The imported action class
        """
        module_path, class_name = class_path.rsplit('.', 1)
        module = importlib.import_module(module_path)
        action_class = getattr(module, class_name)
        
        if not issubclass(action_class, ActionBase):
            raise ValueError(f"Class {class_path} is not a subclass of ActionBase")
        
        return action_class
    
    def _build_function_map(self, function_configs: Dict[str, str]) -> Dict[str, Callable]:
        """
        Build a map of functions from configuration strings.
        
        Args:
            function_configs: Dict mapping param names to function paths
            
        Returns:
            Dict mapping param names to callable functions
        """
        function_map = {}
        for param_name, func_path in function_configs.items():
            module_path, func_name = func_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            function_map[param_name] = getattr(module, func_name)
        return function_map
    
    def create_action(self, action_name: str, action_data: Dict[str, Any], 
                     context: Dict[str, Any] = None) -> Optional[ActionBase]:
        """
        Create an action instance based on configuration and data.
        
        Args:
            action_name: Name of the action to create
            action_data: Data from the action plan
            context: Additional context (character state, etc.)
            
        Returns:
            Action instance ready for execution, or None if creation failed
        """
        if action_name not in self._action_registry:
            self.logger.error(f"Unknown action: {action_name}")
            return None
        
        config = self._action_registry[action_name]
        context = context or {}
        
        
        try:
            # Build constructor arguments
            constructor_args = {}
            for param_name, data_key in config.constructor_params.items():
                if data_key in action_data:
                    value = action_data[data_key]
                elif data_key in context:
                    value = context[data_key]
                else:
                    # Check if parameter has a default value
                    sig = inspect.signature(config.action_class.__init__)
                    param = sig.parameters.get(param_name)
                    if param and param.default != inspect.Parameter.empty:
                        continue  # Skip - will use default
                    else:
                        self.logger.warning(f"Missing required parameter {param_name} for action {action_name}")
                        return None
                
                # Apply preprocessor if available
                if config.preprocessors and param_name in config.preprocessors:
                    value = config.preprocessors[param_name](value)
                
                constructor_args[param_name] = value
            
            # Create the action instance
            action = config.action_class(**constructor_args)
            self.logger.debug(f"Created action {action_name}: {action}")
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to create action {action_name}: {e}")
            return None
    
    def execute_action(self, action_name: str, action_data: Dict[str, Any], 
                      client, context: Dict[str, Any] = None) -> tuple[bool, Any]:
        """
        Create and execute an action in one step.
        
        Args:
            action_name: Name of the action to execute
            action_data: Data from the action plan
            client: API client for action execution
            context: Additional context (character state, etc.)
            
        Returns:
            Tuple of (success: bool, response: Any)
        """
        action = self.create_action(action_name, action_data, context)
        if not action:
            return False, None
        
        try:
            # Execute the action with context passed as kwargs
            kwargs = context.copy() if context else {}
            response = action.execute(client, **kwargs)
            
            # Apply postprocessors if available
            config = self._action_registry[action_name]
            if config.postprocessors:
                for processor in config.postprocessors.values():
                    response = processor(response)
            
            # Check if response indicates success or failure
            if response is None:
                success = False
            elif isinstance(response, dict) and 'success' in response:
                success = response['success']
            else:
                # For API responses that don't have a 'success' field, consider them successful
                success = True
            
            return success, response
            
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
            return False, None
    
    def get_available_actions(self) -> list[str]:
        """Get list of available action names."""
        return list(self._action_registry.keys())
    
    def is_action_registered(self, action_name: str) -> bool:
        """Check if an action is registered."""
        return action_name in self._action_registry