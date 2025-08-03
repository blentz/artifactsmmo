"""
Action Result Model

This module defines the ActionResult class for representing the outcome
of executing GOAP actions in the AI player system. Enhanced to support
sub-goal requests for dynamic dependency resolution.
"""

from typing import Any

from pydantic import BaseModel, Field

from .game_state import GameState


class ActionResult(BaseModel):
    """Result of executing a GOAP action with sub-goal request support.
    
    This enhanced ActionResult enables the goal chain architecture by allowing
    actions to return sub-goal requests instead of failing when dependencies
    are discovered at runtime.
    """
    success: bool
    message: str
    state_changes: dict[GameState, Any]
    cooldown_seconds: int = 0
    sub_goal_requests: list[Any] = Field(
        default_factory=list,
        description="Sub-goals requested by this action for dependency resolution"
    )


# Rebuild the model to resolve forward references when imports are complete
def rebuild_model():
    """Rebuild ActionResult to resolve SubGoalRequest forward reference."""
    try:
        ActionResult.model_rebuild()
    except (AttributeError, ValueError):
        pass  # Ignore errors if dependencies aren't ready yet
