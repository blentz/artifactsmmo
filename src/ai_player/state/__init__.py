"""
State Management Module

Provides type-safe state management for the AI player using enum-based
state keys and Pydantic models for validation and serialization.
"""

from . import action_result as _action_result
from . import character_game_state as _character_game_state
from . import game_state as _game_state
from . import state_manager as _state_manager

GameState = _game_state.GameState
CooldownInfo = _game_state.CooldownInfo
ActionResult = _action_result.ActionResult
CharacterGameState = _character_game_state.CharacterGameState
StateManager = _state_manager.StateManager

__all__ = [
    "GameState",
    "ActionResult",
    "CharacterGameState",
    "CooldownInfo",
    "StateManager",
]
