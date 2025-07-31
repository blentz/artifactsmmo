"""
Action Registry System with Dynamic Action Generation

This module provides automatic discovery and registration of all GOAP actions
through importlib, with support for dynamic generation of parameterized actions.
All action modules are discovered and validated to ensure they implement the
BaseAction interface and use GameState enum for type safety.

The registry enables the GOAP planner to access thousands of parameterized
action instances generated dynamically based on game state and world data.

After one-class-per-file refactoring, this module re-exports all classes
for backwards compatibility.
"""

from typing import Any

from ..state.character_game_state import CharacterGameState
from ..state.game_state import GameState
from .action_factory import ActionFactory
from .action_registry import ActionRegistry
from .base_action import BaseAction
from .combat_action_factory import CombatActionFactory
from .gathering_action_factory import GatheringActionFactory
from .movement_action_factory import MovementActionFactory
from .parameterized_action_factory import ParameterizedActionFactory
from .rest_action_factory import RestActionFactory

# Global action registry instance
_global_registry: ActionRegistry | None = None


def get_global_registry() -> ActionRegistry:
    """Get or create the global action registry instance."""
    global _global_registry
    if _global_registry is None:
        _global_registry = ActionRegistry()

        # Register all action factories
        movement_factory = MovementActionFactory()
        combat_factory = CombatActionFactory()
        gathering_factory = GatheringActionFactory()
        rest_factory = RestActionFactory()

        _global_registry.register_factory(movement_factory)
        _global_registry.register_factory(combat_factory)
        _global_registry.register_factory(gathering_factory)
        _global_registry.register_factory(rest_factory)

    return _global_registry


def get_all_actions(current_state: CharacterGameState, game_data: Any) -> list[BaseAction]:
    """Global function to get all available action instances for GOAP system.

    Parameters:
        current_state: CharacterGameState instance with current character state
        game_data: Complete game data for action generation

    Return values:
        List of all available BaseAction instances for GOAP planning

    This function provides the main entry point for the GOAP planner to
    obtain all available actions for the current state, coordinating
    the action registry and factory system for dynamic action generation.
    """
    registry = get_global_registry()
    return registry.generate_actions_for_state(current_state, game_data)


def register_action_factory(factory: ActionFactory) -> None:
    """Register a new action factory with the registry.

    Parameters:
        factory: ActionFactory instance to add to the global registry

    Return values:
        None (modifies global registry)

    This function registers a new action factory with the global registry,
    enabling automatic discovery and generation of parameterized actions
    for the GOAP planning system.
    """
    registry = get_global_registry()
    registry.register_factory(factory)


# Export all classes for backwards compatibility
__all__ = [
    "ActionFactory",
    "ActionRegistry",
    "ParameterizedActionFactory",
    "get_global_registry",
    "get_all_actions",
    "register_action_factory"
]
