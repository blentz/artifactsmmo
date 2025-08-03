"""
Action Registry System

This module provides factory-based registration and management of GOAP actions
with support for dynamic generation of parameterized actions.
"""

from typing import Any

from ..state.character_game_state import CharacterGameState
from .action_factory import ActionFactory
from .base_action import BaseAction


class ActionRegistry:
    """Registry for factory-based action management and dynamic generation"""

    def __init__(self) -> None:
        """Initialize ActionRegistry for factory-based action management.

        Parameters:
            None

        Return values:
            None (constructor)

        This constructor initializes the action registry system with
        factory registration support for type-safe GOAP integration.
        Factories are the authoritative source of available actions.
        """
        self._action_factories: dict[type[BaseAction], ActionFactory] = {}
        self._initialized = False


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

    def generate_actions_for_state(self, current_state: CharacterGameState, game_data: Any) -> list[BaseAction]:
        """Generate all possible action instances for current game state.

        Parameters:
            current_state: CharacterGameState instance with current character state
            game_data: Complete game data for parameterized action generation

        Return values:
            List of all available BaseAction instances for GOAP planning

        This method coordinates all registered factories to generate the complete
        set of available actions for the current state, providing the GOAP
        planner with dynamic action availability for optimal planning.
        """
        all_actions = []

        # Generate actions using registered factories only
        # All actions must have factories registered - no direct instantiation
        for action_type, factory in self._action_factories.items():
            factory_actions = factory.create_instances(game_data, current_state)
            all_actions.extend(factory_actions)

        return all_actions

    def get_all_action_types(self) -> list[type[BaseAction]]:
        """Get all action types supported by registered factories.

        Parameters:
            None

        Return values:
            List of all BaseAction subclass types supported by factories

        This method returns all action types supported by registered factories,
        enabling analysis of available action types for debugging, validation,
        and system introspection within the AI player architecture.
        """
        return list(self._action_factories.keys())

    def get_action_by_name(self, name: str, current_state: CharacterGameState, game_data: Any) -> BaseAction | None:
        """Get specific action instance by name, generating if needed.

        Parameters:
            name: Unique action name identifier
            current_state: CharacterGameState instance with current character state
            game_data: Complete game data for parameterized action generation

        Return values:
            BaseAction instance matching the name, or None if not found

        This method retrieves a specific action instance by name, using
        factories to generate parameterized instances as needed for GOAP
        execution and action debugging workflows.
        """
        # Debug: collect all action names for debugging
        all_action_names = []

        # Search through all registered factories
        for action_class, factory in self._action_factories.items():
            factory_actions = factory.create_instances(game_data, current_state)
            for action in factory_actions:
                all_action_names.append(action.name)
                if action.name == name:
                    return action

        # Debug logging for missing actions
        print(f"DEBUG: Action '{name}' not found. Available actions: {all_action_names[:10]}...")
        return None
