"""
Game Map Model

This module defines the GameMap Pydantic model for internal representation
of game maps throughout the AI player system.
"""

from typing import Any

from pydantic import BaseModel, Field

from .map_content import MapContent


class GameMap(BaseModel):
    """Internal Pydantic model for game maps"""
    name: str = Field(description="Map name/identifier")
    skin: str = Field(description="Map visual skin")
    x: int = Field(description="Map X coordinate")
    y: int = Field(description="Map Y coordinate")
    content: MapContent | None = Field(default=None, description="Map content information")

    @classmethod
    def from_api_map(cls, api_map: Any) -> 'GameMap':
        """Transform API MapSchema to internal GameMap model"""
        content = None
        if hasattr(api_map, 'content') and api_map.content:
            content_dict = api_map.content.to_dict() if hasattr(api_map.content, 'to_dict') else api_map.content
            content = MapContent.from_api_content(content_dict)

        return cls(
            name=api_map.name,
            skin=api_map.skin,
            x=api_map.x,
            y=api_map.y,
            content=content
        )
