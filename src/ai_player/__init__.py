"""
ArtifactsMMO AI Player Module

This module provides the core AI player functionality for the ArtifactsMMO game.
Implements Goal-Oriented Action Planning (GOAP) with a modular action system
for autonomous character gameplay.
"""

import logging
from typing import Any

from .action_executor import ActionExecutor

# Action System
from .actions import ActionFactory, ActionRegistry, ParameterizedActionFactory, get_all_actions, register_action_factory
from .actions.base_action import BaseAction
from .actions.combat_action import CombatAction
from .actions.gathering_action import GatheringAction

# Action Implementations
from .actions.movement_action import MovementAction
from .actions.movement_action_factory import MovementActionFactory
from .actions.rest_action import RestAction

# Core AI Player Components
from .ai_player import AIPlayer
from .diagnostics.action_diagnostics import ActionDiagnostics
from .diagnostics.planning_diagnostics import PlanningDiagnostics

# Diagnostic System
from .diagnostics.state_diagnostics import StateDiagnostics
from .economic_intelligence import EconomicIntelligence
from .goal_manager import GoalManager
from .inventory_optimizer import InventoryOptimizer
from .pathfinding import PathfindingService

# State Management System
from .state.action_result import ActionResult, rebuild_model
from .state.character_game_state import CharacterGameState
from .state.game_state import CooldownInfo, GameState
from .state.state_manager import StateManager

# Specialized Components
from .task_manager import TaskManager

# Module version
__version__ = "2.0.0"

# Public API exports
__all__ = [
    # Core Components
    "AIPlayer",
    "GoalManager",
    "ActionExecutor",

    # State Management
    "GameState",
    "ActionResult",
    "CharacterGameState",
    "CooldownInfo",
    "StateManager",

    # Action System
    "ActionRegistry",
    "ActionFactory",
    "ParameterizedActionFactory",
    "BaseAction",
    "get_all_actions",
    "register_action_factory",

    # Action Implementations
    "MovementAction",
    "CombatAction",
    "GatheringAction",
    "RestAction",

    # Diagnostics
    "StateDiagnostics",
    "ActionDiagnostics",
    "PlanningDiagnostics",

    # Specialized Components
    "TaskManager",
    "PathfindingService",
    "InventoryOptimizer",
    "EconomicIntelligence",
]


def create_ai_player(character_name: str) -> AIPlayer:
    """Factory function to create a properly configured AI Player instance.

    Parameters:
        character_name: Name of the character to control autonomously

    Return values:
        Configured AIPlayer instance ready for autonomous gameplay

    This factory function creates and initializes an AI Player with all necessary
    components, providing a convenient entry point for creating AI-controlled
    characters in the ArtifactsMMO game system.
    """
    return AIPlayer(character_name)


def get_available_actions(
    current_state: CharacterGameState,
    game_data: Any | None = None
) -> list[BaseAction]:
    """Get all available actions for the current game state.

    Parameters:
        current_state: CharacterGameState instance with current character state
        game_data: Optional game data for parameterized action generation

    Return values:
        List of all available BaseAction instances for GOAP planning

    This function serves as a convenient wrapper around the action registry
    system, providing easy access to all available actions for the current
    game state from external modules and CLI commands.
    """
    return get_all_actions(current_state, game_data)


def validate_game_state(state_dict: dict[str, Any]) -> dict[GameState, Any]:
    """Validate and convert string-keyed state to GameState enum-keyed state.

    Parameters:
        state_dict: Dictionary with string keys representing game state

    Return values:
        Dictionary with validated GameState enum keys and original values

    This function provides a convenient way to validate state dictionaries
    and convert them to use proper GameState enum keys, ensuring type safety
    throughout the AI player system.
    """
    return GameState.validate_state_dict(state_dict)


# Rebuild ActionResult model after all imports are complete
rebuild_model()


def initialize_ai_player_module() -> None:
    """Initialize the AI Player module with necessary setup.

    Parameters:
        None

    Return values:
        None (performs module initialization)

    This function performs any necessary module-level initialization,
    such as setting up logging, registering action factories, and
    validating system dependencies for the AI player functionality.
    """
    # Set up logging for the AI player module
    logger = logging.getLogger("ai_player")
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    # Register available action factories with the global registry
    movement_factory = MovementActionFactory()
    register_action_factory(movement_factory)

    logger.info("AI Player module initialized successfully")


# Initialize module on import
initialize_ai_player_module()
