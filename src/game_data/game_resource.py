"""
Game Resource Model

This module defines the GameResource Pydantic model for internal representation
of game resources throughout the AI player system.
"""

from typing import Any

from pydantic import BaseModel, Field


class GameResource(BaseModel):
    """Internal Pydantic model for game resources"""
    code: str = Field(description="Unique resource identifier")
    name: str = Field(description="Resource display name")
    skill: str = Field(description="Required skill to gather")
    level: int = Field(ge=1, description="Required skill level")
    drops: list[dict[str, Any]] = Field(default_factory=list, description="Resource drops")

    @classmethod
    def from_api_resource(cls, api_resource: Any) -> 'GameResource':
        """Transform API ResourceSchema to internal GameResource model"""
        return cls(
            code=api_resource.code,
            name=api_resource.name,
            skill=api_resource.skill,
            level=api_resource.level,
            drops=[drop.to_dict() if hasattr(drop, 'to_dict') else drop for drop in (api_resource.drops or [])]
        )
