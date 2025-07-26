"""
State Management Module

Provides type-safe state management for the AI player using enum-based
state keys and Pydantic models for validation and serialization.
"""

from . import game_state as _game_state
from . import state_manager as _state_manager

GameState = _game_state.GameState
ActionResult = _game_state.ActionResult
CharacterGameState = _game_state.CharacterGameState
CooldownInfo = _game_state.CooldownInfo
StateManager = _state_manager.StateManager

__all__ = [
    "GameState",
    "ActionResult",
    "CharacterGameState",
    "CooldownInfo",
    "StateManager",
]
