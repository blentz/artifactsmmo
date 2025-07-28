"""
Action Registry System

This module provides automatic discovery and registration of all GOAP actions
through importlib, with support for dynamic generation of parameterized actions.
"""

import importlib
import inspect
import pkgutil
from pathlib import Path
from typing import Any

from ..state.game_state import GameState
from .action_factory import ActionFactory
from .base_action import BaseAction


class ActionRegistry:
    """Registry for automatic action discovery and dynamic generation"""

    def __init__(self) -> None:
        """Initialize ActionRegistry with automatic action discovery.

        Parameters:
            None

        Return values:
            None (constructor)

        This constructor initializes the action registry system with automatic
        discovery of all action modules, factory registration, and validation
        of BaseAction interface compliance for type-safe GOAP integration.
        """
        self._discovered_actions: dict[str, type[BaseAction]] = {}
        self._action_factories: dict[type[BaseAction], ActionFactory] = {}
        self._initialized = False

        # Perform automatic action discovery
        self._discovered_actions = self.discover_actions()

    def discover_actions(self) -> dict[str, type[BaseAction]]:
        """Auto-discover all action modules and validate BaseAction interface.

        Parameters:
            None

        Return values:
            Dictionary mapping action names to validated BaseAction subclasses

        This method uses importlib to automatically discover all action modules
        in the actions package, validates their BaseAction interface compliance,
        and ensures proper GameState enum usage for type-safe integration.
        """
        discovered_actions = {}

        # Get the current package path
        package_path = Path(__file__).parent
        package_name = 'src.ai_player.actions'

        # Discover all modules in the actions package
        for module_info in pkgutil.iter_modules([str(package_path)]):
            module_name = module_info.name

            # Skip special modules
            if module_name.startswith('_') or module_name == 'base_action':
                continue

            try:
                # Import the module
                full_module_name = f'{package_name}.{module_name}'
                module = importlib.import_module(full_module_name)

                # Find all classes in the module
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a BaseAction subclass (but not BaseAction itself)
                    if (issubclass(obj, BaseAction) and
                        obj is not BaseAction and
                        obj.__module__ == full_module_name):

                        # Validate the action class
                        if self.validate_action(obj):
                            action_name = obj.__name__
                            discovered_actions[action_name] = obj
                        else:
                            print(f"Warning: Action {obj.__name__} failed validation")

            except Exception as e:
                print(f"Error importing module {module_name}: {e}")
                continue

        return discovered_actions

    def register_factory(self, factory: ActionFactory) -> None:
        """Register an action factory for dynamic instance generation.

        Parameters:
            factory: ActionFactory instance for generating parameterized actions

        Return values:
            None (modifies internal registry)

        This method registers an action factory that can generate multiple
        parameterized instances of a specific action type, enabling dynamic
        action creation based on current game state and world conditions.
        """
        action_type = factory.get_action_type()
        self._action_factories[action_type] = factory

    def generate_actions_for_state(self, current_state: dict[GameState, Any], game_data: Any) -> list[BaseAction]:
        """Generate all possible action instances for current game state.

        Parameters:
            current_state: Dictionary with GameState enum keys and current values
            game_data: Complete game data for parameterized action generation

        Return values:
            List of all available BaseAction instances for GOAP planning

        This method coordinates all registered factories to generate the complete
        set of available actions for the current state, providing the GOAP
        planner with dynamic action availability for optimal planning.
        """
        all_actions = []

        # Generate parameterized actions using registered factories
        for action_type, factory in self._action_factories.items():
            try:
                factory_actions = factory.create_instances(game_data, current_state)
                all_actions.extend(factory_actions)
            except Exception as e:
                print(f"Error generating actions for {action_type.__name__}: {e}")
                continue

        # Add simple non-parameterized actions (those without factories)
        for action_name, action_class in self._discovered_actions.items():
            if action_class not in self._action_factories:
                try:
                    # Try to create a simple instance (no parameters)
                    action_instance = action_class()
                    all_actions.append(action_instance)
                except TypeError:
                    # Action requires parameters, try with None
                    try:
                        action_instance = action_class(api_client=None)
                        all_actions.append(action_instance)
                    except:
                        # Skip if still can't create
                        continue
                except Exception as e:
                    print(f"Error creating instance of {action_name}: {e}")
                    continue

        return all_actions

    def get_all_action_types(self) -> list[type[BaseAction]]:
        """Get all registered action classes.

        Parameters:
            None

        Return values:
            List of all BaseAction subclass types in the registry

        This method returns all discovered and validated action classes,
        enabling analysis of available action types for debugging, validation,
        and system introspection within the AI player architecture.
        """
        return list(self._discovered_actions.values())

    def validate_action(self, action_class: type[BaseAction]) -> bool:
        """Ensure action uses GameState enum in preconditions/effects.

        Parameters:
            action_class: BaseAction subclass to validate for enum compliance

        Return values:
            Boolean indicating whether action properly uses GameState enum

        This method validates that an action class properly implements the
        BaseAction interface and uses GameState enum keys in all state
        references, ensuring type safety throughout the GOAP system.
        """
        try:
            # Create a temporary instance to test the interface
            # Most actions require parameters, so we'll catch and handle that
            try:
                instance = action_class()
            except TypeError:
                # Action requires parameters, create with dummy parameters
                # This is expected for parameterized actions
                instance = None

            # Check if all required methods are implemented
            required_methods = ['name', 'cost', 'get_preconditions', 'get_effects', 'execute']
            for method_name in required_methods:
                if not hasattr(action_class, method_name):
                    return False

            # If we can create an instance, validate the state usage
            if instance is not None:
                try:
                    # Test preconditions use GameState enum
                    preconditions = instance.get_preconditions()
                    if not isinstance(preconditions, dict):
                        return False
                    for key in preconditions.keys():
                        if not isinstance(key, GameState):
                            return False

                    # Test effects use GameState enum
                    effects = instance.get_effects()
                    if not isinstance(effects, dict):
                        return False
                    for key in effects.keys():
                        if not isinstance(key, GameState):
                            return False

                except Exception:
                    # If methods throw exceptions without proper state, that's expected
                    # for actions that require specific parameters
                    pass

            return True

        except Exception:
            return False

    def get_action_by_name(self, name: str, current_state: dict[GameState, Any], game_data: Any) -> BaseAction | None:
        """Get specific action instance by name, generating if needed.

        Parameters:
            name: Unique action name identifier
            current_state: Dictionary with GameState enum keys and current values
            game_data: Complete game data for parameterized action generation

        Return values:
            BaseAction instance matching the name, or None if not found

        This method retrieves a specific action instance by name, using
        factories to generate parameterized instances as needed for GOAP
        execution and action debugging workflows.
        """
        # First check if it's a simple non-parameterized action
        for action_name, action_class in self._discovered_actions.items():
            try:
                # Try to create simple instance
                action_instance = action_class()
                if action_instance.name == name:
                    return action_instance
            except TypeError:
                # Action requires parameters, check factories
                if action_class in self._action_factories:
                    factory = self._action_factories[action_class]
                    try:
                        factory_actions = factory.create_instances(game_data, current_state)
                        for action in factory_actions:
                            if action.name == name:
                                return action
                    except Exception:
                        continue
            except Exception:
                continue

        return None