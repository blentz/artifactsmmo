"""
Game NPC Model

This module defines the GameNPC Pydantic model for internal representation
of game NPCs throughout the AI player system.
"""

from typing import Any
from pydantic import BaseModel, Field


class GameNPC(BaseModel):
    """Internal Pydantic model for game NPCs"""
    code: str = Field(description="Unique NPC identifier")
    name: str = Field(description="NPC display name")
    description: str = Field(description="NPC description")
    type: str = Field(description="NPC type (e.g., trader)")

    @classmethod
    def from_api_npc(cls, api_npc: Any) -> 'GameNPC':
        """Transform API NPCSchema to internal GameNPC model"""
        return cls(
            code=api_npc.code,
            name=api_npc.name,
            description=api_npc.description,
            type=api_npc.type_.value if hasattr(api_npc.type_, 'value') else str(api_npc.type_)
        )