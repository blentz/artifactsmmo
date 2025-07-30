"""
Internal Game Data Models Module

This module provides backwards-compatible imports for all game data models.
All models have been refactored into separate files following the one-class-per-file
convention while maintaining the same import interface.
"""

# Import all models from their separate files
from .cooldown_info import CooldownInfo
from .game_item import GameItem
from .game_monster import GameMonster
from .game_map import GameMap
from .game_resource import GameResource
from .game_npc import GameNPC
from .map_content import MapContent

# Re-export all models for backwards compatibility
__all__ = [
    "CooldownInfo",
    "GameItem",
    "GameMonster", 
    "GameMap",
    "GameResource",
    "GameNPC",
    "MapContent"
]