"""
Object-oriented YAML data loading for state classes.

This module provides a metaprogramming approach to loading and instantiating
state classes from YAML configuration, enabling data-driven state management.
"""

import importlib
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, Union

import yaml


@dataclass
class StateClassConfig:
    """Configuration for a state class."""
    class_path: str
    constructor_params: Dict[str, Any] = field(default_factory=dict)
    instance_params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    singleton: bool = False


class StateFactory:
    """Factory for creating state instances from YAML configuration."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._class_registry: Dict[str, Type] = {}
        self._instance_cache: Dict[str, Any] = {}
        self._config_registry: Dict[str, StateClassConfig] = {}
    
    def register_state_class(self, name: str, config: StateClassConfig) -> None:
        """Register a state class with its configuration."""
        try:
            # Import the class
            module_path, class_name = config.class_path.rsplit('.', 1)
            module = importlib.import_module(module_path)
            state_class = getattr(module, class_name)
            
            self._class_registry[name] = state_class
            self._config_registry[name] = config
            
            self.logger.debug(f"Registered state class: {name} -> {config.class_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to register state class {name}: {e}")
            raise
    
    def create_state_instance(self, name: str, override_params: Dict[str, Any] = None) -> Any:
        """Create a state instance from configuration."""
        if name not in self._class_registry:
            raise ValueError(f"State class {name} not registered")
        
        config = self._config_registry[name]
        
        # Check singleton cache
        if config.singleton and name in self._instance_cache:
            return self._instance_cache[name]
        
        state_class = self._class_registry[name]
        override_params = override_params or {}
        
        try:
            # Merge constructor parameters
            constructor_params = {**config.constructor_params, **override_params}
            
            # Resolve dependencies
            resolved_params = self._resolve_dependencies(constructor_params, config.dependencies)
            
            # Create instance
            instance = state_class(**resolved_params)
            
            # Apply instance parameters
            for param_name, param_value in config.instance_params.items():
                if hasattr(instance, param_name):
                    setattr(instance, param_name, param_value)
            
            # Cache singleton instances
            if config.singleton:
                self._instance_cache[name] = instance
            
            self.logger.debug(f"Created state instance: {name}")
            return instance
            
        except Exception as e:
            self.logger.error(f"Failed to create state instance {name}: {e}")
            raise
    
    def _resolve_dependencies(self, params: Dict[str, Any], dependencies: List[str]) -> Dict[str, Any]:
        """Resolve dependency references in parameters."""
        resolved = params.copy()
        
        for param_name, param_value in params.items():
            if isinstance(param_value, str) and param_value.startswith('$ref:'):
                # Dependency reference: $ref:dependency_name
                dep_name = param_value[5:]  # Remove '$ref:'
                if dep_name in dependencies:
                    resolved[param_name] = self.create_state_instance(dep_name)
                else:
                    self.logger.warning(f"Unresolved dependency: {dep_name}")
        
        return resolved
    
    def get_singleton_instance(self, name: str) -> Optional[Any]:
        """Get a cached singleton instance."""
        return self._instance_cache.get(name)
    
    def clear_cache(self) -> None:
        """Clear the singleton instance cache."""
        self._instance_cache.clear()


class StateConfigLoader:
    """Loader for state configurations from YAML files."""
    
    def __init__(self, config_path: Union[str, Path] = None):
        self.logger = logging.getLogger(__name__)
        
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent / "config" / "state_configurations.yaml"
        
        self.config_path = Path(config_path)
        self.factory = StateFactory()
        self._load_configurations()
    
    def _load_configurations(self) -> None:
        """Load state configurations from YAML."""
        try:
            if not self.config_path.exists():
                self.logger.warning(f"State configuration file not found: {self.config_path}")
                return
            
            with open(self.config_path) as f:
                config_data = yaml.safe_load(f)
            
            state_configs = config_data.get('state_classes', {})
            
            for name, config_dict in state_configs.items():
                config = StateClassConfig(
                    class_path=config_dict['class_path'],
                    constructor_params=config_dict.get('constructor_params', {}),
                    instance_params=config_dict.get('instance_params', {}),
                    dependencies=config_dict.get('dependencies', []),
                    singleton=config_dict.get('singleton', False)
                )
                
                self.factory.register_state_class(name, config)
            
            self.logger.info(f"Loaded {len(state_configs)} state class configurations")
            
        except Exception as e:
            self.logger.error(f"Failed to load state configurations: {e}")
            raise
    
    def create_state(self, name: str, **kwargs) -> Any:
        """Create a state instance with optional parameter overrides."""
        return self.factory.create_state_instance(name, kwargs)
    
    def get_factory(self) -> StateFactory:
        """Get the underlying state factory."""
        return self.factory
    
    def reload_configurations(self) -> None:
        """Reload configurations from YAML."""
        self.factory.clear_cache()
        self._load_configurations()


class StateManagerMixin:
    """Mixin class for controllers to add YAML-driven state management."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.state_loader: Optional[StateConfigLoader] = None
        self._managed_states: Dict[str, Any] = {}
    
    def initialize_state_management(self, config_path: Union[str, Path] = None) -> None:
        """Initialize YAML-driven state management."""
        self.state_loader = StateConfigLoader(config_path)
        
    def create_managed_state(self, name: str, state_type: str, **kwargs) -> Any:
        """Create and manage a state instance."""
        if not self.state_loader:
            raise RuntimeError("State management not initialized")
        
        state = self.state_loader.create_state(state_type, **kwargs)
        self._managed_states[name] = state
        return state
    
    def get_managed_state(self, name: str) -> Optional[Any]:
        """Get a managed state instance."""
        return self._managed_states.get(name)
    
    def reload_state_configurations(self) -> None:
        """Reload state configurations and recreate managed states."""
        if not self.state_loader:
            return
        
        self.state_loader.reload_configurations()
        
        # Recreate managed states with their current configurations
        old_states = self._managed_states.copy()
        self._managed_states.clear()
        
        for name, old_state in old_states.items():
            try:
                # Try to preserve state by copying data if possible
                state_type = old_state.__class__.__name__.lower()
                new_state = self.state_loader.create_state(state_type)
                
                # Copy data if both have data attribute
                if hasattr(old_state, 'data') and hasattr(new_state, 'data'):
                    new_state.data.update(old_state.data)
                
                self._managed_states[name] = new_state
                
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to recreate managed state {name}: {e}")


# Abstract base class for state classes to follow a common pattern
class YamlConfigurableState(ABC):
    """Abstract base class for states that can be configured via YAML."""
    
    @abstractmethod
    def validate_configuration(self) -> bool:
        """Validate the state configuration."""
        pass
    
    @abstractmethod
    def get_default_data(self) -> Dict[str, Any]:
        """Get default data structure for this state."""
        pass
    
    def apply_yaml_config(self, config: Dict[str, Any]) -> None:
        """Apply YAML configuration to this state."""
        for key, value in config.items():
            if hasattr(self, key):
                setattr(self, key, value)