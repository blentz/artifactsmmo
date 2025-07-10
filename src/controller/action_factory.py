"""
Action Factory for dynamic action instantiation.

This module provides a factory pattern for creating action instances based on YAML configuration,
using snake_case to CamelCase naming conventions to eliminate hardcoded registrations.
"""

import importlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Type

from ..lib.action_context import ActionContext
from ..lib.actions_data import ActionsData
from .actions.base import ActionBase, ActionResult


@dataclass
class ActionExecutorConfig:
    """Configuration for action execution."""
    action_class: Type[ActionBase]
    constructor_params: Dict[str, str] = None
    preprocessors: Dict[str, str] = None
    postprocessors: Dict[str, str] = None


class ActionFactory:
    """
    Factory for creating action instances dynamically using naming conventions.
    
    This class enables metaprogramming by mapping snake_case action names to CamelCase
    class names, eliminating the need for hardcoded registrations.
    """
    
    def __init__(self, config_data: Any = None):
        self.logger = logging.getLogger(__name__)
        self.config_data = config_data
        self._action_cache: Dict[str, Type[ActionBase]] = {}
        
    def _snake_to_camel_case(self, snake_str: str) -> str:
        """Convert snake_case to CamelCase."""
        components = snake_str.split('_')
        return ''.join(word.capitalize() for word in components) + 'Action'
    
    def _load_action_class(self, action_name: str) -> Optional[Type[ActionBase]]:
        """
        Load action class using naming convention.
        
        Args:
            action_name: Snake case action name (e.g., 'analyze_equipment')
            
        Returns:
            Action class or None if not found
        """
        if action_name in self._action_cache:
            return self._action_cache[action_name]
        
        try:
            # Convert snake_case to CamelCase
            class_name = self._snake_to_camel_case(action_name)
            
            # Build module path
            module_path = f"src.controller.actions.{action_name}"
            
            # Import module and get class
            module = importlib.import_module(module_path)
            action_class = getattr(module, class_name)
            
            # Validate it's an ActionBase subclass
            if not issubclass(action_class, ActionBase):
                self.logger.error(f"Class {class_name} is not an ActionBase subclass")
                return None
                
            # Cache the result
            self._action_cache[action_name] = action_class
            self.logger.debug(f"Loaded action class: {action_name} -> {class_name}")
            
            return action_class
            
        except (ImportError, AttributeError) as e:
            self.logger.error(f"Failed to load action class for {action_name}: {e}")
            return None
    
    def create_action(self, action_name: str, context: 'ActionContext') -> Optional[ActionBase]:
        """
        Create an action instance using naming convention.
        
        Args:
            action_name: Name of the action to create
            context: ActionContext instance with unified state
            
        Returns:
            Action instance ready for execution, or None if creation failed
        """
        action_class = self._load_action_class(action_name)
        if not action_class:
            return None
        
        try:
            # All actions use ActionContext pattern
            action = action_class()
            self.logger.debug(f"Created action {action_name}: {action}")
            return action
            
        except Exception as e:
            self.logger.error(f"Failed to create action {action_name}: {e}")
            return None
    
    def execute_action(self, action_name: str, client, context: 'ActionContext') -> ActionResult:
        """
        Create and execute an action in one step.
        
        Args:
            action_name: Name of the action to execute
            client: API client for action execution
            context: ActionContext instance with unified state
            
        Returns:
            ActionResult object with execution results
        """
        action = self.create_action(action_name, context)
        if not action:
            return ActionResult(
                success=False,
                error=f"Failed to create action: {action_name}",
                action_name=action_name
            )
        
        try:
            # Auto-load action parameters from default_actions.yaml
            self._load_action_parameters(action_name, context)
            
            # Store action instance in context for dynamic reactions
            context.action_instance = action
            
            # Execute the action with ActionContext
            result = action.execute(client, context)
            
            # All actions MUST return ActionResult - no exceptions
            if not isinstance(result, ActionResult):
                raise TypeError(f"Action {action_name} must return ActionResult, got {type(result)}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to execute action {action_name}: {e}")
            return ActionResult(
                success=False,
                error=f"Action execution failed: {str(e)}",
                action_name=action_name
            )
    
    def _load_action_parameters(self, action_name: str, context: 'ActionContext') -> None:
        """
        Auto-load action parameters from default_actions.yaml into the action context.
        
        Args:
            action_name: Name of the action being executed
            context: ActionContext to load parameters into
        """
        try:
            # Load action configuration from default_actions.yaml
            actions_data = ActionsData()  # Loads config/default_actions.yaml
            action_config = actions_data.get_actions().get(action_name, {})
            action_parameters = action_config.get('parameters', {})
            
            # Set individual action parameters using flat storage
            for param_name, param_value in action_parameters.items():
                context.set(param_name, param_value)
            
            self.logger.debug(f"Auto-loaded {len(action_parameters)} parameters for {action_name}: {action_parameters}")
            
        except Exception as e:
            self.logger.warning(f"Failed to load parameters for {action_name}: {e}")

    def get_available_actions(self) -> list[str]:
        """
        Get list of available action names by scanning the actions directory.
        
        Returns:
            List of available action names
        """
        import os
        import pkgutil
        
        try:
            # Get the actions package
            actions_package = importlib.import_module('src.controller.actions')
            actions_path = actions_package.__path__
            
            available_actions = []
            
            # Scan all modules in the actions directory
            for importer, modname, ispkg in pkgutil.iter_modules(actions_path):
                if not ispkg and modname != 'base':  # Skip base module
                    available_actions.append(modname)
            
            return available_actions
            
        except Exception as e:
            self.logger.error(f"Failed to scan available actions: {e}")
            return []
    
    def is_action_registered(self, action_name: str) -> bool:
        """Check if an action is available."""
        return self._load_action_class(action_name) is not None
    
    @property
    def action_class_map(self) -> Dict[str, Type[ActionBase]]:
        """
        Get a mapping of action names to their action classes.
        
        This property provides compatibility with code that expects direct access
        to action classes by dynamically loading them.
        
        Returns:
            Dictionary mapping action names to their corresponding action classes
        """
        class_map = {}
        available_actions = self.get_available_actions()
        
        for action_name in available_actions:
            action_class = self._load_action_class(action_name)
            if action_class:
                class_map[action_name] = action_class
        
        return class_map