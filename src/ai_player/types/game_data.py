"""
Game Data Types

This module defines the GameData type that represents the structured cached
game data used throughout the enhanced goal system. This ensures type safety
and provides proper IntelliSense support for game data access.
"""

from pydantic import BaseModel, Field

from src.game_data.models import GameItem, GameMap, GameMonster, GameNPC, GameResource


class GameData(BaseModel):
    """Typed container for cached game data from CacheManager.

    This class provides a type-safe interface to cached game data,
    ensuring that all goal analysis modules have proper type checking
    and IDE support when accessing game content.
    """

    monsters: list[GameMonster] = Field(default_factory=list, description="All cached monster data")
    items: list[GameItem] = Field(default_factory=list, description="All cached item data")
    resources: list[GameResource] = Field(default_factory=list, description="All cached resource data")
    maps: list[GameMap] = Field(default_factory=list, description="All cached map data")
    npcs: list[GameNPC] = Field(default_factory=list, description="All cached NPC data")

    def __len__(self) -> int:
        """Return total count of all cached data objects."""
        return len(self.monsters) + len(self.items) + len(self.resources) + len(self.maps) + len(self.npcs)

    def is_empty(self) -> bool:
        """Check if any game data is cached."""
        return len(self) == 0

    def validate_required_data(self) -> None:
        """Validate that essential game data is present.

        Raises:
            ValueError: If critical game data is missing
        """
        if not self.monsters:
            raise ValueError("Monster data is required but not cached")
        if not self.items:
            raise ValueError("Item data is required but not cached")
        if not self.resources:
            raise ValueError("Resource data is required but not cached")
        if not self.maps:
            raise ValueError("Map data is required but not cached")
