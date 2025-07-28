"""
Action Result Model

This module defines the ActionResult class for representing the outcome
of executing GOAP actions in the AI player system.
"""

from typing import Any

from pydantic import BaseModel

from .game_state_enum import GameState


class ActionResult(BaseModel):
    """Result of executing a GOAP action"""
    success: bool
    message: str
    state_changes: dict[GameState, Any]
    cooldown_seconds: int = 0