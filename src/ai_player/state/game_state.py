"""
Game State Module

This module provides backwards compatibility by re-exporting all game state
classes from their new locations after the one-class-per-file refactoring.
"""

# Re-export all classes from their new locations
from .action_result import ActionResult
from .character_game_state import CharacterGameState
from .game_state_enum import GameState

# Import shared models to maintain existing functionality
from src.game_data.models import CooldownInfo

__all__ = [
    "GameState",
    "ActionResult", 
    "CharacterGameState",
    "CooldownInfo"
]