"""
Map Content Model

This module defines the MapContent Pydantic model for internal representation
of map content information throughout the AI player system.
"""

from pydantic import BaseModel, Field


class MapContent(BaseModel):
    """Internal Pydantic model for map content information"""
    type: str = Field(description="Content type (monster, resource, etc.)")
    code: str = Field(description="Content identifier/code")

    @classmethod
    def from_api_content(cls, api_content: dict) -> 'MapContent':
        """Transform API content dict to internal MapContent model"""
        return cls(
            type=api_content["type"],
            code=api_content["code"]
        )
