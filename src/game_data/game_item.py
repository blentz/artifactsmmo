"""
Game Item Model

This module defines the GameItem Pydantic model for internal representation
of game items throughout the AI player system.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field


class GameItem(BaseModel):
    """Internal Pydantic model for game items"""
    code: str = Field(description="Unique item identifier")
    name: str = Field(description="Item display name")
    level: int = Field(ge=1, description="Required level to use item")
    type: str = Field(description="Item type/category")
    subtype: str = Field(description="Item subtype/subcategory")
    description: str = Field(description="Item description")
    effects: list[dict[str, Any]] = Field(default_factory=list, description="Item effects and bonuses")
    craft: Optional[dict[str, Any]] = Field(default=None, description="Crafting requirements")
    tradeable: bool = Field(default=True, description="Whether item can be traded")

    @classmethod
    def from_api_item(cls, api_item: Any) -> 'GameItem':
        """Transform API ItemSchema to internal GameItem model"""
        return cls(
            code=api_item.code,
            name=api_item.name,
            level=api_item.level,
            type=api_item.type,
            subtype=api_item.subtype,
            description=api_item.description,
            effects=api_item.effects if hasattr(api_item, 'effects') else [],
            craft=api_item.craft.to_dict() if hasattr(api_item, 'craft') and api_item.craft else None,
            tradeable=api_item.tradeable if hasattr(api_item, 'tradeable') else True
        )